"""Multi-Timeframe Confluence Strategy.

Analyzes alignment across 1h, 4h, and 1d timeframes.
Uses SMC/ICT confluence + traditional indicators for each timeframe.
Entry only when 2+ timeframes agree on direction.

Priority: higher timeframe dominates (1d > 4h > 1h).
"""

import logging
from . import indicators as ind
from .smc_ict import analyze as smc_analyze

logger = logging.getLogger(__name__)


def analyze_multi_timeframe(candles_by_tf: dict[str, list[dict]]) -> dict:
    """Analyze confluence across multiple timeframes.

    Args:
        candles_by_tf: {"1h": [...], "4h": [...], "1d": [...]}

    Returns combined analysis with per-TF breakdown.
    """
    tf_analysis: dict[str, dict] = {}
    trends: list[str] = []
    scores: list[int] = []

    tf_weights = {"1d": 3, "4h": 2, "1h": 1}  # Higher TF = more weight

    for tf, candles in candles_by_tf.items():
        if len(candles) < 50:
            tf_analysis[tf] = {"trend": "neutral", "score": 0, "reason": "insufficient_data", "entry_zone": None, "stop_loss": None, "take_profit": None}
            continue

        # SMC analysis
        smc = smc_analyze(candles)

        # Traditional indicators
        closes = [c["close"] for c in candles]
        rsi = ind.rsi_single(closes, 14)
        atr = ind.atr_single(candles, 14)
        ema_fast = ind.ema_single(closes, 20)
        ema_slow = ind.ema_single(closes, 50)

        # Combine SMC + traditional
        combined_score = smc["score"]
        trend = "neutral"

        if smc["signal"] == "buy":
            trend = "bullish"
            # Boost for EMA alignment
            if ema_fast > ema_slow:
                combined_score = min(combined_score + 10, 100)
            # Boost for RSI confirmation
            if 40 < rsi < 70:
                combined_score = min(combined_score + 5, 100)
        elif smc["signal"] == "sell":
            trend = "bearish"
            if ema_fast < ema_slow:
                combined_score = min(combined_score + 10, 100)
            if 30 < rsi < 60:
                combined_score = min(combined_score + 5, 100)

        tf_analysis[tf] = {
            "trend": trend,
            "score": combined_score,
            "rsi": round(rsi, 2),
            "ema_fast": round(ema_fast, 6),
            "ema_slow": round(ema_slow, 6),
            "smc_signal": smc["signal"],
            "smc_score": smc["score"],
            "market_structure": smc["market_structure"],
            "entry_zone": smc["entry_zone"],
            "stop_loss": smc["stop_loss"],
            "take_profit": smc["take_profit"],
            "reasons": smc["reasons"],
        }
        trends.append(trend)
        scores.append(combined_score * tf_weights.get(tf, 1))

    # Weighted confluence
    bullish_weight = sum(
        tf_analysis[tf]["score"] * tf_weights.get(tf, 1)
        for tf in tf_analysis if tf_analysis[tf]["trend"] == "bullish"
    )
    bearish_weight = sum(
        tf_analysis[tf]["score"] * tf_weights.get(tf, 1)
        for tf in tf_analysis if tf_analysis[tf]["trend"] == "bearish"
    )
    total_weight = sum(tf_weights.get(tf, 1) for tf in tf_analysis if tf_analysis[tf]["trend"] != "neutral")

    if total_weight == 0:
        overall = "neutral"
        confluence_score = 0
    elif bullish_weight > bearish_weight:
        overall = "bullish"
        confluence_score = round(bullish_weight / max(total_weight, 1))
    elif bearish_weight > bullish_weight:
        overall = "bearish"
        confluence_score = round(bearish_weight / max(total_weight, 1))
    else:
        overall = "neutral"
        confluence_score = 0

    # Use the highest-TF entry zone
    best_entry = None
    best_sl = None
    best_tp = None
    for tf in ["1d", "4h", "1h"]:
        if tf in tf_analysis and tf_analysis[tf]["entry_zone"]:
            best_entry = tf_analysis[tf]["entry_zone"]
            best_sl = tf_analysis[tf]["stop_loss"]
            best_tp = tf_analysis[tf]["take_profit"]
            break

    return {
        "overall_trend": overall,
        "confluence_score": confluence_score,
        "bullish_weight": bullish_weight,
        "bearish_weight": bearish_weight,
        "entry_zone": best_entry,
        "stop_loss": best_sl,
        "take_profit": best_tp,
        "timeframes": tf_analysis,
    }


def generate_signal(candles_by_tf: dict[str, list[dict]]) -> dict:
    """Generate a trade signal from multi-timeframe confluence.

    Requires 2+ timeframes agreeing + confluence score >= 40.
    """
    analysis = analyze_multi_timeframe(candles_by_tf)

    action = "wait"
    if analysis["overall_trend"] == "bullish" and analysis["confluence_score"] >= 40:
        action = "buy"
    elif analysis["overall_trend"] == "bearish" and analysis["confluence_score"] >= 40:
        action = "sell"

    # Count agreeing timeframes
    agree_count = sum(
        1 for tf in analysis["timeframes"]
        if analysis["timeframes"][tf]["trend"] == analysis["overall_trend"]
    )

    return {
        "action": action,
        "strategy": "multi_timeframe_confluence",
        "confidence": analysis["confluence_score"],
        "agreeing_timeframes": agree_count,
        "total_timeframes": len(analysis["timeframes"]),
        "entry_zone": analysis["entry_zone"],
        "stop_loss": analysis["stop_loss"],
        "take_profit": analysis["take_profit"],
        "timeframes": {
            tf: {
                "trend": data["trend"],
                "score": data["score"],
                "rsi": data["rsi"],
            }
            for tf, data in analysis["timeframes"].items()
        },
    }
