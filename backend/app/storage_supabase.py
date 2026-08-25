"""Supabase storage adapter for AEGIS AI Quant.

Replaces SQLite storage with Supabase PostgreSQL.
Drop-in replacement for storage.py — same interface, different backend.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from supabase import create_client, Client

from . import config

logger = logging.getLogger(__name__)

_supabase: Client | None = None


def _get_client() -> Client:
    """Lazy singleton Supabase client."""
    global _supabase
    if _supabase is None:
        url = config.SUPABASE_URL
        key = config.SUPABASE_SERVICE_KEY
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        _supabase = create_client(url, key)
    return _supabase


# ============================================================
# POSITIONS
# ============================================================

def save_position(symbol: str, quantity: float, average_price: float) -> None:
    sb = _get_client()
    sb.table("positions").upsert({
        "symbol": symbol,
        "quantity": quantity,
        "average_price": average_price,
    }).execute()


def list_positions() -> list[dict]:
    sb = _get_client()
    resp = sb.table("positions").select("*").execute()
    return resp.data or []


def get_position(symbol: str) -> dict | None:
    sb = _get_client()
    resp = sb.table("positions").select("*").eq("symbol", symbol).execute()
    return resp.data[0] if resp.data else None


def delete_position(symbol: str) -> None:
    sb = _get_client()
    sb.table("positions").delete().eq("symbol", symbol).execute()


# ============================================================
# PAPER ORDERS
# ============================================================

def save_paper_order(order: dict) -> None:
    sb = _get_client()
    sb.table("paper_orders").insert({
        "order_id": order.get("order_id"),
        "symbol": order["symbol"],
        "side": order["side"],
        "quantity": order["quantity"],
        "reference_price": order["reference_price"],
        "notional": order.get("notional", 0),
        "status": order["status"],
        "strategy": order.get("strategy", "manual"),
        "mode": order.get("mode", "paper"),
        "exchange_order_id": order.get("exchange_order_id"),
        "fill_price": order.get("fill_price"),
        "fee": order.get("fee", 0),
        "reason": order.get("reason"),
        "created_at": order.get("created_at", datetime.now(timezone.utc).isoformat()),
    }).execute()


def list_paper_orders(limit: int = 100) -> list[dict]:
    sb = _get_client()
    resp = sb.table("paper_orders").select("*").order("created_at", desc=True).limit(limit).execute()
    return resp.data or []


# ============================================================
# MARKET SNAPSHOTS
# ============================================================

def save_market_snapshots(snapshots: list[dict]) -> None:
    if not snapshots:
        return
    sb = _get_client()
    rows = [{
        "symbol": s["symbol"],
        "price": s["price"],
        "source": s.get("source", "unknown"),
        "collected_at": s.get("collected_at", datetime.now(timezone.utc).isoformat()),
    } for s in snapshots]
    sb.table("market_snapshots").insert(rows).execute()


def get_latest_prices() -> dict[str, float]:
    sb = _get_client()
    # Get latest price per symbol using a workaround
    resp = sb.table("market_snapshots").select("symbol, price, collected_at").order("collected_at", desc=True).limit(100).execute()
    prices = {}
    for row in (resp.data or []):
        sym = row["symbol"]
        if sym not in prices:
            prices[sym] = row["price"]
    return prices


# ============================================================
# OHLCV CANDLES
# ============================================================

def save_ohlcv_candles(symbol: str, interval: str, candles: list[dict]) -> None:
    if not candles:
        return
    sb = _get_client()
    rows = [{
        "symbol": symbol,
        "interval": interval,
        "open_time": c["open_time"],
        "close_time": c["close_time"],
        "open": c["open"],
        "high": c["high"],
        "low": c["low"],
        "close": c["close"],
        "volume": c["volume"],
        "source": c.get("source", "unknown"),
    } for c in candles]
    # Upsert to avoid duplicates
    sb.table("ohlcv_candles").upsert(rows, on_conflict="symbol,interval,open_time").execute()


def get_ohlcv_candles(symbol: str, interval: str, limit: int = 500) -> list[dict]:
    sb = _get_client()
    resp = (sb.table("ohlcv_candles")
        .select("*")
        .eq("symbol", symbol)
        .eq("interval", interval)
        .order("open_time", desc=True)
        .limit(limit)
        .execute())
    return list(reversed(resp.data or []))


# ============================================================
# ENGINE STATE
# ============================================================

def save_engine_state(state: dict) -> None:
    sb = _get_client()
    now = datetime.now(timezone.utc).isoformat()
    for key, value in state.items():
        sb.table("engine_state").upsert({
            "name": key,
            "value": json.dumps(value) if not isinstance(value, str) else value,
            "updated_at": now,
        }).execute()


def load_engine_state() -> dict:
    sb = _get_client()
    resp = sb.table("engine_state").select("*").execute()
    state = {}
    for row in (resp.data or []):
        try:
            state[row["name"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            state[row["name"]] = row["value"]
    return state


# ============================================================
# ENGINE LOG
# ============================================================

def log_engine_event(cycle_id: str, event_type: str, details: Any = None, severity: str = "info") -> None:
    sb = _get_client()
    sb.table("engine_log").insert({
        "cycle_id": cycle_id,
        "event_type": event_type,
        "details_json": json.dumps(details) if details is not None else None,
        "severity": severity,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def get_engine_logs(limit: int = 50) -> list[dict]:
    sb = _get_client()
    resp = (sb.table("engine_log")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute())
    return resp.data or []


# ============================================================
# TRADE SIGNALS
# ============================================================

def save_trade_signal(signal: dict) -> None:
    sb = _get_client()
    sb.table("trade_signals").insert({
        "symbol": signal["symbol"],
        "strategy": signal["strategy"],
        "signal_type": signal.get("signal_type", "unknown"),
        "signal_json": json.dumps(signal),
        "executed": signal.get("executed", False),
        "created_at": signal.get("created_at", datetime.now(timezone.utc).isoformat()),
    }).execute()


def get_trade_signals(limit: int = 50) -> list[dict]:
    sb = _get_client()
    resp = (sb.table("trade_signals")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute())
    return resp.data or []


# ============================================================
# TRADE OUTCOMES
# ============================================================

def save_trade_outcome(outcome: dict) -> None:
    sb = _get_client()
    sb.table("trade_outcomes").insert({
        "order_id": outcome.get("order_id"),
        "symbol": outcome["symbol"],
        "strategy": outcome["strategy"],
        "side": outcome["side"],
        "entry_price": outcome["entry_price"],
        "exit_price": outcome.get("exit_price"),
        "quantity": outcome["quantity"],
        "pnl": outcome.get("pnl"),
        "pnl_pct": outcome.get("pnl_pct"),
        "duration_seconds": outcome.get("duration_seconds"),
        "regime_at_entry": outcome.get("regime_at_entry"),
        "features_json": json.dumps(outcome["features"]) if outcome.get("features") else None,
        "status": outcome.get("status", "open"),
        "opened_at": outcome.get("opened_at", datetime.now(timezone.utc).isoformat()),
        "closed_at": outcome.get("closed_at"),
    }).execute()


def list_trade_outcomes(status: str | None = None, limit: int = 100) -> list[dict]:
    sb = _get_client()
    query = sb.table("trade_outcomes").select("*")
    if status:
        query = query.eq("status", status)
    resp = query.order("opened_at", desc=True).limit(limit).execute()
    return resp.data or []


# ============================================================
# SYSTEM CONTROLS
# ============================================================

def set_system_control(name: str, value: str) -> None:
    sb = _get_client()
    sb.table("system_controls").upsert({
        "name": name,
        "value": value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def get_system_control(name: str) -> str | None:
    sb = _get_client()
    resp = sb.table("system_controls").select("value").eq("name", name).execute()
    return resp.data[0]["value"] if resp.data else None


# ============================================================
# TRAILING STOPS
# ============================================================

def save_trailing_stop(stop: dict) -> None:
    sb = _get_client()
    sb.table("trailing_stops_active").upsert({
        "symbol": stop["symbol"],
        "side": stop["side"],
        "entry_price": stop["entry_price"],
        "trail_pct": stop["trail_pct"],
        "highest_price": stop.get("highest_price"),
        "lowest_price": stop.get("lowest_price"),
        "stop_price": stop["stop_price"],
        "status": stop.get("status", "active"),
        "created_at": stop.get("created_at", datetime.now(timezone.utc).isoformat()),
    }, on_conflict="symbol,side").execute()


def list_trailing_stops(status: str = "active") -> list[dict]:
    sb = _get_client()
    resp = sb.table("trailing_stops_active").select("*").eq("status", status).execute()
    return resp.data or []


def delete_trailing_stop(symbol: str, side: str) -> None:
    sb = _get_client()
    sb.table("trailing_stops_active").delete().eq("symbol", symbol).eq("side", side).execute()


# ============================================================
# CIRCUIT BREAKER (via system_controls)
# ============================================================

def save_circuit_breaker_state(state: dict) -> None:
    set_system_control("circuit_breaker", json.dumps(state))


def load_circuit_breaker_state() -> dict:
    raw = get_system_control("circuit_breaker")
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


# ============================================================
# FEAR & GREED
# ============================================================

def save_fear_greed(data: dict) -> None:
    sb = _get_client()
    sb.table("fear_greed").insert({
        "value": data["value"],
        "classification": data["classification"],
        "source": data.get("source", "alternative.me"),
        "collected_at": data.get("collected_at", datetime.now(timezone.utc).isoformat()),
    }).execute()


# ============================================================
# SYSTEM ALERTS
# ============================================================

def log_alert(severity: str, message: str) -> None:
    sb = _get_client()
    sb.table("system_alerts").insert({
        "severity": severity,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


# ============================================================
# STRATEGY STATS
# ============================================================

def save_strategy_stats(strategy_id: str, stats: dict) -> None:
    sb = _get_client()
    sb.table("strategy_stats").upsert({
        "strategy_id": strategy_id,
        "stats_json": json.dumps(stats),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def get_strategy_stats(strategy_id: str) -> dict | None:
    sb = _get_client()
    resp = sb.table("strategy_stats").select("stats_json").eq("strategy_id", strategy_id).execute()
    if resp.data:
        try:
            return json.loads(resp.data[0]["stats_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    return None


# ============================================================
# ICT TRADES JOURNAL
# ============================================================

def save_ict_trade(entry: dict) -> None:
    sb = _get_client()
    sb.table("ict_trades_journal").insert(entry).execute()


def get_ict_trades(limit: int = 100) -> list[dict]:
    sb = _get_client()
    resp = sb.table("ict_trades_journal").select("*").order("created_at", desc=True).limit(limit).execute()
    return resp.data or []


# ============================================================
# MEMORY EPISODES
# ============================================================

def save_memory_episode(episode: dict) -> None:
    sb = _get_client()
    sb.table("memory_episodes").insert({
        "symbol": episode["symbol"],
        "strategy": episode["strategy"],
        "features_json": json.dumps(episode["features"]),
        "result_json": json.dumps(episode["result"]) if episode.get("result") else None,
        "fingerprint": episode["fingerprint"],
        "created_at": episode.get("created_at", datetime.now(timezone.utc).isoformat()),
    }).execute()


# ============================================================
# ML MODELS
# ============================================================

def save_ml_model(model_id: str, model_data: dict) -> None:
    sb = _get_client()
    sb.table("ml_models").upsert({
        "model_id": model_id,
        "model_json": json.dumps(model_data),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def get_ml_model(model_id: str) -> dict | None:
    sb = _get_client()
    resp = sb.table("ml_models").select("model_json").eq("model_id", model_id).execute()
    if resp.data:
        try:
            return json.loads(resp.data[0]["model_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    return None
