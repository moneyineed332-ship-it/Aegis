"""Deterministic quality gates for stored OHLCV candles."""

from datetime import datetime, timedelta, timezone

INTERVAL_MILLISECONDS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}

# Forex has no candles while the market is closed, so a perfectly healthy series
# is full of gaps. The old check treated every gap as corruption: on real Yahoo
# data it rejected 12 of 12 symbol/timeframe combinations, each with two to
# eighteen "missing or irregular candle intervals" that were the Friday 21:00 to
# Sunday 23:00 closure, and the engine then skipped analysis for every symbol on
# every cycle.
#
# A gap is accepted when it is plausibly a scheduled closure. The purpose is to
# stop rejecting the market being closed, not to model a particular broker's
# session: a hole in the middle of a trading day is still counted, and enough of
# them still fails the gate.
def _is_expected_closure(previous_open_ms: int, open_ms: int, interval_ms: int) -> bool:
    """True when a gap is explained by the market being closed, by shape alone."""
    previous = datetime.fromtimestamp(previous_open_ms / 1000, tz=timezone.utc)
    current = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
    delta = current - previous

    # A single missing candle is never a closure: the market is open and a
    # candle is absent.
    if delta <= timedelta(milliseconds=interval_ms * 2):
        return False

    # Weekend, however long it ran and whichever day the series resumes on.
    if previous.weekday() == 4 and current.weekday() in (5, 6, 0):
        return True
    if previous.weekday() == 5 and current.weekday() in (6, 0):
        return True
    if previous.weekday() == 6 and current.weekday() == 0:
        return True
    return False


def _recurring_break_hours(gaps: list[tuple[int, int]], interval_ms: int) -> set[int]:
    """Hours of day at which a session break recurs.

    A session boundary repeats every trading day at the same wall-clock time.
    Corrupted or dropped data does not: it scatters. On real Yahoo data gold
    has a daily break at 20:00 UTC, visible on the 15m, 1h and 4h series, and
    the 4h series shows it at 17:00-20:00 only because its candles are aligned
    to four-hour boundaries, so the hour is clustered rather than exact.

    Requires two or more gaps inside a three-hour window, so a lone hole is
    never mistaken for a schedule. No size filter applies here: a daily break on
    the hourly series is exactly one missing candle, and requiring a larger gap
    would exclude the very case being looked for.
    """
    by_hour: dict[int, int] = {}
    for previous_open_ms, open_ms in gaps:
        if _is_expected_closure(previous_open_ms, open_ms, interval_ms):
            continue
        hour = datetime.fromtimestamp(previous_open_ms / 1000, tz=timezone.utc).hour
        by_hour[hour] = by_hour.get(hour, 0) + 1

    recurring: set[int] = set()
    for hour, count in by_hour.items():
        if count >= 2:
            recurring |= {(hour + offset) % 24 for offset in (-3, -2, -1, 0, 1, 2, 3)}
    return recurring




def _gap_tolerance(candle_count: int) -> int:
    """How many unexplained gaps are tolerated before the gate fails.

    A single missing candle in a long series is not corruption, and rejecting
    the whole series over one hole meant the engine skipped analysis for a
    symbol it could still analyse: gold's 15m series carries one daily break
    that a 50-hour window is too short to recognise as recurring.

    Tolerant of a small fraction, strict beyond it, so a genuinely damaged
    series still fails. Duplicates and impossible OHLC are never tolerated.
    """
    if candle_count <= 0:
        return 0
    return max(1, int(candle_count * 0.02))


def validate_ohlcv(candles: list[dict], interval: str) -> dict:
    errors: list[str] = []
    invalid_candles = 0
    duplicate_count = 0
    gap_count = 0
    closure_count = 0
    partial_count = 0
    missing_intervals = 0
    interval_ms = INTERVAL_MILLISECONDS[interval]
    previous_open_time = None
    seen_open_times: set[int] = set()
    irregular: list[tuple[int, int]] = []
    for candle in candles:
        open_time = candle["open_time"]
        if open_time in seen_open_times:
            duplicate_count += 1
        seen_open_times.add(open_time)
        if previous_open_time is not None and open_time - previous_open_time != interval_ms:
            irregular.append((previous_open_time, open_time))
        previous_open_time = open_time
        if (
            candle["open"] <= 0
            or candle["high"] <= 0
            or candle["low"] <= 0
            or candle["close"] <= 0
            or candle["volume"] < 0
            or candle["high"] < max(candle["open"], candle["close"])
            or candle["low"] > min(candle["open"], candle["close"])
        ):
            invalid_candles += 1

    # Classified only after the whole series is known, because a session break
    # is identified by recurring and a single pass cannot see the recurrence.
    recurring = _recurring_break_hours(irregular, interval_ms)
    for previous_ms, open_ms in irregular:
        if _is_expected_closure(previous_ms, open_ms, interval_ms):
            closure_count += 1
        elif open_ms - previous_ms < interval_ms:
            # Closer together than the interval: a partial trailing candle left
            # by resampling, not a missing one. Counting it as a gap reported
            # "1 missing candle" for a series that had none missing.
            partial_count += 1
        elif datetime.fromtimestamp(previous_ms / 1000, tz=timezone.utc).hour in recurring:
            closure_count += 1
        else:
            gap_count += 1
            # Count the candles absent, not the holes. A tolerance on the hole
            # count alone would accept a single twenty-candle hole in the middle
            # of a trading day, which is exactly the corruption the gate exists
            # to catch.
            missing_intervals += (open_ms - previous_ms) // interval_ms - 1

    if not candles:
        errors.append("No candles are stored for this symbol and interval.")
    if duplicate_count:
        errors.append(f"{duplicate_count} duplicate candle timestamps detected.")
    tolerance = _gap_tolerance(len(candles))
    if gap_count > tolerance or missing_intervals > tolerance:
        errors.append(
            f"{missing_intervals} missing or irregular candle intervals detected "
            f"in {gap_count} gap(s), tolerance {tolerance}."
        )
    if invalid_candles:
        errors.append(f"{invalid_candles} invalid OHLCV candles detected.")
    return {
        "valid": not errors,
        "candle_count": len(candles),
        "duplicate_count": duplicate_count,
        "gap_count": gap_count,
        "missing_intervals": missing_intervals,
        "closure_count": closure_count,
        "partial_count": partial_count,
        "gap_tolerance": tolerance,
        "invalid_candle_count": invalid_candles,
        "errors": errors,
    }

