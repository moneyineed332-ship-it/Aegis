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

    def test_scalping(self):
        from app.scalping import run_scalping

        trades = []
        run_scalping(_trending(200, step=0.001), {
            "ema_fast": 3, "ema_slow": 8, "rsi_period": 3,
            "rsi_overbought": 75, "rsi_oversold": 25,
            "stoch_k": 5, "stoch_d": 3, "stoch_overbought": 80, "stoch_oversold": 20,
            "atr_stop_multiplier": 1.5, "take_profit_ratio": 1.5,
            "initial_capital": 10000, "allocation": 0.3,
            "fee_bps": 10, "slippage_bps": 5, "interval": "5m",
            "max_trades_per_day": 100,
        }, trades_out=trades)
        _check(trades)

    def test_mean_reversion(self):
        from app.mean_reversion import run_mean_reversion

        trades = []
        run_mean_reversion(_trending(200, step=0.001), {
            "period": 20, "entry_z_score": -1.0, "exit_z_score": 0.0,
            "initial_capital": 10000, "allocation": 0.3,
            "fee_bps": 10, "slippage_bps": 5, "interval": "1h",
            "use_shorts": True, "short_entry_z_score": 1.0,
        }, trades_out=trades)
        _check(trades)

    def test_intraday(self):
        from app.intraday import run_intraday

        trades = []
        run_intraday(_trending(200, step=0.001), {
            "ema_fast": 9, "ema_slow": 21, "rsi_period": 14,
            "rsi_oversold": 35, "rsi_overbought": 65,
            "atr_stop_multiplier": 2.0, "use_shorts": True,
            "initial_capital": 10000, "allocation": 0.3,
            "fee_bps": 10, "slippage_bps": 5, "interval": "15m",
        }, trades_out=trades)
        _check(trades)


def _check(trades: list[dict]) -> None:
    for trade in trades:
        assert "signal_index" in trade, "trade is missing its signal bar"
        assert "fill_index" in trade, "trade is missing its fill bar"
        assert trade["fill_index"] > trade["signal_index"], (
            f"look-ahead: signal on bar {trade['signal_index']} "
            f"filled on bar {trade['fill_index']}"
        )


class TestIctBacktesterDefersEntries:
    """The ICT backtester parks a signal and fills it on the next bar.

    It used to open the position at the signal price on the same bar the
    signal was generated from, which is the same look-ahead.
    """

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


class TestNoTradeOnTheEntryBar:
    """A position cannot be exited on the very bar it was filled on."""

    def test_entry_and_exit_never_share_a_fill_bar(self):
        from app.scalping import run_scalping

        trades = []
        run_scalping(_trending(200, step=0.001), {
            "ema_fast": 3, "ema_slow": 8, "rsi_period": 3,
            "rsi_overbought": 75, "rsi_oversold": 25,
            "stoch_k": 5, "stoch_d": 3, "stoch_overbought": 80, "stoch_oversold": 20,
            "atr_stop_multiplier": 1.5, "take_profit_ratio": 1.5,
            "initial_capital": 10000, "allocation": 0.3,
            "fee_bps": 10, "slippage_bps": 5, "interval": "5m",
            "max_trades_per_day": 100,
        }, trades_out=trades)
        for entry, exit_ in zip(trades[::2], trades[1::2]):
            assert exit_["fill_index"] > entry["fill_index"], (
                "a position was closed on the bar it was opened"
            )


class TestResultsMovedDown:
    """Removing the same-bar fill must not improve any headline number.

    A fix for look-ahead that raises returns is a broken fix. These tests pin
    the outcome on a deterministic whipsaw series where the strategies do fire.
    """

    def _choppy(self, n=300, base=100.0):
        import math

        price = base
        closes = []
        for i in range(n):
            price *= 1.03 if (i // 15) % 2 == 0 else 0.97
            closes.append(price + 3 * math.sin(i / 4.0))
        return _bars(closes, spread=1.5)

    def test_intraday_takes_losses_on_a_whipsaw_series(self):
        """The same-bar fill used to cherry-pick the good close of each reversal."""
        from app.intraday import run_intraday

        trades = []
        result = run_intraday(self._choppy(), {
            "ema_fast": 9, "ema_slow": 21, "rsi_period": 14,
            "rsi_oversold": 35, "rsi_overbought": 65,
            "atr_stop_multiplier": 2.0, "use_shorts": True,
            "initial_capital": 10000, "allocation": 0.3,
            "fee_bps": 10, "slippage_bps": 5, "interval": "15m",
        }, trades_out=trades)
        assert len(trades) > 10, "the fixture should exercise the strategy"
        assert result["total_return"] < 0, "a whipsaw series must not be profitable"
        assert result["max_drawdown"] < -0.1
        _check(trades)

    def test_no_absurd_metrics_on_a_whipsaw(self):
        from app.mean_reversion import run_mean_reversion

        result = run_mean_reversion(self._choppy(), {
            "period": 20, "entry_z_score": -1.0, "exit_z_score": 0.0,
            "initial_capital": 10000, "allocation": 0.3,
            "fee_bps": 10, "slippage_bps": 5, "interval": "1h",
            "use_shorts": True, "short_entry_z_score": 1.0,
        })
        # A perfect, risk-free-looking result on a whipsaw is the signature of
        # a look-ahead, so the metrics are bounded.
        assert result["sharpe_ratio"] < 20
        assert result["max_drawdown"] <= 0
