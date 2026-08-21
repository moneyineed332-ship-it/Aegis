"""Forex-specific indicators and adaptations for ICT/SMC analysis.

This module provides Forex-specific adaptations of technical indicators,
accounting for:
- Pip calculations (0.0001 for EUR/USD, GBP/USD; 0.01 for XAU/USD)
- Spread considerations
- Volatility thresholds specific to Forex pairs
- Session-based adjustments
- Contract sizes and lot calculations
"""

import math
from typing import Literal
from .ict_config import Instrument, get_instrument_config, pips_to_price, price_to_pips

ForexInstrument = Literal["EURUSD", "GBPUSD", "XAUUSD"]


# ============================================================
# PIP CALCULATIONS
# ============================================================

def get_pip_value(symbol: ForexInstrument) -> float:
    """Get the pip value for a Forex instrument."""
    cfg = get_instrument_config(symbol)
    return cfg.pip_value


def price_to_pips_forex(symbol: ForexInstrument, price_diff: float) -> float:
    """Convert price difference to pips for Forex instrument."""
    cfg = get_instrument_config(symbol)
    return price_diff / cfg.pip_value


def pips_to_price_forex(symbol: ForexInstrument, pips: float) -> float:
    """Convert pips to price difference for Forex instrument."""
    cfg = get_instrument_config(symbol)
    return pips * cfg.pip_value


def calculate_pip_profit(
    symbol: ForexInstrument,
    entry_price: float,
    exit_price: float,
    lots: float
) -> float:
    """
    Calculate profit/loss in pips and currency.
    
    Args:
        symbol: Forex instrument
        entry_price: Entry price
        exit_price: Exit price
        lots: Position size in lots
    
    Returns:
        dict with pip_profit and currency_profit
    """
    cfg = get_instrument_config(symbol)
    price_diff = exit_price - entry_price
    pips = price_to_pips_forex(symbol, price_diff)
    
    # Currency profit: pips * pip_value * contract_size * lots
    pip_value = cfg.pip_value
    contract_size = cfg.contract_size
    currency_profit = pips * pip_value * contract_size * lots
    
    return {
        "pips": round(pips, 1),
        "currency_profit": round(currency_profit, 2),
        "pip_value": pip_value,
        "contract_size": contract_size
    }


# ============================================================
# SPREAD ANALYSIS
# ============================================================

def calculate_spread_cost(
    symbol: ForexInstrument,
    spread_pips: float,
    lots: float
) -> float:
    """
    Calculate spread cost in currency.
    
    Args:
        symbol: Forex instrument
        spread_pips: Current spread in pips
        lots: Position size in lots
    
    Returns:
        Spread cost in account currency
    """
    cfg = get_instrument_config(symbol)
    pip_value = cfg.pip_value
    contract_size = cfg.contract_size
    
    # Spread cost = spread_pips * pip_value * contract_size * lots
    spread_cost = spread_pips * pip_value * contract_size * lots
    return round(spread_cost, 2)


def is_spread_acceptable(
    symbol: ForexInstrument,
    current_spread_pips: float,
    max_multiplier: float = 2.0
) -> bool:
    """
    Check if current spread is acceptable.
    
    Args:
        symbol: Forex instrument
        current_spread_pips: Current spread in pips
        max_multiplier: Maximum multiplier over typical spread
    
    Returns:
        True if spread is acceptable
    """
    cfg = get_instrument_config(symbol)
    typical_spread = cfg.typical_spread_pips
    max_acceptable = typical_spread * max_multiplier
    
    return current_spread_pips <= max_acceptable


# ============================================================
# VOLATILITY FILTERS
# ============================================================

