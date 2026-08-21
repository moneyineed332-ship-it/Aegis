"""Adaptive strategy selection from the current market regime.

Uses learning data (strategy scores per regime) when available,
falls back to hardcoded rules when no performance data exists.

Enhanced with SMC/ICT and Multi-Timeframe Confluence strategies.

Focused mode (Phase 1): when aegis is reduced to a single trade type,
every regime maps to the configured focused strategy (Donchian Breakout).
"""

from . import config, learning, strategy_registry


# Regime → default strategy mapping (fallback when no learning data)
DEFAULT_STRATEGY_MAP = {
    "bull_trend": "smc_ict",
    "bear_trend": "smc_ict",
    "range": "mean_reversion_bollinger",
    "high_volatility": "multi_timeframe_confluence",
    "low_volatility": "grid_adaptive",
    "capitulation": "multi_timeframe_confluence",
    "euphoria": "smc_ict",
}

# Strategy priority order (lower = preferred when multiple fit)
STRATEGY_PRIORITY = {
    "smc_ict": 1,
    "multi_timeframe_confluence": 2,
    "multi_scale_crossover": 3,
    "donchian_breakout_long_flat": 4,
    "mean_reversion_bollinger": 5,
    "grid_adaptive": 6,
    "sma_crossover_long_flat": 7,
    "scalping_ema_rsi_stoch": 8,
    "swing_macd_fibonacci": 9,
    "intraday_vwap_rsi": 10,
}


def recommend(analysis: dict, risk_summary: dict) -> dict:
    """Generate a trading recommendation based on regime and learned performance.

    Priority:
    1. Risk checks (always apply regardless of learning)
    2. Adaptive ranking from learning module (if data available)
    3. Default regime mapping (fallback)
    """
    regime = analysis["regime"]["regime"]
    confidence = analysis["regime"]["confidence"]
    exposure_ratio = risk_summary["exposure"] / risk_summary["capital"]

    # --- Hard risk gates (always apply) ---
    if risk_summary["conditional_value_at_risk"] > risk_summary["capital"] * 0.05:
        return {
            "action": "wait",
            "strategy": None,
            "confidence": 0.9,
            "reason": "Historical CVaR exceeds the 5% research threshold.",
        }
    if exposure_ratio >= 0.2:
        return {
            "action": "wait",
            "strategy": None,
            "confidence": 0.9,
            "reason": "Current exposure reached the paper-risk threshold.",
        }

    # --- Regime-specific gates ---
    if regime == "capitulation":
        return {
            "action": "wait",
            "strategy": None,
            "confidence": confidence,
            "reason": "Capitulation detected; wait for stabilization before any entry.",
        }
    if regime == "euphoria":
        return {
            "action": "wait",
            "strategy": None,
            "confidence": confidence,
            "reason": "Euphoria detected; avoid chasing extended moves.",
        }
    # Choppy market gate (Phase 1): Donchian breakouts underperform in ranges.
    if config.FOCUSED_MODE and analysis["regime"].get("is_choppy"):
        return {
            "action": "wait",
            "strategy": config.FOCUSED_STRATEGY,
            "confidence": confidence,
            "reason": "Choppy market (low ADX, range regime) — no new breakout trades.",
        }

    # --- Adaptive strategy selection ---
    strategy = _select_strategy(regime)

    if strategy:
        # In focused mode the strategy is always Donchian (or disabled → wait)
        if config.FOCUSED_MODE and not strategy_registry.is_active(strategy):
            return {
                "action": "wait",
                "strategy": strategy,
                "confidence": confidence,
                "reason": (
                    f"{regime} regime: strategy {strategy} is disabled in focused "
                    f"mode ({config.FOCUSED_STRATEGY})."
                ),
            }
        return {
            "action": "research",
            "strategy": strategy,
            "confidence": confidence,
            "reason": _build_reason(regime, strategy),
        }

    return {
        "action": "wait",
        "strategy": None,
        "confidence": confidence,
        "reason": f"{regime} regime: no suitable strategy identified.",
    }


def _select_strategy(regime: str) -> str | None:
    """Select best strategy for regime using learning data if available.

    In focused mode, the configured single strategy is always returned.
    """
    if config.FOCUSED_MODE:
        return config.FOCUSED_STRATEGY

    # Try adaptive ranking first
    try:
        ranking = learning.rank_strategies_for_regime(regime)
        if ranking:
            best = ranking[0]
            if best["regime_score"] > 30 and best["regime_trades"] >= 3:
                return best["strategy_id"]
            if best["regime_score"] > 50:
                return best["strategy_id"]
    except Exception:
        pass

    # Fall back to default mapping
    return DEFAULT_STRATEGY_MAP.get(regime)


def _build_reason(regime: str, strategy: str) -> str:
    """Build a human-readable reason for the recommendation."""
    try:
        stats = learning.get_strategy_stats(strategy)
        if stats.get("total_trades", 0) >= 5:
            return (
                f"{regime} regime → {strategy} "
                f"(score: {stats.get('score', 0):.0f}, "
                f"win rate: {stats.get('win_rate', 0)*100:.0f}%, "
                f"PF: {stats.get('profit_factor', 0):.1f})"
            )
    except Exception:
        pass

    strategy_names = {
        "smc_ict": "SMC/ICT Smart Money Concepts",
        "multi_timeframe_confluence": "Multi-Timeframe Confluence",
        "multi_scale_crossover": "Multi-Scale Crossover",
        "donchian_breakout_long_flat": "Donchian Breakout",
        "mean_reversion_bollinger": "Mean Reversion Bollinger",
        "grid_adaptive": "Grid Adaptatif",
        "sma_crossover_long_flat": "SMA Crossover",
        "scalping_ema_rsi_stoch": "Scalping EMA/RSI/Stoch",
        "swing_macd_fibonacci": "Swing MACD/Fibonacci",
        "intraday_vwap_rsi": "Intraday VWAP/RSI",
    }
    name = strategy_names.get(strategy, strategy)
    return f"{regime} regime → {name} selected for optimal performance"
