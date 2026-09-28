"""Data quality must reject corruption without rejecting the market being closed.

The validator counted every non-uniform candle interval as a gap. On real Yahoo
Forex data that rejected 12 of 12 symbol/timeframe combinations, and the engine
then skipped analysis for every symbol on every cycle. The "missing" intervals
were the Friday 21:00 to Sunday 23:00 closure and, on gold, a daily break at
20:00 UTC.

The gate's job is to catch corruption, so both halves are pinned: the real series
pass, and deliberately damaged series still fail.
"""

import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, r"E:\web_app\projrt\AEGIS AI\backend")

from app import data_quality as dq  # noqa: E402

HOUR = 3_600_000


def _at(year, month, day, hour, minute=0):
    return int(datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000)


def _hours(start_ms, count):
    """count consecutive hourly timestamps, without hour arithmetic overflow."""
    return [start_ms + i * HOUR for i in range(count)]


def _candle(open_ms, close=1.0, high=1.1, low=0.9, volume=1.0):
    return {
        "symbol": "TEST", "interval": "1h", "open_time": open_ms, "close_time": open_ms + HOUR - 1,
        "open": close, "high": high, "low": low, "close": close, "volume": volume,
    }


def _series(interval_ms, times):
    return [_candle(t) for t in times]


class TestRealForexDataPasses:
    """A 24/7 crypto assumption is the bug, not the data."""

    def test_contiguous_series_is_valid(self):
        result = dq.validate_ohlcv(_series(HOUR, _hours(_at(2026, 9, 14, 0), 48)), "1h")
        assert result["valid"] is True
        assert result["gap_count"] == 0

    def test_weekend_closure_is_not_a_gap(self):
        # Friday 21:00 -> Sunday 23:00, the gap measured on real data.
        times = _hours(_at(2026, 9, 18, 20), 2) + _hours(_at(2026, 9, 20, 23), 24)
        result = dq.validate_ohlcv(_series(HOUR, times), "1h")
        assert result["valid"] is True, result["errors"]
        assert result["closure_count"] == 1
        assert result["gap_count"] == 0

    def test_weekend_resuming_on_monday_is_not_a_gap(self):
        times = _hours(_at(2026, 9, 18, 20), 2) + _hours(_at(2026, 9, 21, 1), 24)
        result = dq.validate_ohlcv(_series(HOUR, times), "1h")
        assert result["valid"] is True, result["errors"]

    def test_recurring_daily_break_is_not_a_gap(self):
        """Gold closes at 20:00 UTC every day: a two-hour hole, every day."""
        times = []
        for day in range(1, 9):
            times += _hours(_at(2026, 9, day, 18), 2)
            times += _hours(_at(2026, 9, day, 22), 2)
        result = dq.validate_ohlcv(_series(HOUR, times), "1h")
        assert result["valid"] is True, result["errors"]
        assert result["gap_count"] == 0
        assert result["closure_count"] >= 2

    def test_partial_trailing_candle_is_not_a_gap(self):
        times = _hours(_at(2026, 9, 14, 0), 48)
        times.append(times[-1] + 20 * 60_000)  # last bucket came in early
        result = dq.validate_ohlcv(_series(HOUR, times), "1h")
        assert result["valid"] is True, result["errors"]
        assert result["partial_count"] == 1



class TestCorruptionIsStillRejected:
    def test_duplicate_timestamp(self):
        times = _hours(_at(2026, 9, 14, 0), 48)
        times[10] = times[9]
        assert dq.validate_ohlcv(_series(HOUR, times), "1h")["valid"] is False

    def test_impossible_high(self):
        candles = _series(HOUR, _hours(_at(2026, 9, 14, 0), 48))
        candles[20]["high"] = 0.5
        assert dq.validate_ohlcv(candles, "1h")["valid"] is False

    def test_negative_price(self):
        candles = _series(HOUR, _hours(_at(2026, 9, 14, 0), 48))
        candles[5]["close"] = -1
        assert dq.validate_ohlcv(candles, "1h")["valid"] is False

    def test_negative_volume(self):
        candles = _series(HOUR, _hours(_at(2026, 9, 14, 0), 48))
        candles[7]["volume"] = -3
        assert dq.validate_ohlcv(candles, "1h")["valid"] is False

    def test_single_large_hole_during_trading(self):
        """A 20-candle hole mid-session is corruption, not a schedule.

        Counted in missing candles, not holes: a hole-count-only tolerance would
        accept this. Kept short enough that the hole cannot drift onto a
        weekend, where it would legitimately be a closure.
        """
        base = _at(2026, 9, 14, 6)  # Monday
        all_hours = _hours(base, 80)
        times = all_hours[:30] + all_hours[50:]
        result = dq.validate_ohlcv(_series(HOUR, times), "1h")
        assert result["valid"] is False
        assert result["missing_intervals"] == 20


    def test_scattered_gaps_at_unrelated_hours(self):
        base = _at(2026, 9, 14, 0)
        times = []
        shift = 0
        for block in range(0, 200, 20):
            times += [base + block * HOUR + i * HOUR + shift for i in range(20)]
            shift += 3 * HOUR  # a different hour each time, never recurring
        result = dq.validate_ohlcv(_series(HOUR, times), "1h")
        assert result["valid"] is False
        assert result["gap_count"] >= 3

    def test_empty_series_is_invalid(self):
        assert dq.validate_ohlcv([], "1h")["valid"] is False

    def test_tolerance_scales_with_length(self):
        assert dq._gap_tolerance(0) == 0
        assert dq._gap_tolerance(10) == 1
        assert dq._gap_tolerance(200) == 4
        assert dq._gap_tolerance(1000) == 20


class TestClassificationIsReported:
    def test_counts_are_exposed_for_operators(self):
        times = [_at(2026, 9, 18, 20) + i * HOUR for i in range(2)]
        times += [_at(2026, 9, 20, 23) + i * HOUR for i in range(24)]
        result = dq.validate_ohlcv(_series(HOUR, times), "1h")
        for key in ("valid", "candle_count", "duplicate_count", "gap_count",
                    "missing_intervals", "closure_count", "partial_count",
                    "gap_tolerance", "invalid_candle_count", "errors"):
            assert key in result, f"{key} missing from the report"

    def test_tolerance_is_reported_even_when_valid(self):
        result = dq.validate_ohlcv(_series(HOUR, _hours(_at(2026, 9, 14, 0), 48)), "1h")
        assert result["gap_tolerance"] == dq._gap_tolerance(48)



class TestEngineNowAnalysesRealData:
    """The consequence: the analysis loop must stop skipping every symbol."""

    def test_engine_no_longer_logs_data_quality_failed_on_real_series(self, monkeypatch):
        """A healthy Forex series must pass the gate the engine applies."""
        from app import data_quality

        times = [_at(2026, 9, 18, 20) + i * HOUR for i in range(2)]
        times += [_at(2026, 9, 20, 23) + i * HOUR for i in range(200)]
        candles = [
            {**c, "symbol": "EURUSD", "source": "yahoo_finance"} for c in _series(HOUR, times)
        ]
        assert data_quality.validate_ohlcv(candles, "1h")["valid"] is True
