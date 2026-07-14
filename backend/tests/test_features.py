"""Tests for the feature engineering module."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.features import latest_features, _rsi, _macd, _atr, _bollinger, _ema


def _make_candles(n: int = 100, base_price: float = 100.0) -> list[dict]:
    candles = []
    price = base_price
    for i in range(n):
        price *= 1.001
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


def test_latest_features_keys():
    candles = _make_candles(100)
    result = latest_features(candles)
    expected_keys = {
        "close", "sma_20", "sma_50", "momentum_20", "volatility_20", "range_20",
        "rsi_14", "macd", "macd_signal", "macd_histogram",
        "atr_14", "bollinger_upper", "bollinger_middle", "bollinger_lower",
    }
    assert expected_keys == set(result.keys()), f"Missing keys: {expected_keys - set(result.keys())}"


def test_latest_features_not_enough_candles():
    try:
        latest_features(_make_candles(10))
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_rsi_range():
    candles = _make_candles(100)
    closes = [c["close"] for c in candles]
    rsi = _rsi(closes, 14)
    assert 0 <= rsi <= 100, f"RSI {rsi} out of range"


def test_bollinger_ordering():
    candles = _make_candles(100)
    closes = [c["close"] for c in candles]
    bb = _bollinger(closes, 20, 2.0)
    assert bb["bollinger_lower"] <= bb["bollinger_middle"] <= bb["bollinger_upper"]


def test_atr_positive():
    candles = _make_candles(100)
    atr = _atr(candles, 14)
    assert atr >= 0


def test_ema_basic():
    values = [100.0 + i * 0.1 for i in range(50)]
    ema = _ema(values, 20)
    assert ema > 0


if __name__ == "__main__":
    test_latest_features_keys()
    test_latest_features_not_enough_candles()
    test_rsi_range()
    test_bollinger_ordering()
    test_atr_positive()
    test_ema_basic()
    print("All features tests passed.")
