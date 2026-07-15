"""AEGIS MVP API: paper trading only; no exchange credentials are accepted."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import advisor, ai_analyst, backtesting, backtesting_advanced, binance_testnet, coach, data_quality, deployment, execution, features, free_apis, grid, journal, lab, market_data, mean_reversion, memory, ml_regime, multi_asset, optimizer, regime, risk, settings, storage, strategy_registry, supervisor

app = FastAPI(title="AEGIS AI Quant MVP", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.API_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

INITIAL_CAPITAL = settings.PAPER_CAPITAL
MAX_ORDER_NOTIONAL = 500.0
MAX_TOTAL_EXPOSURE = 2_000.0


class PaperOrder(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]+/[A-Z0-9]+$")
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0, le=10)
    reference_price: float = Field(gt=0)


class Position(BaseModel):
    symbol: str
    quantity: float
    average_price: float


class SmaBacktestRequest(BaseModel):
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    fast_period: int = Field(default=20, ge=2, le=100)
    slow_period: int = Field(default=50, ge=3, le=300)
    initial_capital: float = Field(default=10_000, gt=0, le=1_000_000)
    allocation: float = Field(default=0.95, gt=0, le=1)
    fee_bps: float = Field(default=10, ge=0, le=100)
    slippage_bps: float = Field(default=5, ge=0, le=100)


class WalkForwardRequest(BaseModel):
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    train_candles: int = Field(default=500, ge=100, le=5_000)
    test_candles: int = Field(default=200, ge=100, le=2_000)
    initial_capital: float = Field(default=10_000, gt=0, le=1_000_000)
    allocation: float = Field(default=0.95, gt=0, le=1)
    fee_bps: float = Field(default=10, ge=0, le=100)
    slippage_bps: float = Field(default=5, ge=0, le=100)
    min_volatility: float = Field(default=0.01, ge=0, le=0.2)


class MeanReversionRequest(BaseModel):
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    entry_z_score: float = Field(default=-2.0, ge=-3.0, le=-1.0)
    exit_z_score: float = Field(default=0.0, ge=-0.5, le=0.5)
    period: int = Field(default=20, ge=10, le=50)
    initial_capital: float = Field(default=10_000, gt=0, le=1_000_000)
    allocation: float = Field(default=0.95, gt=0, le=1)
    fee_bps: float = Field(default=10, ge=0, le=100)
    slippage_bps: float = Field(default=5, ge=0, le=100)


class MeanReversionWalkForwardRequest(BaseModel):
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    train_candles: int = Field(default=500, ge=100, le=5_000)
    test_candles: int = Field(default=200, ge=100, le=2_000)
    initial_capital: float = Field(default=10_000, gt=0, le=1_000_000)
    allocation: float = Field(default=0.95, gt=0, le=1)
    fee_bps: float = Field(default=10, ge=0, le=100)
    slippage_bps: float = Field(default=5, ge=0, le=100)
    period: int = Field(default=20, ge=10, le=50)


class GridRequest(BaseModel):
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    grid_count: int = Field(default=10, ge=5, le=30)
    grid_spread_pct: float = Field(default=0.02, ge=0.005, le=0.1)
    initial_capital: float = Field(default=10_000, gt=0, le=1_000_000)
    allocation: float = Field(default=0.95, gt=0, le=1)
    fee_bps: float = Field(default=10, ge=0, le=100)
    slippage_bps: float = Field(default=5, ge=0, le=100)


class GridWalkForwardRequest(BaseModel):
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT"
    interval: Literal["5m", "15m", "1h", "4h"] = "1h"
    train_candles: int = Field(default=500, ge=100, le=5_000)
    test_candles: int = Field(default=200, ge=100, le=2_000)
    initial_capital: float = Field(default=10_000, gt=0, le=1_000_000)
    allocation: float = Field(default=0.95, gt=0, le=1)
    fee_bps: float = Field(default=10, ge=0, le=100)
    slippage_bps: float = Field(default=5, ge=0, le=100)
    grid_count: int = Field(default=10, ge=5, le=30)
    grid_spread_pct: float = Field(default=0.02, ge=0.005, le=0.1)


@app.on_event("startup")
def initialize_storage() -> None:
    storage.initialize()


def current_exposure(positions: list[dict]) -> float:
    return sum(abs(position["quantity"] * position["average_price"]) for position in positions)


def require_admin_token(x_aegis_admin_token: str | None = Header(default=None)) -> None:
    if not settings.ADMIN_TOKEN or x_aegis_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(401, "Administrator token is required.")


@app.get("/health")
def health() -> dict:
    return {**supervisor.status(storage.get_kill_switch()), "timestamp": datetime.now(timezone.utc)}


@app.get("/api/v1/dashboard")
def dashboard() -> dict:
    positions = storage.list_positions()
    candles = storage.list_ohlcv_candles("BTCUSDT", "1h", limit=500)
    quality = data_quality.validate_ohlcv(candles, "1h")
    analysis = None
    risk_metrics = None
    if quality["valid"] and len(candles) >= 50:
        market_features = features.latest_features(candles)
        analysis = {"features": market_features, "regime": regime.classify(market_features)}
        risk_metrics = risk.historical_risk(candles, INITIAL_CAPITAL)

    # Live PnL computation
    recent_orders = storage.list_recent_orders(limit=100)
    exposure = current_exposure(positions)
    equity_curve = storage.compute_equity_curve(INITIAL_CAPITAL, positions, recent_orders)
    current_equity = equity_curve[-1]["equity"] if equity_curve else INITIAL_CAPITAL
    realized_pnl = current_equity - INITIAL_CAPITAL

    # Advanced risk data
    stress_test_data = None
    correlation_data = None
    concentration_data = None
    if quality["valid"] and len(candles) >= 30:
        try:
            btc_position_value = sum(abs(p["quantity"] * p["average_price"]) for p in positions if p["symbol"] == "BTCUSDT")
            stress_test_data = risk.stress_test(candles, INITIAL_CAPITAL, btc_position_value)
        except (ValueError, Exception):
            pass
    # Correlation across all symbols
    try:
        assets = {}
        for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
            sym_candles = storage.list_ohlcv_candles(sym, "1h", limit=200)
            if sym_candles:
                assets[sym] = [c["close"] for c in sym_candles]
        if len(assets) >= 2:
            correlation_data = risk.correlation_matrix(assets)
    except Exception:
        pass
    # Concentration
    snapshots = storage.list_market_snapshots(limit=10)
    prices = {s["symbol"]: s["price"] for s in snapshots}
    concentration_data = risk.concentration_risk(positions, prices)

    return {
        "mode": "paper",
        "capital": INITIAL_CAPITAL,
        "exposure": exposure,
        "max_exposure": MAX_TOTAL_EXPOSURE,
        "current_equity": round(current_equity, 2),
        "realized_pnl": round(realized_pnl, 2),
        "equity_curve": equity_curve,
        "positions": positions,
        "recent_orders": recent_orders,
        "market_snapshots": storage.list_market_snapshots(limit=3),
        "recent_backtests": storage.list_recent_backtests(),
        "recent_decisions": storage.list_recent_decisions(),
        "strategy_registry": strategy_registry.list_strategies(),
        "coach": coach.review(storage.list_recent_backtests(limit=100)),
        "supervisor": supervisor.status(storage.get_kill_switch()),
        "alerts": storage.list_alerts(),
        "data_quality": quality,
        "market_analysis": analysis,
        "risk": risk_metrics,
        "stress_test": stress_test_data,
        "correlation": correlation_data,
        "concentration": concentration_data,
        "fear_greed": storage.list_fear_greed(limit=1),
        "funding_rates": storage.list_funding_rates(limit=3),
        "open_interest": storage.list_open_interest(limit=3),
        "memory": memory.summarize_episodes(storage.list_memory_episodes(limit=200)),
        "journal": journal.analyze_decisions(storage.list_recent_decisions(limit=100), {s["symbol"]: s["price"] for s in storage.list_market_snapshots(limit=10)}),
    }


@app.post("/api/v1/paper-orders", status_code=201)
def create_paper_order(order: PaperOrder) -> dict:
    if storage.get_kill_switch():
        raise HTTPException(423, "Emergency stop is active; paper orders are blocked.")
    notional = order.quantity * order.reference_price
    if notional > MAX_ORDER_NOTIONAL:
        raise HTTPException(422, f"Order exceeds the paper limit of ${MAX_ORDER_NOTIONAL:.0f}.")
    positions = storage.list_positions()
    current = next((position for position in positions if position["symbol"] == order.symbol), None)
    signed_quantity = order.quantity if order.side == "buy" else -order.quantity
    new_quantity = signed_quantity + (current["quantity"] if current else 0)
    new_average_price = order.reference_price if not current or new_quantity == 0 else current["average_price"]
    next_positions = [position for position in positions if position["symbol"] != order.symbol]
    if new_quantity:
        next_positions.append({"symbol": order.symbol, "quantity": new_quantity, "average_price": new_average_price})
    if current_exposure(next_positions) > MAX_TOTAL_EXPOSURE:
        raise HTTPException(422, "Order exceeds the total paper exposure limit.")

    position = None if new_quantity == 0 else {
        "symbol": order.symbol,
        "quantity": new_quantity,
        "average_price": new_average_price,
    }
    return storage.save_order_and_position({
        **order.model_dump(),
        "notional": notional,
    }, position)


@app.get("/api/v1/market-snapshots")
def market_snapshots() -> list[dict]:
    return storage.list_market_snapshots()


@app.post("/api/v1/market-snapshots/refresh", status_code=201)
def refresh_market_snapshots() -> list[dict]:
    try:
        snapshots = market_data.fetch_spot_prices()
    except OSError as error:
        raise HTTPException(502, "Public market-data source is unavailable.") from error
    return storage.save_market_snapshots(snapshots)


@app.get("/api/v1/fear-greed")
def fear_greed() -> list[dict]:
    return storage.list_fear_greed()


@app.post("/api/v1/fear-greed/refresh", status_code=201)
def refresh_fear_greed() -> dict:
    try:
        data = market_data.fetch_fear_greed()
    except (OSError, KeyError) as error:
        raise HTTPException(502, "Fear & Greed source is unavailable.") from error
    return storage.save_fear_greed(data)


@app.get("/api/v1/funding-rates")
def funding_rates(symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> list[dict]:
    return storage.list_funding_rates(symbol)


@app.post("/api/v1/funding-rates/refresh", status_code=201)
def refresh_funding_rates(symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
    try:
        data = market_data.fetch_funding_rates(symbol)
    except OSError as error:
        raise HTTPException(502, "Binance Futures source is unavailable.") from error
    return storage.save_funding_rate(data)


@app.get("/api/v1/open-interest")
def open_interest(symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> list[dict]:
    return storage.list_open_interest(symbol)


@app.post("/api/v1/open-interest/refresh", status_code=201)
def refresh_open_interest(symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
    try:
        data = market_data.fetch_open_interest(symbol)
    except OSError as error:
        raise HTTPException(502, "Binance Futures source is unavailable.") from error
    return storage.save_open_interest(data)


@app.get("/api/v1/ohlcv")
def ohlcv(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
    limit: int = Query(default=200, ge=10, le=500),
) -> list[dict]:
    return storage.list_ohlcv_candles(symbol, interval, limit)


@app.get("/api/v1/data-quality/ohlcv")
def ohlcv_quality(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
) -> dict:
    return data_quality.validate_ohlcv(storage.list_ohlcv_candles(symbol, interval, limit=5_000), interval)


@app.get("/api/v1/risk/summary")
def risk_summary(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=500)
    try:
        metrics = risk.historical_risk(candles, INITIAL_CAPITAL)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {"mode": "paper", "capital": INITIAL_CAPITAL, "exposure": current_exposure(storage.list_positions()), **metrics}


@app.get("/api/v1/risk/stress-test")
def risk_stress_test(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=500)
    positions = storage.list_positions()
    position_value = sum(abs(p["quantity"] * p["average_price"]) for p in positions if p["symbol"] == symbol)
    try:
        return risk.stress_test(candles, INITIAL_CAPITAL, position_value)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/v1/risk/correlation")
def risk_correlation(
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
) -> dict:
    assets = {}
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        candles = storage.list_ohlcv_candles(symbol, interval, limit=200)
        if candles:
            assets[symbol] = [c["close"] for c in candles]
    if len(assets) < 2:
        raise HTTPException(422, "Need at least 2 assets with data for correlation.")
    return risk.correlation_matrix(assets)


@app.get("/api/v1/risk/concentration")
def risk_concentration() -> dict:
    positions = storage.list_positions()
    snapshots = storage.list_market_snapshots(limit=10)
    prices = {s["symbol"]: s["price"] for s in snapshots}
    return risk.concentration_risk(positions, prices)


@app.get("/api/v1/journal/analysis")
def journal_analysis() -> dict:
    decisions = storage.list_recent_decisions(limit=100)
    snapshots = storage.list_market_snapshots(limit=10)
    prices = {s["symbol"]: s["price"] for s in snapshots}
    analyses = journal.analyze_decisions(decisions, prices)
    feedback = journal.feedback_summary(analyses)
    return {**analyses, "feedback": feedback}


@app.get("/api/v1/journal/outcomes")
def journal_outcomes() -> list[dict]:
    decisions = storage.list_recent_decisions(limit=50)
    snapshots = storage.list_market_snapshots(limit=10)
    prices = {s["symbol"]: s["price"] for s in snapshots}
    outcomes = []
    for dec in decisions:
        symbol = dec.get("symbol", "BTCUSDT")
        current_price = prices.get(symbol, 0)
        tracked = journal.track_outcome(dec, current_price)
        outcomes.append({**tracked, "symbol": symbol})
    return outcomes


@app.get("/api/v1/market-analysis")
def market_analysis(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=100)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    try:
        market_features = features.latest_features(candles)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {"symbol": symbol, "interval": interval, "features": market_features, "regime": regime.classify(market_features)}


@app.post("/api/v1/decisions/recommendation", status_code=201)
def recommendation(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=500)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    try:
        market_features = features.latest_features(candles)
        risk_summary = risk.historical_risk(candles, INITIAL_CAPITAL)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    analysis = {"features": market_features, "regime": regime.classify(market_features)}
    decision = advisor.recommend(analysis, {"capital": INITIAL_CAPITAL, "exposure": current_exposure(storage.list_positions()), **risk_summary})
    return storage.save_decision(symbol, interval, {"analysis": analysis, "risk": risk_summary, "recommendation": decision})


@app.get("/api/v1/decisions")
def decisions() -> list[dict]:
    return storage.list_recent_decisions()


@app.get("/api/v1/strategies")
def strategies() -> list[dict]:
    return strategy_registry.list_strategies()


@app.get("/api/v1/coach/review")
def coach_review() -> dict:
    backtests = storage.list_recent_backtests(limit=100)
    review = coach.review(backtests)
    analysis = coach.propose_improvements(review.get("strategy_analysis", []))
    return {**review, "improvement_proposals": analysis}


@app.get("/api/v1/lab/promotions")
def lab_promotions() -> list[dict]:
    return [lab.promotion_decision(backtest) for backtest in storage.list_recent_backtests(limit=100)]


@app.get("/api/v1/memory")
def memory_list(symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
    episodes = storage.list_memory_episodes(symbol, limit=100)
    return {
        "summary": memory.summarize_episodes(episodes),
        "episodes": episodes[:20],
    }


@app.post("/api/v1/memory/remember", status_code=201)
def memory_remember(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    strategy: str = "unknown",
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, "1h", limit=100)
    try:
        market_features = features.latest_features(candles)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    episodes = storage.list_memory_episodes(symbol, limit=200)
    result = memory.remember(market_features, episodes)
    # Save current episode
    storage.save_memory_episode(symbol, strategy, market_features, None, result["current_fingerprint"])
    return result


@app.get("/api/v1/memory/compare")
def memory_compare(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, "1h", limit=100)
    try:
        market_features = features.latest_features(candles)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    episodes = storage.list_memory_episodes(symbol, limit=200)
    return memory.remember(market_features, episodes)


@app.get("/api/v1/supervisor")
def supervisor_status() -> dict:
    return {**supervisor.status(storage.get_kill_switch()), "alerts": storage.list_alerts()}


@app.post("/api/v1/supervisor/emergency-stop")
def emergency_stop(_: str | None = Header(default=None, alias="X-AEGIS-Admin-Token")) -> dict:
    require_admin_token(_)
    storage.set_kill_switch(True, "Emergency stop activated manually.")
    return supervisor.status(True)


@app.post("/api/v1/supervisor/resume")
def resume(_: str | None = Header(default=None, alias="X-AEGIS-Admin-Token")) -> dict:
    require_admin_token(_)
    storage.set_kill_switch(False, "Service resumed manually after emergency stop.")
    return supervisor.status(False)


@app.post("/api/v1/execution/market-order", status_code=201)
def execute_market_order(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    side: Literal["buy", "sell"] = "buy",
    quantity: float = 0.001,
) -> dict:
    if storage.get_kill_switch():
        raise HTTPException(423, "Emergency stop is active.")
    snapshots = storage.list_market_snapshots(limit=1)
    if not snapshots:
        raise HTTPException(422, "No market data available. Refresh prices first.")
    current_price = snapshots[0]["price"]
    result = execution.market_order(symbol, side, quantity, current_price)
    if result["status"] == "filled":
        notional = result["fill_price"] * quantity
        if notional > 500:
            raise HTTPException(422, "Order exceeds paper limit of $500.")
        order_data = {"symbol": symbol, "side": side, "quantity": quantity, "reference_price": result["fill_price"], "notional": notional}
        signed_quantity = quantity if side == "buy" else -quantity
        positions = storage.list_positions()
        current = next((p for p in positions if p["symbol"] == symbol), None)
        new_quantity = signed_quantity + (current["quantity"] if current else 0)
        new_avg = result["fill_price"] if not current or new_quantity == 0 else current["average_price"]
        position = None if new_quantity == 0 else {"symbol": symbol, "quantity": new_quantity, "average_price": new_avg}
        storage.save_order_and_position(order_data, position)
    return result


@app.post("/api/v1/execution/limit-order", status_code=201)
def execute_limit_order(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    side: Literal["buy", "sell"] = "buy",
    quantity: float = 0.001,
    limit_price: float = 0,
) -> dict:
    if limit_price <= 0:
        raise HTTPException(422, "limit_price must be positive.")
    snapshots = storage.list_market_snapshots(limit=1)
    current_price = snapshots[0]["price"] if snapshots else limit_price
    return execution.limit_order(symbol, side, quantity, limit_price, current_price)


@app.post("/api/v1/execution/fractioned-order", status_code=201)
def execute_fractioned_order(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    side: Literal["buy", "sell"] = "buy",
    quantity: float = 0.01,
    chunks: int = 3,
) -> dict:
    if storage.get_kill_switch():
        raise HTTPException(423, "Emergency stop is active.")
    snapshots = storage.list_market_snapshots(limit=1)
    if not snapshots:
        raise HTTPException(422, "No market data available.")
    current_price = snapshots[0]["price"]
    return execution.fractioned_order(symbol, side, quantity, current_price, chunks)


@app.post("/api/v1/execution/estimate-slippage")
def estimate_slippage(order_value: float = 100) -> dict:
    return {"order_value": order_value, "estimated_slippage_bps": execution.estimate_slippage(order_value)}


@app.post("/api/v1/deployment/pipeline", status_code=201)
def create_deployment_pipeline(
    strategy_id: str = "sma_crossover_long_flat",
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
) -> dict:
    return deployment.create_pipeline(strategy_id, symbol, {})


@app.post("/api/v1/deployment/validate-backtest")
def validate_deployment_backtest(
    strategy_id: str = "sma_crossover_long_flat",
    stage: str = "backtest",
) -> dict:
    backtests = storage.list_recent_backtests(limit=10)
    relevant = [b for b in backtests if b["strategy"] == strategy_id]
    if not relevant:
        raise HTTPException(422, f"No backtests found for strategy {strategy_id}")
    latest = relevant[0]
    metrics = latest["metrics"].get("out_of_sample_metrics", latest["metrics"])
    return deployment.validate_backtest(metrics, stage)


@app.post("/api/v1/ohlcv/refresh", status_code=201)
def refresh_ohlcv(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
    limit: int = Query(default=200, ge=10, le=500),
) -> dict:
    try:
        candles = market_data.fetch_ohlcv(symbol, interval, limit)
    except OSError as error:
        raise HTTPException(502, "Public OHLCV source is unavailable.") from error
    return {"stored": storage.save_ohlcv_candles(candles), "symbol": symbol, "interval": interval}


@app.post("/api/v1/ohlcv/refresh-history", status_code=201)
def refresh_ohlcv_history(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
    batches: int = Query(default=4, ge=1, le=20),
) -> dict:
    end_time = None
    stored = 0
    try:
        for _ in range(batches):
            candles = market_data.fetch_ohlcv(symbol, interval, limit=500, end_time=end_time)
            if not candles:
                break
            stored += storage.save_ohlcv_candles(candles)
            end_time = candles[0]["open_time"] - 1
    except OSError as error:
        raise HTTPException(502, "Public OHLCV source is unavailable.") from error
    return {"stored": stored, "symbol": symbol, "interval": interval, "batches": batches}


@app.post("/api/v1/backtests/sma-crossover", status_code=201)
def run_sma_backtest(request: SmaBacktestRequest) -> dict:
    if request.fast_period >= request.slow_period:
        raise HTTPException(422, "fast_period must be lower than slow_period.")
    parameters = request.model_dump()
    candles = storage.list_ohlcv_candles(request.symbol, request.interval, limit=500)
    quality = data_quality.validate_ohlcv(candles, request.interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    try:
        metrics = backtesting.run_sma_crossover(candles, parameters)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return storage.save_backtest("sma_crossover_long_flat", request.symbol, request.interval, parameters, metrics)


@app.post("/api/v1/backtests/sma-crossover/walk-forward", status_code=201)
def run_sma_walk_forward(request: WalkForwardRequest = WalkForwardRequest()) -> dict:
    parameters = request.model_dump()
    candles = storage.list_ohlcv_candles(request.symbol, request.interval, limit=request.train_candles + request.test_candles)
    quality = data_quality.validate_ohlcv(candles, request.interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    try:
        report = backtesting.run_walk_forward(candles, parameters, candidates=[(10, 30), (20, 50), (30, 100)])
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return storage.save_backtest("sma_crossover_walk_forward", request.symbol, request.interval, parameters, report)


@app.post("/api/v1/backtests/donchian-breakout/walk-forward", status_code=201)
def run_donchian_walk_forward(request: WalkForwardRequest = WalkForwardRequest()) -> dict:
    parameters = request.model_dump()
    candles = storage.list_ohlcv_candles(request.symbol, request.interval, limit=request.train_candles + request.test_candles)
    quality = data_quality.validate_ohlcv(candles, request.interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    try:
        report = backtesting.run_donchian_walk_forward(candles, parameters, candidates=[(20, 10), (40, 20), (55, 20)])
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return storage.save_backtest("donchian_breakout_walk_forward", request.symbol, request.interval, parameters, report)


@app.post("/api/v1/backtests/mean-reversion", status_code=201)
def run_mean_reversion_backtest(request: MeanReversionRequest) -> dict:
    parameters = request.model_dump()
    candles = storage.list_ohlcv_candles(request.symbol, request.interval, limit=500)
    quality = data_quality.validate_ohlcv(candles, request.interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    try:
        metrics = mean_reversion.run_mean_reversion(candles, parameters)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return storage.save_backtest("mean_reversion_bollinger", request.symbol, request.interval, parameters, metrics)


@app.post("/api/v1/backtests/mean-reversion/walk-forward", status_code=201)
def run_mean_reversion_walk_forward(request: MeanReversionWalkForwardRequest = MeanReversionWalkForwardRequest()) -> dict:
    parameters = request.model_dump()
    candles = storage.list_ohlcv_candles(request.symbol, request.interval, limit=request.train_candles + request.test_candles)
    quality = data_quality.validate_ohlcv(candles, request.interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    try:
        report = mean_reversion.run_mean_reversion_walk_forward(
            candles, parameters, candidates=[(-1.5, -0.5), (-2.0, 0.0), (-2.5, 0.5)]
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return storage.save_backtest("mean_reversion_walk_forward", request.symbol, request.interval, parameters, report)


@app.post("/api/v1/backtests/grid", status_code=201)
def run_grid_backtest(request: GridRequest) -> dict:
    parameters = request.model_dump()
    candles = storage.list_ohlcv_candles(request.symbol, request.interval, limit=500)
    quality = data_quality.validate_ohlcv(candles, request.interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    try:
        metrics = grid.run_grid(candles, parameters)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return storage.save_backtest("grid_adaptive", request.symbol, request.interval, parameters, metrics)


@app.post("/api/v1/backtests/grid/walk-forward", status_code=201)
def run_grid_walk_forward(request: GridWalkForwardRequest = GridWalkForwardRequest()) -> dict:
    parameters = request.model_dump()
    candles = storage.list_ohlcv_candles(request.symbol, request.interval, limit=request.train_candles + request.test_candles)
    quality = data_quality.validate_ohlcv(candles, request.interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    try:
        report = grid.run_grid_walk_forward(
            candles, parameters, candidates=[(8, 0.01), (10, 0.02), (15, 0.03)]
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return storage.save_backtest("grid_walk_forward", request.symbol, request.interval, parameters, report)


# === Phase 3: Auto-Improvement & Optimization ===

@app.post("/api/v1/optimizer/sma", status_code=200)
def optimize_sma_strategy(symbol: str = "BTCUSDT", interval: str = "1h") -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    result = optimizer.optimize_sma(candles, INITIAL_CAPITAL)
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/optimizer/donchian", status_code=200)
def optimize_donchian_strategy(symbol: str = "BTCUSDT", interval: str = "1h") -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    result = optimizer.optimize_donchian(candles, INITIAL_CAPITAL)
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/optimizer/mean-reversion", status_code=200)
def optimize_mean_reversion_strategy(symbol: str = "BTCUSDT", interval: str = "1h") -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    result = optimizer.optimize_mean_reversion(candles, INITIAL_CAPITAL)
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/optimizer/grid", status_code=200)
def optimize_grid_strategy(symbol: str = "BTCUSDT", interval: str = "1h") -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    result = optimizer.optimize_grid(candles, INITIAL_CAPITAL)
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/optimizer/compare", status_code=200)
def compare_all_strategies(symbol: str = "BTCUSDT", interval: str = "1h") -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    results = {
        "sma_crossover": optimizer.optimize_sma(candles, INITIAL_CAPITAL),
        "donchian_breakout": optimizer.optimize_donchian(candles, INITIAL_CAPITAL),
        "mean_reversion": optimizer.optimize_mean_reversion(candles, INITIAL_CAPITAL),
        "grid": optimizer.optimize_grid(candles, INITIAL_CAPITAL),
    }
    comparison = optimizer.compare_strategies(results)
    comparison["symbol"] = symbol
    comparison["interval"] = interval
    comparison["details"] = results
    return comparison


# === WebSocket Alerts ===

from fastapi import WebSocket as FastAPIWebSocket
from app.alerts import manager as alert_manager

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: FastAPIWebSocket):
    await alert_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        alert_manager.disconnect(websocket)


@app.get("/api/v1/alerts/history")
def get_alert_history(limit: int = 50) -> list[dict]:
    return alert_manager.alert_history[-limit:]


@app.get("/api/v1/alerts/thresholds")
def get_alert_thresholds() -> dict:
    return alert_manager.thresholds


@app.post("/api/v1/alerts/thresholds")
def update_alert_thresholds(thresholds: dict) -> dict:
    for key, value in thresholds.items():
        if key in alert_manager.thresholds:
            alert_manager.thresholds[key] = value
    return alert_manager.thresholds


@app.post("/api/v1/alerts/check")
def check_alerts() -> dict:
    """Manually trigger alert checks on current data."""
    candles = storage.list_ohlcv_candles("BTCUSDT", "1h", limit=200)
    if len(candles) < 50:
        return {"alerts": [], "error": "insufficient_data"}

    feat = features.latest_features(candles)
    positions = storage.list_positions()
    equity_data = storage.compute_equity_curve(INITIAL_CAPITAL, positions, storage.list_recent_orders(100))

    alerts = alert_manager.check_features(feat, positions, INITIAL_CAPITAL)
    dd_alert = alert_manager.check_drawdown(equity_data)
    if dd_alert:
        alerts.append(dd_alert)

    regime_result = regime.classify(feat)
    regime_alert = alert_manager.check_regime(regime_result)
    if regime_alert:
        alerts.append(regime_alert)

    return {"alerts": alerts, "checked_at": datetime.now(timezone.utc).isoformat()}


# === Advanced Backtesting ===

@app.post("/api/v1/backtests/advanced/walk-forward", status_code=201)
def advanced_walk_forward(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    objective: str = "sharpe_ratio",
    n_splits: int = 3,
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=3000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})

    base_params = {
        "initial_capital": INITIAL_CAPITAL, "allocation": 0.95,
        "fee_bps": 10, "slippage_bps": 5, "interval": interval,
    }
    param_grid = {
        "fast_period": [5, 10, 15, 20, 25],
        "slow_period": [30, 40, 50, 60, 80],
    }
    result = backtesting_advanced.walk_forward_optimize(
        candles, backtesting.run_sma_crossover, base_params, param_grid,
        train_ratio=0.7, n_splits=n_splits, objective=objective,
    )
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/backtests/advanced/monte-carlo", status_code=201)
def monte_carlo(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    fast_period: int = 10,
    slow_period: int = 30,
    n_simulations: int = 1000,
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})

    params = {
        "fast_period": fast_period, "slow_period": slow_period,
        "initial_capital": INITIAL_CAPITAL, "allocation": 0.95,
        "fee_bps": 10, "slippage_bps": 5, "interval": interval,
    }
    result = backtesting_advanced.monte_carlo_simulation(
        candles, backtesting.run_sma_crossover, params, n_simulations,
    )
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/backtests/advanced/sensitivity", status_code=201)
def sensitivity(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    param_name: str = "fast_period",
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})

    base_params = {
        "fast_period": 10, "slow_period": 30,
        "initial_capital": INITIAL_CAPITAL, "allocation": 0.95,
        "fee_bps": 10, "slippage_bps": 5, "interval": interval,
    }
    param_ranges = {
        "fast_period": [5, 8, 10, 12, 15, 20, 25, 30],
        "slow_period": [20, 30, 40, 50, 60, 80, 100],
        "allocation": [0.5, 0.7, 0.8, 0.9, 0.95],
        "fee_bps": [0, 5, 10, 15, 20],
    }
    param_range = param_ranges.get(param_name, [1, 2, 3, 4, 5])

    result = backtesting_advanced.sensitivity_analysis(
        candles, backtesting.run_sma_crossover, base_params, param_name, param_range,
    )
    result["symbol"] = symbol
    result["interval"] = interval
    return result


# === ML Regime Prediction ===

@app.post("/api/v1/ml/regime/train", status_code=201)
def train_ml_regime(symbol: str = "BTCUSDT", interval: str = "1h", epochs: int = 200) -> dict:
    """Train ML regime predictor from historical features."""
    candles = storage.list_ohlcv_candles(symbol, interval, limit=5000)
    if len(candles) < 200:
        raise HTTPException(422, "Need at least 200 candles for ML training")

    feature_sets = []
    regime_labels = []
    window = 50

    for i in range(window, len(candles)):
        window_candles = candles[i - window:i + 1]
        try:
            feat = features.latest_features(window_candles)
            feature_sets.append(feat)
            regime_result = regime.classify(feat)
            regime_labels.append(regime_result["regime"])
        except ValueError:
            continue

    result = ml_regime.predictor.train(feature_sets, regime_labels, epochs=epochs)
    result["symbol"] = symbol
    result["candles_used"] = len(candles)
    result["samples_generated"] = len(feature_sets)
    return result


@app.get("/api/v1/ml/regime/predict")
def predict_regime(symbol: str = "BTCUSDT", interval: str = "1h") -> dict:
    """Predict current regime using trained ML model."""
    candles = storage.list_ohlcv_candles(symbol, interval, limit=200)
    if len(candles) < 50:
        raise HTTPException(422, "Need at least 50 candles")

    feat = features.latest_features(candles)
    prediction = ml_regime.predictor.predict(feat)
    rule_based = regime.classify(feat)

    return {
        "symbol": symbol,
        "ml_prediction": prediction,
        "rule_based": rule_based,
        "agreement": prediction["regime"] == rule_based["regime"],
    }


@app.get("/api/v1/ml/regime/summary")
def ml_regime_summary() -> dict:
    """Get ML model summary and feature importance."""
    return ml_regime.predictor.summary()


# === Binance Testnet ===

@app.get("/api/v1/binance/testnet/status")
def binance_testnet_status() -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.test_connection()


@app.get("/api/v1/binance/testnet/price")
def binance_testnet_price(symbol: str = "BTCUSDT") -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.get_price(symbol)


@app.get("/api/v1/binance/testnet/account")
def binance_testnet_account() -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.get_account()


@app.post("/api/v1/binance/testnet/order/market", status_code=201)
def binance_testnet_market_order(symbol: str, side: str, quantity: float) -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.place_market_order(symbol, side, quantity)


@app.post("/api/v1/binance/testnet/order/limit", status_code=201)
def binance_testnet_limit_order(symbol: str, side: str, quantity: float, price: float) -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.place_limit_order(symbol, side, quantity, price)


@app.delete("/api/v1/binance/testnet/order")
def binance_testnet_cancel_order(symbol: str, order_id: int) -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.cancel_order(symbol, order_id)


@app.get("/api/v1/binance/testnet/orders")
def binance_testnet_orders(symbol: str | None = None) -> list[dict]:
    client = binance_testnet.BinanceTestnet()
    return client.get_open_orders(symbol)


@app.get("/api/v1/binance/testnet/klines")
def binance_testnet_klines(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500) -> list[dict]:
    client = binance_testnet.BinanceTestnet()
    return client.get_klines(symbol, interval, limit)


@app.get("/api/v1/binance/testnet/health")
def binance_testnet_health() -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.health_check()


# === Multi-Asset ===

@app.get("/api/v1/assets/classes")
def get_asset_classes() -> dict:
    return multi_asset.get_asset_classes()


@app.get("/api/v1/assets/symbols")
def get_supported_symbols() -> list[str]:
    return multi_asset.get_supported_symbols()


@app.get("/api/v1/assets/price")
def get_asset_price(symbol: str, asset_class: str | None = None) -> dict:
    return multi_asset.fetch_asset_price(symbol, asset_class)


@app.get("/api/v1/assets/ohlcv")
def get_asset_ohlcv(symbol: str, interval: str = "1h", limit: int = 200, asset_class: str | None = None) -> list[dict]:
    return multi_asset.fetch_asset_ohlcv(symbol, interval, limit, asset_class)


@app.get("/api/v1/assets/forex")
def get_forex_rates(base: str = "USD") -> dict:
    return multi_asset.fetch_forex_rates(base)


@app.get("/api/v1/assets/commodities")
def get_commodity_prices() -> list[dict]:
    return multi_asset.fetch_commodity_prices()


@app.get("/api/v1/assets/stock/{symbol}")
def get_stock_price(symbol: str) -> dict:
    return multi_asset.fetch_stock_price(symbol)


# === AI Analyst (Gemini) ===

@app.get("/api/v1/ai/status")
def ai_status() -> dict:
    return ai_analyst.get_status()


@app.post("/api/v1/ai/analyze-market", status_code=201)
def ai_analyze_market(symbol: str = "BTCUSDT", interval: str = "1h") -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=100)
    if not candles:
        raise HTTPException(422, {"message": "No candle data available. Refresh market data first."})
    feats = features.latest_features(candles)
    risk_data = risk.historical_risk(candles, INITIAL_CAPITAL)
    regime_data = regime.classify(feats)
    return ai_analyst.analyze_market(candles, feats, risk_data, regime_data)


@app.post("/api/v1/ai/assess-risk", status_code=201)
def ai_assess_risk(symbol: str = "BTCUSDT", interval: str = "1h") -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=100)
    if not candles:
        raise HTTPException(422, {"message": "No candle data available."})
    risk_data = risk.historical_risk(candles, INITIAL_CAPITAL)
    positions = storage.list_positions()
    return ai_analyst.assess_risk(candles, risk_data, positions)


@app.post("/api/v1/ai/review-strategies", status_code=201)
def ai_review_strategies() -> dict:
    backtests = storage.list_recent_backtests(limit=10)
    candles = storage.list_ohlcv_candles("BTCUSDT", "1h", limit=2000)
    opt_results = {}
    if candles:
        try:
            sma = optimizer.optimize_sma(candles, INITIAL_CAPITAL)
            donchian = optimizer.optimize_donchian(candles, INITIAL_CAPITAL)
            mr = optimizer.optimize_mean_reversion(candles, INITIAL_CAPITAL)
            grid = optimizer.optimize_grid(candles, INITIAL_CAPITAL)
            opt_results = optimizer.compare_strategies({
                "sma_crossover": sma,
                "donchian_breakout": donchian,
                "mean_reversion": mr,
                "grid_adaptive": grid,
            })
        except Exception:
            opt_results = {"error": "Optimization failed"}
    return ai_analyst.review_strategies(backtests, opt_results)


@app.post("/api/v1/ai/analyze-sentiment", status_code=201)
def ai_analyze_sentiment() -> dict:
    market = {}
    try:
        market = market_data.fetch_spot_prices()
    except Exception:
        pass
    fg = storage.list_fear_greed()
    fr = {}
    try:
        fr = market_data.fetch_funding_rates("BTCUSDT")
    except Exception:
        pass
    return ai_analyst.analyze_sentiment(market, fg, fr)


# === Free APIs (CoinGecko, DeFiLlama, PerpFinder, etc.) ===

@app.get("/api/v1/free/coingecko/global")
def free_coingecko_global() -> dict:
    return free_apis.coingecko_global()


@app.get("/api/v1/free/coingecko/trending")
def free_coingecko_trending() -> list[dict]:
    return free_apis.coingecko_trending()


@app.get("/api/v1/free/coingecko/gainers")
def free_coingecko_gainers() -> list[dict]:
    return free_apis.coingecko_top_gainers()


@app.get("/api/v1/free/coingecko/losers")
def free_coingecko_losers() -> list[dict]:
    return free_apis.coingecko_top_losers()


@app.get("/api/v1/free/defillama/tvl")
def free_defillama_tvl() -> dict:
    return free_apis.defillama_tvl()


@app.get("/api/v1/free/defillama/chains")
def free_defillama_chains() -> list[dict]:
    return free_apis.defillama_chains()


@app.get("/api/v1/free/defillama/protocols")
def free_defillama_protocols() -> list[dict]:
    return free_apis.defillama_top_protocols()


@app.get("/api/v1/free/defillama/yields")
def free_defillama_yields() -> list[dict]:
    return free_apis.defillama_yields()


@app.get("/api/v1/free/perpfinder/funding")
def free_perpfinder_funding() -> list[dict]:
    return free_apis.perpfinder_funding_rates()


@app.get("/api/v1/free/perpfinder/open-interest")
def free_perpfinder_oi() -> list[dict]:
    return free_apis.perpfinder_open_interest()


@app.get("/api/v1/free/perpfinder/liquidations")
def free_perpfinder_liquidations() -> list[dict]:
    return free_apis.perpfinder_liquidations()


@app.get("/api/v1/free/mempool/fees")
def free_mempool_fees() -> dict:
    return free_apis.mempool_fees()


@app.get("/api/v1/free/dexscreener/trending")
def free_dexscreener_trending() -> list[dict]:
    return free_apis.dexscreener_trending()


@app.get("/api/v1/free/polymarket/crypto")
def free_polymarket_crypto() -> list[dict]:
    return free_apis.polymarket_crypto_markets()


@app.get("/api/v1/free/fear-greed/historical")
def free_fear_greed_historical(limit: int = 30) -> list[dict]:
    return free_apis.fear_greed_historical(limit)


@app.get("/api/v1/free/blockstream")
def free_blockstream() -> dict:
    return free_apis.blockstream_info()


@app.get("/api/v1/free/all")
def free_all_data() -> dict:
    return free_apis.get_all_free_data()
