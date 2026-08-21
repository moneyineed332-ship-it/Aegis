"""Tests for the market regime classifier."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.regime import classify, reset_hysteresis


@pytest.fixture(autouse=True)
def _reset():
    reset_hysteresis()
    yield
    reset_hysteresis()


def test_bull_trend():
    features = {
        "sma_20": 105, "sma_50": 100,
        "momentum_20": 0.05, "volatility_20": 0.01,
    }
    result = classify(features)
    assert result["regime"] == "bull_trend"


def test_bear_trend():
    features = {
        "sma_20": 95, "sma_50": 100,
        "momentum_20": -0.05, "volatility_20": 0.01,
    }
    result = classify(features)
    assert result["regime"] == "bear_trend"


def test_high_volatility():
    features = {
        "sma_20": 100, "sma_50": 100,
        "momentum_20": 0.01, "volatility_20": 0.04,
    }
    result = classify(features)
    assert result["regime"] == "high_volatility"


def test_low_volatility():
    features = {
        "sma_20": 100.2, "sma_50": 100,
        "momentum_20": 0.001, "volatility_20": 0.005,
        "rsi_14": 50, "adx": 15, "bollinger_width": 0.02,
    }
    result = classify(features)
    assert result["regime"] == "low_volatility"


def test_capitulation():
    features = {
        "sma_20": 90, "sma_50": 100,
        "momentum_20": -0.15, "volatility_20": 0.05,
        "rsi_14": 25, "adx": 35, "close": 100,
    }
    result = classify(features)
    assert result["regime"] == "capitulation"


def test_euphoria():
    features = {
        "sma_20": 120, "sma_50": 100,
        "momentum_20": 0.20, "volatility_20": 0.04,
        "rsi_14": 80, "adx": 35, "close": 100,
    }
    result = classify(features)
    assert result["regime"] == "euphoria"


def test_range():
    features = {
        "sma_20": 100.3, "sma_50": 100,
        "momentum_20": 0.003, "volatility_20": 0.015,
        "rsi_14": 50, "adx": 15, "bollinger_width": 0.03,
    }
    result = classify(features)
    assert result["regime"] == "range"


def test_probabilities_sum_to_one():
    features = {
        "sma_20": 105, "sma_50": 100,
        "momentum_20": 0.05, "volatility_20": 0.01,
    }
    result = classify(features)
    total = sum(result["probabilities"].values())
    assert abs(total - 1.0) < 0.01, f"Probabilities sum to {total}"


def test_confidence_range():
    features = {
        "sma_20": 105, "sma_50": 100,
        "momentum_20": 0.05, "volatility_20": 0.01,
    }
    result = classify(features)
    assert 0 <= result["confidence"] <= 1


if __name__ == "__main__":
    test_bull_trend()
    test_bear_trend()
    test_high_volatility()
    test_low_volatility()
    test_capitulation()
    test_euphoria()
    test_range()
    test_probabilities_sum_to_one()
    test_confidence_range()
    print("All regime tests passed.")
