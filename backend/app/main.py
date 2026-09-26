"""AEGIS MVP API: paper trading and live trading modes."""

import asyncio
import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from . import advisor, backtesting, backtesting_advanced, binance_testnet, coach, config, data_quality, deployment, engine, execution, features, journal, lab, learning, market_data, memory, ml_regime, multi_asset, oms, optimizer, position_monitor, regime, risk, security, storage, strategy_registry, supervisor
from .routers import backtesting as backtesting_router, market as market_router, risk as risk_router, ai as ai_router, free_apis as free_apis_router
from .logging_config import setup_logging, request_id_var
from . import metrics as app_metrics

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the FastAPI app."""
    # --- Startup ---
    setup_logging(level="INFO")
    logger.info("AEGIS AI Quant starting up")

    storage.initialize()
    logger.info("Database initialized")

    # Clean stale positions from previous sessions
    cleaned = storage.cleanup_stale_positions()
    if cleaned:
        logger.info("Cleaned %d stale position(s)", cleaned)

    # Start engine if enabled (non-blocking to avoid delaying health checks)
    if config.ENGINE_ENABLED:
        async def _start_engine_background():
            try:
                await engine.start_engine()
                logger.info("Autonomous engine started (ENGINE_ENABLED=true)")
            except Exception as exc:
                logger.error("Failed to start engine: %s", exc)
        asyncio.create_task(_start_engine_background())

    yield

    # --- Shutdown ---
    if config.ENGINE_ENABLED:
        try:
            await engine.stop_engine()
            logger.info("Autonomous engine stopped")
        except Exception as exc:
            logger.error("Failed to stop engine: %s", exc)

    logger.info("AEGIS AI Quant shut down")


app = FastAPI(title="AEGIS AI Quant", version="0.2.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.get("/health")
async def root_health():
    """Lightweight health check for Fly.io (no engine dependency)."""
    return {"status": "ok", "service": "aegis-ai-quant"}
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-AEGIS-Admin-Token"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Track request metrics, assign request IDs, and log access."""
    req_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    request_id_var.set(req_id)

    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start

    path = request.url.path
    if path.startswith("/api/"):
        method = request.method
        status = str(response.status_code)
        app_metrics.http_requests_total.labels(method=method, path=path, status=status).inc()
        app_metrics.http_request_duration_seconds.labels(method=method, path=path).observe(elapsed)

    response.headers["X-Request-ID"] = req_id
    return response

# Include routers
app.include_router(backtesting_router.router)
app.include_router(market_router.router)
app.include_router(risk_router.router)
app.include_router(ai_router.router)
app.include_router(free_apis_router.router)

# ICT Dashboard router (initialize with instances)
try:
    from .trade_journal import trade_journal
    from .routers.ict_dashboard import initialize_dashboard
    
    # Initialize dashboard (risk/position managers resolved from engine)
    initialize_dashboard(trade_journal=trade_journal)
    from .routers import ict_dashboard as ict_dashboard_router
    app.include_router(ict_dashboard_router.router)
    logger.info("ICT Dashboard router initialized")
except ImportError as e:
    logger.warning(f"Could not initialize ICT Dashboard router: {e}")

# Utiliser le capital ICT/SMC si configuré, sinon capital standard
INITIAL_CAPITAL = config.active_capital()
MAX_ORDER_NOTIONAL = config.MAX_ORDER_NOTIONAL
MAX_TOTAL_EXPOSURE = config.MAX_TOTAL_EXPOSURE

# Dashboard cache (TTL 5 seconds)
_dashboard_cache: dict = {"data": None, "timestamp": 0}
DASHBOARD_CACHE_TTL = 5  # seconds


class PaperOrder(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]+(/[A-Z0-9]+)?$")
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0, le=10)
    reference_price: float = Field(gt=0)


def current_exposure(positions: list[dict]) -> float:
    return sum(abs(position["quantity"] * position["average_price"]) for position in positions)


def require_admin_token(
    x_aegis_admin_token: str | None = Header(default=None),
) -> None:
    """Header-only admin auth. Tokens in query strings are rejected
    (they leak into server/proxy logs and browser history)."""
    from .deps import require_admin_token as _require_admin_token
    _require_admin_token(x_aegis_admin_token)


def _build_journal_data() -> dict:
    decisions = storage.list_recent_decisions(limit=100)
    prices = {s["symbol"]: s["price"] for s in storage.list_market_snapshots(limit=10)}
    analyses = journal.analyze_decisions(decisions, prices)
    feedback = journal.feedback_summary(analyses)
    return {**analyses, "feedback": feedback}


