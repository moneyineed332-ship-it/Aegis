"""Shared technical indicators — single source of truth.

All strategy files import from here instead of duplicating logic.
Provides both series (list) and scalar (single value) variants.
"""

from __future__ import annotations

import math
from statistics import fmean, stdev


# ── EMA ─────────────────────────────────────────────────────────────

def ema_series(data: list[float], period: int) -> list[float]:
    """Full EMA series. Seeds with data[0]."""
    if not data:
        return []
    k = 2 / (period + 1)
    result = [data[0]]
    for i in range(1, len(data)):
        result.append(data[i] * k + result[-1] * (1 - k))
    return result


def ema_single(values: list[float], period: int) -> float:
    """Single EMA value. Seeds with mean of first *period* elements."""
    if len(values) < period:
        return fmean(values) if values else 0.0
    multiplier = 2 / (period + 1)
    ema = fmean(values[:period])
    for price in values[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


# ── RSI ─────────────────────────────────────────────────────────────

def rsi_series(closes: list[float], period: int = 14) -> list[float]:
    """Full RSI series (Wilder smoothing)."""
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    rsi_vals = [50.0] * period
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = fmean(gains[:period])
    avg_loss = fmean(losses[:period])
    if avg_loss == 0:
        rsi_vals.append(100.0)
    else:
        rsi_vals.append(100 - 100 / (1 + avg_gain / avg_loss))
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_vals.append(100.0)
        else:
            rsi_vals.append(100 - 100 / (1 + avg_gain / avg_loss))
    return rsi_vals


def rsi_single(closes: list[float], period: int = 14) -> float:
    """Single RSI value (latest)."""
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


# ── ATR ─────────────────────────────────────────────────────────────

def atr_series(candles: list[dict], period: int = 14) -> list[float]:
    """Full ATR series (Wilder smoothing)."""
    if len(candles) < period + 1:
        return [0.0] * len(candles)
    true_ranges = [0.0]
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        true_ranges.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr_vals = [0.0] * period
    atr_val = fmean(true_ranges[1:period + 1])
    atr_vals.append(atr_val)
    for i in range(period + 1, len(true_ranges)):
        atr_val = (atr_val * (period - 1) + true_ranges[i]) / period
        atr_vals.append(atr_val)
    return atr_vals


def atr_single(candles: list[dict], period: int = 14) -> float:
    """Single ATR value (latest)."""
    if len(candles) < period + 1:
        return 0.0
    true_ranges: list[float] = []
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


# ── ADX ─────────────────────────────────────────────────────────────

def adx_dict(candles: list[dict], period: int = 14) -> dict:
    """ADX + DI as a dict (for features.py)."""
    if len(candles) < period * 2 + 1:
        return {"adx": 25.0, "plus_di": 0.0, "minus_di": 0.0}

    plus_dm_list: list[float] = []
    minus_dm_list: list[float] = []
    tr_list: list[float] = []

    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_high = candles[i - 1]["high"]
        prev_low = candles[i - 1]["low"]
        prev_close = candles[i - 1]["close"]

        up_move = high - prev_high
        down_move = prev_low - low

        plus_dm_list.append(up_move if up_move > down_move and up_move > 0 else 0)
        minus_dm_list.append(down_move if down_move > up_move and down_move > 0 else 0)
        tr_list.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))

    if len(tr_list) < period:
        return {"adx": 25.0, "plus_di": 0.0, "minus_di": 0.0}

    atr_val = fmean(tr_list[:period])
    plus_dm_smooth = fmean(plus_dm_list[:period])
    minus_dm_smooth = fmean(minus_dm_list[:period])

    dx_values: list[float] = []
    for i in range(period, len(tr_list)):
        atr_val = (atr_val * (period - 1) + tr_list[i]) / period
        plus_dm_smooth = (plus_dm_smooth * (period - 1) + plus_dm_list[i]) / period
        minus_dm_smooth = (minus_dm_smooth * (period - 1) + minus_dm_list[i]) / period

        if atr_val == 0:
            plus_di = minus_di = 0
        else:
            plus_di = (plus_dm_smooth / atr_val) * 100
            minus_di = (minus_dm_smooth / atr_val) * 100

        di_sum = plus_di + minus_di
        dx_values.append(abs(plus_di - minus_di) / di_sum * 100 if di_sum > 0 else 0)

    if len(dx_values) < period:
        adx_val = fmean(dx_values) if dx_values else 25.0
    else:
        adx_val = fmean(dx_values[:period])
        for dx in dx_values[period:]:
            adx_val = (adx_val * (period - 1) + dx) / period

    return {
        "adx": round(adx_val, 6),
        "plus_di": round((plus_dm_smooth / atr_val * 100) if atr_val > 0 else 0, 6),
        "minus_di": round((minus_dm_smooth / atr_val * 100) if atr_val > 0 else 0, 6),
    }


