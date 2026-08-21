"""Configuration Presets for ICT/SMC Trading Bot.

This module provides ready-to-use configuration presets for different trading styles:
- Conservative: Lower risk, wider stops, more selective
- Moderate: Balanced risk/reward
- Aggressive: Higher risk, tighter stops, more trades
- Scalping: Very short timeframes, quick entries/exits
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class TradingPreset:
    """Trading configuration preset."""
    name: str
    description: str
    risk_per_trade_pct: float
    max_daily_drawdown_pct: float
    max_total_drawdown_pct: float
    max_consecutive_losses: int
    max_trades_per_session: int
    min_rr_ratio: float
    target_rr_ratio: float
    sl_atr_multiplier: float
    tp_first_target_r: float
    partial_close_pct: float
    breakeven_trigger_r: float
    breakeven_offset_pips: float


# ============================================================
# PRESETS DEFINITIONS
# ============================================================

CONSERVATIVE_PRESET = TradingPreset(
    name="conservative",
    description="Lower risk, wider stops, highly selective entries",
    risk_per_trade_pct=0.3,  # 0.3% per trade
    max_daily_drawdown_pct=1.5,  # 1.5% daily DD
    max_total_drawdown_pct=8.0,  # 8% total DD
    max_consecutive_losses=2,  # Max 2 consecutive losses
    max_trades_per_session=2,  # Max 2 trades per session
    min_rr_ratio=2.0,  # Minimum 2:1 RR
    target_rr_ratio=3.0,  # Target 3:1 RR
    sl_atr_multiplier=2.0,  # Wider SL (2x ATR)
    tp_first_target_r=1.5,  # First TP at 1.5R
    partial_close_pct=0.3,  # Close 30% at TP1
    breakeven_trigger_r=1.5,  # BE at 1.5R
    breakeven_offset_pips=5.0  # 5 pips offset
)

MODERATE_PRESET = TradingPreset(
    name="moderate",
    description="Balanced risk/reward, standard ICT/SMC parameters",
    risk_per_trade_pct=0.5,  # 0.5% per trade
    max_daily_drawdown_pct=2.0,  # 2% daily DD
    max_total_drawdown_pct=10.0,  # 10% total DD
    max_consecutive_losses=3,  # Max 3 consecutive losses
    max_trades_per_session=3,  # Max 3 trades per session
    min_rr_ratio=1.5,  # Minimum 1.5:1 RR
    target_rr_ratio=2.0,  # Target 2:1 RR
    sl_atr_multiplier=1.5,  # Standard SL (1.5x ATR)
    tp_first_target_r=1.0,  # First TP at 1R
    partial_close_pct=0.5,  # Close 50% at TP1
    breakeven_trigger_r=1.0,  # BE at 1R
    breakeven_offset_pips=3.0  # 3 pips offset
)

AGGRESSIVE_PRESET = TradingPreset(
    name="aggressive",
    description="Higher risk, tighter stops, more frequent trades",
    risk_per_trade_pct=1.0,  # 1% per trade
    max_daily_drawdown_pct=3.0,  # 3% daily DD
    max_total_drawdown_pct=15.0,  # 15% total DD
    max_consecutive_losses=4,  # Max 4 consecutive losses
    max_trades_per_session=5,  # Max 5 trades per session
    min_rr_ratio=1.2,  # Minimum 1.2:1 RR
    target_rr_ratio=1.5,  # Target 1.5:1 RR
    sl_atr_multiplier=1.0,  # Tighter SL (1x ATR)
    tp_first_target_r=0.8,  # First TP at 0.8R
    partial_close_pct=0.6,  # Close 60% at TP1
    breakeven_trigger_r=0.8,  # BE at 0.8R
    breakeven_offset_pips=2.0  # 2 pips offset
)

SCALPING_PRESET = TradingPreset(
    name="scalping",
    description="Short timeframes, quick entries/exits, high frequency",
    risk_per_trade_pct=0.2,  # 0.2% per trade (lower per trade)
    max_daily_drawdown_pct=1.0,  # 1% daily DD
    max_total_drawdown_pct=5.0,  # 5% total DD
    max_consecutive_losses=3,  # Max 3 consecutive losses
    max_trades_per_session=10,  # Max 10 trades per session
    min_rr_ratio=1.5,  # Minimum 1.5:1 RR
    target_rr_ratio=2.0,  # Target 2:1 RR
    sl_atr_multiplier=0.5,  # Very tight SL (0.5x ATR)
    tp_first_target_r=0.5,  # First TP at 0.5R
    partial_close_pct=0.7,  # Close 70% at TP1
    breakeven_trigger_r=0.5,  # BE at 0.5R
    breakeven_offset_pips=1.0  # 1 pip offset
)

GOLD_CONSERVATIVE_PRESET = TradingPreset(
    name="gold_conservative",
    description="XAU/USD specific conservative preset",
    risk_per_trade_pct=0.3,  # 0.3% per trade
    max_daily_drawdown_pct=2.0,  # 2% daily DD
    max_total_drawdown_pct=10.0,  # 10% total DD
    max_consecutive_losses=2,  # Max 2 consecutive losses
    max_trades_per_session=1,  # Max 1 trade per session
    min_rr_ratio=2.0,  # Minimum 2:1 RR
    target_rr_ratio=3.0,  # Target 3:1 RR
    sl_atr_multiplier=2.5,  # Very wide SL for gold (2.5x ATR)
    tp_first_target_r=1.5,  # First TP at 1.5R
    partial_close_pct=0.3,  # Close 30% at TP1
    breakeven_trigger_r=1.5,  # BE at 1.5R
    breakeven_offset_pips=20.0  # 20 pips offset (gold specific)
)

# ============================================================
# PRESET MAPPING
# ============================================================

PRESETS = {
    "conservative": CONSERVATIVE_PRESET,
    "moderate": MODERATE_PRESET,
    "aggressive": AGGRESSIVE_PRESET,
    "scalping": SCALPING_PRESET,
    "gold_conservative": GOLD_CONSERVATIVE_PRESET,
}

INSTRUMENT_PRESETS = {
    "EURUSD": {
        "conservative": CONSERVATIVE_PRESET,
        "moderate": MODERATE_PRESET,
        "aggressive": AGGRESSIVE_PRESET,
        "scalping": SCALPING_PRESET,
    },
    "GBPUSD": {
        "conservative": CONSERVATIVE_PRESET,
        "moderate": MODERATE_PRESET,
        "aggressive": AGGRESSIVE_PRESET,
        "scalping": SCALPING_PRESET,
    },
    "XAUUSD": {
        "conservative": GOLD_CONSERVATIVE_PRESET,
        "moderate": MODERATE_PRESET,  # Use moderate for gold
        "gold_conservative": GOLD_CONSERVATIVE_PRESET,
    },
}


# ============================================================
# FUNCTIONS
# ============================================================

def get_preset(preset_name: str) -> TradingPreset:
    """Get a preset by name."""
    preset = PRESETS.get(preset_name)
    if not preset:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(PRESETS.keys())}")
    return preset


def get_instrument_preset(instrument: str, preset_name: str) -> TradingPreset:
    """Get a preset for a specific instrument."""
    instrument_presets = INSTRUMENT_PRESETS.get(instrument)
    if not instrument_presets:
        raise ValueError(f"Unknown instrument: {instrument}. Available: {list(INSTRUMENT_PRESETS.keys())}")
    
    preset = instrument_presets.get(preset_name)
    if not preset:
        raise ValueError(f"Preset '{preset_name}' not available for {instrument}. Available: {list(instrument_presets.keys())}")
    
    return preset


def apply_preset_to_config(preset: TradingPreset, config_dict: dict) -> dict:
    """
    Apply a preset to an instrument configuration dictionary.
    
    Args:
        preset: Trading preset to apply
        config_dict: Base instrument configuration as dict
    
    Returns:
        New configuration dict with preset applied
    """
    config_dict.update({
        "risk_per_trade_pct": preset.risk_per_trade_pct,
        "max_daily_drawdown_pct": preset.max_daily_drawdown_pct,
        "max_total_drawdown_pct": preset.max_total_drawdown_pct,
        "max_consecutive_losses": preset.max_consecutive_losses,
        "max_trades_per_session": preset.max_trades_per_session,
        "min_rr_ratio": preset.min_rr_ratio,
        "target_rr_ratio": preset.target_rr_ratio,
        "sl_atr_multiplier": preset.sl_atr_multiplier,
        "tp_first_target_r": preset.tp_first_target_r,
        "partial_close_pct": preset.partial_close_pct,
        "breakeven_trigger_r": preset.breakeven_trigger_r,
        "breakeven_offset_pips": preset.breakeven_offset_pips,
    })
    
    return config_dict


def list_presets() -> dict:
    """List all available presets with descriptions."""
    return {
        name: preset.description
        for name, preset in PRESETS.items()
    }


def list_instrument_presets(instrument: str) -> dict:
    """List available presets for a specific instrument."""
    instrument_presets = INSTRUMENT_PRESETS.get(instrument, {})
    return {
        name: preset.description
        for name, preset in instrument_presets.items()
    }
