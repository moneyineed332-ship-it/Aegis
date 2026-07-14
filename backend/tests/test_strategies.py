"""Tests for the mean reversion and grid strategies."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.mean_reversion import run_mean_reversion
from app.grid import run_grid


def _make_candles(n: int = 100, base_price: float = 100.0) -> list[dict]:
    candles = []
    price = base_price
    import random
    random.seed(42)
    for i in range(n):
        price *= 1 + random.uniform(-0.01, 0.01)
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


def test_mean_reversion_basic():
    candles = _make_candles(200)
    params = {
        "period": 20,
        "entry_z_score": -2.0,
        "exit_z_score": 0.0,
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
    }
    result = run_mean_reversion(candles, params)
    assert "final_equity" in result
    assert "trade_count" in result
    assert result["final_equity"] > 0


def test_mean_reversion_not_enough_candles():
    candles = _make_candles(5)
    params = {
        "period": 20,
        "entry_z_score": -2.0,
        "exit_z_score": 0.0,
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
    }
    try:
        run_mean_reversion(candles, params)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_grid_basic():
    candles = _make_candles(200)
    params = {
        "grid_count": 10,
        "grid_spread_pct": 0.02,
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
    }
    result = run_grid(candles, params)
    assert "final_equity" in result
    assert "trade_count" in result
    assert result["final_equity"] > 0


def test_grid_not_enough_candles():
    candles = _make_candles(1)
    params = {
        "grid_count": 10,
        "grid_spread_pct": 0.02,
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
    }
    try:
        run_grid(candles, params)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_metrics_format():
    candles = _make_candles(200)
    params = {
        "period": 20,
        "entry_z_score": -2.0,
        "exit_z_score": 0.0,
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "1h",
    }
    result = run_mean_reversion(candles, params)
    assert isinstance(result["total_return"], float)
    assert isinstance(result["max_drawdown"], float)
    assert isinstance(result["sharpe_ratio"], float)
    assert isinstance(result["win_rate"], float)


if __name__ == "__main__":
    test_mean_reversion_basic()
    test_mean_reversion_not_enough_candles()
    test_grid_basic()
    test_grid_not_enough_candles()
    test_metrics_format()
    print("All strategy tests passed.")