@app.get("/api/v1/dashboard")
def dashboard() -> dict:
    """Dashboard with 5-second TTL cache to avoid redundant recomputation."""
    now = time.time()
    
    # Return cached data if still valid
    if _dashboard_cache["data"] and (now - _dashboard_cache["timestamp"]) < DASHBOARD_CACHE_TTL:
        return _dashboard_cache["data"]
    
    # Compute fresh dashboard
    positions = storage.list_positions()
    # Utiliser les symboles ICT/SMC si configurés, sinon fallback sur symboles existants
    primary_symbol = config.ICT_PRIMARY_INSTRUMENT if hasattr(config, 'ICT_PRIMARY_INSTRUMENT') else (config.FOCUSED_SYMBOLS[0] if config.FOCUSED_MODE else "BTCUSDT")
    candles = storage.list_ohlcv_candles(primary_symbol, "1h", limit=500)
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
    snapshots_prices = {s["symbol"]: s["price"] for s in storage.list_market_snapshots(limit=10)}
    equity_curve = storage.compute_equity_curve(INITIAL_CAPITAL, positions, recent_orders, snapshots_prices)
    current_equity = equity_curve[-1]["equity"] if equity_curve else INITIAL_CAPITAL
    # current_equity includes open positions, so it is NOT realized PnL.
    # Take the realized part from the FIFO matcher and expose it separately.
    realized = position_monitor.get_realized_pnl(recent_orders)
    realized_pnl = round(realized["realized_pnl"] - realized["total_fees"], 2)

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
        # Correlation across the active universe
        try:
            assets = {}
            for sym in market_data.SYMBOLS:
                sym_candles = storage.list_ohlcv_candles(sym, "1h", limit=200)
                if sym_candles:
                    assets[sym] = [c["close"] for c in sym_candles]
            if len(assets) >= 2:
                correlation_data = risk.correlation_matrix(assets)
        except Exception as e:
            logger.debug("Correlation matrix failed: %s", e, exc_info=True)
    # Concentration
    snapshots = storage.list_market_snapshots(limit=10)
    prices = {s["symbol"]: s["price"] for s in snapshots}
    concentration_data = risk.concentration_risk(positions, prices)

    result = {
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
        "journal": _build_journal_data(),
    }
    
    # Update cache
    _dashboard_cache["data"] = result
    _dashboard_cache["timestamp"] = now
    
    return result


@app.post("/api/v1/paper-orders", status_code=201)
@limiter.limit("10/minute")
def create_paper_order(
    request: Request,
    order: PaperOrder,
    _admin: None = Depends(require_admin_token),
) -> dict:
    if storage.get_kill_switch():
        raise HTTPException(423, "Emergency stop is active; paper orders are blocked.")
    symbol = storage.normalize_symbol(order.symbol)
    notional = order.quantity * order.reference_price
    if notional > MAX_ORDER_NOTIONAL:
        raise HTTPException(422, f"Order exceeds the paper limit of ${MAX_ORDER_NOTIONAL:.0f}.")
    positions = storage.list_positions()
    current = next((position for position in positions if position["symbol"] == symbol), None)

    # Shared netting helper: the local copy used abs(total_cost / new_qty),
    # which moved the cost basis on every partial close.
    position = oms.net_position(current, symbol, order.side, order.quantity, order.reference_price)

    next_positions = [p for p in positions if p["symbol"] != symbol]
    if position:
        next_positions.append(position)
    if current_exposure(next_positions) > MAX_TOTAL_EXPOSURE:
        raise HTTPException(422, "Order exceeds the total paper exposure limit.")

    return storage.save_order_and_position({
        **order.model_dump(),
        "symbol": symbol,
        "notional": notional,
        "status": "filled_simulated",
        "strategy": "manual",
        "mode": "paper",
    }, position)



@app.get("/api/v1/data-quality/ohlcv")
def ohlcv_quality(
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
) -> dict:
    return data_quality.validate_ohlcv(storage.list_ohlcv_candles(symbol, interval, limit=5_000), interval)


@app.get("/api/v1/risk/summary")
def risk_summary(
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=500)
    try:
        metrics = risk.historical_risk(candles, INITIAL_CAPITAL)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {"mode": "paper", "capital": INITIAL_CAPITAL, "exposure": current_exposure(storage.list_positions()), **metrics}



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
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
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
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
    _admin: None = Depends(require_admin_token),
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


