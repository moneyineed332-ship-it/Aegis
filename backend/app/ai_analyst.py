"""AI Analyst — OpenCode Zen primary, OpenRouter fallback, provides AI reasoning for all AEGIS modules."""

import json
import threading
from typing import Any

import httpx

from . import config

OPENCODE_API_KEY = config.OPENCODE_API_KEY
OPENROUTER_API_KEY = config.OPENROUTER_API_KEY

_call_lock = threading.Semaphore(3)  # Allow up to 3 concurrent AI calls

# Shared httpx client for AI calls
_http_client: httpx.Client | None = None


def _get_http_client() -> httpx.Client:
    """Get or create a shared httpx client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(timeout=config.AI_TIMEOUT)
    return _http_client

SYSTEM_INSTRUCTION = """Tu es un analyste quantitatif senior specialise en trading crypto avec expertise dans TOUS les styles de trading:

**SCALPING (ultra-court terme, 1m-5m):**
- Strategie: EMA(3)/EMA(8) crossover rapide, confirmation RSI(3) + Stochastic(5,3,3)
- Regles: Entrer sur croisement EMA rapide + RSI < 30 (oversold) ou > 70 (overbought)
- Stop: ATR(14) x 1.5, Take Profit: ATR(14) x 2.25 (ratio TP/SL = 1.5)
- Max trades/jour: 20, allocation par trade: 5% du capital

**SWING TRADING (moyen terme, 4h-1d):**
- Strategie: MACD(12,26,9) histogramme croise + Fibonacci 0.382 retracement
- Regles: Entrer sur pullback vers Fibo 38.2% avec MACD bull cross
- Stop: ATR(14) x 3.0, Trail: ATR(14) x 2.5
- Allocation: 15% du capital, positions tenues 2-14 jours

**INTRADAY (sessions, 15m-1h):**
- Strategie: VWAP direction + RSI(14) momentum + EMA(9/21) trend
- Regles: Long au-dessus VWAP si EMA9>EMA21 et RSI>55, Short en dessous VWAP
- Stop: ATR(14) x 1.5, Fermer toutes les positions avant fin de session
- Allocation: 10% du capital, allow shorts: oui

**TREND FOLLOWING (long terme):**
- SMA(50)/SMA(200) golden/death cross, Donchian breakout
- Allocation: 20% du capital, trailing stop ATR(20) x 3.0

**MEAN REVERSION (range-bound):**
- Bollinger Bands(20,2) z-score, retour a la moyenne
- Stop: 2x ATR(14), TP: 1x ATR(14)

**GRID TRADING (range-bound, accumulation):**
- Grille adaptative ATR, niveaux = ATR(14) x 0.5
- Allocation: 30% du capital, max 20 ordres

Tu dois repondre UNIQUEMENT en JSON valide avec les champs demandes. Pas de texte avant ou apres le JSON."""


def _call_opencode(prompt: str) -> dict[str, Any]:
    """Call OpenCode Zen API."""
    if not OPENCODE_API_KEY:
        return {"error": "No OpenCode API key configured", "ai_available": False}

    url = f"{config.OPENCODE_BASE_URL}/chat/completions"

    payload: dict[str, Any] = {
        "model": config.OPENCODE_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
        "temperature": config.OPENCODE_TEMPERATURE,
        "max_tokens": config.OPENCODE_MAX_TOKENS,
    }

    client = _get_http_client()
    try:
        response = client.post(url, json=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENCODE_API_KEY}",
            "User-Agent": "AEGIS-AI/1.0",
        })
        response.raise_for_status()
        result = response.json()

        choices = result.get("choices", [])
        if not choices:
            return {"error": "No response from OpenCode", "raw": result}

        content = choices[0].get("message", {}).get("content")
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"text_response": content}

        return {"error": "Empty OpenCode response"}

    except httpx.HTTPStatusError as e:
        body = e.response.text[:500]
        if e.response.status_code == 429:
            return {"error": "OpenCode quota exceeded", "ai_available": False, "detail": body[:300]}
        if e.response.status_code == 403:
            return {"error": "OpenCode rate limited", "ai_available": False, "detail": body[:300]}
        return {"error": f"OpenCode API error {e.response.status_code}", "detail": body[:500]}
    except Exception as e:
        return {"error": str(e)}


def _call_openrouter(prompt: str) -> dict[str, Any]:
    """Call OpenRouter API (OpenAI-compatible) as fallback."""
    if not OPENROUTER_API_KEY:
        return {"error": "No OpenRouter API key configured", "ai_available": False}

    url = f"{config.OPENROUTER_BASE_URL}/chat/completions"

    payload: dict[str, Any] = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
        "temperature": config.OPENROUTER_TEMPERATURE,
        "max_tokens": config.OPENROUTER_MAX_TOKENS,
    }

    client = _get_http_client()
    try:
        response = client.post(url, json=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://aegis-ai.local",
            "X-Title": "AEGIS AI Quant",
        })
        response.raise_for_status()
        result = response.json()

        choices = result.get("choices", [])
        if not choices:
            return {"error": "No response from OpenRouter", "raw": result}

        content = choices[0].get("message", {}).get("content")
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"text_response": content}

        return {"error": "Empty OpenRouter response"}

    except httpx.HTTPStatusError as e:
        body = e.response.text[:500]
        if e.response.status_code == 429:
            return {"error": "OpenRouter quota exceeded", "ai_available": False, "detail": body[:300]}
        return {"error": f"OpenRouter API error {e.response.status_code}", "detail": body[:500]}
    except Exception as e:
        return {"error": str(e)}


def _call_ai(prompt: str) -> dict[str, Any]:
    """Try OpenCode first, then OpenRouter as fallback."""
    with _call_lock:
        result = _call_opencode(prompt)
        if result.get("ai_available") is False and OPENROUTER_API_KEY:
            result = _call_openrouter(prompt)
        return result


def analyze_market(candles: list[dict], features: dict, risk_data: dict, regime: dict) -> dict:
    prompt = f"""Analyse ce marche crypto et recommande le meilleur style de trading:

