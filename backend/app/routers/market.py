"""Market data routes."""

import os
import shutil
import time
from typing import Literal

from fastapi import APIRouter, Response

from .. import config, engine, market_data, metrics, storage

router = APIRouter(prefix="/api/v1", tags=["market"])


@router.get("/health")
def health() -> dict:
    """Basic health check — returns mode."""
    return {"status": "ok", "mode": config.MODE}


@router.get("/health/detailed")
def health_detailed() -> dict:
    """Deep health check: DB, disk, engine status."""
    checks = {}

    # Database check
    try:
        start = time.perf_counter()
        with storage.connection() as db:
            db.execute("SELECT 1").fetchone()
        checks["database"] = {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}

    # Disk space check
    try:
        db_path = storage.DATABASE_PATH
        stat = os.stat(db_path) if db_path.exists() else None
        usage = shutil.disk_usage(str(db_path.parent)) if db_path.parent.exists() else None
        if usage:
            free_gb = round(usage.free / (1024**3), 1)
            checks["disk"] = {
                "status": "ok" if free_gb > 1.0 else "warning",
                "free_gb": free_gb,
                "db_size_bytes": stat.st_size if stat else 0,
            }
        else:
            checks["disk"] = {"status": "unknown"}
    except Exception as e:
        checks["disk"] = {"status": "error", "error": str(e)}

    # Engine check
    try:
        engine_status = engine.get_engine_status()
        checks["engine"] = {
            "status": "ok",
            "running": engine_status.get("status") == "running",
            "cycle_count": engine_status.get("cycle_count", 0),
        }
    except Exception as e:
        checks["engine"] = {"status": "error", "error": str(e)}

    # Positions count
    try:
        positions = storage.list_positions()
        checks["positions"] = {
            "status": "ok",
            "count": len(positions),
        }
    except Exception as e:
        checks["positions"] = {"status": "error", "error": str(e)}

    overall = "ok" if all(c.get("status") == "ok" for c in checks.values()) else "degraded"
    return {
        "status": overall,
        "mode": config.MODE,
        "checks": checks,
    }


@router.get("/metrics")
def prometheus_metrics() -> Response:
    """Prometheus text exposition format metrics endpoint."""
    return Response(content=metrics.serialize(), media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/market-snapshots")
def get_market_snapshots() -> list[dict]:
    return storage.list_market_snapshots()


@router.post("/market-snapshots/refresh")
def refresh_market_snapshots() -> list[dict]:
    snapshots = market_data.fetch_spot_prices()
    return storage.save_market_snapshots(snapshots)


@router.get("/ohlcv")
def get_ohlcv(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "EURUSD", interval: Literal["5m", "15m", "1h", "4h"] = "1h", limit: int = 200) -> list[dict]:
    return market_data.fetch_ohlcv(symbol, interval, limit)


@router.post("/ohlcv/refresh-history")
def refresh_history(symbol: Literal["EURUSD", "GBPUSD", "XAUUSD", "PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "EURUSD", interval: Literal["5m", "15m", "1h", "4h"] = "1h", batches: int = 4) -> dict:
    candles = market_data.fetch_ohlcv(symbol, interval, limit=batches * 200)
    return {"symbol": symbol, "interval": interval, "candles": len(candles)}


@router.get("/fear-greed")
def get_fear_greed() -> list[dict]:
    return storage.list_fear_greed()


@router.post("/fear-greed/refresh")
def refresh_fear_greed() -> dict:
    data = market_data.fetch_fear_greed()
    return storage.save_fear_greed(data)


@router.get("/funding-rates")
def get_funding_rates(symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> list[dict]:
    return storage.list_funding_rates(symbol)


@router.post("/funding-rates/refresh")
def refresh_funding_rates(symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
    data = market_data.fetch_funding_rates(symbol)
    return storage.save_funding_rate(data)


@router.get("/open-interest")
def get_open_interest(symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> list[dict]:
    return storage.list_open_interest(symbol)


@router.post("/open-interest/refresh")
def refresh_open_interest(symbol: Literal["PAXGUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT") -> dict:
    data = market_data.fetch_open_interest(symbol)
    return storage.save_open_interest(data)
