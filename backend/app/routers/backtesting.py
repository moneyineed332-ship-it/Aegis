"""Backtesting routes."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import backtesting, config, market_data
from ..deps import require_admin_token


class SmcIctBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD"
    interval: Literal["1h", "4h"] = "1h"
    initial_capital: float = Field(default=config.ICT_PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)
    min_score: int = Field(default=40, ge=0, le=100)
    atr_stop_multiplier: float = Field(default=2.0, gt=0)
    lookback: int = Field(default=50, ge=20, le=200)


class MultiTimeframeBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD"
    interval: Literal["1h", "4h"] = "1h"
    initial_capital: float = Field(default=config.ICT_PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)
    min_confluence: int = Field(default=40, ge=0, le=100)
    atr_stop_multiplier: float = Field(default=2.5, gt=0)


class MultiScaleCrossoverBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD"
    interval: Literal["1h", "4h"] = "1h"
    initial_capital: float = Field(default=config.ICT_PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)
    min_score: int = Field(default=40, ge=0, le=100)
    atr_stop_multiplier: float = Field(default=2.5, gt=0)

router = APIRouter(
    prefix="/api/v1/backtests",
    tags=["backtesting"],
    dependencies=[Depends(require_admin_token)],
)


class SmaBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    fast_period: int = Field(default=20, ge=2, le=100)
    slow_period: int = Field(default=50, ge=3, le=300)
    initial_capital: float = Field(default=config.ICT_PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)


class DonchianBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    breakout_period: int = Field(default=20, ge=5, le=100)
    exit_period: int = Field(default=10, ge=3, le=50)
    initial_capital: float = Field(default=config.ICT_PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)



@router.post("/sma-crossover")
def run_sma_backtest(req: SmaBacktestRequest) -> dict:
    candles = market_data.fetch_ohlcv(req.symbol, req.interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        return backtesting.run_sma_crossover(candles, req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/donchian-breakout")
def run_donchian_backtest(req: DonchianBacktestRequest) -> dict:
    candles = market_data.fetch_ohlcv(req.symbol, req.interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        return backtesting.run_donchian_breakout(candles, req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))



@router.post("/sma-crossover/walk-forward")
def run_sma_walk_forward(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD") -> dict:
    candles = market_data.fetch_ohlcv(symbol, "1h", limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        base_params = {"initial_capital": config.PAPER_CAPITAL, "allocation": 0.95, "fee_bps": 10, "slippage_bps": 5, "interval": "1h", "train_candles": 350, "test_candles": 150}
        candidates = [(10, 30), (20, 50), (30, 100)]
        return backtesting.run_walk_forward(candles, base_params, candidates)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/donchian-breakout/walk-forward")
def run_donchian_walk_forward(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD") -> dict:
    candles = market_data.fetch_ohlcv(symbol, "1h", limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        base_params = {"initial_capital": config.PAPER_CAPITAL, "allocation": 0.95, "fee_bps": 10, "slippage_bps": 5, "interval": "1h", "train_candles": 350, "test_candles": 150}
        candidates = [(20, 10), (40, 20), (55, 20)]
        return backtesting.run_donchian_walk_forward(candles, base_params, candidates)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))



@router.post("/smc-ict")
def run_smc_ict_backtest(req: SmcIctBacktestRequest) -> dict:
    candles = market_data.fetch_ohlcv(req.symbol, req.interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        return backtesting.run_smc_ict(candles, req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/multi-timeframe")
def run_multi_timeframe_backtest(req: MultiTimeframeBacktestRequest) -> dict:
    candles = market_data.fetch_ohlcv(req.symbol, req.interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        return backtesting.run_multi_timeframe(candles, req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/multi-scale-crossover")
def run_multi_scale_crossover_backtest(req: MultiScaleCrossoverBacktestRequest) -> dict:
    candles = market_data.fetch_ohlcv(req.symbol, req.interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        return backtesting.run_multi_scale_crossover(candles, req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/smc-ict/walk-forward")
def run_smc_ict_walk_forward(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD") -> dict:
    candles = market_data.fetch_ohlcv(symbol, "1h", limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        base_params = {"initial_capital": config.PAPER_CAPITAL, "allocation": 0.95, "fee_bps": 10, "slippage_bps": 5, "interval": "1h", "train_candles": 350, "test_candles": 150}
        candidates = [
            {"min_score": 30, "atr_stop_multiplier": 1.5, "lookback": 40},
            {"min_score": 40, "atr_stop_multiplier": 2.0, "lookback": 50},
            {"min_score": 50, "atr_stop_multiplier": 2.5, "lookback": 60},
        ]
        return backtesting.run_smc_ict_walk_forward(candles, base_params, candidates)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/multi-timeframe/walk-forward")
def run_multi_timeframe_walk_forward(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD"] = "EURUSD") -> dict:
    candles = market_data.fetch_ohlcv(symbol, "1h", limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        base_params = {"initial_capital": config.PAPER_CAPITAL, "allocation": 0.95, "fee_bps": 10, "slippage_bps": 5, "interval": "1h", "train_candles": 350, "test_candles": 150}
        candidates = [
            {"min_confluence": 30, "atr_stop_multiplier": 2.0},
            {"min_confluence": 40, "atr_stop_multiplier": 2.5},
            {"min_confluence": 50, "atr_stop_multiplier": 3.0},
        ]
        return backtesting.run_multi_timeframe_walk_forward(candles, base_params, candidates)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

