"""AI analyst routes."""

from typing import Literal

from fastapi import APIRouter, HTTPException

from .. import ai_analyst, config, features, market_data, regime, risk, storage

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/status")
def get_ai_status() -> dict:
    return ai_analyst.get_status()


@router.post("/analyze-market")
def analyze_market(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "EURUSD", interval: Literal["5m", "15m", "1h", "4h"] = "1h") -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    feat = features.latest_features(candles)
    regime_data = regime.classify(feat)
    capital = config.ICT_PAPER_CAPITAL
    risk_data = risk.historical_risk(candles, capital)
    return ai_analyst.analyze_market(candles, feat, risk_data, regime_data)


@router.post("/assess-risk")
def assess_risk(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "EURUSD", interval: Literal["5m", "15m", "1h", "4h"] = "1h") -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    capital = config.ICT_PAPER_CAPITAL
    risk_data = risk.historical_risk(candles, capital)
    positions = storage.list_positions()
    return ai_analyst.assess_risk(candles, risk_data, positions)


@router.post("/review-strategies")
def review_strategies() -> dict:
    backtests = storage.list_recent_backtests(limit=20)
    return ai_analyst.review_strategies(backtests, {})


@router.post("/analyze-sentiment")
def analyze_sentiment() -> dict:
    fear_greed = storage.list_fear_greed()
    funding = storage.list_funding_rates()
    return ai_analyst.analyze_sentiment({}, fear_greed, funding)
