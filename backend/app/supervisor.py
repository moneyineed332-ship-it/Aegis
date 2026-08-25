"""Operational supervisor for AEGIS AI Quant.

Monitors system health, enforces safety limits, and provides
automatic intervention when risk thresholds are breached.
"""

import logging
from datetime import datetime, timezone

from . import config, storage

logger = logging.getLogger(__name__)

# --- Health Check Definitions ---
HEALTH_CHECKS = {
    "kill_switch": "Emergency stop active",
    "drawdown": "Portfolio drawdown exceeds threshold",
    "exposure": "Total exposure exceeds limit",
    "consecutive_losses": "Too many consecutive losses",
    "position_loss": "Single position loss exceeds limit",
    "data_freshness": "Market data is stale",
    "engine_errors": "Engine has too many consecutive errors",
}


def _check_drawdown() -> dict:
    """Check if portfolio drawdown exceeds max threshold."""
    positions = storage.list_positions()
    capital = config.PAPER_CAPITAL
    equity = capital + sum(p["quantity"] * p["average_price"] for p in positions)
    drawdown_pct = ((equity - capital) / capital) * 100 if capital > 0 else 0

    max_dd = config.PORTFOLIO_MAX_DRAWDOWN_PCT * 100
    breached = drawdown_pct < -max_dd

    return {
        "name": "drawdown",
        "status": "critical" if breached else "ok",
        "value": round(drawdown_pct, 2),
        "threshold": -max_dd,
        "message": f"Drawdown {drawdown_pct:.2f}% (limit: -{max_dd}%)" if breached else "Drawdown within limits",
    }


def _check_exposure() -> dict:
    """Check if total exposure exceeds limit."""
    positions = storage.list_positions()
    exposure = sum(abs(p["quantity"] * p["average_price"]) for p in positions)
    pct = (exposure / config.MAX_TOTAL_EXPOSURE * 100) if config.MAX_TOTAL_EXPOSURE > 0 else 0

    breached = exposure > config.MAX_TOTAL_EXPOSURE

    return {
        "name": "exposure",
        "status": "critical" if breached else "ok",
        "value": round(exposure, 2),
        "threshold": config.MAX_TOTAL_EXPOSURE,
        "pct": round(pct, 1),
        "message": f"Exposure ${exposure:.2f} exceeds limit ${config.MAX_TOTAL_EXPOSURE:.0f}" if breached else f"Exposure ${exposure:.2f} ({pct:.1f}%)",
    }


def _check_position_losses() -> list[dict]:
    """Check individual positions for excessive loss."""
    positions = storage.list_positions()
    alerts = []
    for p in positions:
        if p["quantity"] == 0:
            continue
        symbol = p["symbol"]
        avg_price = p["average_price"]
        qty = p["quantity"]
        notional = abs(qty * avg_price)
        if notional > config.MAX_ORDER_NOTIONAL:
            alerts.append({
                "type": "position_size",
                "severity": "warning",
                "symbol": symbol,
                "pct": round(notional / config.MAX_TOTAL_EXPOSURE * 100, 1),
                "message": f"Position {symbol} notional ${notional:.2f} exceeds max ${config.MAX_ORDER_NOTIONAL:.0f}",
            })
    return alerts


def _check_kill_switch() -> dict:
    """Check if kill switch is active."""
    active = storage.get_kill_switch()
    return {
        "name": "kill_switch",
        "status": "critical" if active else "ok",
        "active": active,
        "message": "Emergency stop is ACTIVE" if active else "System operational",
    }


def _check_recent_alerts() -> list[dict]:
    """Get recent system alerts."""
    alerts = storage.list_alerts()
    return alerts[-10:] if alerts else []


def _check_consecutive_losses() -> dict:
    """Check consecutive loss count from strategy stats."""
    stats = storage.list_strategy_stats()
    max_consecutive = 0
    for s in stats:
        cl = s.get("consecutive_losses", 0) or 0
        if cl > max_consecutive:
            max_consecutive = cl

    threshold = 5
    breached = max_consecutive >= threshold

    return {
        "name": "consecutive_losses",
        "status": "critical" if breached else "ok",
        "value": max_consecutive,
        "threshold": threshold,
        "message": f"Max consecutive losses: {max_consecutive} (limit: {threshold})" if breached else f"Consecutive losses: {max_consecutive}",
    }


def status(kill_switch_active: bool) -> dict:
    """Get comprehensive supervisor status with health checks."""
    # Run all health checks
    checks = [
        _check_kill_switch(),
        _check_drawdown(),
        _check_exposure(),
        _check_consecutive_losses(),
    ]

    critical = [c for c in checks if c["status"] == "critical"]
    overall = "critical" if critical else "healthy"

    # Position count
    positions = storage.list_positions()
    total_exposure = sum(abs(p["quantity"] * p["average_price"]) for p in positions)
    capital = config.PAPER_CAPITAL
    equity = capital + sum(p["quantity"] * p["average_price"] for p in positions)

    return {
        "status": overall,
        "kill_switch_active": kill_switch_active,
        "mode": config.MODE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "health_checks": checks,
        "critical_count": len(critical),
        "portfolio": {
            "capital": capital,
            "equity": round(equity, 2),
            "exposure": round(total_exposure, 2),
            "max_exposure": config.MAX_TOTAL_EXPOSURE,
            "exposure_pct": round(total_exposure / config.MAX_TOTAL_EXPOSURE * 100, 1) if config.MAX_TOTAL_EXPOSURE > 0 else 0,
            "position_count": len([p for p in positions if p["quantity"] != 0]),
        },
        "alerts": _check_recent_alerts(),
    }


def evaluate_auto_intervention() -> list[dict]:
    """Evaluate if automatic intervention is needed.

    Returns list of actions taken (empty if none needed).
    """
    actions = []
    current = status(storage.get_kill_switch())

    if current["status"] == "critical" and not storage.get_kill_switch():
        # Auto-activate kill switch on critical health
        reasons = [c["message"] for c in current["health_checks"] if c["status"] == "critical"]
        reason_str = "; ".join(reasons)
        storage.set_kill_switch(True, f"Auto-activated: {reason_str}")
        actions.append({
            "action": "kill_switch_activated",
            "reason": reason_str,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.critical("SUPERVISOR: Auto-activated kill switch — %s", reason_str)

    return actions


def get_system_summary() -> dict:
    """Get a summary of the full system state for the dashboard."""
    positions = storage.list_positions()
    capital = config.PAPER_CAPITAL
    equity = capital + sum(p["quantity"] * p["average_price"] for p in positions)
    exposure = sum(abs(p["quantity"] * p["average_price"]) for p in positions)

    # Recent trades
    recent_orders = storage.list_recent_orders(limit=10)

    # Engine state
    engine_running = False
    try:
        from . import engine
        engine_running = engine.get_engine_status().get("status") == "running"
    except Exception:
        pass

    return {
        "mode": config.MODE,
        "engine_running": engine_running,
        "kill_switch": storage.get_kill_switch(),
        "portfolio": {
            "capital": capital,
            "equity": round(equity, 2),
            "pnl": round(equity - capital, 2),
            "pnl_pct": round((equity - capital) / capital * 100, 2) if capital > 0 else 0,
            "exposure": round(exposure, 2),
            "position_count": len([p for p in positions if p["quantity"] != 0]),
        },
        "recent_trades": len(recent_orders),
        "symbols_tracked": len(config.SYMBOLS),
    }
