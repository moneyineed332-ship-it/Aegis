"""Risk management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Literal

from .. import config, consensus, execution, market_data, risk, storage
from ..deps import require_admin_token

router = APIRouter(prefix="/api/v1", tags=["risk"])


class TrailingStopRequest(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{2,10}$")
    side: Literal["buy", "sell"]
    entry_price: float = Field(gt=0)
    trail_pct: float = Field(gt=0, le=0.5, default=0.05)


class ConsensusVoteRequest(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    strategy_name: str = Field(min_length=1, max_length=100)
    signal: Literal["buy", "sell", "wait"]
    confidence: float = Field(ge=0, le=1)
    weight: float = Field(gt=0, le=10, default=1.0)
    reason: str = Field(max_length=500, default="")


@router.get("/risk/var")
def get_var(symbol: str = "EURUSD") -> dict:
    # Use ICT symbol if provided, otherwise default to EURUSD
    target_symbol = symbol if symbol in ["EURUSD", "GBPUSD", "XAUUSD"] else "EURUSD"
    candles = storage.list_ohlcv_candles(target_symbol, "1h", limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data for risk computation.")
    capital = config.ICT_PAPER_CAPITAL
    return risk.historical_risk(candles, capital)


@router.get("/risk/stress-test")
def get_stress_test(symbol: str = "EURUSD") -> dict:
    # Use ICT symbol if provided, otherwise default to EURUSD
    target_symbol = symbol if symbol in ["EURUSD", "GBPUSD", "XAUUSD"] else "EURUSD"
    candles = storage.list_ohlcv_candles(target_symbol, "1h", limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data for stress test.")
    capital = config.ICT_PAPER_CAPITAL
    return risk.stress_test(candles, capital)


@router.get("/risk/correlation")
def get_correlation() -> dict:
    assets: dict[str, list[float]] = {}
    for sym in config.SYMBOLS:
        candles = storage.list_ohlcv_candles(sym, "1h", limit=200)
        if candles:
            assets[sym] = [c["close"] for c in candles]
    if not assets:
        raise HTTPException(status_code=404, detail="No data for correlation matrix.")
    return risk.correlation_matrix(assets)


@router.get("/risk/concentration")
def get_concentration() -> dict:
    positions = storage.list_positions()
    prices = {}
    try:
        snapshots = market_data.fetch_spot_prices()
        prices = {s["symbol"]: s["price"] for s in snapshots}
    except Exception:
        pass
    return risk.concentration_risk(positions, prices)


@router.get("/risk/circuit-breaker")
def get_circuit_breaker() -> dict:
    return risk.get_circuit_breaker_status()


@router.post("/risk/circuit-breaker/reset")
def reset_circuit_breaker(_admin: None = Depends(require_admin_token)) -> dict:
    risk.reset_circuit_breaker()
    return {"status": "reset", "message": "Circuit breaker has been reset"}


@router.post("/trailing-stop")
def create_trailing_stop(req: TrailingStopRequest, _admin: None = Depends(require_admin_token)) -> dict:
    return execution.create_trailing_stop(req.symbol, req.side, req.entry_price, req.trail_pct)


@router.get("/trailing-stops")
def list_trailing_stops() -> list[dict]:
    return execution.get_all_trailing_stops()


@router.delete("/trailing-stop/{symbol}/{side}")
def delete_trailing_stop(symbol: str, side: str, _admin: None = Depends(require_admin_token)) -> dict:
    return execution.remove_trailing_stop(symbol, side)


@router.get("/trailing-stops/check")
def check_trailing_stops_endpoint() -> list[dict]:
    prices = {}
    try:
        snapshots = market_data.fetch_spot_prices()
        prices = {s["symbol"]: s["price"] for s in snapshots}
    except Exception:
        pass
    return execution.check_trailing_stops(prices)


@router.get("/consensus")
def compute_consensus() -> dict:
    return consensus.compute_consensus()


@router.post("/consensus/vote")
def add_consensus_vote(req: ConsensusVoteRequest, _admin: None = Depends(require_admin_token)) -> dict:
    return consensus.add_strategy_vote(req.strategy_id, req.strategy_name, req.signal, req.confidence, req.weight, req.reason)


@router.post("/consensus/clear")
def clear_consensus_votes(_admin: None = Depends(require_admin_token)) -> dict:
    consensus.clear_votes()
    return {"status": "cleared"}


@router.post("/position-sizing")
def compute_position_sizing(
    capital: float = Query(gt=0),
    entry_price: float = Query(gt=0),
    stop_loss: float = Query(gt=0),
    risk_pct: float = Query(default=0.02, gt=0, le=1),
    _admin: None = Depends(require_admin_token),
) -> dict:
    return execution.calculate_position_size(capital, risk_pct, entry_price, stop_loss)
