"""Regression tests for ICT/SMC integration bugs (real data paths, no mocks).

Covers: BOS/CHoCH string matching, last_price premium/discount, OB/FVG
price keys, min/max over swing dicts, session priority, revenge-block
expiry, ICT state round-trips, Yahoo 4h resampling.
"""

import sys
import os
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ict_signal_generator import ICTSignalGenerator, SignalDirection, ConfluenceFactor
from app.session_filter import SessionFilter
from app import market_data


def _trend_candles(n=80, base=1.1000, step=0.0010):
    candles = []
    for i in range(n):
        o = base + i * step
        candles.append({
            "open": o, "high": o + 0.0008, "low": o - 0.0004,
            "close": o + 0.0005, "open_time": i,
        })
    return candles


def _chop_candles(n=60, base=1.1000):
    import math
    candles = []
    for i in range(n):
        o = base + 0.004 * math.sin(i / 3.0)
        candles.append({
            "open": o, "high": o + 0.0012, "low": o - 0.0012,
            "close": o + 0.0006 * math.sin(i / 2.0),
            "open_time": i,
        })
    return candles


class TestBosChochMatching:
    def test_bos_values_score_points(self):
        gen = ICTSignalGenerator("EURUSD")
        structure = {
            "last_bos": "bullish_bos",  # exact market_structure() format
            "last_choch": None,
            "swing_highs_lows": {"highs": [], "lows": []},
            "last_price": 1.0,
        }
        score, factors = gen._calculate_confluence(
            SignalDirection.BUY, "bullish", structure,
            {"recent_bull_sweep": False}, {"bullish_fvg": None}, {"bullish_ob": None},
        )
        assert ConfluenceFactor.BOS_CHOCH in factors
        assert score >= 2

    def test_choch_against_trend_scores(self):
        gen = ICTSignalGenerator("EURUSD")
        structure = {
            "last_bos": None,
            "last_choch": "bearish_choch",
            "swing_highs_lows": {"highs": [], "lows": []},
            "last_price": 1.0,
        }
        _, factors = gen._calculate_confluence(
            SignalDirection.BUY, "bullish", structure,
            {"recent_bull_sweep": False}, {"bullish_fvg": None}, {"bullish_ob": None},
        )
        assert ConfluenceFactor.BOS_CHOCH in factors

    def test_direction_prefers_bos_trend(self):
        gen = ICTSignalGenerator("EURUSD")
        structure = {"last_bos": "bullish_bos", "last_choch": None}
        direction = gen._determine_direction(
            "bullish", structure, {"recent_bull_sweep": False},
            {"bullish_fvg": None}, {"bullish_ob": None},
        )
        assert direction == SignalDirection.BUY


