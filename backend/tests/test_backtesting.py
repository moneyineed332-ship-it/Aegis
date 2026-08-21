"""Tests for the backtesting engine."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.backtesting import run_sma_crossover, run_donchian_breakout, run_smc_ict, run_multi_timeframe, run_multi_scale_crossover


def _make_candles(n: int = 100, base_price: float = 100.0) -> list[dict]:
    """Generate synthetic OHLCV candles with a gentle uptrend."""
    candles = []
    price = base_price
    for i in range(n):
        price *= 1.001  # +0.1% per candle
        candles.append({
            "symbol": "BTCUSDT",
            "interval": "1h",
            "open_time": i * 3_600_000,
            "close_time": (i + 1) * 3_600_000,
            "open": price * 0.999,
            "high": price * 1.002,
            "low": price * 0.998,
            "close": price,
            "volume": 1000.0,
            "source": "test",
        })
    return candles


def test_sma_crossover_basic():
    candles = _make_candles(200)
    params = {
        "fast_period": 10,
        "slow_period": 30,
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
    }
    result = run_sma_crossover(candles, params)
    assert "final_equity" in result
    assert "total_return" in result
    assert "max_drawdown" in result
    assert "sharpe_ratio" in result
    assert "trade_count" in result
    assert "win_rate" in result
    assert result["final_equity"] > 0
    assert result["max_drawdown"] <= 0


def test_sma_crossover_not_enough_candles():
    candles = _make_candles(10)
    params = {
        "fast_period": 10,
        "slow_period": 30,
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
    }
    try:
        run_sma_crossover(candles, params)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_donchian_breakout_basic():
    candles = _make_candles(200)
    params = {
        "breakout_period": 20,
        "exit_period": 10,
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
        "min_volatility": 0.01,
    }
    result = run_donchian_breakout(candles, params)
    assert "final_equity" in result
    assert "total_return" in result
    assert result["final_equity"] > 0


def test_donchian_not_enough_candles():
    candles = _make_candles(5)
    params = {
        "breakout_period": 20,
        "exit_period": 10,
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
        "min_volatility": 0.01,
    }
    try:
        run_donchian_breakout(candles, params)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_smc_ict_basic():
    candles = _make_candles(200)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
        "min_score": 40,
        "atr_stop_multiplier": 2.0,
        "lookback": 50,
    }
    result = run_smc_ict(candles, params)
    assert "final_equity" in result
    assert "total_return" in result
    assert "max_drawdown" in result
    assert "sharpe_ratio" in result
    assert "trade_count" in result
    assert "win_rate" in result
    assert result["final_equity"] > 0
    assert result["max_drawdown"] <= 0


def test_smc_ict_not_enough_candles():
    candles = _make_candles(20)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
        "min_score": 40,
        "atr_stop_multiplier": 2.0,
        "lookback": 50,
    }
    try:
        run_smc_ict(candles, params)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_multi_timeframe_basic():
    candles = _make_candles(200)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
        "min_confluence": 40,
        "atr_stop_multiplier": 2.5,
    }
    result = run_multi_timeframe(candles, params)
    assert "final_equity" in result
    assert "total_return" in result
    assert result["final_equity"] > 0


def test_multi_timeframe_not_enough_candles():
    candles = _make_candles(50)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
        "min_confluence": 40,
        "atr_stop_multiplier": 2.5,
    }
    try:
        run_multi_timeframe(candles, params)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_multi_scale_crossover_basic():
    candles = _make_candles(200)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
        "min_score": 40,
        "atr_stop_multiplier": 2.5,
    }
    result = run_multi_scale_crossover(candles, params)
    assert "final_equity" in result
    assert "total_return" in result
    assert result["final_equity"] > 0


def test_multi_scale_crossover_not_enough_candles():
    candles = _make_candles(30)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
        "min_score": 40,
        "atr_stop_multiplier": 2.5,
    }
    try:
        run_multi_scale_crossover(candles, params)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    test_sma_crossover_basic()
    test_sma_crossover_not_enough_candles()
    test_donchian_breakout_basic()
    test_donchian_not_enough_candles()
    test_smc_ict_basic()
    test_smc_ict_not_enough_candles()
    test_multi_timeframe_basic()
    test_multi_timeframe_not_enough_candles()
    test_multi_scale_crossover_basic()
    test_multi_scale_crossover_not_enough_candles()
    print("All backtesting tests passed.")
