"""Rule-based market-regime classifier; designed for auditability, not prediction."""

PROBABILITY_FLOOR = 0.05


def classify(features: dict) -> dict:
    """Classify the current market regime from explainable features.

    Priority order (most specific first):
      1. capitulation — sharp drop with high volatility
      2. euphoria — extreme rally with high volatility
      3. high_volatility — elevated volatility without extreme momentum
      4. low_volatility — calm market, tight range
      5. bull_trend — upward trend
      6. bear_trend — downward trend
      7. range — fallback / consolidation
    """
    trend_strength = features["sma_20"] / features["sma_50"] - 1
    volatility = features["volatility_20"]
    momentum = features["momentum_20"]

    regime = "range"
    confidence = 0.5

    if momentum < -0.10 and volatility > 0.04:
        regime = "capitulation"
        confidence = min(0.9, 0.6 + abs(momentum) * 2 + volatility * 5)
    elif momentum > 0.15 and volatility > 0.03:
        regime = "euphoria"
        confidence = min(0.9, 0.6 + abs(momentum) * 2 + volatility * 5)
    elif volatility >= 0.03:
        regime = "high_volatility"
        confidence = min(0.9, 0.5 + volatility * 10)
    elif volatility < 0.008 and abs(trend_strength) < 0.005:
        regime = "low_volatility"
        confidence = min(0.9, 0.5 + (0.008 - volatility) * 50)
    elif trend_strength >= 0.01 and momentum > 0:
        regime = "bull_trend"
        confidence = min(0.9, 0.5 + abs(trend_strength) * 10 + volatility * 5)
    elif trend_strength <= -0.01 and momentum < 0:
        regime = "bear_trend"
        confidence = min(0.9, 0.5 + abs(trend_strength) * 10 + volatility * 5)
    else:
        regime = "range"
        confidence = min(0.7, 0.4 + (1 - abs(trend_strength) * 10) * 0.3)

    confidence = round(confidence, 4)

    all_regimes = ("bull_trend", "bear_trend", "range", "high_volatility", "low_volatility", "capitulation", "euphoria")
    probabilities = {name: PROBABILITY_FLOOR for name in all_regimes}
    probabilities[regime] = confidence
    # Normalize so probabilities sum to ~1
    total = sum(probabilities.values())
    probabilities = {k: round(v / total, 4) for k, v in probabilities.items()}

    return {"regime": regime, "confidence": confidence, "probabilities": probabilities}
