"""Rule-based market-regime classifier; designed for auditability, not prediction.

Enhanced with ADX, Stochastic RSI, VWAP, and hysteresis.
"""

import threading

def reset_hysteresis():
    """Reset hysteresis state for testing."""
    global _prev_regime, _prev_confidence
    with _regime_lock:
        _prev_regime = None
        _prev_confidence = 0.0


PROBABILITY_FLOOR = 0.05

_prev_regime: str | None = None
_prev_confidence: float = 0.0
_regime_lock = threading.Lock()

REGIME_LABELS = {
    "bull_trend": "Tendance Haussière",
    "bear_trend": "Tendance Baissière",
    "range": "Consolidation",
    "high_volatility": "Haute Volatilité",
    "low_volatility": "Basse Volatilité",
    "capitulation": "Capitulation",
    "euphoria": "Euphorie",
}


def classify(features: dict, hysteresis: float = 0.15) -> dict:
    """Classify the current market regime from explainable features.

    Uses ADX for trend strength, RSI/Stochastic RSI for momentum,
    Bollinger width for volatility, and hysteresis to prevent flip-flopping.

    Priority order (most specific first):
      1. capitulation — sharp drop with high volatility + oversold RSI
      2. euphoria — extreme rally with high volatility + overbought RSI
      3. high_volatility — elevated volatility without extreme momentum
      4. low_volatility — calm market, tight range, low ADX
      5. bull_trend — upward trend with ADX confirmation
      6. bear_trend — downward trend with ADX confirmation
      7. range — fallback / consolidation
    """
    global _prev_regime, _prev_confidence

    # Use all available features
    trend_strength = features.get("sma_ratio", features.get("sma_20", 0) / max(features.get("sma_50", 1), 1) - 1)
    volatility = features.get("volatility_20", 0)
    momentum = features.get("momentum_20", 0)
    rsi = features.get("rsi_14", 50)
    adx = features.get("adx", 25)
    bollinger_width = features.get("bollinger_width", 0)
    stoch_rsi_k = features.get("stoch_rsi_k", 50)
    williams_r = features.get("williams_r", -50)
    zscore = features.get("zscore_20", 0)
    atr_ratio = features.get("atr_14", 0) / features.get("close", 1) if features.get("close", 0) > 0 else 0

    regime = "range"
    confidence = 0.5

    # --- Capitulation: crash + oversold + high vol ---
    if momentum < -0.08 and (volatility > 0.025 or atr_ratio > 0.03) and rsi < 35:
        regime = "capitulation"
        confidence = min(0.95, 0.65 + abs(momentum) * 1.5 + volatility * 3 + (35 - rsi) / 100)

    # --- Euphoria: parabolic rally + overbought + high vol ---
    elif momentum > 0.12 and (volatility > 0.025 or atr_ratio > 0.03) and rsi > 70:
        regime = "euphoria"
        confidence = min(0.95, 0.65 + abs(momentum) * 1.5 + volatility * 3 + (rsi - 70) / 100)

    # --- High Volatility: wide bands + elevated ATR but no extreme momentum ---
    elif (volatility > 0.025 or bollinger_width > 0.06 or atr_ratio > 0.025) and abs(momentum) < 0.08:
        regime = "high_volatility"
        confidence = min(0.9, 0.55 + volatility * 8 + bollinger_width * 2)

    # --- Low Volatility: tight range + low ATR + low ADX ---
    elif volatility < 0.01 and abs(trend_strength) < 0.005 and adx < 20 and bollinger_width < 0.03:
        regime = "low_volatility"
        confidence = min(0.9, 0.55 + (0.01 - volatility) * 30 + (20 - adx) / 100)

    # --- Bull Trend: ADX confirms + positive momentum + RSI > 50 ---
    elif trend_strength >= 0.008 and momentum > 0 and adx > 20 and rsi > 45:
        regime = "bull_trend"
        confidence = min(0.9, 0.5 + abs(trend_strength) * 8 + adx / 200 + (rsi - 45) / 200)

    # --- Bear Trend: ADX confirms + negative momentum + RSI < 50 ---
    elif trend_strength <= -0.008 and momentum < 0 and adx > 20 and rsi < 55:
        regime = "bear_trend"
        confidence = min(0.9, 0.5 + abs(trend_strength) * 8 + adx / 200 + (55 - rsi) / 200)

    # --- Range: fallback ---
    else:
        regime = "range"
        confidence = min(0.7, 0.4 + (1 - abs(trend_strength) * 8) * 0.3)

    # --- Hysteresis: prevent flip-flopping at boundaries ---
    with _regime_lock:
        if _prev_regime and _prev_regime != regime:
            if _prev_confidence > confidence + hysteresis:
                regime = _prev_regime
                confidence = _prev_confidence

        _prev_regime = regime
        _prev_confidence = confidence

    confidence = round(confidence, 4)

    # Build probability distribution
    all_regimes = ("bull_trend", "bear_trend", "range", "high_volatility", "low_volatility", "capitulation", "euphoria")
    probabilities = {name: PROBABILITY_FLOOR for name in all_regimes}
    probabilities[regime] = confidence
    total = sum(probabilities.values())
    probabilities = {k: round(v / total, 4) for k, v in probabilities.items()}

    # Choppy filter (Phase 1): weak trend + low ADX + flat range → avoid false
    # Donchian breakouts. Used by the advisor as an entry gate.
    is_choppy = bool(adx < 20 and regime == "range")

    return {
        "regime": regime,
        "confidence": confidence,
        "is_choppy": is_choppy,
        "probabilities": probabilities,
        "label": REGIME_LABELS.get(regime, regime),
        "indicators": {
            "adx": round(adx, 2),
            "rsi": round(rsi, 2),
            "stoch_rsi_k": round(stoch_rsi_k, 2),
            "bollinger_width": round(bollinger_width, 4),
            "zscore": round(zscore, 2),
            "momentum": round(momentum, 4),
            "volatility": round(volatility, 4),
        },
    }
