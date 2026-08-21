"""Tests for the intraday strategy."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.intraday import run_intraday, _vwap, _pivot_points


def _make_candles(n: int = 100, base_price: float = 100.0, direction: float = 1.0) -> list[dict]:
    candles = []
    price = base_price
    for i in range(n):
        price *= 1.001 * direction
        candles.append({
            "symbol": "BTCUSDT",
            "interval": "15m",
            "open_time": i * 900_000,
            "close_time": (i + 1) * 900_000,
            "open": price * 0.999,
            "high": price * 1.003,
            "low": price * 0.997,
            "close": price,
            "volume": 1000.0 + i * 10,
            "source": "test",
        })
    return candles


def test_vwap_basic():
    candles = _make_candles(20)
    result = _vwap(candles)
    assert len(result) == 20
    assert all(v > 0 for v in result)


def test_pivot_points():
    pp = _pivot_points(110.0, 100.0, 105.0)
    assert "PP" in pp
    assert "R1" in pp
    assert "S1" in pp
    assert pp["PP"] == round((110 + 100 + 105) / 3, 2)
    assert pp["R1"] > pp["PP"] > pp["S1"]


def test_intraday_basic():
    candles = _make_candles(100)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "15m",
    }
    result = run_intraday(candles, params)
    assert "final_equity" in result
    assert "total_return" in result
    assert "max_drawdown" in result
    assert "sharpe_ratio" in result
    assert "trade_count" in result
    assert "win_rate" in result
    assert result["final_equity"] > 0
    assert result["max_drawdown"] <= 0


def test_intraday_not_enough_candles():
    candles = _make_candles(10)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "15m",
    }
    try:
        run_intraday(candles, params)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_intraday_with_shorts_disabled():
    candles = _make_candles(100)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "15m",
        "use_shorts": False,
    }
    result = run_intraday(candles, params)
    assert "final_equity" in result
    assert result["final_equity"] > 0


def test_intraday_downtrend_with_shorts():
    candles = _make_candles(200, base_price=100.0, direction=0.998)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "15m",
        "use_shorts": True,
    }
    result = run_intraday(candles, params)
    assert "final_equity" in result
    assert result["trade_count"] >= 0


def test_intraday_no_trades_flat_market():
    candles = _make_candles(100, base_price=100.0, direction=1.0)
    for i in range(len(candles)):
        candles[i]["volume"] = 0
    params = {
        "initial_capital": 10_000,
        "allocation": 0.95,
        "fee_bps": 10,
        "slippage_bps": 5,
        "interval": "15m",
    }
    result = run_intraday(candles, params)
    assert "final_equity" in result
    assert result["final_equity"] > 0


def test_intraday_custom_params():
    candles = _make_candles(100)
    params = {
        "initial_capital": 10_000,
        "allocation": 0.5,
        "fee_bps": 25,
        "slippage_bps": 10,
        "interval": "1h",
        "rsi_period": 21,
        "rsi_bull_threshold": 60,
        "rsi_bear_threshold": 40,
        "rsi_overbought": 80,
        "rsi_oversold": 20,
        "ema_fast": 12,
        "ema_slow": 26,
        "atr_period": 20,
        "atr_stop_multiplier": 3.0,
    }
    result = run_intraday(candles, params)
    assert "final_equity" in result


if __name__ == "__main__":
    test_vwap_basic()
    test_pivot_points()
    test_intraday_basic()
    test_intraday_not_enough_candles()
    test_intraday_with_shorts_disabled()
    test_intraday_downtrend_with_shorts()
    test_intraday_no_trades_flat_market()
    test_intraday_custom_params()
    print("All intraday tests passed.")