class TestLevelsAndSwings:
    def test_entry_uses_fvg_price_low(self):
        gen = ICTSignalGenerator("EURUSD")
        fvg = {"bullish_fvg": {"price_low": 1.0950, "price_high": 1.0960}}
        entry, sl, tp = gen._calculate_levels(
            SignalDirection.BUY, {"swing_highs_lows": {"highs": [], "lows": []}},
            {"buy_side_liquidity": []}, fvg, {}, 1.1000,
        )
        assert entry == 1.0950
        assert sl < entry < tp

    def test_entry_uses_ob_price_low(self):
        gen = ICTSignalGenerator("EURUSD")
        ob = {"bullish_ob": {"price_low": 1.0940, "price_high": 1.0955}}
        entry, sl, tp = gen._calculate_levels(
            SignalDirection.BUY, {"swing_highs_lows": {"highs": [], "lows": []}},
            {"buy_side_liquidity": []}, {}, ob, 1.1000,
        )
        assert entry == 1.0940

    def test_tp_uses_liquidity_price(self):
        gen = ICTSignalGenerator("EURUSD")
        liq = {"buy_side_liquidity": [{"price": 1.1100}]}
        entry, sl, tp = gen._calculate_levels(
            SignalDirection.BUY, {"swing_highs_lows": {"highs": [], "lows": []}},
            liq, {}, {}, 1.1000,
        )
        assert tp == 1.1100

    def test_swing_dicts_do_not_crash(self):
        """swing_highs_lows holds dicts {"price": ...} — min/max must not TypeError."""
        gen = ICTSignalGenerator("EURUSD")
        structure = {
            "swing_highs_lows": {
                "highs": [{"index": i, "price": 1.10 + i * 0.001, "time": i} for i in range(6)],
                "lows": [{"index": i, "price": 1.09 + i * 0.001, "time": i} for i in range(6)],
            },
            "last_price": 1.0950,
            "last_bos": None,
            "last_choch": None,
        }
        entry, sl, tp = gen._calculate_levels(
            SignalDirection.BUY, structure, {"buy_side_liquidity": []},
            {}, {}, 1.1000,
        )
        assert sl < entry  # SL under lowest swing minus buffer
        score, _ = gen._calculate_confluence(
            SignalDirection.BUY, "bullish", structure,
            {"recent_bull_sweep": False}, {}, {},
        )
        assert isinstance(score, int)

    def test_premium_discount_awards_point(self):
        gen = ICTSignalGenerator("EURUSD")
        structure = {
            "swing_highs_lows": {
                "highs": [{"index": i, "price": 1.20, "time": i} for i in range(6)],
                "lows": [{"index": i, "price": 1.00, "time": i} for i in range(6)],
            },
            "last_price": 1.05,  # discount zone (< mid 1.10)
            "last_bos": None,
            "last_choch": None,
        }
        _, factors = gen._calculate_confluence(
            SignalDirection.BUY, "bullish", structure,
            {"recent_bull_sweep": False}, {}, {},
        )
        assert ConfluenceFactor.PREMIUM_DISCOUNT in factors

    def test_full_signal_path_does_not_crash(self):
        gen = ICTSignalGenerator("EURUSD")
        candles = _trend_candles(120) + _chop_candles(60)
        signal = gen.generate_signal(
            candles_h4=candles, candles_h1=candles, candles_m15=candles,
            candles_m5=candles, current_price=candles[-1]["close"],
        )
        assert signal is None or hasattr(signal, "direction")


class TestSessionPriority:
    def test_overlap_wins_at_14utc(self):
        f = SessionFilter()
        assert f.get_current_session(datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)) == "overlap"

    def test_london_wins_over_asian_at_0830(self):
        f = SessionFilter()
        assert f.get_current_session(datetime(2026, 1, 15, 8, 30, tzinfo=timezone.utc)) == "london"

    def test_trading_allowed_london_morning(self):
        f = SessionFilter()
        assert f.is_session_active("EURUSD", now=datetime(2026, 1, 15, 8, 30, tzinfo=timezone.utc)) is True

    def test_asian_night_still_asian(self):
        f = SessionFilter()
        assert f.get_current_session(datetime(2026, 1, 15, 2, 0, tzinfo=timezone.utc)) == "asian"


class TestRevengeExpiry:
    def _check(self, rm):
        from unittest.mock import patch as _patch
        with _patch("app.ict_risk_manager.is_trading_allowed", return_value=True), \
             _patch("app.ict_risk_manager.is_news_blocking", return_value=False):
            return rm.check_all_limits(
                instrument="EURUSD", entry_price=1.10, sl_price=1.09,
                tp_price=1.12, direction="buy",
            )

    def test_expired_block_clears(self):
        from app.ict_risk_manager import IctRiskManager
        rm = IctRiskManager(initial_capital=50.0)
        rm._revenge_trading_blocked = True
        rm._revenge_blocked_at = datetime.now(timezone.utc) - timedelta(hours=5)
        status = self._check(rm)
        assert rm._revenge_trading_blocked is False
        assert not any("Revenge" in r for r in status.blocking_reasons)

    def test_fresh_block_holds(self):
        from app.ict_risk_manager import IctRiskManager
        rm = IctRiskManager(initial_capital=50.0)
        rm._revenge_trading_blocked = True
        rm._revenge_blocked_at = datetime.now(timezone.utc)
        status = self._check(rm)
        assert any("Revenge" in r for r in status.blocking_reasons)