def check_volatility_filters(
    symbol: ForexInstrument,
    current_atr_pips: float
) -> dict:
    """
    Check if volatility is within acceptable range for trading.
    
    Args:
        symbol: Forex instrument
        current_atr_pips: Current ATR in pips
    
    Returns:
        dict with volatility status and recommendations
    """
    cfg = get_instrument_config(symbol)
    min_atr = cfg.min_atr_pips
    max_atr = cfg.max_atr_pips
    
    volatility_status = "normal"
    recommendation = "trade_normal"
    risk_adjustment = 1.0  # No adjustment
    
    if current_atr_pips < min_atr:
        volatility_status = "low"
        recommendation = "reduce_position_size"
        risk_adjustment = 0.5  # Reduce risk by 50%
    elif current_atr_pips > max_atr:
        volatility_status = "high"
        recommendation = "avoid_trading"
        risk_adjustment = 0.0  # No trading
    
    # XAU/USD specific handling
    if symbol == "XAUUSD":
        if current_atr_pips > 500:  # Very high volatility for gold
            volatility_status = "extreme"
            recommendation = "avoid_trading"
            risk_adjustment = 0.0
    
    return {
        "status": volatility_status,
        "recommendation": recommendation,
        "risk_adjustment": risk_adjustment,
        "current_atr_pips": current_atr_pips,
        "min_atr_pips": min_atr,
        "max_atr_pips": max_atr,
        "within_range": min_atr <= current_atr_pips <= max_atr
    }


# ============================================================
# POSITION SIZING
# ============================================================

def calculate_forex_position_size(
    symbol: ForexInstrument,
    account_balance: float,
    risk_percent: float,
    entry_price: float,
    stop_loss_price: float
) -> dict:
    """
    Calculate optimal position size based on risk percentage.
    
    Args:
        symbol: Forex instrument
        account_balance: Account balance in EUR/USD
        risk_percent: Risk percentage (e.g., 0.5 for 0.5%)
        entry_price: Entry price
        stop_loss_price: Stop loss price
    
    Returns:
        dict with position size in lots and risk details
    """
    cfg = get_instrument_config(symbol)
    
    # Calculate risk amount in currency
    risk_amount = account_balance * (risk_percent / 100)
    
    # Calculate stop loss distance in pips
    sl_distance = abs(entry_price - stop_loss_price)
    sl_pips = price_to_pips_forex(symbol, sl_distance)
    
    if sl_pips == 0:
        return {
            "lots": 0.0,
            "risk_amount": 0.0,
            "sl_pips": 0.0,
            "error": "Stop loss distance is zero"
        }
    
    # Calculate position size
    # Position size = Risk Amount / (SL_Pips * Pip_Value * Contract_Size)
    pip_value = cfg.pip_value
    contract_size = cfg.contract_size
    
    lots = risk_amount / (sl_pips * pip_value * contract_size)
    
    # Round to standard lot size (0.01 minimum)
    lots = round(max(lots, 0.01), 2)
    
    # Calculate actual risk with rounded lots
    actual_risk = sl_pips * pip_value * contract_size * lots
    actual_risk_percent = (actual_risk / account_balance) * 100
    
    return {
        "lots": lots,
        "risk_amount": round(actual_risk, 2),
        "risk_percent": round(actual_risk_percent, 2),
        "sl_pips": round(sl_pips, 1),
        "sl_distance": round(sl_distance, 5),
        "pip_value": pip_value,
        "contract_size": contract_size
    }


def validate_position_size(
    symbol: ForexInstrument,
    lots: float,
    account_balance: float
) -> dict:
    """
    Validate if position size is within acceptable limits.
    
    Args:
        symbol: Forex instrument
        lots: Position size in lots
        account_balance: Account balance
    
    Returns:
        dict with validation result
    """
    cfg = get_instrument_config(symbol)
    
    # Calculate notional value
    pip_value = cfg.pip_value
    contract_size = cfg.contract_size
    # Approximate notional: lots * contract_size (simplified)
    notional_value = lots * contract_size
    
    # Calculate leverage
    leverage = notional_value / account_balance if account_balance > 0 else 0
    
    # Maximum reasonable leverage for retail Forex (typically 1:30 to 1:500)
    max_leverage = 100  # Conservative limit
    
    is_valid = leverage <= max_leverage
    warning = None
    
    if leverage > 50:
        warning = "High leverage - consider reducing position size"
    elif leverage > max_leverage:
        warning = "Excessive leverage - position size too large"
    
    return {
        "is_valid": is_valid,
        "leverage": round(leverage, 2),
        "notional_value": round(notional_value, 2),
        "max_leverage": max_leverage,
        "warning": warning
    }


# ============================================================
# RISK/REWARD CALCULATIONS
# ============================================================

