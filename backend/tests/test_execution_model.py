"""Tests for the backtester execution model (no look-ahead).

The rule: a decision taken from data up to and including bar ``i`` is filled at
bar ``i + 1``'s open, and a position cannot be exited on the bar it was opened.
The old loops read ``candles[i]``, formed a signal from it, and filled at
``candles[i]["close"]`` — assuming they knew a bar's close and traded at that
same close.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.execution_model import (
    assert_no_lookahead,
    fill_price,
    intrabar_exit_price,
    is_last_index,
    next_bar_open,
)


def _bars(closes, spread=0.0):
    out = []
    for i, c in enumerate(closes):
        out.append({
            "open": c, "high": c + spread, "low": c - spread, "close": c,
            "volume": 1000, "close_time": f"2026-01-01T{i % 24:02d}:00:00Z",
        })
    return out


class TestFillPrice:
    def test_fills_at_the_next_bar_open(self):
        candles = _bars([100, 110, 120])
        assert fill_price(candles, 0, "buy", 0) == 110
        assert fill_price(candles, 1, "sell", 0) == 120

    def test_does_not_use_the_signal_bar_close(self):
        # Bar 0 closed at 100 and bar 1 opened at 110. A fill decided on bar 0
        # must be 110, never 100.
        candles = _bars([100, 110])
        assert fill_price(candles, 0, "buy", 0) == candles[1]["open"]
        assert fill_price(candles, 0, "buy", 0) != candles[0]["close"]

    def test_buy_pays_slippage(self):
        candles = _bars([100, 110])
        assert fill_price(candles, 0, "buy", 0.01) == pytest.approx(111.1)

    def test_sell_receives_slippage(self):
        candles = _bars([100, 110])
        assert fill_price(candles, 0, "sell", 0.01) == pytest.approx(108.9)

    def test_last_bar_cannot_fill(self):
        candles = _bars([100, 110, 120])
        for side in ("buy", "sell"):
            assert fill_price(candles, 2, side, 0) is None

    def test_next_bar_open_helper(self):
        candles = _bars([100, 110])
        assert next_bar_open(candles, 0) is candles[1]
        assert next_bar_open(candles, 1) is None

    def test_missing_open_returns_none(self):
        assert fill_price([{"close": 100}, {"close": 110}], 0, "buy", 0) is None


class TestIntrabarExit:
    def _bar(self, high, low):
        return {"high": high, "low": low, "open": (high + low) / 2, "close": (high + low) / 2}

    def test_long_stop_hit(self):
        assert intrabar_exit_price(self._bar(105, 95), "buy", 96, 110)[1] == "stop_loss"

    def test_long_target_hit(self):
        assert intrabar_exit_price(self._bar(115, 105), "buy", 96, 110)[1] == "take_profit"

    def test_no_hit(self):
        assert intrabar_exit_price(self._bar(105, 100), "buy", 96, 110) is None

    def test_pessimistic_when_both_levels_in_one_bar(self):
        # The intrabar path is unknown, so the stop is assumed to come first.
        assert intrabar_exit_price(self._bar(115, 95), "buy", 96, 110)[1] == "stop_loss"

    def test_short_stop_hit(self):
        assert intrabar_exit_price(self._bar(115, 105), "sell", 110, 96)[1] == "stop_loss"

    def test_short_target_hit(self):
        assert intrabar_exit_price(self._bar(105, 95), "sell", 110, 96)[1] == "take_profit"

    def test_missing_levels(self):
        assert intrabar_exit_price(self._bar(105, 95), "buy", 0, 0) is None


class TestIsLastIndex:
    def test_last_bar(self):
        assert is_last_index(9, 10) is True
        assert is_last_index(8, 10) is False


class TestAssertNoLookahead:
    def test_passes_when_fills_are_strictly_later(self):
        assert_no_lookahead([{"signal_index": 3, "fill_index": 4}], [])

    def test_fails_on_same_bar(self):
        with pytest.raises(AssertionError, match="look-ahead"):
            assert_no_lookahead([{"signal_index": 3, "fill_index": 3}], [])

    def test_fails_when_fill_precedes_signal(self):
        with pytest.raises(AssertionError):
            assert_no_lookahead([{"signal_index": 5, "fill_index": 4}], [])

    def test_ignores_trades_without_metadata(self):
        assert_no_lookahead([{"side": "buy", "price": 100}], [])


def _trending(n=220, base=100.0, step=0.002):
    return _bars([base * (1 + step) ** i for i in range(n)], spread=base * 0.004)


def _check(trades: list[dict]) -> None:
    for trade in trades:
        assert "signal_index" in trade, "trade is missing its signal bar"
        assert "fill_index" in trade, "trade is missing its fill bar"
        assert trade["fill_index"] > trade["signal_index"], (
            f"look-ahead: signal on bar {trade['signal_index']} "
            f"filled on bar {trade['fill_index']}"
        )


class TestBacktestersRespectTheInvariant:
    """The invariant is enforced inside each run; these tests also read the
    trade list back so it is verified from outside, not just asserted."""

    def test_smc_ict(self):
        from app.backtesting import run_smc_ict

        trades = []
        run_smc_ict(_trending(), {
            "initial_capital": 10000, "allocation": 0.5, "fee_bps": 10,
            "slippage_bps": 5, "interval": "1h", "min_score": 0,
            "atr_stop_multiplier": 2.0, "lookback": 40,
        }, trades_out=trades)
        _check(trades)

    def test_multi_scale_crossover(self):
        from app.backtesting import run_multi_scale_crossover

        trades = []
        run_multi_scale_crossover(_trending(200), {
            "initial_capital": 10000, "allocation": 0.5, "fee_bps": 10,
            "slippage_bps": 5, "interval": "1h", "min_score": 0,
            "atr_stop_multiplier": 2.5,
        }, trades_out=trades)
        _check(trades)

    def test_runs_without_error(self):
        from datetime import datetime, timedelta, timezone

        from app.ict_backtester import IctBacktester

        candles = _trending(300, step=0.001)
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i, c in enumerate(candles):
            c["time"] = base + timedelta(hours=i)

        bt = IctBacktester()
        report = bt.run_backtest(
            "EURUSD", candles,
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        assert report is not None

    def test_position_never_opens_on_its_signal_bar(self):
        """The signal is parked and only consumed on a strictly later bar."""
        import inspect

        from app.ict_backtester import IctBacktester

        source = inspect.getsource(IctBacktester.run_backtest)
        assert "pending" in source
        assert "i > pending_index" in source
        # The fill price is the NEXT bar's open, not the signal bar's close.
        assert 'new_entry = candle["open"]' in source
        # The signal is still derived from data up to and including bar i.
        assert "candles[:i + 1]" in source
        # No bar may open a position on its own signal.
        assert 'entry_price=signal["entry_price"]' not in source

