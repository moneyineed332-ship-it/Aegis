"""Explainable market features derived from validated OHLCV candles.

Enhanced with ADX, Stochastic RSI, VWAP, and multi-timeframe support.
"""

from statistics import fmean, pstdev, stdev
import math


def _ema(values: list[float], period: int) -> float:
    """Exponential moving average — single value from a window."""
    if len(values) < period:
        return fmean(values)
    multiplier = 2 / (period + 1)
    ema = fmean(values[:period])
    for price in values[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def _ema_series(values: list[float], period: int) -> list[float]:
    """Build full EMA series — O(n) instead of O(n²)."""
    if len(values) < period:
        return [fmean(values[:i + 1]) for i in range(len(values))]
    multiplier = 2 / (period + 1)
    result = [fmean(values[:period])]
    for price in values[period:]:
        result.append((price - result[-1]) * multiplier + result[-1])
    return result


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


def _stochastic_rsi(closes: list[float], rsi_period: int = 14, stoch_period: int = 14, k_period: int = 3, d_period: int = 3) -> dict:
    """Stochastic RSI — momentum oscillator for overbought/oversold."""
    if len(closes) < rsi_period + stoch_period + k_period + d_period:
        return {"stoch_rsi_k": 50.0, "stoch_rsi_d": 50.0}

    rsi_values = []
    for i in range(rsi_period + 1, len(closes) + 1):
        rsi_values.append(_rsi(closes[:i], rsi_period))

    if len(rsi_values) < stoch_period:
        return {"stoch_rsi_k": 50.0, "stoch_rsi_d": 50.0}

    stoch_rsi_values = []
    for i in range(stoch_period, len(rsi_values) + 1):
        window = rsi_values[i - stoch_period:i]
        rsi_min = min(window)
        rsi_max = max(window)
        if rsi_max == rsi_min:
            stoch_rsi_values.append(50.0)
        else:
            stoch_rsi_values.append((rsi_values[i - 1] - rsi_min) / (rsi_max - rsi_min) * 100)

    k_values = []
    for i in range(k_period, len(stoch_rsi_values) + 1):
        k_values.append(fmean(stoch_rsi_values[i - k_period:i]))

    k = k_values[-1] if k_values else 50.0
    d = fmean(k_values[-d_period:]) if len(k_values) >= d_period else k

    return {"stoch_rsi_k": round(k, 6), "stoch_rsi_d": round(d, 6)}


def _adx(candles: list[dict], period: int = 14) -> dict:
    """Average Directional Index — trend strength (0-100)."""
    if len(candles) < period * 2 + 1:
        return {"adx": 25.0, "plus_di": 0.0, "minus_di": 0.0}

    plus_dm_list = []
    minus_dm_list = []
    tr_list = []

    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_high = candles[i - 1]["high"]
        prev_low = candles[i - 1]["low"]
        prev_close = candles[i - 1]["close"]

        up_move = high - prev_high
        down_move = prev_low - low

        plus_dm = up_move if up_move > down_move and up_move > 0 else 0
        minus_dm = down_move if down_move > up_move and down_move > 0 else 0

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))

        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)
        tr_list.append(tr)

    if len(tr_list) < period:
        return {"adx": 25.0, "plus_di": 0.0, "minus_di": 0.0}

    atr_val = fmean(tr_list[:period])
    plus_dm_smooth = fmean(plus_dm_list[:period])
    minus_dm_smooth = fmean(minus_dm_list[:period])

    dx_values = []
    for i in range(period, len(tr_list)):
        atr_val = (atr_val * (period - 1) + tr_list[i]) / period
        plus_dm_smooth = (plus_dm_smooth * (period - 1) + plus_dm_list[i]) / period
        minus_dm_smooth = (minus_dm_smooth * (period - 1) + minus_dm_list[i]) / period

        if atr_val == 0:
            plus_di = 0
            minus_di = 0
        else:
            plus_di = (plus_dm_smooth / atr_val) * 100
            minus_di = (minus_dm_smooth / atr_val) * 100

        di_sum = plus_di + minus_di
        if di_sum == 0:
            dx_values.append(0)
        else:
            dx_values.append(abs(plus_di - minus_di) / di_sum * 100)

    if len(dx_values) < period:
        adx_val = fmean(dx_values) if dx_values else 25.0
    else:
        adx_val = fmean(dx_values[:period])
        for dx in dx_values[period:]:
            adx_val = (adx_val * (period - 1) + dx) / period

    final_plus_di = (plus_dm_smooth / atr_val * 100) if atr_val > 0 else 0
    final_minus_di = (minus_dm_smooth / atr_val * 100) if atr_val > 0 else 0

    return {
        "adx": round(adx_val, 6),
        "plus_di": round(final_plus_di, 6),
        "minus_di": round(final_minus_di, 6),
    }