def calculate_rr_ratio_forex(
    symbol: ForexInstrument,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float
) -> dict:
    """
    Calculate Risk/Reward ratio for Forex trade.
    
    Args:
        symbol: Forex instrument
        entry_price: Entry price
        stop_loss_price: Stop loss price
        take_profit_price: Take profit price
    
    Returns:
        dict with RR ratio and details in pips
    """
    risk_distance = abs(entry_price - stop_loss_price)
    reward_distance = abs(take_profit_price - entry_price)
    
    if risk_distance == 0:
        return {
            "rr_ratio": 0.0,
            "risk_pips": 0.0,
            "reward_pips": 0.0,
            "error": "Risk distance is zero"
        }
    
    rr_ratio = reward_distance / risk_distance
    risk_pips = price_to_pips_forex(symbol, risk_distance)
    reward_pips = price_to_pips_forex(symbol, reward_distance)
    
    cfg = get_instrument_config(symbol)
    min_rr = cfg.min_rr_ratio
    target_rr = cfg.target_rr_ratio
    
    is_acceptable = rr_ratio >= min_rr
    is_target = rr_ratio >= target_rr
    
    return {
        "rr_ratio": round(rr_ratio, 2),
        "risk_pips": round(risk_pips, 1),
        "reward_pips": round(reward_pips, 1),
        "risk_distance": round(risk_distance, 5),
        "reward_distance": round(reward_distance, 5),
        "min_rr": min_rr,
        "target_rr": target_rr,
        "is_acceptable": is_acceptable,
        "is_target": is_target
    }


def validate_sl_placement(
    symbol: ForexInstrument,
    entry_price: float,
    sl_price: float,
    atr_pips: float
) -> dict:
    """
    Validate if stop loss placement is structurally sound.
    
    Args:
        symbol: Forex instrument
        entry_price: Entry price
        sl_price: Stop loss price
        atr_pips: Current ATR in pips
    
    Returns:
        dict with validation result
    """
    cfg = get_instrument_config(symbol)
    sl_distance_pips = price_to_pips_forex(symbol, abs(entry_price - sl_price))
    
    # Check if SL is too tight (less than 0.5 ATR)
    min_sl_atr = 0.5
    max_sl_atr = cfg.sl_atr_multiplier
    
    sl_atr_ratio = sl_distance_pips / atr_pips if atr_pips > 0 else 0
    
    is_valid = min_sl_atr <= sl_atr_ratio <= max_sl_atr
    warning = None
    
    if sl_atr_ratio < min_sl_atr:
        warning = "Stop loss too tight - risk of being stopped out by noise"
    elif sl_atr_ratio > max_sl_atr:
        warning = "Stop loss too wide - excessive risk"
    
    return {
        "is_valid": is_valid,
        "sl_distance_pips": round(sl_distance_pips, 1),
        "atr_pips": round(atr_pips, 1),
        "sl_atr_ratio": round(sl_atr_ratio, 2),
        "min_sl_atr": min_sl_atr,
        "max_sl_atr": max_sl_atr,
        "warning": warning
    }


# ============================================================
# SESSION-SPECIFIC ADJUSTMENTS
# ============================================================

def get_session_adjustment(symbol: ForexInstrument, session: str) -> dict:
    """
    Get session-specific parameter adjustments.
    
    Different sessions may require different risk parameters:
    - Asian session: Typically lower volatility, tighter spreads
    - London session: Higher volatility, good for trend following
    - New York session: High volatility, news events
    - Overlap: Maximum volatility and opportunity
    
    Args:
        symbol: Forex instrument
        session: Session name (asian, london, new_york, overlap)
    
    Returns:
        dict with parameter multipliers
    """
    base_config = {
        "risk_multiplier": 1.0,
        "atr_multiplier": 1.0,
        "spread_tolerance": 2.0,
        "position_size_multiplier": 1.0
    }
    
    # Session-specific adjustments
    if session == "asian":
        base_config.update({
            "risk_multiplier": 0.8,  # Reduce risk in quieter session
            "atr_multiplier": 0.9,
            "spread_tolerance": 1.5,  # Less tolerance for wide spreads
            "position_size_multiplier": 0.8
        })
    elif session == "london":
        base_config.update({
            "risk_multiplier": 1.0,  # Normal risk
            "atr_multiplier": 1.0,
            "spread_tolerance": 2.0,
            "position_size_multiplier": 1.0
        })
    elif session == "new_york":
        base_config.update({
            "risk_multiplier": 0.9,  # Slightly reduce due to news risk
            "atr_multiplier": 1.1,
            "spread_tolerance": 2.5,
            "position_size_multiplier": 0.9
        })
    elif session == "overlap":
        base_config.update({
            "risk_multiplier": 1.1,  # Slightly increase in high opportunity session
            "atr_multiplier": 1.2,
            "spread_tolerance": 3.0,
            "position_size_multiplier": 1.1
        })
    
    # XAU/USD specific adjustments
    if symbol == "XAUUSD":
        base_config["risk_multiplier"] *= 0.8  # More conservative for gold
        base_config["position_size_multiplier"] *= 0.7
    
    return base_config


