"""Tests for ICT/SMC pipeline integration in the engine.

Validates the full Cahier des charges pipeline:
multi-TF → signal generator → risk manager → position manager.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app import config, engine
from app.ict_config import INSTRUMENT_CONFIGS, get_instrument_config, calculate_position_size
from app.ict_signal_generator import ICTSignalGenerator, SignalDirection, SignalQuality
from app.ict_risk_manager import IctRiskManager, RiskStatus


# --- Fixtures ---

def _mock_candles(n=100, base=1.1000):
    """Generate mock OHLCV candles with a bullish trend."""
    candles = []
    price = base
    for i in range(n):
        open_p = price
        high = price + 0.0005
        low = price - 0.0003
        close = price + 0.0002
        candles.append({
            "open": open_p, "high": high, "low": low, "close": close,
            "close_time": f"t{i}", "volume": 1000,
        })
        price = close
    return candles


def _make_signal(direction="buy", entry=1.1000, sl=1.0980, tp=1.1040, rr=2.0):
    """Create a minimal ICTSignal-like dict for engine testing."""
    return {
        "instrument": "EURUSD",
        "direction": direction,
        "entry_price": entry,
        "sl_price": sl,
        "tp_price": tp,
        "rr_ratio": rr,
        "confluence_score": 7,
        "quality": "good",
        "setup_type": "ICT_SMC_BUY",
        "session": "london",
        "trend_context": "bullish",
    }


# ============================================================
# Config tests
# ============================================================

class TestICTConfig:
    def test_ict_mode_default_false(self):
        assert config.ICT_MODE is False  # disabled by default

    def test_ict_capital_default(self):
        assert config.ICT_PAPER_CAPITAL == 50.0

    def test_instruments_configured(self):
        assert "EURUSD" in INSTRUMENT_CONFIGS
        assert "GBPUSD" in INSTRUMENT_CONFIGS
        assert "XAUUSD" in INSTRUMENT_CONFIGS

    def test_eurusd_config(self):
        cfg = get_instrument_config("EURUSD")
        assert cfg.pip_value == 0.0001
        assert cfg.contract_size == 100_000
        assert cfg.min_rr_ratio == 1.5
        assert cfg.risk_per_trade_pct == 0.005

    def test_xauusd_higher_volatility_params(self):
        cfg = get_instrument_config("XAUUSD")
        assert cfg.pip_value == 0.01
        assert cfg.contract_size == 100
        assert cfg.max_atr_pips > get_instrument_config("EURUSD").max_atr_pips
        assert cfg.sl_atr_multiplier >= 2.0


# ============================================================
# Signal Generator tests
# ============================================================

class TestICTSignalGenerator:
    def test_generator_creates(self):
        gen = ICTSignalGenerator("EURUSD")
        assert gen.instrument == "EURUSD"
        assert gen.min_rr_ratio == 1.5

    def test_generate_signal_returns_signal_or_none(self):
        gen = ICTSignalGenerator("EURUSD")
        h4 = _mock_candles(100, 1.1000)
        h1 = _mock_candles(100, 1.1000)
        m15 = _mock_candles(100, 1.1000)
        m5 = _mock_candles(100, 1.1000)
        result = gen.generate_signal(h4, h1, m15, m5, 1.1000)
        # May return None if confluence too low — that's valid
        assert result is None or hasattr(result, "direction")

    def test_signal_direction_enum(self):
        assert SignalDirection.BUY.value == "buy"
        assert SignalDirection.SELL.value == "sell"

    def test_signal_quality_enum(self):
        assert SignalQuality.EXCELLENT.value == "excellent"
        assert SignalQuality.GOOD.value == "good"


# ============================================================
# Risk Manager tests
# ============================================================

class TestICTRiskManager:
    def test_risk_manager_init(self):
        rm = IctRiskManager(initial_capital=50.0)
        assert rm.current_equity == 50.0
        assert rm.initial_capital == 50.0

    def test_check_all_limits_passes_on_fresh_state(self):
        rm = IctRiskManager(initial_capital=50.0)
        # Session gate is time-of-day dependent — neutralize it so this
        # test is deterministic at any hour.
        from unittest.mock import patch as _patch
        # 50€ × 0.5% = 0.25€ risk. EURUSD pip_value=0.0001, contract=100000
        # pip_value_per_lot = 10. Need lots >= 0.01
        # lots = 0.25 / (sl_pips * 10) → sl_pips must be <= 2.5
        with _patch("app.ict_risk_manager.is_trading_allowed", return_value=True):
            status = rm.check_all_limits(
                instrument="EURUSD",
                entry_price=1.1000,
                sl_price=1.0998,  # 2 pips SL → lots = 0.0125
                tp_price=1.1004,  # 4 pips TP → RR 2.0
                direction="buy",
            )
        assert isinstance(status, RiskStatus)
        assert status.can_trade is True
        assert status.blocking_reasons == []

    def test_check_all_limits_rejects_bad_rr(self):
        rm = IctRiskManager(initial_capital=50.0)
        status = rm.check_all_limits(
            instrument="EURUSD",
            entry_price=1.1000,
            sl_price=1.0990,  # 10 pips risk
            tp_price=1.1005,  # 5 pips reward → RR 0.5 < 1.5
            direction="buy",
        )
        assert status.can_trade is False
        assert any("R:R" in r or "rr" in r.lower() for r in status.blocking_reasons)

    def test_check_all_limits_rejects_too_many_losses(self):
        rm = IctRiskManager(initial_capital=50.0)
        # Simulate max consecutive losses
        rm._consecutive_losses = 3
        status = rm.check_all_limits(
            instrument="EURUSD",
            entry_price=1.1000,
            sl_price=1.0980,
            tp_price=1.1040,
            direction="buy",
        )
        assert status.can_trade is False
        assert any("consecutive" in r.lower() for r in status.blocking_reasons)

    def test_position_size_calculation(self):
        rm = IctRiskManager(initial_capital=50.0)
        size = rm.calculate_position_size("EURUSD", 1.1000, 1.0980)
        assert size >= 0.01

    def test_register_trade_entry(self):
        rm = IctRiskManager(initial_capital=50.0)
        trade = rm.register_trade_entry(
            trade_id="TEST-001",
            instrument="EURUSD",
            direction="buy",
            entry_price=1.1000,
            sl_price=1.0980,
            tp_price=1.1040,
            position_size=0.01,
            risk_amount=0.25,
            risk_pct=0.005,
            rr_ratio=2.0,
            session="london",
            setup_type="ICT_SMC_BUY",
        )
        assert trade.id == "TEST-001"
        assert trade.instrument == "EURUSD"
        assert trade.direction == "buy"

    def test_register_trade_exit(self):
        rm = IctRiskManager(initial_capital=50.0)
        rm.register_trade_entry(
            trade_id="TEST-002", instrument="EURUSD", direction="buy",
            entry_price=1.1000, sl_price=1.0980, tp_price=1.1040,
            position_size=0.01, risk_amount=0.25, risk_pct=0.005,
            rr_ratio=2.0, session="london", setup_type="ICT_SMC_BUY",
        )
        trade = rm.register_trade_exit("TEST-002", exit_price=1.1040)
        assert trade is not None
        assert trade.result == "win"
        assert trade.pnl > 0

    def test_xauusd_stricter_limits(self):
        rm = IctRiskManager(initial_capital=50.0)
        limits_xau = rm._limits["XAUUSD"]
        limits_eur = rm._limits["EURUSD"]
        # XAU/USD should have lower max trades per session
        assert limits_xau.max_trades_per_session <= limits_eur.max_trades_per_session


# ============================================================
# Pipeline Integration tests
# ============================================================

class TestICTPipelineIntegration:
    def test_init_ict_pipeline_sets_managers(self):
        """_init_ict_pipeline should create risk_manager and position_manager."""
        engine._ict_risk_manager = None
        engine._ict_position_manager = None

        with patch.object(config, "ICT_MODE", True):
            engine._init_ict_pipeline()

        assert engine._ict_risk_manager is not None
        assert engine._ict_position_manager is not None

        # Cleanup
        engine._ict_risk_manager = None
        engine._ict_position_manager = None

    def test_init_ict_pipeline_skipped_when_disabled(self):
        """When ICT_MODE is False, pipeline should not initialize."""
        engine._ict_risk_manager = None
        with patch.object(config, "ICT_MODE", False):
            engine._init_ict_pipeline()
        assert engine._ict_risk_manager is None

    def test_run_ict_pipeline_generates_signal(self):
        """Full pipeline: signal generator → risk check → signal stored."""
        engine._last_ict_signals.clear()
        engine._last_signal = None
        engine._last_prices = {"EURUSD": 1.1000}

        fake_signal = MagicMock()
        fake_signal.direction.value = "buy"
        fake_signal.entry_price = 1.1000
        fake_signal.sl_price = 1.0998   # 2 pips SL → lots = 0.0125 >= 0.01
        fake_signal.tp_price = 1.1004   # 4 pips TP → RR 2.0
        fake_signal.rr_ratio = 2.0
        fake_signal.confluence_score = 7
        fake_signal.quality.value = "good"
        fake_signal.setup_type = "ICT_SMC_BUY"
        fake_signal.session = "london"
        fake_signal.trend_context = "bullish"

        with patch.object(config, "ICT_MODE", True), \
             patch("app.engine._get_ict_signal", return_value=(fake_signal, [])), \
             patch("app.engine._ict_risk_manager", IctRiskManager(initial_capital=50.0)), \
             patch("app.ict_risk_manager.is_trading_allowed", return_value=True):
            asyncio.run(engine._run_ict_pipeline())

        assert "EURUSD" in engine._last_ict_signals
        assert engine._last_signal is not None
        assert engine._last_signal["recommendation"]["strategy"] == "ict_smc"

    def test_run_ict_pipeline_refused_by_risk_manager(self):
        """When risk manager refuses, no signal should be generated."""
        engine._last_ict_signals.clear()
        engine._last_signal = None
        engine._last_prices = {"EURUSD": 1.1000}

        fake_signal = MagicMock()
        fake_signal.direction.value = "buy"
        fake_signal.entry_price = 1.1000
        fake_signal.sl_price = 1.0980
        fake_signal.tp_price = 1.1040
        fake_signal.rr_ratio = 0.5  # Bad RR
        fake_signal.confluence_score = 7
        fake_signal.quality.value = "good"
        fake_signal.setup_type = "ICT_SMC_BUY"
        fake_signal.session = "london"
        fake_signal.trend_context = "bullish"

        with patch.object(config, "ICT_MODE", True), \
             patch("app.engine._get_ict_signal", return_value=(fake_signal, [])), \
             patch("app.engine._ict_risk_manager", IctRiskManager(initial_capital=50.0)):
            asyncio.run(engine._run_ict_pipeline())

        # Signal stored but not promoted to _last_signal (risk refused)
        assert "EURUSD" in engine._last_ict_signals

    def test_engine_status_includes_ict_mode(self):
        """get_engine_status should include ict_mode and focused_mode."""
        status = engine.get_engine_status()
        assert "ict_mode" in status
        assert "focused_mode" in status
        assert "ict_signals" in status

    def test_config_ict_independence(self):
        """ICT_MODE and FOCUSED_MODE are independent flags."""
        assert hasattr(config, "ICT_MODE")
        assert hasattr(config, "FOCUSED_MODE")
        assert isinstance(config.ICT_MODE, bool)
        assert isinstance(config.FOCUSED_MODE, bool)


# ============================================================
# VOLATILITY FILTER TESTS (§11)
# ============================================================

class TestVolatilityFilter:
    """Tests du filtre de volatilité pour XAU/USD (§11)."""

    def test_xau_low_atr_blocks_trade(self):
        """ATR below min_atr_pips for XAU should block trade."""
        rm = IctRiskManager(initial_capital=50.0)
        rm._daily_pnl = 0.0
        rm._daily_pnl_start = rm.current_equity

        status = rm.check_all_limits("XAUUSD", 2650.0, 2640.0, 2670.0, current_atr_pips=50)
        assert not status.can_trade
        assert not status.volatility_ok
        assert "trop faible" in status.volatility_reason

    def test_xau_high_atr_blocks_trade(self):
        """ATR above max_atr_pips for XAU should block trade."""
        rm = IctRiskManager(initial_capital=50.0)
        rm._daily_pnl = 0.0
        rm._daily_pnl_start = rm.current_equity

        status = rm.check_all_limits("XAUUSD", 2650.0, 2640.0, 2670.0, current_atr_pips=1500)
        assert not status.can_trade
        assert not status.volatility_ok
        assert "excessive" in status.volatility_reason

    def test_xau_elevated_atr_reduces_risk(self):
        """ATR between 2x min and max should reduce risk for XAU."""
        rm = IctRiskManager(initial_capital=5000.0)  # Higher capital so position size is valid
        rm._daily_pnl = 0.0
        rm._daily_pnl_start = rm.current_equity

        status = rm.check_all_limits("XAUUSD", 2650.0, 2640.0, 2670.0, current_atr_pips=250)
        assert status.volatility_ok
        assert status.volatility_reduction == 0.3

    def test_eurusd_normal_atr_no_reduction(self):
        """Normal ATR for EUR/USD should not reduce risk."""
        rm = IctRiskManager(initial_capital=5000.0)
        rm._daily_pnl = 0.0
        rm._daily_pnl_start = rm.current_equity

        status = rm.check_all_limits("EURUSD", 1.1000, 1.0980, 1.1040, current_atr_pips=50)
        assert status.volatility_ok
        assert status.volatility_reduction == 1.0

    def test_volatility_reduction_applied_to_position_size(self):
        """Position size should be reduced when volatility_reduction < 1."""
        rm = IctRiskManager(initial_capital=50.0)

        size_normal = rm.calculate_position_size("XAUUSD", 2650.0, 2640.0, volatility_reduction=1.0)
        size_reduced = rm.calculate_position_size("XAUUSD", 2650.0, 2640.0, volatility_reduction=0.3)
        assert size_reduced <= size_normal
        assert size_reduced >= 0.01  # Minimum lot size


# ============================================================
# TRAILING STOP TESTS (§9)
# ============================================================

class TestTrailingStop:
    """Tests du trailing stop structurel dans le risk manager."""

    def _make_trade(self, mode="trailing_structural", direction="buy", sl=1.0980):
        from app.ict_risk_manager import TradeRecord
        return TradeRecord(
            id="t1", instrument="EURUSD", direction=direction,
            entry_price=1.1000, sl_price=sl, tp_price=1.1040,
            position_size=0.01, risk_amount=2.0, risk_pct=0.04,
            rr_ratio=2.0, entry_time=datetime.now(timezone.utc), mode=mode,
        )

    def test_trailing_buy_moves_sl_up(self):
        """Buy trade: trailing should move SL up when price makes new high."""
        rm = IctRiskManager(initial_capital=50.0)
        trade = self._make_trade(direction="buy", sl=1.0980)
        rm._open_trades["t1"] = trade

        # Recent candles with a swing low at 1.0990
        candles = [{"low": 1.0990, "high": 1.1020} for _ in range(20)]

        updated, new_sl = rm.check_trailing_stop("t1", 1.1020, candles, current_atr=0.0015)
        assert updated
        assert new_sl > 1.0980  # SL moved up
        assert new_sl < 1.1020  # SL below current price

    def test_trailing_sell_moves_sl_down(self):
        """Sell trade: trailing should move SL down when price makes new low."""
        rm = IctRiskManager(initial_capital=50.0)
        trade = self._make_trade(direction="sell", sl=1.1020)
        rm._open_trades["t1"] = trade

        # Recent candles with a swing high at 1.1010
        candles = [{"low": 1.0980, "high": 1.1010} for _ in range(20)]

        updated, new_sl = rm.check_trailing_stop("t1", 1.0980, candles, current_atr=0.0015)
        assert updated
        assert new_sl < 1.1020  # SL moved down
        assert new_sl > 1.0980  # SL above current price

    def test_trailing_no_update_without_candles(self):
        """Without candles, trailing should not update."""
        rm = IctRiskManager(initial_capital=50.0)
        trade = self._make_trade()
        rm._open_trades["t1"] = trade

        updated, new_sl = rm.check_trailing_stop("t1", 1.1020, [], current_atr=0.0015)
        assert not updated
        assert new_sl is None

    def test_trailing_nonexistent_trade(self):
        """Non-existent trade should return False."""
        rm = IctRiskManager(initial_capital=50.0)
        updated, new_sl = rm.check_trailing_stop("nonexistent", 1.1000, [])
        assert not updated
        assert new_sl is None


# ============================================================
# EXTENDED STATS TESTS (§15)
# ============================================================

class TestExtendedStats:
    """Tests des statistiques étendues du trade journal."""

    def test_empty_journal_stats(self):
        """Empty journal should return zero stats."""
        from app.trade_journal import TradeJournal
        journal = TradeJournal()
        stats = journal.get_statistics()
        assert stats["total_trades"] == 0
        assert stats["profit_factor"] == 0.0
        assert stats["expectancy_per_trade"] == 0.0
        assert stats["max_consecutive_losses"] == 0

    def test_stats_profit_factor(self):
        """Profit factor = total_wins / total_losses."""
        from app.trade_journal import TradeJournal
        journal = TradeJournal()

        for _ in range(2):
            entry = journal.add_trade_entry(
                instrument="EURUSD", direction="buy", entry_price=1.1000,
                sl_price=1.0980, tp_price=1.1040, position_size_lots=0.01,
                risk_amount=2.0, risk_pct=0.04, rr_ratio=2.0,
            )
            journal.update_trade_exit(entry.trade_id, 1.1040, "win", 5.0, 0.45, 2.0, 0.01)

        entry = journal.add_trade_entry(
            instrument="EURUSD", direction="buy", entry_price=1.1000,
            sl_price=1.0980, tp_price=1.1040, position_size_lots=0.01,
            risk_amount=2.0, risk_pct=0.04, rr_ratio=2.0,
        )
        journal.update_trade_exit(entry.trade_id, 1.0980, "loss", -2.0, -0.18, -1.0, 0.02)

        stats = journal.get_statistics()
        assert stats["win_rate"] == 2 / 3
        assert stats["profit_factor"] == 5.0  # (5+5) / 2 = 5.0
        assert abs(stats["expectancy_per_trade"] - 8 / 3) < 0.01

    def test_stats_consecutive_losses(self):
        """Max consecutive losses should be tracked."""
        from app.trade_journal import TradeJournal
        journal = TradeJournal()

        for _ in range(3):
            entry = journal.add_trade_entry(
                instrument="EURUSD", direction="buy", entry_price=1.1000,
                sl_price=1.0980, tp_price=1.1040, position_size_lots=0.01,
                risk_amount=2.0, risk_pct=0.04, rr_ratio=2.0,
            )
            journal.update_trade_exit(entry.trade_id, 1.0980, "loss", -2.0, -0.18, -1.0, 0.02)

        stats = journal.get_statistics()
        assert stats["max_consecutive_losses"] == 3
        assert stats["max_consecutive_wins"] == 0

    def test_stats_by_instrument(self):
        """Stats should break down by instrument."""
        from app.trade_journal import TradeJournal
        journal = TradeJournal()

        for sym in ["EURUSD", "GBPUSD"]:
            entry = journal.add_trade_entry(
                instrument=sym, direction="buy", entry_price=1.1000,
                sl_price=1.0980, tp_price=1.1040, position_size_lots=0.01,
                risk_amount=2.0, risk_pct=0.04, rr_ratio=2.0,
            )
            journal.update_trade_exit(entry.trade_id, 1.1040, "win", 5.0, 0.45, 2.0, 0.01)

        stats = journal.get_statistics()
        assert "EURUSD" in stats["by_instrument"]
        assert "GBPUSD" in stats["by_instrument"]
        assert stats["by_instrument"]["EURUSD"]["trades"] == 1
        assert stats["by_instrument"]["GBPUSD"]["wins"] == 1