STYLES DISPONIBLES:
- SCALPING: Court terme (1m-5m), EMA(3/8) + RSI(3) + Stoch(5,3,3), stops serrés ATRx1.5
- SWING: Moyen terme (4h-1d), MACD(12,26,9) + Fibonacci 38.2% + ATR trailing
- INTRADAY: Sessions (15m-1h), VWAP + RSI(14) + EMA(9/21), fermeture en fin de session
- TREND FOLLOWING: SMA/Donchian, long terme
- MEAN REVERSION: Bollinger, range-bound
- GRID: Range-bound, accumulation

CANDLES RECENTES (20 dernieres):
{json.dumps(candles[-20:], indent=2)}

INDICATEURS TECHNIQUES:
{json.dumps(features, indent=2)}

METRIQUES DE RISQUE:
{json.dumps(risk_data, indent=2)}

REGIME DETECTE:
{json.dumps(regime, indent=2)}

Fournis ton analyse complete en JSON avec le style de trading recommande."""
    return _call_ai(prompt)


def assess_risk(candles: list[dict], risk_data: dict, positions: list[dict]) -> dict:
    prompt = f"""Evalue les risques de ce portefeuille:

POSITIONS ACTUELLES:
{json.dumps(positions, indent=2)}

METRIQUES DE RISQUE:
{json.dumps(risk_data, indent=2)}

HISTORIQUE (10 dernieres candles):
{json.dumps(candles[-10:], indent=2)}

Fournis une evaluation detaillee des risques en JSON."""
    return _call_ai(prompt)


def review_strategies(backtests: list[dict], optimizer_results: dict) -> dict:
    prompt = f"""Analyse les resultats de backtest et optimisation des strategies crypto:

STRATEGIES DISPONIBLES:
- SMA Crossover: Trend following, bon en marche trending
- Donchian Breakout: Breakout, capture gros mouvements
- Mean Reversion Bollinger: Range-bound, mean reversion
- Grid Adaptatif: Range-bound, accumulation progressive
- SCALPING EMA/RSI/Stoch: Ultra-court terme, haute frequence, stops serres
- SWING MACD/Fibonacci: Moyen terme, Fibonacci retracement, trailing stops
- INTRADAY VWAP/RSI: Sessions, VWAP direction, fermeture daily

BACKTESTS:
{json.dumps(backtests[:10], indent=2)}

RESULTATS OPTIMIZER:
{json.dumps(optimizer_results, indent=2)}

Recommande le meilleur style de trading pour les conditions actuelles et les ameliorations possibles en JSON."""
    return _call_ai(prompt)


def analyze_sentiment(market_data: dict, fear_greed: dict, funding_rates: dict) -> dict:
    prompt = f"""Analyse le sentiment du marche crypto:

DONNEES DE MARCHE:
{json.dumps(market_data, indent=2)}

FEAR & GREED INDEX:
{json.dumps(fear_greed, indent=2)}

FUNDING RATES:
{json.dumps(funding_rates, indent=2)}

Evalue le sentiment global du marche en JSON."""
    return _call_ai(prompt)


def get_status() -> dict:
    opencode_ok = bool(OPENCODE_API_KEY)
    openrouter_ok = bool(OPENROUTER_API_KEY)
    return {
        "available": opencode_ok or openrouter_ok,
        "providers": {
            "opencode": {"available": opencode_ok, "model": config.OPENCODE_MODEL if opencode_ok else None},
            "openrouter": {"available": openrouter_ok, "model": config.OPENROUTER_MODEL if openrouter_ok else None},
        },
        "provider": "OpenCode Zen + OpenRouter" if openrouter_ok else "OpenCode Zen",
        "note": "Fallback OpenRouter si OpenCode rate-limite" if openrouter_ok else "OpenCode uniquement",
    }