class TestICTStateRoundTrip:
    def test_position_dict_round_trip(self):
        from app.position_manager import Position, TradeStatus
        pos = Position(
            id="p1", instrument="EURUSD", direction="buy", entry_price=1.10,
            initial_sl_price=1.09, initial_tp_price=1.12, position_size_lots=0.01,
            risk_amount=0.25, rr_ratio=2.0, mode="trailing_structural",
            current_sl_price=1.095, current_tp_price=1.12,
            status=TradeStatus.OPEN,
        )
        restored = Position.from_dict(pos.to_dict())
        assert restored.current_sl_price == 1.095  # not reset to initial
        assert restored.status == TradeStatus.OPEN
        assert restored.entry_time is not None

    def test_risk_save_load_round_trip(self):
        from app.ict_risk_manager import IctRiskManager
        from app import storage
        saved = {}
        real_set = storage.set_engine_state
        real_get = storage.get_engine_state
        storage.set_engine_state = lambda k, v: saved.__setitem__(k, v)
        storage.get_engine_state = lambda k: saved.get(k)
        try:
            rm = IctRiskManager(initial_capital=50.0)
            rm.current_equity = 48.5
            rm._consecutive_losses = 2
            rm._revenge_trading_blocked = True
            rm._revenge_blocked_at = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
            rm.save_state()
            rm2 = IctRiskManager(initial_capital=50.0)
            rm2.load_state()
            assert rm2.current_equity == 48.5
            assert rm2._consecutive_losses == 2
            assert rm2._revenge_trading_blocked is True
        finally:
            storage.set_engine_state = real_set
            storage.get_engine_state = real_get


class TestYahooResample:
    def test_4h_groups_60m(self):
        payload = {
            "timestamp": [1000 + 3600 * i for i in range(8)],
            "indicators": {"quote": [{
                "open": [1.0 + 0.001 * i for i in range(8)],
                "high": [1.001 + 0.001 * i for i in range(8)],
                "low": [0.999 + 0.001 * i for i in range(8)],
                "close": [1.0005 + 0.001 * i for i in range(8)],
                "volume": [10] * 8,
            }]},
        }
        real = market_data._fetch_yahoo_chart
        market_data._fetch_yahoo_chart = lambda *a, **k: payload
        try:
            candles = market_data._fetch_ohlcv_yahoo("EURUSD", "4h", 10)
        finally:
            market_data._fetch_yahoo_chart = real
        assert len(candles) == 2
        assert candles[0]["open"] == 1.0
        assert candles[0]["close"] == pytest.approx(1.0035)
        assert candles[0]["source"] == "yahoo_finance"

    def test_unknown_symbol_empty(self):
        assert market_data._fetch_ohlcv_yahoo("FAKE", "1h", 10) == []
        assert market_data._fetch_forex_spot_yahoo("FAKE", "now") is None


class TestPositionSizingUnits:
    """The sizing helper takes a FRACTION, not a percentage.

    A fraction was previously passed to a function expecting a percentage,
    which sized every position 100x too small.
    """

    def test_fraction_matches_risk_budget(self):
        from app.forex_indicators import calculate_forex_position_size

        # 5000 EUR, 0.5% = 25 EUR budget, 20 pip SL on a 100k contract.
        result = calculate_forex_position_size("EURUSD", 5000.0, 0.005, 1.1000, 1.0980)
        assert result["sl_pips"] == pytest.approx(20.0)
        assert result["risk_amount"] == pytest.approx(24.0, abs=1.0)
        assert result["lots"] > 0.1

    def test_large_account_not_undersized(self):
        from app.forex_indicators import calculate_forex_position_size

        result = calculate_forex_position_size("EURUSD", 500_000.0, 0.005, 1.1000, 1.0980)
        assert result["lots"] == pytest.approx(12.5, abs=0.1)
        assert result["risk_amount"] == pytest.approx(2500.0, rel=0.02)

    def test_config_helper_uses_fraction(self):
        from app.ict_config import calculate_position_size, get_instrument_config

        cfg = get_instrument_config("EURUSD")
        assert cfg.risk_per_trade_pct == 0.005
        lots = calculate_position_size("EURUSD", 5000.0, 1.1000, 1.0980)
        assert lots > 0.1, "position sizing collapsed to the broker minimum"

    def test_double_capital_double_size(self):
        from app.ict_config import calculate_position_size

        # Large enough that 0.01-lot rounding does not distort the ratio.
        small = calculate_position_size("EURUSD", 100_000.0, 1.1000, 1.0980)
        large = calculate_position_size("EURUSD", 200_000.0, 1.1000, 1.0980)
        assert small == pytest.approx(2.5, abs=0.02)
        assert large == pytest.approx(small * 2, rel=0.01)


