"""Backtesting routes."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import backtesting, config, grid, intraday, market_data, mean_reversion, scalping, swing
from ..deps import require_admin_token


class SmcIctBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "EURUSD"
    interval: Literal["1h", "4h"] = "1h"
    initial_capital: float = Field(default=config.ICT_PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)
    min_score: int = Field(default=40, ge=0, le=100)
    atr_stop_multiplier: float = Field(default=2.0, gt=0)
    lookback: int = Field(default=50, ge=20, le=200)


class MultiTimeframeBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "EURUSD"
    interval: Literal["1h", "4h"] = "1h"
    initial_capital: float = Field(default=config.ICT_PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)
    min_confluence: int = Field(default=40, ge=0, le=100)
    atr_stop_multiplier: float = Field(default=2.5, gt=0)


class MultiScaleCrossoverBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "EURUSD"
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
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "EURUSD"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    fast_period: int = Field(default=20, ge=2, le=100)
    slow_period: int = Field(default=50, ge=3, le=300)
    initial_capital: float = Field(default=config.ICT_PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)


class DonchianBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "EURUSD"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    breakout_period: int = Field(default=20, ge=5, le=100)
    exit_period: int = Field(default=10, ge=3, le=50)
    initial_capital: float = Field(default=config.ICT_PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)


class MeanReversionBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "EURUSD"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    period: int = Field(default=20, ge=5, le=100)
    entry_z_score: float = Field(default=2.0, gt=0)
    exit_z_score: float = Field(default=0.5, gt=0)
    initial_capital: float = Field(default=config.ICT_PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)


class GridBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    grid_count: int = Field(default=10, ge=3, le=50)
    grid_spread_pct: float = Field(default=0.05, gt=0, le=0.5)
    initial_capital: float = Field(default=config.PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)


class ScalpingBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT"
    interval: Literal["1m", "5m", "15m"] = "5m"
    initial_capital: float = Field(default=config.PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.2, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)


class SwingBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT"
    interval: Literal["4h", "1d"] = "4h"
    initial_capital: float = Field(default=config.PAPER_CAPITAL, gt=0)
    allocation: float = Field(default=0.3, gt=0, le=1)
    fee_bps: float = Field(default=config.DEFAULT_FEE_BPS, ge=0)
    slippage_bps: float = Field(default=config.DEFAULT_SLIPPAGE_BPS, ge=0)


class IntradayBacktestRequest(BaseModel):
    symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT"
    interval: Literal["15m", "30m", "1h"] = "15m"
    initial_capital: float = Field(default=config.PAPER_CAPITAL, gt=0)
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


@router.post("/mean-reversion")
def run_mean_reversion_backtest(req: MeanReversionBacktestRequest) -> dict:
    candles = market_data.fetch_ohlcv(req.symbol, req.interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        return mean_reversion.run_mean_reversion(candles, req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/grid")
def run_grid_backtest(req: GridBacktestRequest) -> dict:
    candles = market_data.fetch_ohlcv(req.symbol, req.interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        return grid.run_grid(candles, req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/scalping")
def run_scalping_backtest(req: ScalpingBacktestRequest) -> dict:
    candles = market_data.fetch_ohlcv(req.symbol, req.interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        return scalping.run_scalping(candles, req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/swing")
def run_swing_backtest(req: SwingBacktestRequest) -> dict:
    candles = market_data.fetch_ohlcv(req.symbol, req.interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        return swing.run_swing(candles, req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/intraday")
def run_intraday_backtest(req: IntradayBacktestRequest) -> dict:
    candles = market_data.fetch_ohlcv(req.symbol, req.interval, limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        return intraday.run_intraday(candles, req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/sma-crossover/walk-forward")
def run_sma_walk_forward(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
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
def run_donchian_walk_forward(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
    candles = market_data.fetch_ohlcv(symbol, "1h", limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        base_params = {"initial_capital": config.PAPER_CAPITAL, "allocation": 0.95, "fee_bps": 10, "slippage_bps": 5, "interval": "1h", "train_candles": 350, "test_candles": 150}
        candidates = [(20, 10), (40, 20), (55, 20)]
        return backtesting.run_donchian_walk_forward(candles, base_params, candidates)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/mean-reversion/walk-forward")
def run_mean_reversion_walk_forward(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
    candles = market_data.fetch_ohlcv(symbol, "1h", limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        base_params = {"initial_capital": config.PAPER_CAPITAL, "allocation": 0.95, "fee_bps": 10, "slippage_bps": 5, "interval": "1h", "train_candles": 350, "test_candles": 150}
        candidates = [(0.5, 1.5), (1.0, 2.0), (1.5, 2.5)]
        return mean_reversion.run_mean_reversion_walk_forward(candles, base_params, candidates)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/grid/walk-forward")
def run_grid_walk_forward(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
    candles = market_data.fetch_ohlcv(symbol, "1h", limit=500)
    if not candles:
        raise HTTPException(status_code=404, detail="No candle data available.")
    try:
        base_params = {"initial_capital": config.PAPER_CAPITAL, "allocation": 0.95, "fee_bps": 10, "slippage_bps": 5, "interval": "1h", "train_candles": 350, "test_candles": 150}
        candidates = [(5, 0.02), (10, 0.05), (15, 0.08)]
        return grid.run_grid_walk_forward(candles, base_params, candidates)
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
def run_smc_ict_walk_forward(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
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
def run_multi_timeframe_walk_forward(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
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