def _macd(closes: list[float]) -> dict:
    """MACD line, signal line, histogram — O(n) implementation."""
    if len(closes) < 35:
        return {"macd": 0.0, "macd_signal": 0.0, "macd_histogram": 0.0}

    ema12_series = _ema_series(closes, 12)
    ema26_series = _ema_series(closes, 26)

    macd_series = [e12 - e26 for e12, e26 in zip(ema12_series, ema26_series)]

    if len(macd_series) >= 9:
        signal = _ema_series(macd_series, 9)[-1]
    else:
        signal = macd_series[-1]

    macd_line = macd_series[-1]
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
    """Bollinger Bands (sample std)."""
    if len(closes) < period:
        mid = fmean(closes)
        return {"bollinger_upper": mid, "bollinger_middle": mid, "bollinger_lower": mid, "bollinger_width": 0.0}
    window = closes[-period:]
    mid = fmean(window)
    std = stdev(window) if len(window) > 1 else 0.0
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = (upper - lower) / mid if mid > 0 else 0
    return {
        "bollinger_upper": round(upper, 6),
        "bollinger_middle": round(mid, 6),
        "bollinger_lower": round(lower, 6),
        "bollinger_width": round(width, 6),
    }


def _vwap(candles: list[dict], period: int = 20) -> float:
    """Volume Weighted Average Price — recent period."""
    if not candles:
        return 0.0
    recent = candles[-period:]
    total_volume = 0.0
    total_pv = 0.0
    for c in recent:
        typical_price = (c["high"] + c["low"] + c["close"]) / 3
        vol = c.get("volume", 0)
        total_pv += typical_price * vol
        total_volume += vol
    return round(total_pv / total_volume, 6) if total_volume > 0 else recent[-1]["close"]


def _williams_r(candles: list[dict], period: int = 14) -> float:
    """Williams %R — overbought/oversold oscillator (-100 to 0)."""
    if len(candles) < period:
        return -50.0
    recent = candles[-period:]
    highest = max(c["high"] for c in recent)
    lowest = min(c["low"] for c in recent)
    current_close = candles[-1]["close"]
    if highest == lowest:
        return -50.0
    wr = (highest - current_close) / (highest - lowest) * -100
    return round(wr, 6)


def _obv(candles: list[dict]) -> float:
    """On-Balance Volume — cumulative volume flow."""
    if len(candles) < 2:
        return 0.0
    obv = 0.0
    for i in range(1, len(candles)):
        vol = candles[i].get("volume", 0)
        if candles[i]["close"] > candles[i - 1]["close"]:
            obv += vol
        elif candles[i]["close"] < candles[i - 1]["close"]:
            obv -= vol
    return round(obv, 2)


def _zscore(values: list[float], lookback: int = 20) -> float:
    """Z-score of the last value relative to the lookback window."""
    if len(values) < lookback:
        return 0.0
    window = values[-lookback:]
    mean = fmean(window)
    std = stdev(window) if len(window) > 1 else 0.001
    return round((values[-1] - mean) / std, 6) if std > 0 else 0.0


def latest_features(candles: list[dict]) -> dict:
    """Compute all explainable market features from OHLCV candles.

    Includes: SMA, RSI, MACD, ATR, Bollinger, ADX, Stochastic RSI,
    VWAP, Williams %R, OBV, Z-score, and volatility metrics.
    """
    if len(candles) < 50:
        raise ValueError("At least 50 candles are required for market features.")

    closes = [candle["close"] for candle in candles]
    returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]

    # Base features
    sma_fast = fmean(closes[-20:])
    sma_slow = fmean(closes[-50:])
    volatility = stdev(returns[-20:]) if len(returns[-20:]) > 1 else 0.0
    momentum = closes[-1] / closes[-20] - 1 if closes[-20] != 0 else 0
    range_ratio = (max(c["high"] for c in candles[-20:]) - min(c["low"] for c in candles[-20:])) / closes[-1] if closes[-1] > 0 else 0

    # Core indicators
    rsi = _rsi(closes, 14)
    macd_data = _macd(closes)
    atr_val = _atr(candles, 14)
    bollinger_data = _bollinger(closes, 20, 2.0)

    # Enhanced indicators
    adx_data = _adx(candles, 14)
    stoch_rsi_data = _stochastic_rsi(closes)
    vwap_val = _vwap(candles, 20)
    williams_r = _williams_r(candles, 14)
    obv_val = _obv(candles)
    zscore_val = _zscore(closes, 20)

    # Volatility metrics
    returns_20 = returns[-20:] if len(returns) >= 20 else returns
    vol_annualized = volatility * math.sqrt(8760) if volatility else 0
    downside_returns = [r for r in returns_20 if r < 0]
    downside_vol = stdev(downside_returns) if len(downside_returns) > 1 else 0.001
    sortino_vol = downside_vol * math.sqrt(8760)

    # Trend strength
    sma_ratio = (sma_fast / sma_slow - 1) if sma_slow > 0 else 0
    trend_strength = abs(sma_ratio)

    return {
        "close": closes[-1],
        "sma_20": round(sma_fast, 6),
        "sma_50": round(sma_slow, 6),
        "sma_ratio": round(sma_ratio, 6),
        "momentum_20": round(momentum, 6),
        "volatility_20": round(volatility, 6),
        "volatility_annualized": round(vol_annualized, 6),
        "range_20": round(range_ratio, 6),
        "rsi_14": round(rsi, 6),
        **macd_data,
        "atr_14": round(atr_val, 6),
        **bollinger_data,
        **adx_data,
        **stoch_rsi_data,
        "vwap": round(vwap_val, 6),
        "williams_r": round(williams_r, 6),
        "obv": round(obv_val, 2),
        "zscore_20": round(zscore_val, 6),
        "trend_strength": round(trend_strength, 6),
        "downside_volatility": round(sortino_vol, 6),
    }
