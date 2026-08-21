"""Explainable market features derived from validated OHLCV candles.

Enhanced with ADX, Stochastic RSI, VWAP, and multi-timeframe support.
"""

from statistics import fmean, stdev
import math

from .indicators import (
    ema_series, ema_single, rsi_single, adx_dict, macd_dict,
    atr_single, bollinger_dict, market_structure, order_blocks,
    fair_value_gaps, liquidity_zones, premium_discount, smc_confluence,
    multi_timeframe_confluence, multi_scale_crossover,
)


def _stochastic_rsi(closes: list[float], rsi_period: int = 14, stoch_period: int = 14, k_period: int = 3, d_period: int = 3) -> dict:
    """Stochastic RSI — momentum oscillator for overbought/oversold."""
    if len(closes) < rsi_period + stoch_period + k_period + d_period:
        return {"stoch_rsi_k": 50.0, "stoch_rsi_d": 50.0}

    rsi_values = []
    for i in range(rsi_period + 1, len(closes) + 1):
        rsi_values.append(rsi_single(closes[:i], rsi_period))

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
    rsi = rsi_single(closes, 14)
    macd_data = macd_dict(closes)
    atr_val = atr_single(candles, 14)
    bollinger_data = bollinger_dict(closes, 20, 2.0)

    # Enhanced indicators
    adx_data = adx_dict(candles, 14)
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

    # SMC/ICT features
    ms = market_structure(candles)
    ob = order_blocks(candles)
    fvg = fair_value_gaps(candles)
    liq = liquidity_zones(candles)
    pd = premium_discount(candles)
    smc = smc_confluence(candles)
    msc = multi_scale_crossover(candles)

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
        # SMC/ICT
        "smc_trend": ms["trend"],
        "smc_score": smc["score"],
        "smc_direction": smc["direction"],
        "has_bullish_ob": ob["bullish_ob"] is not None,
        "has_bearish_ob": ob["bearish_ob"] is not None,
        "bullish_fvg_count": fvg["bullish_fvg_count"],
        "bearish_fvg_count": fvg["bearish_fvg_count"],
        "bsl_count": liq["bsl_count"],
        "ssl_count": liq["ssl_count"],
        "recent_bull_sweep": liq["recent_bull_sweep"] is not None,
        "recent_bear_sweep": liq["recent_bear_sweep"] is not None,
        "pd_zone": pd["zone"],
        "pd_position": pd["position_in_range"],
        # Multi-Scale Crossover
        "msc_signal": msc["signal"],
        "msc_score": msc["score"],
    }
