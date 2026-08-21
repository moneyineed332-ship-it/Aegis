"""SMC/ICT Strategy — Smart Money Concepts + Inner Circle Trader.

Combines:
  - Market structure (BOS / CHoCH) for trend direction
  - Order Blocks for entry zones
  - Fair Value Gaps for price targets
  - Liquidity sweeps for confirmation
  - Premium/Discount zones for timing

Signal generation:
  1. Confirm market structure direction
  2. Wait for price to reach an order block or FVG
  3. Confirm with liquidity sweep
  4. Enter in discount/premium zone
"""

import logging
from .indicators import (
    market_structure, order_blocks, fair_value_gaps,
    liquidity_zones, premium_discount, smc_confluence,
    rsi_single, atr_single,
)

logger = logging.getLogger(__name__)


def analyze(candles: list[dict], lookback: int = 20) -> dict:
    """Full SMC/ICT analysis on a single timeframe.

    Returns signal with direction, entry zone, stop loss, take profit.
    """
    if len(candles) < 50:
        return {"signal": "neutral", "score": 0, "reason": "insufficient_data"}

    confluence = smc_confluence(candles, lookback)
    ms = confluence["market_structure"]
    ob = confluence["order_blocks"]
    fvg = confluence["fair_value_gaps"]
    liq = confluence["liquidity"]
    pd = confluence["premium_discount"]
    current_price = candles[-1]["close"]
    atr = atr_single(candles, 14)
    rsi = rsi_single([c["close"] for c in candles], 14)

    signal = "neutral"
    entry_zone = None
    stop_loss = None
    take_profit = None
    confidence = 0
    reasons: list[str] = list(confluence["reasons"])

    # ── LONG setup ──
    if confluence["direction"] == "bullish" and confluence["score"] >= 40:
        signal = "buy"
        confidence = min(confluence["score"], 95)

        # Entry zone: bullish OB or bullish FVG
        if ob["bullish_ob"]:
            entry_zone = {
                "type": "bullish_ob",
                "low": ob["bullish_ob"]["price_low"],
                "high": ob["bullish_ob"]["price_high"],
            }
        elif fvg["bullish_fvg"]:
            entry_zone = {
                "type": "bullish_fvg",
                "low": fvg["bullish_fvg"]["price_low"],
                "high": fvg["bullish_fvg"]["price_high"],
            }

        if entry_zone:
            stop_loss = entry_zone["low"] - atr * 1.5
            take_profit = current_price + atr * 3

        # Boost confidence for liquidity sweep
        if liq["recent_bull_sweep"]:
            confidence = min(confidence + 10, 95)
            reasons.append("Liquidity sweep confirms entry")

        # Boost for discount zone
        if pd["zone"] == "discount":
            confidence = min(confidence + 5, 95)
            reasons.append("Price in discount zone")

        # Reduce for overbought RSI (but keep minimum to avoid zeroing signal)
        if rsi > 70:
            confidence = max(confidence - 10, 10)
            reasons.append(f"RSI overbought ({rsi:.0f})")

    # ── SHORT setup ──
    elif confluence["direction"] == "bearish" and confluence["score"] >= 40:
        signal = "sell"
        confidence = min(confluence["score"], 95)

        if ob["bearish_ob"]:
            entry_zone = {
                "type": "bearish_ob",
                "low": ob["bearish_ob"]["price_low"],
                "high": ob["bearish_ob"]["price_high"],
            }
        elif fvg["bearish_fvg"]:
            entry_zone = {
                "type": "bearish_fvg",
                "low": fvg["bearish_fvg"]["price_low"],
                "high": fvg["bearish_fvg"]["price_high"],
            }

        if entry_zone:
            stop_loss = entry_zone["high"] + atr * 1.5
            take_profit = current_price - atr * 3

        if liq["recent_bear_sweep"]:
            confidence = min(confidence + 10, 95)
            reasons.append("Liquidity sweep confirms entry")

        if pd["zone"] == "premium":
            confidence = min(confidence + 5, 95)
            reasons.append("Price in premium zone")

        if rsi < 30:
            confidence = max(confidence - 10, 10)
            reasons.append(f"RSI oversold ({rsi:.0f})")

    return {
        "signal": signal,
        "score": confidence,
        "entry_zone": entry_zone,
        "stop_loss": round(stop_loss, 6) if stop_loss else None,
        "take_profit": round(take_profit, 6) if take_profit else None,
        "market_structure": ms["trend"],
        "last_bos": ms["last_bos"],
        "last_choch": ms["last_choch"],
        "order_blocks": ob,
        "fair_value_gaps": fvg,
        "liquidity": {
            "bsl_count": liq["bsl_count"],
            "ssl_count": liq["ssl_count"],
            "recent_bull_sweep": liq["recent_bull_sweep"] is not None,
            "recent_bear_sweep": liq["recent_bear_sweep"] is not None,
        },
        "premium_discount": pd,
        "reasons": reasons,
    }


def generate_signal(candles: list[dict]) -> dict:
    """Generate a trade signal for the engine.

    Returns standardized signal format:
        action: "buy" | "sell" | "wait"
        strategy: "smc_ict"
        confidence: 0-100
        entry / stop_loss / take_profit
    """
    analysis = analyze(candles)

    action = "wait"
    if analysis["signal"] == "buy" and analysis["score"] >= 40:
        action = "buy"
    elif analysis["signal"] == "sell" and analysis["score"] >= 40:
        action = "sell"

    return {
        "action": action,
        "strategy": "smc_ict",
        "confidence": analysis["score"],
        "entry_zone": analysis["entry_zone"],
        "stop_loss": analysis["stop_loss"],
        "take_profit": analysis["take_profit"],
        "market_structure": analysis["market_structure"],
        "last_bos": analysis["last_bos"],
        "last_choch": analysis["last_choch"],
        "reasons": analysis["reasons"],
    }
