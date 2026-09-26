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
def calculate_forex_position_size(
    symbol: ForexInstrument,
    account_balance: float,
    risk_fraction: float,
    entry_price: float,
    stop_loss_price: float
) -> dict:
    """
    Calculate optimal position size based on risk fraction.

    Args:
        symbol: Forex instrument
        account_balance: Account balance in EUR/USD
        risk_fraction: Risk as a FRACTION of the balance, matching
            IctConfig.risk_per_trade_pct (0.005 means 0.5%). Passing a
            percentage such as 0.5 here would size the position 100x too small.
        entry_price: Entry price
        stop_loss_price: Stop loss price

    Returns:
        dict with position size in lots and risk details
    """
    cfg = get_instrument_config(symbol)

    # Calculate risk amount in currency
    risk_amount = account_balance * risk_fraction

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
