"""Gemini AI Analyst — provides AI reasoning for all AEGIS modules."""

import json
import os
import threading
import urllib.request
import urllib.error
from typing import Any

GEMINI_API_KEYS: list[str] = []
for key_env in [
    "GEMINI_API_KEY_1",
    "GEMINI_API_KEY_2",
    "GEMINI_API_KEY_3",
    "GEMINI_API_KEY_4",
]:
    k = os.getenv(key_env, "")
    if k:
        GEMINI_API_KEYS.append(k)

if not GEMINI_API_KEYS:
    single = os.getenv("GEMINI_API_KEY", "")
    if single:
        GEMINI_API_KEYS.append(single)

_key_index = 0
_key_lock = threading.Lock()


def _next_key() -> str:
    global _key_index
    if not GEMINI_API_KEYS:
        return ""
    with _key_lock:
        key = GEMINI_API_KEYS[_key_index % len(GEMINI_API_KEYS)]
        _key_index += 1
    return key


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_INSTRUCTION = """Tu es un analyste quantitatif senior spécialisé en trading crypto.
Tu Analyses les données de marché fournies et fournis:
1. Évaluation du régime de marché (tendance/horizontal/volatil)
2. Évaluation du risque (échelle 1-10 avec justification)
3. Recommandation de stratégie (niveaux d'entrée/sortie, taille de position)
4. Niveaux clés de support/résistance
5. Évaluation du sentiment basée sur les indicateurs disponibles

Réponds TOUJOURS en JSON structuré. Sois conservateur avec les recommandations.
Inclus les niveaux de confiance. Réponds en français."""

TOOL_SCHEMAS = {
    "market_analysis": {
        "name": "market_analysis",
        "description": "Analyse complète du marché crypto",
        "parameters": {
            "type": "object",
            "properties": {
                "regime": {"type": "string", "description": "bull_trend, bear_trend, range, high_volatility, low_volatility, capitulation, euphoria"},
                "risk_score": {"type": "integer", "description": "1-10"},
                "risk_justification": {"type": "string"},
                "strategy": {"type": "string", "description": "Recommandation de stratégie"},
                "entry_level": {"type": "number"},
                "exit_level": {"type": "number"},
                "stop_loss": {"type": "number"},
                "position_size_pct": {"type": "number", "description": "Pourcentage du capital"},
                "support_levels": {"type": "array", "items": {"type": "number"}},
                "resistance_levels": {"type": "array", "items": {"type": "number"}},
                "sentiment": {"type": "string", "description": "bearish, neutral, bullish"},
                "confidence": {"type": "number", "description": "0-1"},
                "reasoning": {"type": "string"},
            },
            "required": ["regime", "risk_score", "strategy", "confidence", "reasoning"],
        },
    },
    "risk_assessment": {
        "name": "risk_assessment",
        "description": "Évaluation détaillée des risques",
        "parameters": {
            "type": "object",
            "properties": {
                "overall_risk": {"type": "integer", "description": "1-10"},
                "var_analysis": {"type": "string"},
                "drawdown_risk": {"type": "string"},
                "correlation_risk": {"type": "string"},
                "liquidity_risk": {"type": "string"},
                "recommendation": {"type": "string"},
                "max_position_pct": {"type": "number"},
                "hedging_suggestion": {"type": "string"},
            },
            "required": ["overall_risk", "recommendation"],
        },
    },
    "strategy_review": {
        "name": "strategy_review",
        "description": "Revue et optimisation des stratégies",
        "parameters": {
            "type": "object",
            "properties": {
                "best_strategy": {"type": "string"},
                "improvements": {"type": "array", "items": {"type": "string"}},
                "parameter_adjustments": {"type": "object"},
                "expected_impact": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["best_strategy", "confidence"],
        },
    },
    "sentiment_analysis": {
        "name": "sentiment_analysis",
        "description": "Analyse de sentiment basée sur les données de marché",
        "parameters": {
            "type": "object",
            "properties": {
                "overall_sentiment": {"type": "string", "description": "very_bearish, bearish, neutral, bullish, very_bullish"},
                "fear_greed_interpretation": {"type": "string"},
                "volume_analysis": {"type": "string"},
                "momentum_analysis": {"type": "string"},
                "onchain_analysis": {"type": "string"},
                "news_impact": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["overall_sentiment", "confidence"],
        },
    },
}


def _call_gemini(prompt: str, tool_name: str | None = None) -> dict[str, Any]:
    api_key = _next_key()
    if not api_key:
        return {"error": "No Gemini API key configured", "ai_available": False}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"

    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
        },
    }

    if tool_name and tool_name in TOOL_SCHEMAS:
        payload["tools"] = [{"functionDeclarations": [TOOL_SCHEMAS[tool_name]]}]

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        candidates = result.get("candidates", [])
        if not candidates:
            return {"error": "No response from Gemini", "raw": result}

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        for part in parts:
            if "functionCall" in part:
                return part["functionCall"].get("args", {})
            if "text" in part:
                try:
                    return json.loads(part["text"])
                except json.JSONDecodeError:
                    return {"text_response": part["text"]}

        return {"error": "Empty response"}

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"Gemini API error {e.code}", "detail": body[:500]}
    except Exception as e:
        return {"error": str(e)}


def analyze_market(candles: list[dict], features: dict, risk_data: dict, regime: dict) -> dict:
    prompt = f"""Analyse ce marché crypto:

CANDLES RÉCENTES (20 dernières):
{json.dumps(candles[-20:], indent=2)}

INDICATEURS TECHNIQUES:
{json.dumps(features, indent=2)}

MÉTRIQUES DE RISQUE:
{json.dumps(risk_data, indent=2)}

RÉGIME DÉTECTÉ:
{json.dumps(regime, indent=2)}

Fournis ton analyse complète en JSON."""
    return _call_gemini(prompt, "market_analysis")


def assess_risk(candles: list[dict], risk_data: dict, positions: list[dict]) -> dict:
    prompt = f"""Évalue les risques de ce portefeuille:

POSITIONS ACTUELLES:
{json.dumps(positions, indent=2)}

MÉTRIQUES DE RISQUE:
{json.dumps(risk_data, indent=2)}

HISTORIQUE (10 dernières candles):
{json.dumps(candles[-10:], indent=2)}

Fournis une évaluation détaillée des risques en JSON."""
    return _call_gemini(prompt, "risk_assessment")


def review_strategies(backtests: list[dict], optimizer_results: dict) -> dict:
    prompt = f"""Analyse les résultats de backtest et optimisation:

BACKTESTS:
{json.dumps(backtests[:10], indent=2)}

RÉSULTATS OPTIMIZER:
{json.dumps(optimizer_results, indent=2)}

Recommande la meilleure stratégie et les améliorations possibles en JSON."""
    return _call_gemini(prompt, "strategy_review")


def analyze_sentiment(market_data: dict, fear_greed: dict, funding_rates: dict) -> dict:
    prompt = f"""Analyse le sentiment du marché crypto:

DONNÉES DE MARCHÉ:
{json.dumps(market_data, indent=2)}

FEAR & GREED INDEX:
{json.dumps(fear_greed, indent=2)}

FUNDING RATES:
{json.dumps(funding_rates, indent=2)}

Évalue le sentiment global du marché en JSON."""
    return _call_gemini(prompt, "sentiment_analysis")


def get_status() -> dict:
    return {
        "available": len(GEMINI_API_KEYS) > 0,
        "api_keys_count": len(GEMINI_API_KEYS),
        "model": GEMINI_MODEL,
        "provider": "Google Gemini",
    }
