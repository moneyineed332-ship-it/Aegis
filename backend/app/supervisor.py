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


def _market_prices() -> dict:
    """Last known market prices by symbol (empty dict if unavailable)."""
    try:
        return {s["symbol"]: s["price"] for s in storage.list_market_snapshots(limit=50)}
    except Exception:
        return {}


def portfolio_equity(capital: float | None = None) -> float:
    """Capital + unrealized PnL valued at last market prices.

    Falls back to entry price per position when no snapshot exists,
    so equity is never worse than cost basis in that case.
    """
    from . import position_monitor
    cap = capital if capital is not None else config.PAPER_CAPITAL
    try:
        summary = position_monitor.compute_portfolio_summary(
            storage.list_positions(), _market_prices(), cap
        )
        return float(summary["equity"])
    except Exception:
        return cap


def _check_drawdown() -> dict:
    """Check if portfolio drawdown exceeds max threshold."""
    capital = config.PAPER_CAPITAL
    equity = portfolio_equity(capital)
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
    """Check individual positions for excessive loss (market prices).

    A position losing more than POSITION_MAX_LOSS_PCT is critical;
    an oversized position (vs MAX_ORDER_NOTIONAL) is a warning.
    """
    from . import position_monitor
    positions = storage.list_positions()
    prices = _market_prices()
    alerts = []
    max_loss_pct = config.POSITION_MAX_LOSS_PCT * 100
    for p in positions:
        if p["quantity"] == 0:
            continue
        symbol = p["symbol"]
        detail = position_monitor.compute_position_pnl(
            p, prices.get(symbol, p["average_price"])
        )
        loss_pct = detail["unrealized_pnl_pct"]
        if loss_pct <= -max_loss_pct:
            alerts.append({
                "type": "position_loss",
                "severity": "critical",
                "symbol": symbol,
                "pct": loss_pct,
                "message": f"Position {symbol} down {loss_pct:.2f}% (limit: -{max_loss_pct:.0f}%)",
            })
        notional = detail["notional"]
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

    # Individual position losses feed the overall status too.
    position_alerts = _check_position_losses()
    position_critical = [a for a in position_alerts if a.get("severity") == "critical"]
    if position_critical:
        checks.append({
            "name": "position_loss",
            "status": "critical",
            "value": min(a["pct"] for a in position_critical),
            "threshold": -config.POSITION_MAX_LOSS_PCT * 100,
            "message": "; ".join(a["message"] for a in position_critical),
        })
        critical = [c for c in checks if c["status"] == "critical"]

    overall = "critical" if critical else "healthy"

    # Position count
    positions = storage.list_positions()
    total_exposure = sum(abs(p["quantity"] * p["average_price"]) for p in positions)
    capital = config.PAPER_CAPITAL
    equity = portfolio_equity(capital)

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
        # Flatten paper positions first so no losing position is left
        # open behind the kill switch, then auto-activate it.
        closed = flatten_all_positions(reason="auto_kill_switch")
        if closed:
            actions.append({
                "action": "positions_flattened",
                "closed": closed,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
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


def flatten_all_positions(reason: str = "manual") -> list[dict]:
    """Close every open paper position at last market price.

    Records a closing order per position and removes it from storage.
    Positions without any price reference are left untouched and reported.
    """
    prices = _market_prices()
    closed = []
    for p in storage.list_positions():
        qty = p.get("quantity", 0)
        if not qty:
            continue
        symbol = p["symbol"]
        price = prices.get(symbol, p.get("average_price", 0))
        if not price:
            closed.append({"symbol": symbol, "closed": False, "reason": "no_price"})
            continue
        side = "sell" if qty > 0 else "buy"
        quantity = abs(qty)
        storage.save_order_and_position(
            {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "reference_price": price,
                "notional": quantity * price,
                "status": "filled_flattened",
                "strategy": "supervisor",
                "mode": "paper",
                "reason": reason,
            },
            None,
        )
        closed.append({"symbol": symbol, "closed": True, "quantity": quantity, "price": price})
        logger.warning("SUPERVISOR: flattened %s (%s)", symbol, reason)
    return closed


def get_system_summary() -> dict:
    """Get a summary of the full system state for the dashboard."""
    positions = storage.list_positions()
    capital = config.PAPER_CAPITAL
    equity = portfolio_equity(capital)
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
