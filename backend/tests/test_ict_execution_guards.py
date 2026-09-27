"""Fail-closed guarantees for the ICT execution path.

Two real defects fixed here:

1. ``_execute_ict_trade`` used ``if _ict_risk_manager:`` before the risk gate.
   A missing risk manager therefore skipped validation and placed the order
   anyway, then skipped the journal entries too -- a trade invisible to the
   drawdown and daily-loss limits. It now refuses.

2. The ICT managers were created lazily inside ``task_generate_signals``,
   which is scheduled after ``task_execute_trades`` could run, and only after
   the first analysis cycle. ``start_engine`` now initializes them and refuses
   to start if that fails.
"""

import asyncio
import inspect

import pytest

from app import engine


class TestExecuteIctTradeFailsClosed:
    """No order may be submitted without a live risk manager."""

    def _rec(self, **over):
        rec = {
            "instrument": "EURUSD",
            "action": "buy",
            "entry_price": 1.0850,
            "sl_price": 1.0800,
            "tp_price": 1.0950,
            "position_size": 0.01,
        }
        rec.update(over)
        return rec

    def test_refuses_when_risk_manager_missing(self, monkeypatch):
        submitted = []
        monkeypatch.setattr(engine, "_ict_risk_manager", None, raising=False)
        monkeypatch.setattr(engine, "_ict_position_manager", object(), raising=False)
        monkeypatch.setattr(
            engine.oms.oms, "submit_market_order",
            lambda **kw: submitted.append(kw) or {"status": "filled", "fill_price": kw["current_price"]},
        )
        asyncio.run(engine._execute_ict_trade("EURUSD", self._rec(), 1.0850))
        assert submitted == [], "order was submitted with no risk manager"

    def test_refuses_when_position_manager_missing(self, monkeypatch):
        submitted = []
        monkeypatch.setattr(engine, "_ict_risk_manager", object(), raising=False)
        monkeypatch.setattr(engine, "_ict_position_manager", None, raising=False)
        monkeypatch.setattr(
            engine.oms.oms, "submit_market_order",
            lambda **kw: submitted.append(kw) or {"status": "filled", "fill_price": kw["current_price"]},
        )
        asyncio.run(engine._execute_ict_trade("EURUSD", self._rec(), 1.0850))
        assert submitted == [], "order was submitted with no position manager"

    def test_source_has_no_optional_risk_gate(self):
        """Pin the shape: the gate must not sit behind a truthiness test.

        Comments are stripped first, because the fix documents the old form by
        name and a naive substring search would match its own explanation.
        """
        lines = [
            ln for ln in inspect.getsource(engine._execute_ict_trade).splitlines()
            if not ln.lstrip().startswith("#")
        ]
        code = "\n".join(lines)
        assert "if _ict_risk_manager:" not in code
        assert "if _ict_position_manager:" not in code
        assert "_ict_risk_manager is None or _ict_position_manager is None" in code



class TestIctPipelineInitializedAtStartup:
    def test_start_engine_initializes_before_scheduler(self):
        src = inspect.getsource(engine.start_engine)
        init_at = src.index("_init_ict_pipeline()")
        sched_at = src.index("scheduler.start()")
        assert init_at < sched_at, "ICT must be initialized before the scheduler runs"

    def test_start_engine_raises_if_init_fails(self):
        src = inspect.getsource(engine.start_engine)
        assert "RuntimeError" in src

    def test_init_reports_success(self):
        assert inspect.signature(engine._init_ict_pipeline).return_annotation is bool

    def test_init_returns_true_when_ict_disabled(self, monkeypatch):
        """Disabled ICT is not a failure; it must not block the engine."""
        monkeypatch.setattr(engine.config, "ICT_MODE", False)
        assert engine._init_ict_pipeline() is True


class TestRiskFractionIsNotAPercentage:
    """risk_per_trade_pct is a FRACTION (0.005), and the dashboard said otherwise."""

    def test_next_trade_risk_is_not_divided_by_100(self):
        from app.routers import ict_dashboard

        src = inspect.getsource(ict_dashboard.get_risk_metrics)
        assert "risk_per_trade_pct / 100" not in src
        assert "risk_per_trade_pct * 100" in src

    def test_value_on_a_50_eur_account(self, monkeypatch):
        from app.ict_config import get_instrument_config
        from app.routers import ict_dashboard

        cfg = get_instrument_config("EURUSD")
        assert cfg.risk_per_trade_pct == 0.005
        assert 50.0 * cfg.risk_per_trade_pct == pytest.approx(0.25)
        assert 50.0 * (cfg.risk_per_trade_pct / 100) == pytest.approx(0.0025)