class TestSmallAccountRiskGate:
    """A 50 EUR account cannot respect 0.5% with a 0.01 lot minimum.

    The gate must check the risk actually taken and stay honest about it
    instead of either blocking every setup or silently oversizing.
    """

    def _manager(self, capital):
        from app.ict_risk_manager import IctRiskManager
        return IctRiskManager(initial_capital=capital)

    def test_eurusd_trades_at_min_lot_with_reported_risk(self):
        rm = self._manager(50.0)
        status = rm.check_all_limits("EURUSD", 1.1000, 1.0980, 1.1040, "fixed_tp", None, "buy")
        assert not any("trop petite" in r for r in status.blocking_reasons)
        size = rm.calculate_position_size("EURUSD", 1.1000, 1.0980)
        assert size == pytest.approx(0.01)

    def test_xauusd_blocked_because_min_lot_risks_too_much(self):
        rm = self._manager(50.0)
        status = rm.check_all_limits("XAUUSD", 2650.0, 2640.0, 2670.0, "fixed_tp", None, "buy")
        assert any("risque effectif" in r.lower() for r in status.blocking_reasons)

    def test_large_account_accepts_theoretical_size(self):
        rm = self._manager(50_000.0)
        status = rm.check_all_limits("EURUSD", 1.1000, 1.0980, 1.1040, "fixed_tp", None, "buy")
        assert not any("risque effectif" in r.lower() for r in status.blocking_reasons)


class TestSharedTradeId:
    """Risk manager and position manager must share one trade identifier."""

    def test_position_manager_reuses_oms_order_id(self):
        from app.position_manager import PositionManager
        from app.ict_config import get_instrument_config

        cfg = get_instrument_config("EURUSD")
        pm = PositionManager(risk_manager=None)
        update = pm.open_position(
            instrument="EURUSD",
            direction="buy",
            entry_price=1.1000,
            sl_price=1.0980,
            tp_price=1.1060,
            account_balance=5000.0,
            trade_id="AEGIS-1700000000-1",
        )
        assert update.action == "open"
        assert update.position_id == "AEGIS-1700000000-1"
        assert cfg.min_rr_ratio > 0

    def test_exit_settles_the_registered_trade(self):
        from app.ict_risk_manager import IctRiskManager

        rm = IctRiskManager(initial_capital=5000.0)
        rm.register_trade_entry(
            trade_id="AEGIS-1700000000-1",
            instrument="EURUSD",
            direction="buy",
            entry_price=1.1000,
            sl_price=1.0980,
            tp_price=1.1060,
            position_size=0.12,
            risk_amount=24.0,
            risk_pct=0.005,
            rr_ratio=3.0,
            session="London",
            setup_type="ICT_SMC",
        )
        settled = rm.register_trade_exit("AEGIS-1700000000-1", 1.1060)
        assert settled is not None
        assert settled.pnl > 0
        assert rm._open_trades == {}

    def test_unknown_id_returns_none(self):
        from app.ict_risk_manager import IctRiskManager

        rm = IctRiskManager(initial_capital=5000.0)
        assert rm.register_trade_exit("does-not-exist", 1.1000) is None

