"""AI analyst routes."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from .. import ai_analyst, config, features, market_data, regime, risk, storage
from ..deps import require_admin_token

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/status", dependencies=[Depends(require_admin_token)])
def get_ai_status() -> dict:
    return ai_analyst.get_status()


@router.post("/analyze-market")
def analyze_market(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD", interval: Literal["5m", "15m", "1h", "4h"] = "1h", _admin: None = Depends(require_admin_token)) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    feat = features.latest_features(candles)
    regime_data = regime.classify(feat)
    capital = config.ICT_PAPER_CAPITAL
    risk_data = risk.historical_risk(candles, capital)
    return ai_analyst.analyze_market(candles, feat, risk_data, regime_data)


@router.post("/assess-risk")
def assess_risk(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD", interval: Literal["5m", "15m", "1h", "4h"] = "1h", _admin: None = Depends(require_admin_token)) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    capital = config.ICT_PAPER_CAPITAL
    risk_data = risk.historical_risk(candles, capital)
    positions = storage.list_positions()
    return ai_analyst.assess_risk(candles, risk_data, positions)