@app.get("/api/v1/focus/status")
def focus_status() -> dict:
    """Active-mode summary: focused single-strategy or ICT/SMC forex."""
    ict_mode = config.ICT_MODE and not config.FOCUSED_MODE
    symbols = (
        config.FOCUSED_SYMBOLS
        if config.FOCUSED_MODE
        else (config.ICT_SYMBOLS if ict_mode else config.SYMBOLS)
    )
    strategy = config.FOCUSED_STRATEGY if config.FOCUSED_MODE else "ict_smc"
    return {
        "focused_mode": config.FOCUSED_MODE,
        "ict_mode": ict_mode,
        "strategy": strategy,
        "strategy_name": strategy_registry.get_strategy(strategy).get("name", strategy)
        if strategy_registry.get_strategy(strategy) else strategy,
        "symbols": symbols,
        "max_positions": config.MAX_POSITIONS,
        "donchian_parameters": config.DONCHIAN_PARAMS,
        "mode": config.MODE,
        "tradable_strategies": [
            s["id"] for s in strategy_registry.STRATEGIES
            if strategy_registry.is_active(s["id"])
        ],
    }


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
def memory_list(symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
    episodes = storage.list_memory_episodes(symbol, limit=100)
    return {
        "summary": memory.summarize_episodes(episodes),
        "episodes": episodes[:20],
    }


@app.post("/api/v1/memory/remember", status_code=201)
def memory_remember(
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    strategy: str = "unknown",
    _admin: None = Depends(require_admin_token),
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
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
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


@app.get("/api/v1/auth/verify")
def verify_admin_token(_admin: None = Depends(require_admin_token)) -> dict:
    """Confirm an admin token is valid without performing any action.

    Lets the dashboard validate a runtime-entered token instead of shipping the
    secret inside the client bundle.
    """
    return {"authenticated": True, "mode": config.MODE}


@app.post("/api/v1/supervisor/emergency-stop")
def emergency_stop(_admin: None = Depends(require_admin_token)) -> dict:
    storage.set_kill_switch(True, "Emergency stop activated manually.")
    return supervisor.status(True)


@app.post("/api/v1/supervisor/resume")
def resume(_admin: None = Depends(require_admin_token)) -> dict:
    storage.set_kill_switch(False, "Service resumed manually after emergency stop.")
    return supervisor.status(False)


@app.post("/api/v1/execution/market-order", status_code=201)
@limiter.limit("10/minute")
def execute_market_order(
    request: Request,
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    side: Literal["buy", "sell"] = "buy",
    quantity: float = 0.001,
    _admin: None = Depends(require_admin_token),
) -> dict:
    if storage.get_kill_switch():
        raise HTTPException(423, "Emergency stop is active.")
    if quantity <= 0:
        raise HTTPException(422, "quantity must be positive.")
    snapshots = storage.list_market_snapshots(limit=1)
    if not snapshots:
        raise HTTPException(422, "No market data available. Refresh prices first.")
    current_price = snapshots[0]["price"]

    # Reject on the reference notional BEFORE simulating anything. The old code
    # filled first and only then raised on the limit, so an oversized order was
    # reported as a rejection while its position had already been booked.
    if quantity * current_price > config.MAX_ORDER_NOTIONAL:
        raise HTTPException(422, f"Order exceeds paper limit of ${config.MAX_ORDER_NOTIONAL}.")

    # The OMS applies the kill switch, min/max notional, total exposure, the
    # circuit breaker and the netting in one place.
    return oms.oms.submit_market_order(
        symbol=symbol,
        side=side,
        quantity=quantity,
        current_price=current_price,
        strategy="manual",
        reason="Market order from /execution/market-order",
    )


@app.post("/api/v1/execution/limit-order", status_code=201)
@limiter.limit("10/minute")
def execute_limit_order(
    request: Request,
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    side: Literal["buy", "sell"] = "buy",
    quantity: float = 0.001,
    limit_price: float = 0,
    _admin: None = Depends(require_admin_token),
) -> dict:
    if storage.get_kill_switch():
        raise HTTPException(423, "Emergency stop is active.")
    if limit_price <= 0:
        raise HTTPException(422, "limit_price must be positive.")
    if quantity <= 0:
        raise HTTPException(422, "quantity must be positive.")
    snapshots = storage.list_market_snapshots(limit=1)
    current_price = snapshots[0]["price"] if snapshots else limit_price

    # Pre-trade limits are enforced up-front so a rejected order comes back as
    # HTTP 422, not 201 with a "rejected" body. The OMS re-checks everything.
    validation = oms.oms._validate_pre_trade(symbol, side, quantity, limit_price)
    if not validation["valid"]:
        raise HTTPException(422, validation["reason"])

    # Routed through the OMS so the fill actually updates the position and the
    # pending-order book. This endpoint used to call the raw simulator, so it
    # honoured no limits and persisted nothing.
    return oms.oms.submit_limit_order(
        symbol=symbol,
        side=side,
        quantity=quantity,
        limit_price=limit_price,
        current_price=current_price,
        strategy="manual",
        reason="Limit order from /execution/limit-order",
    )


@app.post("/api/v1/execution/fractioned-order", status_code=201)
@limiter.limit("10/minute")
def execute_fractioned_order(
    request: Request,
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    side: Literal["buy", "sell"] = "buy",
    quantity: float = Query(default=0.01, gt=0, le=10),
    chunks: int = Query(default=3, ge=1, le=10),
    _admin: None = Depends(require_admin_token),
) -> dict:
    if storage.get_kill_switch():
        raise HTTPException(423, "Emergency stop is active.")
    snapshots = storage.list_market_snapshots(limit=1)
    if not snapshots:
        raise HTTPException(422, "No market data available.")
    current_price = snapshots[0]["price"]

    # The OMS has no chunked path, so the pre-trade limits are enforced here on
    # the full order, BEFORE any chunk is simulated. The old code chunked and
    # filled first, then raised on the notional limit.
    validation = oms.oms._validate_pre_trade(symbol, side, quantity, current_price)
    if not validation["valid"]:
        raise HTTPException(422, validation["reason"])

    result = execution.fractioned_order(symbol, side, quantity, current_price, chunks)
    if result["status"] == "filled":
        order_data = {
            "symbol": symbol,
            "side": side,
            "quantity": result["total_filled"],
            "reference_price": result["avg_fill_price"],
            "notional": result["total_notional"],
        }
        positions = storage.list_positions()
        current = next((p for p in positions if p["symbol"] == symbol), None)
        position = oms.net_position(
            current, symbol, side, result["total_filled"], result["avg_fill_price"]
        )
        storage.save_order_and_position(order_data, position)
    return result


@app.post("/api/v1/execution/estimate-slippage")
def estimate_slippage(order_value: float = 100) -> dict:
    return {"order_value": order_value, "estimated_slippage_bps": execution.estimate_slippage(order_value)}


@app.post("/api/v1/deployment/pipeline", status_code=201)
@limiter.limit("5/minute")
def create_deployment_pipeline(
    request: Request,
    strategy_id: str = "sma_crossover_long_flat",
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    _admin: None = Depends(require_admin_token),
) -> dict:
    return deployment.create_pipeline(strategy_id, symbol, {})


@app.post("/api/v1/deployment/validate-backtest")
def validate_deployment_backtest(
    strategy_id: str = "sma_crossover_long_flat",
    stage: str = "backtest",
    _admin: None = Depends(require_admin_token),
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
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
    limit: int = Query(default=200, ge=10, le=500),
    _admin: None = Depends(require_admin_token),
) -> dict:
    try:
        candles = market_data.fetch_ohlcv(symbol, interval, limit)
    except OSError as error:
        raise HTTPException(502, "Public OHLCV source is unavailable.") from error
    return {"stored": storage.save_ohlcv_candles(candles), "symbol": symbol, "interval": interval}


# === Phase 3: Auto-Improvement & Optimization ===

@app.post("/api/v1/optimizer/sma", status_code=200)
def optimize_sma_strategy(
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
    _admin: None = Depends(require_admin_token),
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    result = optimizer.optimize_sma(candles, INITIAL_CAPITAL)
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/optimizer/donchian", status_code=200)
def optimize_donchian_strategy(
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
    _admin: None = Depends(require_admin_token),
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    result = optimizer.optimize_donchian(candles, INITIAL_CAPITAL)
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/optimizer/mean-reversion", status_code=200)
def optimize_mean_reversion_strategy(
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
    _admin: None = Depends(require_admin_token),
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    result = optimizer.optimize_mean_reversion(candles, INITIAL_CAPITAL)
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/optimizer/grid", status_code=200)
def optimize_grid_strategy(
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
    _admin: None = Depends(require_admin_token),
) -> dict:
    candles = storage.list_ohlcv_candles(symbol, interval, limit=2000)
    quality = data_quality.validate_ohlcv(candles, interval)
    if not quality["valid"]:
        raise HTTPException(422, {"message": "OHLCV quality gate failed.", "quality": quality})
    result = optimizer.optimize_grid(candles, INITIAL_CAPITAL)
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/optimizer/compare", status_code=200)
def compare_all_strategies(
    symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    interval: Literal["5m", "15m", "1h", "4h"] = "1h",
    _admin: None = Depends(require_admin_token),
) -> dict:
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

from .alerts import manager as alert_manager  # noqa: E402

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alerts. Requires admin token if configured."""
    token = websocket.query_params.get("token", "")
    if config.ADMIN_TOKEN:
        if not token or not hmac.compare_digest(token, config.ADMIN_TOKEN):
            await websocket.close(code=4001, reason="Unauthorized")
            return
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
def update_alert_thresholds(thresholds: dict, _admin: None = Depends(require_admin_token)) -> dict:
    allowed_keys = set(alert_manager.thresholds.keys())
    for key, value in thresholds.items():
        if key in allowed_keys and isinstance(value, (int, float)):
            alert_manager.thresholds[key] = value
    return alert_manager.thresholds


@app.post("/api/v1/alerts/check")
async def check_alerts(_admin: None = Depends(require_admin_token)) -> dict:
    """Manually trigger alert checks on current data and broadcast to WS clients."""
    all_alerts = []
    for symbol in market_data.SYMBOLS:
        candles = storage.list_ohlcv_candles(symbol, "1h", limit=200)
        if len(candles) < 50:
            continue
        feat = features.latest_features(candles)
        positions = [p for p in storage.list_positions() if p["symbol"] == symbol]
        snapshots_prices = {s["symbol"]: s["price"] for s in storage.list_market_snapshots(limit=10)}
        equity_data = storage.compute_equity_curve(INITIAL_CAPITAL, positions, storage.list_recent_orders(100), snapshots_prices)

        alerts = alert_manager.check_features(feat, positions, INITIAL_CAPITAL)
        dd_alert = alert_manager.check_drawdown(equity_data)
        if dd_alert:
            alerts.append(dd_alert)

        regime_result = regime.classify(feat)
        regime_alert = alert_manager.check_regime(regime_result, symbol)
        if regime_alert:
            alerts.append(regime_alert)

        for a in alerts:
            a["symbol"] = symbol
            await alert_manager.broadcast(a)
        all_alerts.extend(alerts)

    return {"alerts": all_alerts, "checked_at": datetime.now(timezone.utc).isoformat()}


# === Position Monitoring ===

@app.get("/api/v1/positions/monitor")
def get_position_monitor() -> dict:
    """Get real-time position monitoring data with PnL and risk metrics."""
    positions = storage.list_positions()
    snapshots = storage.list_market_snapshots(limit=10)
    prices = {s["symbol"]: s["price"] for s in snapshots}
    return position_monitor.monitor_cycle(prices)


@app.get("/api/v1/positions/pnl")
def get_position_pnl() -> dict:
    """Get PnL summary (unrealized + realized)."""
    positions = storage.list_positions()
    snapshots = storage.list_market_snapshots(limit=10)
    prices = {s["symbol"]: s["price"] for s in snapshots}
    capital = config.active_capital()
    orders = storage.list_recent_orders(limit=200)

    realized = position_monitor.get_realized_pnl(orders)
    portfolio = position_monitor.compute_portfolio_summary(
        positions, prices, capital,
        realized_pnl=realized["realized_pnl"],
        total_fees=realized["total_fees"],
    )
    portfolio["total_pnl_pct"] = round(
        (portfolio["total_pnl"] / capital * 100) if capital > 0 else 0, 2
    )
    return portfolio


@app.get("/api/v1/positions/risks")
def get_position_risks() -> dict:
    """Check positions against risk thresholds."""
    positions = storage.list_positions()
    snapshots = storage.list_market_snapshots(limit=10)
    prices = {s["symbol"]: s["price"] for s in snapshots}
    capital = config.PAPER_CAPITAL
    alerts = position_monitor.check_position_risks(positions, prices, capital)
    return {
        "alerts": alerts,
        "thresholds": {
            "position_max_loss_pct": config.POSITION_MAX_LOSS_PCT * 100,
            "position_max_drawdown_pct": config.POSITION_MAX_DRAWDOWN_PCT * 100,
            "portfolio_max_drawdown_pct": config.PORTFOLIO_MAX_DRAWDOWN_PCT * 100,
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/portfolio/correlation")
def get_portfolio_correlation() -> dict:
    """Multi-asset correlation analysis with dynamic sizing recommendations."""
    from .multi_asset_correlation import compute_portfolio_correlation_risk
    symbols = list(config.FOCUSED_SYMBOLS if config.FOCUSED_MODE else ("BTCUSDT", "ETHUSDT", "SOLUSDT"))
    return compute_portfolio_correlation_risk(symbols)


@app.get("/api/v1/portfolio/daily-report")
def get_daily_report(date: str | None = None) -> dict:
    """Generate comprehensive daily report with PnL, trades, regimes, and performance."""
    from .daily_report import generate_daily_report
    return generate_daily_report(date)


class ClosePositionRequest(BaseModel):
    symbol: str
    side: str = "sell"


@app.post("/api/v1/positions/close", status_code=200)
def close_position(req: ClosePositionRequest, _admin: None = Depends(require_admin_token)) -> dict:
    """Close a position by executing a market order in the opposite direction."""
    if storage.get_kill_switch():
        raise HTTPException(423, "Kill switch is active. Resume trading first.")
    symbol = storage.normalize_symbol(req.symbol)
    positions = storage.list_positions()
    pos = next((p for p in positions if p["symbol"] == symbol), None)
    if not pos or pos["quantity"] == 0:
        raise HTTPException(404, f"No open position for {symbol}")

    snapshots = storage.list_market_snapshots(limit=10)
    prices = {storage.normalize_symbol(s["symbol"]): s["price"] for s in snapshots}
    current_price = prices.get(symbol)
    if not current_price:
        raise HTTPException(422, f"No price data for {symbol}")

    close_side = "sell" if pos["quantity"] > 0 else "buy"
    quantity = abs(pos["quantity"])

    result = oms.oms.submit_market_order(
        symbol=symbol,
        side=close_side,
        quantity=quantity,
        current_price=current_price,
        strategy="manual",
        reason=f"Manual close by user",
    )
    return {"closed": result.get("status") == "filled", "order": result}


class ManualOrderRequest(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]+/[A-Z0-9]+$")
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"] = "market"
    quantity: float = Field(gt=0, le=10)
    limit_price: float | None = None


@app.post("/api/v1/orders/manual", status_code=201)
def place_manual_order(req: ManualOrderRequest, _admin: None = Depends(require_admin_token)) -> dict:
    """Place a manual order (market or limit)."""
    if storage.get_kill_switch():
        raise HTTPException(423, "Kill switch is active. Resume trading first.")
    symbol = storage.normalize_symbol(req.symbol)
    snapshots = storage.list_market_snapshots(limit=10)
    prices = {s["symbol"]: s["price"] for s in snapshots}
    current_price = prices.get(symbol)
    if not current_price:
        raise HTTPException(422, f"No price data for {symbol}. Refresh market data first.")

    if req.order_type == "limit" and req.limit_price is None:
        raise HTTPException(422, "limit_price is required for limit orders")

    if req.order_type == "limit":
        result = execution.execute_limit_order(
            symbol=symbol,
            side=req.side,
            quantity=req.quantity,
            limit_price=req.limit_price,
            current_price=current_price,
            strategy="manual",
        )
    else:
        result = oms.oms.submit_market_order(
            symbol=symbol,
            side=req.side,
            quantity=req.quantity,
            current_price=current_price,
            strategy="manual",
            reason="Manual order from UI",
        )
    return result


@app.get("/api/v1/orders/open")
def list_open_orders() -> dict:
    """List all pending open limit orders."""
    orders = storage.list_open_orders()
    return {"count": len(orders), "orders": orders}


@app.post("/api/v1/orders/cancel/{order_id}")
def cancel_open_order_endpoint(order_id: str, _admin: None = Depends(require_admin_token)) -> dict:
    """Cancel a pending open limit order."""
    storage.cancel_open_order(order_id)
    return {"status": "cancelled", "order_id": order_id}


@app.websocket("/ws/positions")
async def websocket_positions(websocket: WebSocket):
    """Stream real-time position data every 5 seconds. Requires admin token if configured."""
    token = websocket.query_params.get("token", "")
    if config.ADMIN_TOKEN:
        if not token or not hmac.compare_digest(token, config.ADMIN_TOKEN):
            await websocket.close(code=4001, reason="Unauthorized")
            return
    await websocket.accept()
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
            except asyncio.TimeoutError:
                pass

            # Send current position state
            positions = storage.list_positions()
            snapshots = storage.list_market_snapshots(limit=10)
            prices = {s["symbol"]: s["price"] for s in snapshots}
            capital = config.active_capital()
            realized = position_monitor.get_realized_pnl(storage.list_recent_orders(limit=200))

            portfolio = position_monitor.compute_portfolio_summary(
                positions, prices, capital,
                realized_pnl=realized["realized_pnl"],
                total_fees=realized["total_fees"],
            )
            portfolio["total_pnl_pct"] = round(
                (portfolio["total_pnl"] / capital * 100) if capital > 0 else 0, 2
            )
            portfolio["kill_switch"] = storage.get_kill_switch()
            portfolio["mode"] = config.MODE

            await websocket.send_json({"type": "position_update", "data": portfolio})
    except WebSocketDisconnect:
        pass


# === Learning & Strategy Performance ===

@app.get("/api/v1/learning/strategies")
def get_strategy_performance() -> list[dict]:
    """Get performance stats for all strategies, ranked by score."""
    return learning.get_all_strategy_stats()


@app.get("/api/v1/learning/strategies/{strategy_id}")
def get_strategy_performance_detail(strategy_id: str) -> dict:
    """Get detailed performance stats for a single strategy."""
    return learning.get_strategy_stats(strategy_id)


@app.get("/api/v1/learning/regime/{regime}")
def get_strategies_for_regime(regime: str) -> list[dict]:
    """Rank strategies by their performance in a given regime."""
    return learning.rank_strategies_for_regime(regime)


@app.get("/api/v1/learning/weights/{regime}")
def get_adaptive_weights(regime: str) -> dict:
    """Get adaptive strategy weights for the current regime."""
    return learning.get_advisor_weights(regime)


@app.get("/api/v1/learning/trades")
def get_trade_outcomes(
    strategy: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get trade outcome records with optional filters."""
    return storage.list_trade_outcomes(strategy=strategy, status=status, limit=limit)


@app.get("/api/v1/learning/memory/{symbol}")
def get_memory_consolidation(symbol: str) -> dict:
    """Get consolidated memory patterns for a symbol."""
    return learning.consolidate_memory(symbol)


@app.get("/api/v1/learning/summary")
def get_learning_summary() -> dict:
    """Get a summary of the learning system state."""
    all_stats = learning.get_all_strategy_stats()
    outcomes = storage.list_trade_outcomes(limit=1000)
    open_trades = [o for o in outcomes if o["status"] == "open"]
    closed_trades = [o for o in outcomes if o["status"] == "closed"]

    total_pnl = sum((o.get("pnl") or 0) for o in closed_trades)
    win_count = sum(1 for o in closed_trades if (o.get("pnl") or 0) > 0)

    return {
        "strategies_tracked": len(all_stats),
        "total_trades": len(outcomes),
        "open_trades": len(open_trades),
        "closed_trades": len(closed_trades),
        "overall_win_rate": round(win_count / max(len(closed_trades), 1), 4),
        "total_realized_pnl": round(total_pnl, 2),
        "top_strategies": [
            {"strategy": s.get("strategy_id"), "score": s.get("score", 0), "win_rate": s.get("win_rate", 0)}
            for s in all_stats[:5]
        ],
    }


# === Security ===

@app.get("/api/v1/security/summary")
def get_security_summary(_admin: None = Depends(require_admin_token)) -> dict:
    """Get security event summary (admin only)."""
    return security.get_security_summary()


# === Advanced Backtesting ===

@app.post("/api/v1/backtests/advanced/walk-forward", status_code=201)
def advanced_walk_forward(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    objective: str = "sharpe_ratio",
    n_splits: int = 3,
    _admin: None = Depends(require_admin_token),
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
    n_simulations: int = Query(default=1000, ge=10, le=5000),
    seed: int | None = None,
    _admin: None = Depends(require_admin_token),
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
        seed=seed,
    )
    result["symbol"] = symbol
    result["interval"] = interval
    return result


@app.post("/api/v1/backtests/advanced/sensitivity", status_code=201)
def sensitivity(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    param_name: str = "fast_period",
    _admin: None = Depends(require_admin_token),
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
@limiter.limit("2/minute")
def train_ml_regime(request: Request, symbol: str = "BTCUSDT", interval: str = "1h", epochs: int = 200, _admin: None = Depends(require_admin_token)) -> dict:
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
def binance_testnet_account(_admin: None = Depends(require_admin_token)) -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.get_account()


@app.post("/api/v1/binance/testnet/order/market", status_code=201)
def binance_testnet_market_order(symbol: str, side: str, quantity: float, _admin: None = Depends(require_admin_token)) -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.place_market_order(symbol, side, quantity)


@app.post("/api/v1/binance/testnet/order/limit", status_code=201)
def binance_testnet_limit_order(symbol: str, side: str, quantity: float, price: float, _admin: None = Depends(require_admin_token)) -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.place_limit_order(symbol, side, quantity, price)


@app.delete("/api/v1/binance/testnet/order")
def binance_testnet_cancel_order(symbol: str, order_id: int, _admin: None = Depends(require_admin_token)) -> dict:
    client = binance_testnet.BinanceTestnet()
    return client.cancel_order(symbol, order_id)


@app.get("/api/v1/binance/testnet/orders")
def binance_testnet_orders(symbol: str | None = None, _admin: None = Depends(require_admin_token)) -> list[dict]:
    client = binance_testnet.BinanceTestnet()
    return client.get_open_orders(symbol)


@app.get("/api/v1/binance/testnet/klines")
def binance_testnet_klines(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500, _admin: None = Depends(require_admin_token)) -> list[dict]:
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




# === Autonomous Engine Control ===

@app.get("/api/v1/engine/status")
def engine_status() -> dict:
    """Get autonomous engine status."""
    return engine.get_engine_status()


@app.post("/api/v1/engine/start")
@limiter.limit("2/minute")
async def engine_start(request: Request, _admin: None = Depends(require_admin_token)) -> dict:
    """Start the autonomous trading engine."""
    if storage.get_engine_state("status") == "running":
        return {"status": "already_running"}
    return await engine.start_engine()


@app.post("/api/v1/engine/stop")
@limiter.limit("2/minute")
async def engine_stop(request: Request, _admin: None = Depends(require_admin_token)) -> dict:
    """Stop the autonomous trading engine."""
    return await engine.stop_engine()


@app.get("/api/v1/engine/logs")
def engine_logs(limit: int = 50) -> list[dict]:
    """Get recent engine log entries."""
    return storage.list_engine_logs(limit)


@app.get("/api/v1/engine/stats")
def engine_stats() -> dict:
    """Get engine statistics."""
    return storage.get_engine_stats()


@app.get("/api/v1/engine/signals")
def engine_signals(limit: int = 20) -> list[dict]:
    """Get recent trade signals."""
    return storage.list_trade_signals(limit)


@app.post("/api/v1/engine/trigger/{task_name}")
@limiter.limit("5/minute")
def engine_trigger_task(request: Request, task_name: str, _admin: None = Depends(require_admin_token)) -> dict:
    """Immediately trigger a specific engine task."""
    from .scheduler import scheduler
    if scheduler.trigger_now(task_name):
        return {"triggered": task_name}
    raise HTTPException(400, f"Task '{task_name}' not found or already running")


# === Order Management System (OMS) ===

@app.get("/api/v1/oms/status")
def oms_status() -> dict:
    """Get OMS status."""
    from . import oms as _oms
    return _oms.oms.get_status()


@app.get("/api/v1/oms/orders")
def oms_orders(limit: int = 50) -> list[dict]:
    """Get recent orders from OMS."""
    from . import oms as _oms
    return _oms.oms.get_order_history(limit)


@app.get("/api/v1/oms/open")
def oms_open_orders() -> list[dict]:
    """Get open orders from exchange."""
    from . import oms as _oms
    return _oms.oms.get_open_orders()


@app.get("/api/v1/oms/reconcile")
def oms_reconcile(_admin: None = Depends(require_admin_token)) -> dict:
    """Reconcile local positions with exchange state."""
    from . import oms as _oms
    return _oms.oms.reconcile_positions()


@app.get("/api/v1/oms/mode")
def oms_mode() -> dict:
    """Get current execution mode and limits."""
    from . import execution as _execution
    return _execution.get_execution_mode()


@app.post("/api/v1/oms/mode")
@limiter.limit("5/minute")
def oms_set_mode(request: Request, mode: str = "paper", _admin: None = Depends(require_admin_token)) -> dict:
    """Switch execution mode (paper/live). Requires admin token."""
    if mode not in ("paper", "live"):
        raise HTTPException(400, "Mode must be 'paper' or 'live'")
    old_mode = config.MODE
    config.MODE = mode
    security.log_mode_switch(old_mode, mode)
    storage.log_engine_event("mode-switch", "mode_changed", {"old_mode": old_mode, "new_mode": mode}, "warning")
    return {"mode": mode, "message": f"Execution mode set to {mode}"}
