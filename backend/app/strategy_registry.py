"""Strategy registry.
Varying by config: Active/Disabled
"""

from . import config

STRATEGIES = [
    {"id": "sma_crossover_long_flat", "name": "SMA Crossover", "type": "trend_following", "status": "confirmation"},
    {"id": "donchian_breakout_long_flat", "name": "Donchian Breakout", "type": "trend_following", "status": "active"},
    # mean_reversion_bollinger, grid_adaptive, scalping_ema_rsi_stoch,
    # swing_macd_fibonacci and intraday_vwap_rsi went out with the crypto
    # engine. Each was backed by a module that only ever ran on 24/7 crypto
    # markets: no session close, no swap, so a grid or a scalping loop had
    # nothing to hold it to a Forex book.
    {"id": "smc_ict", "name": "SMC/ICT Smart Money", "type": "smc_ict", "status": "disabled"},
    {"id": "multi_timeframe_confluence", "name": "Multi-TF Confluence", "type": "multi_timeframe", "status": "disabled"},
    {"id": "multi_scale_crossover", "name": "Multi-Scale Crossover", "type": "trend_following", "status": "disabled"},
]

# Keep unresolved references
_FOCUSED_STRATEGY = config.FOCUSED_STRATEGY


def list_strategies() -> list[dict]:
    return STRATEGIES


def get_strategy(strategy_id: str) -> dict | None:
    for s in STRATEGIES:
        if s["id"] == strategy_id:
            return s
    return None


def is_active(strategy_id: str) -> bool:
    """Return True if the strategy should be traded in the current config.

    In focused mode, only the configured single strategy is tradable.
    SMA Crossover stays enabled as a confirmation layer for Donchian.
    """
    if not config.FOCUSED_MODE:
        return get_strategy(strategy_id) is not None
    if strategy_id == config.FOCUSED_STRATEGY:
        return True
    if strategy_id == "sma_crossover_long_flat":
        return True  # confirmation layer
    return False