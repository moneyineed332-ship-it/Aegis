"""Tests for the shared indicators module."""

import math
from statistics import fmean

import pytest

from .indicators import (
    ema_series,
    ema_single,
    rsi_series,
    rsi_single,
    atr_series,
    atr_single,
    adx_dict,
    adx_series,
    bollinger_dict,
    bollinger_series,
    macd_dict,
    macd_series,
    stochastic,
    periods_per_year,
    sortino_ratio,
)


class TestEMA:
    def test_ema_series_basic(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = ema_series(data, 3)
        assert len(result) == 5
        assert result[0] == 1.0

    def test_ema_series_empty(self):
        assert ema_series([], 3) == []

    def test_ema_single_basic(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = ema_single(data, 3)
        assert isinstance(result, float)
        assert result > 0

    def test_ema_single_short_data(self):
        data = [1.0, 2.0]
        result = ema_single(data, 5)
        assert result == fmean(data)


class TestRSI:
    def test_rsi_series_basic(self):
        closes = [44.0, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42,
                  45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00,
                  46.03, 46.41, 46.22, 45.64]
        result = rsi_series(closes, 14)
        assert len(result) == 20
        assert all(0 <= v <= 100 for v in result)

    def test_rsi_single_basic(self):
        closes = [44.0, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42,
                  45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00,
                  46.03, 46.41, 46.22, 45.64]
        result = rsi_single(closes, 14)
        assert 0 <= result <= 100

    def test_rsi_single_short_data(self):
        assert rsi_single([1.0, 2.0], 14) == 50.0


class TestATR:
    def test_atr_series_basic(self):
        candles = [
            {"high": 10, "low": 8, "close": 9},
            {"high": 11, "low": 9, "close": 10},
            {"high": 12, "low": 10, "close": 11},
            {"high": 13, "low": 11, "close": 12},
            {"high": 14, "low": 12, "close": 13},
        ]
        result = atr_series(candles, 3)
        assert len(result) == 5
        assert all(v >= 0 for v in result)

    def test_atr_single_basic(self):
        candles = [
            {"high": 10, "low": 8, "close": 9},
            {"high": 11, "low": 9, "close": 10},
            {"high": 12, "low": 10, "close": 11},
            {"high": 13, "low": 11, "close": 12},
            {"high": 14, "low": 12, "close": 13},
        ]
        result = atr_single(candles, 3)
        assert result >= 0

    def test_atr_single_short_data(self):
        assert atr_single([{"high": 10, "low": 8, "close": 9}], 14) == 0.0


class TestADX:
    def test_adx_dict_basic(self):
        candles = [{"high": 10, "low": 8, "close": 9, "high-1": 9, "low-1": 7, "close-1": 8}] * 30
        result = adx_dict(candles, 14)
        assert "adx" in result
        assert "plus_di" in result
        assert "minus_di" in result

    def test_adx_series_basic(self):
        candles = [{"high": 10, "low": 8, "close": 9, "high-1": 9, "low-1": 7, "close-1": 8}] * 30
        result = adx_series(candles, 14)
        assert len(result) == 30


class TestBollinger:
    def test_bollinger_dict_basic(self):
        closes = [10.0, 11.0, 12.0, 11.5, 10.5, 11.0, 12.0, 13.0, 12.5, 11.5,
                  10.5, 11.0, 12.0, 13.0, 14.0, 13.5, 12.5, 11.5, 12.0, 13.0]
        result = bollinger_dict(closes, 20, 2.0)
        assert "bollinger_upper" in result
        assert "bollinger_middle" in result
        assert "bollinger_lower" in result
        assert "bollinger_width" in result

    def test_bollinger_series_basic(self):
        closes = [10.0, 11.0, 12.0, 11.5, 10.5, 11.0, 12.0, 13.0, 12.5, 11.5,
                  10.5, 11.0, 12.0, 13.0, 14.0, 13.5, 12.5, 11.5, 12.0, 13.0]
        result = bollinger_series(closes, 20)
        assert len(result) == 1
        assert len(result[0]) == 3


class TestMACD:
    def test_macd_dict_basic(self):
        closes = list(range(1, 40))
        result = macd_dict(closes)
        assert "macd" in result
        assert "macd_signal" in result
        assert "macd_histogram" in result

    def test_macd_series_basic(self):
        closes = list(range(1, 40))
        macd_line, signal_line, histogram = macd_series(closes)
        assert len(macd_line) == 39
        assert len(signal_line) == 39
        assert len(histogram) == 39


class TestStochastic:
    def test_stochastic_basic(self):
        candles = [{"high": 10 + i, "low": 8 + i, "close": 9 + i} for i in range(10)]
        k_vals, d_vals = stochastic(candles, 5, 3)
        assert len(k_vals) == 10
        # D must be aligned with K: same length, same index (D[i] = SMA of K ending at i)
        assert len(d_vals) == len(k_vals) == 10
        assert d_vals[9] == pytest.approx(sum(k_vals[7:10]) / 3)


class TestPeriodsPerYear:
    def test_all_intervals(self):
        assert periods_per_year("1m") == 525_600
        assert periods_per_year("5m") == 105_120
        assert periods_per_year("15m") == 35_040
        assert periods_per_year("30m") == 17_520
        assert periods_per_year("1h") == 8_760
        assert periods_per_year("4h") == 2_190
        assert periods_per_year("1d") == 365

    def test_unknown_interval(self):
        assert periods_per_year("unknown") == 8_760


class TestSortinoRatio:
    def test_positive_returns(self):
        returns = [0.01, -0.02, 0.015, -0.01, 0.02]
        result = sortino_ratio(returns, 8760)
        assert result != 0.0

    def test_insufficient_data(self):
        assert sortino_ratio([0.01], 8760) == 0.0

    def test_no_downside(self):
        assert sortino_ratio([0.01, 0.02, 0.03], 8760) == 0.0
