"""Deterministic quality gates for stored OHLCV candles."""

INTERVAL_MILLISECONDS = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}


def validate_ohlcv(candles: list[dict], interval: str) -> dict:
    errors: list[str] = []
    invalid_candles = 0
    duplicate_count = 0
    gap_count = 0
    previous_open_time = None
    seen_open_times: set[int] = set()
    for candle in candles:
        open_time = candle["open_time"]
        if open_time in seen_open_times:
            duplicate_count += 1
        seen_open_times.add(open_time)
        if previous_open_time is not None and open_time - previous_open_time != INTERVAL_MILLISECONDS[interval]:
            gap_count += 1
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
    if not candles:
        errors.append("No candles are stored for this symbol and interval.")
    if duplicate_count:
        errors.append(f"{duplicate_count} duplicate candle timestamps detected.")
    if gap_count:
        errors.append(f"{gap_count} missing or irregular candle intervals detected.")
    if invalid_candles:
        errors.append(f"{invalid_candles} invalid OHLCV candles detected.")
    return {"valid": not errors, "candle_count": len(candles), "duplicate_count": duplicate_count, "gap_count": gap_count, "invalid_candle_count": invalid_candles, "errors": errors}