class TestForexAtFiftyEurosCanTrade:
    """50 EUR must be able to open a Forex position, and be told the truth.

    Both gates used to refuse every order: the risk manager because a 0.01 lot
    on a 100 000 contract risks 10-40 % of equity against a 5 % cap, and the
    OMS because the lot count was passed where it expected units, making the
    notional read 0.0109 instead of 1 085. Contracts are now derived from the
    capital and the OMS is fed units.
    """

    def test_all_instruments_pass_both_gates(self):
        from app import oms, storage
        from app.ict_config import calculate_position_size, get_instrument_config
        from app.ict_risk_manager import IctRiskManager

        storage.initialize()
        rm = IctRiskManager(initial_capital=50.0)
        cases = [
            ("EURUSD", 1.0850, 1.0800, 1.0950),
            ("GBPUSD", 1.2700, 1.2650, 1.2800),
            ("XAUUSD", 2650.0, 2630.0, 2690.0),
        ]
        for symbol, entry, sl, tp in cases:
            cfg = get_instrument_config(symbol)
            status = rm.check_all_limits(symbol, entry, sl, tp, direction="buy")
            risky = [r for r in status.blocking_reasons if "risque effectif" in r.lower()]
            assert risky == [], f"{symbol} still blocked by the effective risk cap: {risky}"

            lots = max(calculate_position_size(symbol, 50.0, entry, sl), 0.01)
            units = lots * cfg.contract_size
            notional = units * entry
            assert notional <= 75, f"{symbol} notional {notional:.2f} over the order cap"

    def test_risk_stays_near_the_configured_budget(self):
        from app.ict_config import calculate_position_size, get_instrument_config

        for symbol, entry, sl in [
            ("EURUSD", 1.0850, 1.0800),
            ("GBPUSD", 1.2700, 1.2650),
            ("XAUUSD", 2650.0, 2630.0),
        ]:
            cfg = get_instrument_config(symbol)
            lots = calculate_position_size(symbol, 50.0, entry, sl)
            pips = abs(entry - sl) / cfg.pip_value
            risk = lots * cfg.contract_size * cfg.pip_value * pips
            # Budget is 0.5% of 50 EUR = 0.25. Allow a wide band: the point is
            # that it is a fraction of the account, not a multiple of it.
            assert risk <= 2.5, f"{symbol} risks {risk:.2f} EUR on a 50 EUR account"
            assert risk >= 0.05

    def test_lots_are_converted_to_units_for_the_book(self):
        from app.ict_config import lots_to_units

        assert lots_to_units("EURUSD", 1.0) == pytest.approx(
            __import__("app.ict_config", fromlist=["get_contract_size"]).get_contract_size("EURUSD")
        )

    def test_commissions_scale_with_the_contract(self):
        """A 7 EUR/lot fee on a 12.50 EUR position would make every trade a loss."""
        from app import ict_config as ic

        for symbol in ("EURUSD", "GBPUSD", "XAUUSD"):
            cfg = ic.INSTRUMENT_CONFIGS[symbol]
            notional = ic.lots_to_units(symbol, 0.01) * ic._REFERENCE_PRICES[symbol]
            assert cfg.commission_per_lot < notional, (
                f"{symbol} commission {cfg.commission_per_lot} exceeds notional {notional}"
            )

    def test_micro_contracts_are_refused_outside_paper_mode(self, monkeypatch):
        """A live broker fills 0.01 lot at the real size; synthetic would over-size 100x."""
        from app import ict_config as ic

        monkeypatch.setattr(ic.aegis_config, "MODE", "live")
        monkeypatch.setattr(ic.aegis_config, "ICT_MICRO_CONTRACTS", True)
        ic._apply_micro_contracts()
        assert ic.MICRO_CONTRACT_ACTIVE is False

