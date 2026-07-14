"""Explainable market features derived from validated OHLCV candles."""

from statistics import fmean, pstdev


def _ema(values: list[float], period: int) -> float:
    """Exponential moving average — single value from a window."""
    if len(values) < period:
        return fmean(values)
    multiplier = 2 / (period + 1)
    ema = fmean(values[:period])
    for price in values[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def _rsi(closes: list[float], period: int = 14) -> float:
    """Relative Strength Index (Wilder smoothing)."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]
    avg_gain = fmean(gains[:period])
    avg_loss = fmean(losses[:period])
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 6)


def _macd(closes: list[float]) -> dict:
    """MACD line, signal line, histogram."""
    if len(closes) < 35:
        return {"macd": 0.0, "macd_signal": 0.0, "macd_histogram": 0.0}
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = ema12 - ema26

    # Build MACD series for signal line (EMA9 of MACD values)
    macd_values = []
    for i in range(26, len(closes) + 1):
        e12 = _ema(closes[:i], 12)
        e26 = _ema(closes[:i], 26)
        macd_values.append(e12 - e26)
    signal = _ema(macd_values, 9) if len(macd_values) >= 9 else macd_line
    return {
        "macd": round(macd_line, 6),
        "macd_signal": round(signal, 6),
        "macd_histogram": round(macd_line - signal, 6),
    }


def _atr(candles: list[dict], period: int = 14) -> float:
    """Average True Range (Wilder smoothing)."""
    if len(candles) < period + 1:
        return 0.0
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    if len(true_ranges) < period:
        return fmean(true_ranges)
    atr_val = fmean(true_ranges[:period])
    for tr in true_ranges[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return round(atr_val, 6)


def _bollinger(closes: list[float], period: int = 20, num_std: float = 2.0) -> dict:
    """Bollinger Bands."""
    if len(closes) < period:
        mid = fmean(closes)
        return {"bollinger_upper": mid, "bollinger_middle": mid, "bollinger_lower": mid}
    window = closes[-period:]
    mid = fmean(window)
    std = pstdev(window)
    return {
        "bollinger_upper": round(mid + num_std * std, 6),
        "bollinger_middle": round(mid, 6),
        "bollinger_lower": round(mid - num_std * std, 6),
    }


def latest_features(candles: list[dict]) -> dict:
    """Compute all explainable market features from OHLCV candles."""
    if len(candles) < 50:
        raise ValueError("At least 50 candles are required for market features.")
    closes = [candle["close"] for candle in candles]
    returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]

    # Base features
    sma_fast = fmean(closes[-20:])
    sma_slow = fmean(closes[-50:])
    volatility = pstdev(returns[-20:])
    momentum = closes[-1] / closes[-20] - 1
    range_ratio = (max(candle["high"] for candle in candles[-20:]) - min(candle["low"] for candle in candles[-20:])) / closes[-1]

    # New indicators
    rsi = _rsi(closes, 14)
    macd_data = _macd(closes)
    atr_val = _atr(candles, 14)
    bollinger_data = _bollinger(closes, 20, 2.0)

    return {
        "close": closes[-1],
        "sma_20": round(sma_fast, 6),
        "sma_50": round(sma_slow, 6),
        "momentum_20": round(momentum, 6),
        "volatility_20": round(volatility, 6),
        "range_20": round(range_ratio, 6),
        "rsi_14": round(rsi, 6),
        **macd_data,
        "atr_14": round(atr_val, 6),
        **bollinger_data,
    }