# ============================================================
# FOREX-SPECIFIC TECHNICAL INDICATORS
# ============================================================

def forex_atr(candles: list[dict], period: int = 14, symbol: ForexInstrument = "EURUSD") -> dict:
    """
    Calculate ATR specifically for Forex with pip conversion.
    
    Args:
        candles: OHLCV candles
        period: ATR period
        symbol: Forex instrument for pip conversion
    
    Returns:
        dict with ATR in price and pips
    """
    if len(candles) < period + 1:
        return {
            "atr_price": 0.0,
            "atr_pips": 0.0,
            "atr_percentage": 0.0
        }
    
    true_ranges = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        true_ranges.append(tr)
    
    # Calculate ATR using Wilder's smoothing
    atr = sum(true_ranges[:period]) / period
    for i in range(period, len(true_ranges)):
        atr = (atr * (period - 1) + true_ranges[i]) / period
    
    current_price = candles[-1]["close"]
    atr_pips = price_to_pips_forex(symbol, atr)
    atr_percentage = (atr / current_price) * 100 if current_price > 0 else 0
    
    return {
        "atr_price": round(atr, 5),
        "atr_pips": round(atr_pips, 1),
        "atr_percentage": round(atr_percentage, 3),
        "current_price": current_price
    }


def forex_pivot_points(candles: list[dict], symbol: ForexInstrument = "EURUSD") -> dict:
    """
    Calculate Forex pivot points (Standard, Fibonacci, Camarilla).
    
    Args:
        candles: OHLCV candles (need at least 1 previous day candle)
        symbol: Forex instrument
    
    Returns:
        dict with various pivot point calculations
    """
    if len(candles) < 1:
        return {"error": "Insufficient data for pivot points"}
    
    # Use previous candle for pivot calculation
    prev = candles[-1]
    high = prev["high"]
    low = prev["low"]
    close = prev["close"]
    
    # Standard Pivot Points
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)
    
    # Fibonacci Pivot Points
    fib_r1 = pivot + (high - low) * 0.382
    fib_r2 = pivot + (high - low) * 0.618
    fib_r3 = pivot + (high - low) * 1.0
    fib_s1 = pivot - (high - low) * 0.382
    fib_s2 = pivot - (high - low) * 0.618
    fib_s3 = pivot - (high - low) * 1.0
    
    # Convert to pips
    pip_value = get_pip_value(symbol)
    
    def to_pips(price):
        return round(price / pip_value, 1)
    
    return {
        "standard": {
            "pivot": round(pivot, 5),
            "r1": round(r1, 5),
            "r2": round(r2, 5),
            "r3": round(r3, 5),
            "s1": round(s1, 5),
            "s2": round(s2, 5),
            "s3": round(s3, 5),
        },
        "fibonacci": {
            "pivot": round(pivot, 5),
            "r1": round(fib_r1, 5),
            "r2": round(fib_r2, 5),
            "r3": round(fib_r3, 5),
            "s1": round(fib_s1, 5),
            "s2": round(fib_s2, 5),
            "s3": round(fib_s3, 5),
        },
        "in_pips": {
            "pivot": to_pips(pivot),
            "r1": to_pips(r1),
            "r2": to_pips(r2),
            "r3": to_pips(r3),
            "s1": to_pips(s1),
            "s2": to_pips(s2),
            "s3": to_pips(s3),
        },
        "high": high,
        "low": low,
        "close": close
    }