def adx_series(candles: list[dict], period: int = 14) -> list[float]:
    """ADX series (for regime filter in mean_reversion)."""
    if len(candles) < period * 2:
        return [25.0] * len(candles)

    plus_dm = [0.0]
    minus_dm = [0.0]
    for i in range(1, len(candles)):
        h, l = candles[i]["high"], candles[i]["low"]
        ph, pl = candles[i - 1]["high"], candles[i - 1]["low"]
        up = h - ph
        down = pl - l
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)

    tr = [0.0]
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))

    atr_val = fmean(tr[1:period + 1])
    plus_val = fmean(plus_dm[1:period + 1])
    minus_val = fmean(minus_dm[1:period + 1])

    atr_smooth = [0.0] * period
    plus_dm_smooth = [0.0] * period
    minus_dm_smooth = [0.0] * period
    atr_smooth.append(atr_val)
    plus_dm_smooth.append(plus_val)
    minus_dm_smooth.append(minus_val)

    for i in range(period + 1, len(candles)):
        atr_val = (atr_val * (period - 1) + tr[i]) / period
        plus_val = (plus_val * (period - 1) + plus_dm[i]) / period
        minus_val = (minus_val * (period - 1) + minus_dm[i]) / period
        atr_smooth.append(atr_val)
        plus_dm_smooth.append(plus_val)
        minus_dm_smooth.append(minus_val)

    plus_di = [100 * p / a if a > 0 else 0 for p, a in zip(plus_dm_smooth, atr_smooth)]
    minus_di = [100 * m / a if a > 0 else 0 for m, a in zip(minus_dm_smooth, atr_smooth)]

    dx = []
    for p, m in zip(plus_di, minus_di):
        total = p + m
        dx.append(100 * abs(p - m) / total if total > 0 else 0)

    adx_vals = [25.0] * period
    if len(dx) > period:
        adx_val = fmean(dx[1:period + 1])
        adx_vals.append(adx_val)
        for i in range(period + 1, len(dx)):
            adx_val = (adx_val * (period - 1) + dx[i]) / period
            adx_vals.append(adx_val)

    return adx_vals


# ── Bollinger Bands ─────────────────────────────────────────────────

def bollinger_dict(closes: list[float], period: int = 20, num_std: float = 2.0) -> dict:
    """Bollinger Bands as dict (for features.py)."""
    if len(closes) < period:
        mid = fmean(closes) if closes else 0.0
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


def bollinger_series(closes: list[float], period: int) -> list[tuple[float, float, float]]:
    """Bollinger series as (lower, upper, mid) tuples (for mean_reversion)."""
    bands: list[tuple[float, float, float]] = []
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]
        mid = fmean(window)
        std = stdev(window) if len(window) > 1 else 0
        bands.append((mid - 2 * std, mid + 2 * std, mid))
    return bands


# ── MACD ────────────────────────────────────────────────────────────

def macd_dict(closes: list[float]) -> dict:
    """MACD line, signal, histogram as dict (for features.py)."""
    if len(closes) < 35:
        return {"macd": 0.0, "macd_signal": 0.0, "macd_histogram": 0.0}
    ema12 = ema_series(closes, 12)
    ema26 = ema_series(closes, 26)
    macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    signal = ema_series(macd_line, 9)[-1] if len(macd_line) >= 9 else macd_line[-1]
    macd_val = macd_line[-1]
    return {
        "macd": round(macd_val, 6),
        "macd_signal": round(signal, 6),
        "macd_histogram": round(macd_val - signal, 6),
    }


