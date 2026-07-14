"""Transparent strategy selection from the current market regime."""


def recommend(analysis: dict, risk_summary: dict) -> dict:
    regime = analysis["regime"]["regime"]
    exposure_ratio = risk_summary["exposure"] / risk_summary["capital"]
    if risk_summary["conditional_value_at_risk"] > risk_summary["capital"] * 0.05:
        return {"action": "wait", "strategy": None, "confidence": 0.9, "reason": "Historical CVaR exceeds the 5% research threshold."}
    if exposure_ratio >= 0.2:
        return {"action": "wait", "strategy": None, "confidence": 0.9, "reason": "Current exposure reached the paper-risk threshold."}
    if regime == "bull_trend":
        return {"action": "research", "strategy": "donchian_breakout_long_flat", "confidence": analysis["regime"]["confidence"], "reason": "Bull trend detected; evaluate trend-following only through walk-forward."}
    if regime == "range":
        return {"action": "research", "strategy": "mean_reversion_bollinger", "confidence": analysis["regime"]["confidence"], "reason": "Range regime; evaluate mean-reversion through walk-forward."}
    if regime == "low_volatility":
        return {"action": "research", "strategy": "grid_adaptive", "confidence": analysis["regime"]["confidence"], "reason": "Low volatility regime; grid trading may capture range-bound moves."}
    if regime == "capitulation":
        return {"action": "wait", "strategy": None, "confidence": analysis["regime"]["confidence"], "reason": "Capitulation detected; wait for stabilization before any entry."}
    if regime == "euphoria":
        return {"action": "wait", "strategy": None, "confidence": analysis["regime"]["confidence"], "reason": "Euphoria detected; avoid chasing extended moves."}
    return {"action": "wait", "strategy": None, "confidence": analysis["regime"]["confidence"], "reason": f"{regime} regime is excluded from current long-only strategies."}