def macd_series(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[list[float], list[float], list[float]]:
    """MACD as 3 full series (for swing.py)."""
    ema_fast = ema_series(closes, fast)
    ema_slow = ema_series(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema_series(macd_line, signal)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]
    return macd_line, signal_line, histogram


# ── Stochastic ──────────────────────────────────────────────────────

def stochastic(candles: list[dict], k_period: int = 5, d_period: int = 3) -> tuple[list[float], list[float]]:
    """Stochastic oscillator (K, D) as full series."""
    if len(candles) < k_period:
        return [50.0] * len(candles), [50.0] * len(candles)
    k_vals = [50.0] * (k_period - 1)
    for i in range(k_period - 1, len(candles)):
        window = candles[i - k_period + 1:i + 1]
        high_max = max(c["high"] for c in window)
        low_min = min(c["low"] for c in window)
        if high_max == low_min:
            k_vals.append(50.0)
        else:
            k_vals.append((candles[i]["close"] - low_min) / (high_max - low_min) * 100)
    d_vals = [50.0] * (k_period + d_period - 2)
    for i in range(d_period - 1, len(k_vals)):
        d_vals.append(fmean(k_vals[i - d_period + 1:i + 1]))
    return k_vals, d_vals


# ── Periods Per Year ────────────────────────────────────────────────

_INTERVALS: dict[str, int] = {
    "1m": 525_600,
    "5m": 105_120,
    "15m": 35_040,
    "30m": 17_520,
    "1h": 8_760,
    "4h": 2_190,
    "1d": 365,
}


def periods_per_year(interval: str) -> int:
    """Return annualization factor for a candle interval."""
    return _INTERVALS.get(interval, 8_760)


# ── Sortino Ratio ───────────────────────────────────────────────────

def sortino_ratio(returns: list[float], ppy: int) -> float:
    """Sortino ratio — penalises only downside volatility."""
    if len(returns) < 2:
        return 0.0
    downside = [r for r in returns if r < 0]
    if len(downside) < 2:
        return 0.0
    ds = stdev(downside)
    return round(fmean(returns) / ds * math.sqrt(ppy), 4) if ds > 0 else 0.0


# ════════════════════════════════════════════════════════════════════
# SMC/ICT — Smart Money Concepts & Inner Circle Trader
# ════════════════════════════════════════════════════════════════════


# ── Swing Highs / Swing Lows ──────────────────────────────────────

def swing_highs_lows(candles: list[dict], lookback: int = 5) -> dict:
    """Detect swing highs and swing lows (pivot points).

    A swing high: candle[i]['high'] > neighbors on both sides.
    A swing low:  candle[i]['low']  < neighbors on both sides.
    """
    highs: list[dict] = []
    lows: list[dict] = []
    for i in range(lookback, len(candles) - lookback):
        is_high = all(
            candles[i]["high"] > candles[i - j]["high"] and
            candles[i]["high"] > candles[i + j]["high"]
            for j in range(1, lookback + 1)
        )
        is_low = all(
            candles[i]["low"] < candles[i - j]["low"] and
            candles[i]["low"] < candles[i + j]["low"]
            for j in range(1, lookback + 1)
        )
        if is_high:
            highs.append({"index": i, "price": candles[i]["high"], "time": candles[i].get("open_time", i)})
        if is_low:
            lows.append({"index": i, "price": candles[i]["low"], "time": candles[i].get("open_time", i)})
    return {"highs": highs, "lows": lows}


# ── Market Structure (BOS / CHoCH) ───────────────────────────────

def market_structure(candles: list[dict], lookback: int = 5) -> dict:
    """Detect ICT/SMC Market Structure (HH, HL, LH, LL, BOS, CHoCH).

    Enhanced detection according to ICT methodology:
    - Higher High (HH): New swing high higher than previous swing high
    - Higher Low (HL): New swing low higher than previous swing low  
    - Lower High (LH): New swing high lower than previous swing high
    - Lower Low (LL): New swing low lower than previous swing low
    - BOS (Break of Structure): Price breaks significant swing point in trend direction
    - CHoCH (Change of Character): Structure change indicating potential trend reversal

    Returns:
        trend: "bullish" | "bearish" | "neutral"
        last_bos: "bullish_bos" | "bearish_bos" | None
        last_choch: "bullish_choch" | "bearish_choch" | None
        structure_points: list of swing points with detailed ICT classification
        recent_sequence: last 5 structure points for pattern recognition
    """
    pivots = swing_highs_lows(candles, lookback)
    swing_highs = pivots["highs"]
    swing_lows = pivots["lows"]

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {
            "trend": "neutral", 
            "last_bos": None, 
            "last_choch": None, 
            "structure_points": [],
            "recent_sequence": []
        }

    structure_points = []
    trend = "neutral"
    last_bos = None
    last_choch = None
    
    # Enhanced swing point classification
    # Analyze consecutive swing highs with ICT methodology
    for i in range(1, len(swing_highs)):
        prev_h = swing_highs[i - 1]
        curr_h = swing_highs[i]
        
        if curr_h["price"] > prev_h["price"]:
            structure_points.append({
                "type": "hh",
                "classification": "higher_high",
                "price": curr_h["price"],
                "index": curr_h["index"],
                "time": curr_h.get("time"),
                "significance": "strong" if curr_h["price"] > prev_h["price"] * 1.001 else "normal"  # 0.1% threshold
            })
        elif curr_h["price"] < prev_h["price"]:
            structure_points.append({
                "type": "lh", 
                "classification": "lower_high",
                "price": curr_h["price"],
                "index": curr_h["index"],
                "time": curr_h.get("time"),
                "significance": "strong" if curr_h["price"] < prev_h["price"] * 0.999 else "normal"
            })
        else:
            # Equal highs - potential liquidity zone
            structure_points.append({
                "type": "eh",
                "classification": "equal_highs",
                "price": curr_h["price"],
                "index": curr_h["index"],
                "time": curr_h.get("time"),
                "significance": "liquidity_zone"
            })

    # Analyze consecutive swing lows with ICT methodology
    for i in range(1, len(swing_lows)):
        prev_l = swing_lows[i - 1]
        curr_l = swing_lows[i]
        
        if curr_l["price"] > prev_l["price"]:
            structure_points.append({
                "type": "hl",
                "classification": "higher_low",
                "price": curr_l["price"],
                "index": curr_l["index"],
                "time": curr_l.get("time"),
                "significance": "strong" if curr_l["price"] > prev_l["price"] * 1.001 else "normal"
            })
        elif curr_l["price"] < prev_l["price"]:
            structure_points.append({
                "type": "ll",
                "classification": "lower_low",
                "price": curr_l["price"],
                "index": curr_l["index"],
                "time": curr_l.get("time"),
                "significance": "strong" if curr_l["price"] < prev_l["price"] * 0.999 else "normal"
            })
        else:
            # Equal lows - potential liquidity zone
            structure_points.append({
                "type": "el",
                "classification": "equal_lows",
                "price": curr_l["price"],
                "index": curr_l["index"],
                "time": curr_l.get("time"),
                "significance": "liquidity_zone"
            })

    # Sort by index for chronological order
    structure_points.sort(key=lambda x: x["index"])

    # Determine trend using ICT market structure rules
    # Bullish trend: HH + HL sequence
    # Bearish trend: LH + LL sequence
    recent = structure_points[-6:] if len(structure_points) >= 6 else structure_points
    hh_count = sum(1 for p in recent if p["type"] == "hh")
    hl_count = sum(1 for p in recent if p["type"] == "hl")
    lh_count = sum(1 for p in recent if p["type"] == "lh")
    ll_count = sum(1 for p in recent if p["type"] == "ll")

    # ICT trend determination logic
    if hh_count >= 2 and hl_count >= 1:
        trend = "bullish"
    elif lh_count >= 2 and ll_count >= 1:
        trend = "bearish"
    elif hh_count == 1 and hl_count == 1 and lh_count == 0 and ll_count == 0:
        trend = "bullish"  # Early bullish structure
    elif lh_count == 1 and ll_count == 1 and hh_count == 0 and hl_count == 0:
        trend = "bearish"  # Early bearish structure

    # Enhanced BOS detection
    current_price = candles[-1]["close"]
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        recent_sh = swing_highs[-1]["price"]
        recent_sl = swing_lows[-1]["price"]
        prev_sh = swing_highs[-2]["price"]
        prev_sl = swing_lows[-2]["price"]
        
        # Bullish BOS: Price breaks above recent swing high in bullish context
        if trend == "bullish" and current_price > recent_sh:
            last_bos = "bullish_bos"
        # Bearish BOS: Price breaks below recent swing low in bearish context  
        elif trend == "bearish" and current_price < recent_sl:
            last_bos = "bearish_bos"
        
        # CHoCH detection (structure change indicating potential reversal)
        # Bullish CHoCH: In bearish trend, price breaks above recent swing high
        if trend == "bearish" and current_price > recent_sh:
            last_choch = "bullish_choch"
        # Bearish CHoCH: In bullish trend, price breaks below recent swing low
        elif trend == "bullish" and current_price < recent_sl:
            last_choch = "bearish_choch"

    # Recent sequence for pattern recognition (last 5 structure points)
    recent_sequence = structure_points[-5:] if len(structure_points) >= 5 else structure_points

    return {
        "trend": trend,
        "last_bos": last_bos,
        "last_choch": last_choch,
        "structure_points": structure_points,
        "recent_sequence": recent_sequence,
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "current_price": current_price
    }


# ── Order Blocks ──────────────────────────────────────────────────

def order_blocks(candles: list[dict], lookback: int = 50) -> dict:
    """Detect Order Blocks (institutional supply/demand zones).

    Bullish OB: last bearish candle before a strong bullish move.
    Bearish OB: last bullish candle before a strong bearish move.
    """
    if len(candles) < lookback:
        lookback = len(candles)

    recent = candles[-lookback:]
    bullish_obs: list[dict] = []
    bearish_obs: list[dict] = []

    for i in range(2, len(recent)):
        prev = recent[i - 2]
        move = recent[i - 1]
        confirm = recent[i]
        current_price = candles[-1]["close"]

        # Enhanced Bullish OB detection with fill status
        if (prev["close"] < prev["open"] and
                confirm["close"] > confirm["open"] and
                confirm["close"] > prev["high"] and
                (confirm["close"] - confirm["open"]) > (prev["open"] - prev["close"]) * 1.5):
            
            # Calculate OB metrics
            ob_range = prev["high"] - prev["low"]
            ob_mid = (prev["high"] + prev["low"]) / 2
            
            # Determine fill status
            fill_status = "open"
            fill_percentage = 0.0
            
            if current_price <= prev["low"]:
                fill_status = "filled"
                fill_percentage = 100.0
            elif current_price < ob_mid:
                fill_status = "partially_filled"
                fill_percentage = ((ob_mid - current_price) / ob_range) * 100
            elif current_price < prev["high"]:
                fill_status = "partially_filled"
                fill_percentage = ((prev["high"] - current_price) / ob_range) * 100
            
            # Count retests
            retest_count = 0
            for j in range(i + 1, len(recent)):
                if prev["low"] <= recent[j]["low"] <= prev["high"]:
                    retest_count += 1
            
            bullish_obs.append({
                "price_low": prev["low"],
                "price_high": prev["high"],
                "price_mid": ob_mid,
                "index": len(candles) - lookback + i - 2,
                "time": prev.get("time"),
                "strength": round((confirm["close"] - prev["low"]) / prev["low"] * 100, 4) if prev["low"] > 0 else 0,
                "status": fill_status,
                "fill_percentage": round(fill_percentage, 2),
                "retest_count": retest_count,
                "type": "demand_zone"
            })

        # Enhanced Bearish OB detection with fill status
        if (prev["close"] > prev["open"] and
                confirm["close"] < confirm["open"] and
                confirm["close"] < prev["low"] and
                (confirm["open"] - confirm["close"]) > (prev["close"] - prev["open"]) * 1.5):
            
            # Calculate OB metrics
            ob_range = prev["high"] - prev["low"]
            ob_mid = (prev["high"] + prev["low"]) / 2
            
            # Determine fill status
            fill_status = "open"
            fill_percentage = 0.0
            
            if current_price >= prev["high"]:
                fill_status = "filled"
                fill_percentage = 100.0
            elif current_price > ob_mid:
                fill_status = "partially_filled"
                fill_percentage = ((current_price - ob_mid) / ob_range) * 100
            elif current_price > prev["low"]:
                fill_status = "partially_filled"
                fill_percentage = ((current_price - prev["low"]) / ob_range) * 100
            
            # Count retests
            retest_count = 0
            for j in range(i + 1, len(recent)):
                if prev["low"] <= recent[j]["high"] <= prev["high"]:
                    retest_count += 1
            
            bearish_obs.append({
                "price_low": prev["low"],
                "price_high": prev["high"],
                "price_mid": ob_mid,
                "index": len(candles) - lookback + i - 2,
                "time": prev.get("time"),
                "strength": round((prev["high"] - confirm["close"]) / prev["high"] * 100, 4) if prev["high"] > 0 else 0,
                "status": fill_status,
                "fill_percentage": round(fill_percentage, 2),
                "retest_count": retest_count,
                "type": "supply_zone"
            })

    # Sort by index and return detailed info
    bullish_obs.sort(key=lambda x: x["index"])
    bearish_obs.sort(key=lambda x: x["index"])

    return {
        "bullish_ob": bullish_obs[-1] if bullish_obs else None,
        "bearish_ob": bearish_obs[-1] if bearish_obs else None,
        "all_bullish_obs": bullish_obs,
        "all_bearish_obs": bearish_obs,
        "bullish_ob_count": len(bullish_obs),
        "bearish_ob_count": len(bearish_obs),
    }


# ── Fair Value Gaps (FVG) ────────────────────────────────────────

def fair_value_gaps(candles: list[dict], lookback: int = 50) -> dict:
    """Detect Fair Value Gaps (price imbalances / inefficiencies) with detailed status tracking.

    Enhanced ICT methodology:
    - Bullish FVG: candle[0].high < candle[2].low (gap up) - demand inefficiency
    - Bearish FVG: candle[0].low > candle[2].high (gap down) - supply inefficiency
    - Track fill status: open, partially_filled, filled
    - Calculate fill percentage and retest count
    - Classify FVG significance by size

    Returns:
        bullish_fvg: most recent bullish FVG with detailed info
        bearish_fvg: most recent bearish FVG with detailed info
        all_bullish_fvgs: all bullish FVGs with status
        all_bearish_fvgs: all bearish FVGs with status
    """
    if len(candles) < lookback:
        lookback = len(candles)

    recent = candles[-lookback:]
    bullish_fvgs: list[dict] = []
    bearish_fvgs: list[dict] = []
    current_price = candles[-1]["close"]

    for i in range(2, len(recent)):
        c0 = recent[i - 2]
        c1 = recent[i - 1]
        c2 = recent[i]

        # Enhanced Bullish FVG detection
        if c0["high"] < c2["low"]:
            gap_size = c2["low"] - c0["high"]
            gap_mid = (c0["high"] + c2["low"]) / 2
            
            # Determine fill status
            fill_status = "open"
            fill_percentage = 0.0
            
            if current_price <= c0["high"]:
                fill_status = "filled"
                fill_percentage = 100.0
            elif current_price < gap_mid:
                fill_status = "partially_filled"
                fill_percentage = ((gap_mid - current_price) / gap_size) * 100
            elif current_price < c2["low"]:
                fill_status = "partially_filled"
                fill_percentage = ((c2["low"] - current_price) / gap_size) * 100
            
            # Count retests (price entering FVG zone)
            retest_count = 0
            for j in range(i + 1, len(recent)):
                if c0["high"] <= recent[j]["low"] <= c2["low"]:
                    retest_count += 1
            
            # Classify significance
            gap_pct = round(gap_size / c1["close"] * 100, 4) if c1["close"] > 0 else 0
            significance = "normal"
            if gap_pct > 0.1:  # More than 0.1% gap
                significance = "strong"
            elif gap_pct > 0.05:
                significance = "moderate"
            
            bullish_fvgs.append({
                "price_low": c0["high"],
                "price_high": c2["low"],
                "price_mid": gap_mid,
                "gap_size": round(gap_size, 6),
                "gap_pct": gap_pct,
                "index": len(candles) - lookback + i - 1,
                "time": c0.get("time"),
                "status": fill_status,
                "fill_percentage": round(fill_percentage, 2),
                "retest_count": retest_count,
                "significance": significance,
                "type": "demand_inefficiency"
            })

        # Enhanced Bearish FVG detection
        if c0["low"] > c2["high"]:
            gap_size = c0["low"] - c2["high"]
            gap_mid = (c0["low"] + c2["high"]) / 2
            
            # Determine fill status
            fill_status = "open"
            fill_percentage = 0.0
            
            if current_price >= c0["low"]:
                fill_status = "filled"
                fill_percentage = 100.0
            elif current_price > gap_mid:
                fill_status = "partially_filled"
                fill_percentage = ((current_price - gap_mid) / gap_size) * 100
            elif current_price > c2["high"]:
                fill_status = "partially_filled"
                fill_percentage = ((current_price - c2["high"]) / gap_size) * 100
            
            # Count retests
            retest_count = 0
            for j in range(i + 1, len(recent)):
                if c2["high"] <= recent[j]["high"] <= c0["low"]:
                    retest_count += 1
            
            # Classify significance
            gap_pct = round(gap_size / c1["close"] * 100, 4) if c1["close"] > 0 else 0
            significance = "normal"
            if gap_pct > 0.1:
                significance = "strong"
            elif gap_pct > 0.05:
                significance = "moderate"
            
            bearish_fvgs.append({
                "price_low": c2["high"],
                "price_high": c0["low"],
                "price_mid": gap_mid,
                "gap_size": round(gap_size, 6),
                "gap_pct": gap_pct,
                "index": len(candles) - lookback + i - 1,
                "time": c0.get("time"),
                "status": fill_status,
                "fill_percentage": round(fill_percentage, 2),
                "retest_count": retest_count,
                "significance": significance,
                "type": "supply_inefficiency"
            })

    # Sort by index and return detailed info
    bullish_fvgs.sort(key=lambda x: x["index"])
    bearish_fvgs.sort(key=lambda x: x["index"])

    return {
        "bullish_fvg": bullish_fvgs[-1] if bullish_fvgs else None,
        "bearish_fvg": bearish_fvgs[-1] if bearish_fvgs else None,
        "all_bullish_fvgs": bullish_fvgs,
        "all_bearish_fvgs": bearish_fvgs,
        "bullish_fvg_count": len(bullish_fvgs),
        "bearish_fvg_count": len(bearish_fvgs),
    }


# ── Liquidity Zones ───────────────────────────────────────────────

def liquidity_zones(candles: list[dict], lookback: int = 50) -> dict:
    """Detect liquidity zones with enhanced ICT methodology.

    Enhanced detection:
    - Equal Highs/Lows: Multiple swing points at similar levels
    - Buy-side liquidity: Above current price (sell-side stops)
    - Sell-side liquidity: Below current price (buy-side stops)
    - Internal/External liquidity classification
    - Valid sweep detection with confirmation requirements
    - Liquidity pool strength assessment

    Returns:
        buy_side_liquidity: zones above current price
        sell_side_liquidity: zones below current price
        equal_highs: detected equal high zones
        equal_lows: detected equal low zones
        recent_bull_sweep: validated bullish liquidity sweep
        recent_bear_sweep: validated bearish liquidity sweep
    """
    pivots = swing_highs_lows(candles, lookback)
    current_price = candles[-1]["close"]
    current_high = candles[-1]["high"]
    current_low = candles[-1]["low"]
    
    # pip tolerance for equality detection (0.0001 for forex)
    pip_tolerance = 0.0001 * 10  # 10 pips tolerance for equality

    buy_side_liq: list[dict] = []   # Above current price (sell-side stops)
    sell_side_liq: list[dict] = []  # Below current price (buy-side stops)
    
    # Detect Equal Highs (liquidity pools at similar high levels)
    equal_highs = []
    swing_highs = pivots["highs"]
    for i in range(len(swing_highs)):
        for j in range(i + 1, len(swing_highs)):
            if abs(swing_highs[i]["price"] - swing_highs[j]["price"]) < pip_tolerance:
                equal_highs.append({
                    "price": (swing_highs[i]["price"] + swing_highs[j]["price"]) / 2,
                    "count": 2,
                    "strength": "moderate",
                    "type": "external_liquidity",
                    "levels": [swing_highs[i]["price"], swing_highs[j]["price"]]
                })
    
    # Detect Equal Lows (liquidity pools at similar low levels)
    equal_lows = []
    swing_lows = pivots["lows"]
    for i in range(len(swing_lows)):
        for j in range(i + 1, len(swing_lows)):
            if abs(swing_lows[i]["price"] - swing_lows[j]["price"]) < pip_tolerance:
                equal_lows.append({
                    "price": (swing_lows[i]["price"] + swing_lows[j]["price"]) / 2,
                    "count": 2,
                    "strength": "moderate",
                    "type": "external_liquidity",
                    "levels": [swing_lows[i]["price"], swing_lows[j]["price"]]
                })

    # Classify buy-side liquidity (above current price)
    for sh in swing_highs:
        if sh["price"] > current_price:
            # Determine if internal or external liquidity
            liq_type = "external_liquidity"
            if sh["price"] < current_price * 1.002:  # Within 0.2% - internal
                liq_type = "internal_liquidity"
            
            buy_side_liq.append({
                "price": sh["price"],
                "type": liq_type,
                "swept": current_high >= sh["price"],
                "index": sh["index"],
                "time": sh.get("time")
            })

    # Classify sell-side liquidity (below current price)
    for sl in swing_lows:
        if sl["price"] < current_price:
            # Determine if internal or external liquidity
            liq_type = "external_liquidity"
            if sl["price"] > current_price * 0.998:  # Within 0.2% - internal
                liq_type = "internal_liquidity"
            
            sell_side_liq.append({
                "price": sl["price"],
                "type": liq_type,
                "swept": current_low <= sl["price"],
                "index": sl["index"],
                "time": sl.get("time")
            })

    # Enhanced sweep detection with confirmation
    # Valid sweep: price moves beyond level, shows reaction, then confirms structure
    swept_bull = None
    swept_bear = None
    
    if len(candles) >= 5:
        # Bullish sweep: price sweeps below low then reacts upward
        for sl in swing_lows[-5:]:
            sweep_candle = None
            reaction_candles = []
            
            # Find the sweep candle
            for i in range(len(candles) - 10, len(candles)):
                if candles[i]["low"] <= sl["price"]:
                    sweep_candle = candles[i]
                    reaction_candles = candles[i+1:i+4]  # Next 3 candles for reaction
                    break
            
            if sweep_candle and reaction_candles:
                # Check for bullish reaction (higher closes)
                reaction_higher = all(c["close"] > sweep_candle["close"] for c in reaction_candles)
                wick_beyond = sweep_candle["low"] < sl["price"]
                close_above = sweep_candle["close"] > sl["price"]
                
                if wick_beyond and (close_above or reaction_higher):
                    swept_bull = {
                        "price": sl["price"],
                        "index": sl["index"],
                        "time": sl.get("time"),
                        "sweep_low": sweep_candle["low"],
                        "confirmed": True,
                        "reaction_strength": "strong" if reaction_higher else "moderate"
                    }
                    break
        
        # Bearish sweep: price sweeps above high then reacts downward
        for sh in swing_highs[-5:]:
            sweep_candle = None
            reaction_candles = []
            
            # Find the sweep candle
            for i in range(len(candles) - 10, len(candles)):
                if candles[i]["high"] >= sh["price"]:
                    sweep_candle = candles[i]
                    reaction_candles = candles[i+1:i+4]  # Next 3 candles for reaction
                    break
            
            if sweep_candle and reaction_candles:
                # Check for bearish reaction (lower closes)
                reaction_lower = all(c["close"] < sweep_candle["close"] for c in reaction_candles)
                wick_beyond = sweep_candle["high"] > sh["price"]
                close_below = sweep_candle["close"] < sh["price"]
                
                if wick_beyond and (close_below or reaction_lower):
                    swept_bear = {
                        "price": sh["price"],
                        "index": sh["index"],
                        "time": sh.get("time"),
                        "sweep_high": sweep_candle["high"],
                        "confirmed": True,
                        "reaction_strength": "strong" if reaction_lower else "moderate"
                    }
                    break

    return {
        "buy_side_liquidity": buy_side_liq[:5],
        "sell_side_liquidity": sell_side_liq[:5],
        "bsl_count": len(buy_side_liq),
        "ssl_count": len(sell_side_liq),
        "equal_highs": equal_highs,
        "equal_lows": equal_lows,
        "recent_bull_sweep": swept_bull,
        "recent_bear_sweep": swept_bear,
        "total_liquidity_zones": len(buy_side_liq) + len(sell_side_liq) + len(equal_highs) + len(equal_lows)
    }


# ── Premium / Discount Zones ──────────────────────────────────────

def premium_discount(candles: list[dict], lookback: int = 50) -> dict:
    """Compute premium and discount zones based on recent range.

    Premium: > 50% of range (expensive — sell zone)
    Discount: < 50% of range (cheap — buy zone)
    Equilibrium: ~50% (neutral)
    """
    if len(candles) < lookback:
        lookback = len(candles)

    recent = candles[-lookback:]
    range_high = max(c["high"] for c in recent)
    range_low = min(c["low"] for c in recent)
    range_size = range_high - range_low

    if range_size <= 0:
        return {"zone": "equilibrium", "position_in_range": 50.0, "range_high": range_high, "range_low": range_low}

    current_price = candles[-1]["close"]
    position_pct = (current_price - range_low) / range_size * 100

    if position_pct > 65:
        zone = "premium"
    elif position_pct < 35:
        zone = "discount"
    else:
        zone = "equilibrium"

    return {
        "zone": zone,
        "position_in_range": round(position_pct, 2),
        "range_high": round(range_high, 6),
        "range_low": round(range_low, 6),
        "range_size": round(range_size, 6),
        "fib_0_236": round(range_low + range_size * 0.236, 6),
        "fib_0_382": round(range_low + range_size * 0.382, 6),
        "fib_0_5": round(range_low + range_size * 0.5, 6),
        "fib_0_618": round(range_low + range_size * 0.618, 6),
        "fib_0_786": round(range_low + range_size * 0.786, 6),
    }


# ── SMC Confluence Score ─────────────────────────────────────────

def smc_confluence(candles: list[dict], lookback: int = 20) -> dict:
    """Compute an SMC/ICT confluence score combining all concepts.

    Score 0-100:
      - Market structure trend alignment (+25)
      - Order block proximity (+20)
      - FVG presence (+15)
      - Liquidity sweep (+20)
      - Premium/Discount zone (+10)
      - Trend HH/HL or LH/LL pattern (+10)
    """
    ms = market_structure(candles, lookback)
    ob = order_blocks(candles, lookback)
    fvg = fair_value_gaps(candles, lookback)
    liq = liquidity_zones(candles, lookback)
    pd = premium_discount(candles, lookback)
    current_price = candles[-1]["close"]

    score = 0
    direction = "neutral"
    reasons: list[str] = []

    # 1. Market structure (+25)
    if ms["trend"] == "bullish":
        score += 25
        direction = "bullish"
        reasons.append(f"Structure: {ms['trend']}")
    elif ms["trend"] == "bearish":
        score += 25
        direction = "bearish"
        reasons.append(f"Structure: {ms['trend']}")

    if ms["last_bos"]:
        score += 5
        reasons.append(f"BOS: {ms['last_bos']}")
    if ms["last_choch"]:
        score += 10
        reasons.append(f"CHoCH: {ms['last_choch']}")

    # 2. Order blocks (+20)
    if ob["bullish_ob"] and direction == "bullish":
        ob_low = ob["bullish_ob"]["price_low"]
        ob_high = ob["bullish_ob"]["price_high"]
        if ob_low <= current_price <= ob_high:
            score += 20
            reasons.append("Price in bullish OB")
        elif current_price <= ob_high * 1.01:
            score += 10
            reasons.append("Near bullish OB")
    if ob["bearish_ob"] and direction == "bearish":
        ob_low = ob["bearish_ob"]["price_low"]
        ob_high = ob["bearish_ob"]["price_high"]
        if ob_low <= current_price <= ob_high:
            score += 20
            reasons.append("Price in bearish OB")
        elif current_price >= ob_low * 0.99:
            score += 10
            reasons.append("Near bearish OB")

    # 3. Fair value gaps (+15)
    if fvg["bullish_fvg"] and direction == "bullish":
        score += 15
        reasons.append(f"Bullish FVG gap: {fvg['bullish_fvg']['gap_pct']}%")
    if fvg["bearish_fvg"] and direction == "bearish":
        score += 15
        reasons.append(f"Bearish FVG gap: {fvg['bearish_fvg']['gap_pct']}%")

    # 4. Liquidity sweep (+20)
    if liq["recent_bull_sweep"] and direction == "bullish":
        score += 20
        reasons.append("Bullish liquidity sweep detected")
    if liq["recent_bear_sweep"] and direction == "bearish":
        score += 20
        reasons.append("Bearish liquidity sweep detected")

    # 5. Premium / Discount (+10)
    if pd["zone"] == "discount" and direction == "bullish":
        score += 10
        reasons.append(f"Discount zone ({pd['position_in_range']:.0f}%)")
    elif pd["zone"] == "premium" and direction == "bearish":
        score += 10
        reasons.append(f"Premium zone ({pd['position_in_range']:.0f}%)")

    return {
        "score": min(score, 100),
        "direction": direction,
        "market_structure": ms,
        "order_blocks": ob,
        "fair_value_gaps": fvg,
        "liquidity": liq,
        "premium_discount": pd,
        "reasons": reasons,
    }


# ════════════════════════════════════════════════════════════════════
# Multi-Timeframe Confluence
# ════════════════════════════════════════════════════════════════════

def multi_timeframe_confluence(candles_by_tf: dict[str, list[dict]]) -> dict:
    """Analyze confluence across multiple timeframes.

    Args:
        candles_by_tf: {"1h": [...], "4h": [...], "1d": [...]}

    Returns confluence score and per-timeframe analysis.
    """
    tf_results: dict[str, dict] = {}
    trend_votes: list[str] = []

    for tf, candles in candles_by_tf.items():
        if len(candles) < 50:
            tf_results[tf] = {"trend": "neutral", "score": 0, "reason": "insufficient_data"}
            continue

        smc = smc_confluence(candles)
        closes = [c["close"] for c in candles]
        rsi_val = rsi_single(closes, 14)

        tf_results[tf] = {
            "trend": smc["direction"],
            "score": smc["score"],
            "rsi": rsi_val,
            "market_structure": smc["market_structure"]["trend"],
            "reasons": smc["reasons"],
        }
        trend_votes.append(smc["direction"])

    # Overall confluence
    bullish_votes = trend_votes.count("bullish")
    bearish_votes = trend_votes.count("bearish")
    total_votes = len(trend_votes)

    if total_votes == 0:
        overall = "neutral"
        confluence_score = 0
    elif bullish_votes > bearish_votes and bullish_votes >= 2:
        overall = "bullish"
        confluence_score = round(bullish_votes / total_votes * 100)
    elif bearish_votes > bullish_votes and bearish_votes >= 2:
        overall = "bearish"
        confluence_score = round(bearish_votes / total_votes * 100)
    else:
        overall = "neutral"
        confluence_score = 0

    return {
        "overall_trend": overall,
        "confluence_score": confluence_score,
        "bullish_votes": bullish_votes,
        "bearish_votes": bearish_votes,
        "total_timeframes": total_votes,
        "timeframes": tf_results,
    }


# ── Enhanced SMA Crossover (Multi-Scale) ──────────────────────────

def multi_scale_crossover(candles: list[dict]) -> dict:
    """Multi-scale SMA/EMA crossover strategy.

    Uses fast (10), medium (20), slow (50) moving averages.
    Entry when all 3 align (fast > medium > slow for long).
    Adds EMA ribbon for confirmation.
    """
    closes = [c["close"] for c in candles]
    if len(closes) < 50:
        return {"signal": "neutral", "score": 0, "reason": "insufficient_data"}

    sma_fast = fmean(closes[-10:])
    sma_med = fmean(closes[-20:])
    sma_slow = fmean(closes[-50:])

    ema_fast = ema_single(closes, 10)
    ema_med = ema_single(closes, 20)
    ema_slow = ema_single(closes, 50)

    # Previous values for crossover detection
    prev_sma_fast = fmean(closes[-11:-1])
    prev_sma_med = fmean(closes[-21:-1])

    score = 0
    signal = "neutral"
    reasons: list[str] = []

    # SMA alignment
    if sma_fast > sma_med > sma_slow:
        score += 30
        signal = "bullish"
        reasons.append("SMA alignment: fast > med > slow")
    elif sma_fast < sma_med < sma_slow:
        score += 30
        signal = "bearish"
        reasons.append("SMA alignment: fast < med < slow")

    # EMA confirmation
    if ema_fast > ema_med > ema_slow and signal == "bullish":
        score += 20
        reasons.append("EMA ribbon confirms bullish")
    elif ema_fast < ema_med < ema_slow and signal == "bearish":
        score += 20
        reasons.append("EMA ribbon confirms bearish")

    # Fresh crossover (more weight)
    if prev_sma_fast <= prev_sma_med and sma_fast > sma_med:
        score += 25
        signal = "bullish"
        reasons.append("Fresh fast/med crossover")
    elif prev_sma_fast >= prev_sma_med and sma_fast < sma_med:
        score += 25
        signal = "bearish"
        reasons.append("Fresh fast/med crossover")

    # Distance between MAs (momentum)
    spread_pct = abs(sma_fast - sma_slow) / sma_slow * 100 if sma_slow > 0 else 0
    if spread_pct > 1:
        score += 15
        reasons.append(f"Strong MA spread: {spread_pct:.1f}%")

    # RSI filter
    rsi_val = rsi_single(closes, 14)
    if signal == "bullish" and 40 < rsi_val < 70:
        score += 10
        reasons.append(f"RSI confirms: {rsi_val:.0f}")
    elif signal == "bearish" and 30 < rsi_val < 60:
        score += 10
        reasons.append(f"RSI confirms: {rsi_val:.0f}")

    return {
        "signal": signal,
        "score": min(score, 100),
        "sma_fast": round(sma_fast, 6),
        "sma_med": round(sma_med, 6),
        "sma_slow": round(sma_slow, 6),
        "ema_fast": round(ema_fast, 6),
        "ema_med": round(ema_med, 6),
        "ema_slow": round(ema_slow, 6),
        "rsi": round(rsi_val, 6),
        "reasons": reasons,
    }
