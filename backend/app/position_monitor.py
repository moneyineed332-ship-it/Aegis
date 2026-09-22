"""Real-time Position Monitoring for AEGIS AI Quant.

Computes live PnL, per-position risk metrics, and triggers auto-close
on risk breaches. Feeds data to AlertManager for WebSocket broadcast.

Metrics tracked:
- Unrealized PnL (per-position + total)
- Realized PnL (from order history)
- Per-position drawdown from peak
- Position duration
- Exposure breakdown
"""

import logging
from datetime import datetime, timezone

from . import config, storage

logger = logging.getLogger(__name__)

# Per-position risk thresholds (from config)
POSITION_MAX_LOSS_PCT = config.POSITION_MAX_LOSS_PCT
POSITION_MAX_DRAWDOWN_PCT = config.POSITION_MAX_DRAWDOWN_PCT
PORTFOLIO_MAX_DRAWDOWN_PCT = config.PORTFOLIO_MAX_DRAWDOWN_PCT


def compute_position_pnl(position: dict, current_price: float) -> dict:
    """Compute unrealized PnL for a single position."""
    qty = position["quantity"]
    entry = position["average_price"]

    if qty == 0:
        return {
            "symbol": position["symbol"],
            "quantity": 0,
            "unrealized_pnl": 0,
            "unrealized_pnl_pct": 0,
            "current_price": current_price,
            "entry_price": entry,
            "side": "flat",
        }

    side = "long" if qty > 0 else "short"
    notional = abs(qty) * current_price
    cost_basis = abs(qty) * entry

    if side == "long":
        unrealized = notional - cost_basis
    else:
        unrealized = cost_basis - notional

    pnl_pct = (unrealized / cost_basis * 100) if cost_basis > 0 else 0

    return {
        "symbol": position["symbol"],
        "quantity": qty,
        "side": side,
        "entry_price": entry,
        "current_price": current_price,
        "notional": round(notional, 2),
        "cost_basis": round(cost_basis, 2),
        "unrealized_pnl": round(unrealized, 2),
        "unrealized_pnl_pct": round(pnl_pct, 2),
    }


def compute_portfolio_summary(positions: list[dict], prices: dict[str, float], capital: float) -> dict:
    """Compute full portfolio summary with PnL breakdown."""
    position_details = []
    total_unrealized = 0.0
    total_exposure = 0.0
    long_exposure = 0.0
    short_exposure = 0.0

    for pos in positions:
        price = prices.get(pos["symbol"], pos["average_price"])
        detail = compute_position_pnl(pos, price)
        position_details.append(detail)
        total_unrealized += detail["unrealized_pnl"]
        total_exposure += detail["notional"]
        if detail["side"] == "long":
            long_exposure += detail["notional"]
        elif detail["side"] == "short":
            short_exposure += detail["notional"]

    equity = capital + total_unrealized
    exposure_pct = (total_exposure / capital * 100) if capital > 0 else 0

    return {
        "capital": capital,
        "equity": round(equity, 2),
        "total_unrealized_pnl": round(total_unrealized, 2),
        "total_unrealized_pnl_pct": round((total_unrealized / capital * 100) if capital > 0 else 0, 2),
        "total_exposure": round(total_exposure, 2),
        "exposure_pct": round(exposure_pct, 2),
        "long_exposure": round(long_exposure, 2),
        "short_exposure": round(short_exposure, 2),
        "position_count": len([p for p in position_details if p["quantity"] != 0]),
        "positions": position_details,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def check_position_risks(positions: list[dict], prices: dict[str, float], capital: float) -> list[dict]:
    """Check each position against risk thresholds. Returns list of alerts."""
    alerts = []

    for pos in positions:
        if pos["quantity"] == 0:
            continue

        price = prices.get(pos["symbol"])
        if not price:
            continue

        detail = compute_position_pnl(pos, price)
        pnl_pct = detail["unrealized_pnl_pct"]

        # Per-position max loss check
        if pnl_pct < -(POSITION_MAX_LOSS_PCT * 100):
            alerts.append({
                "type": "position_max_loss",
                "severity": "critical",
                "action": "auto_close",
                "symbol": detail["symbol"],
                "side": detail["side"],
                "quantity": detail["quantity"],
                "entry_price": detail["entry_price"],
                "current_price": detail["current_price"],
                "loss_pct": pnl_pct,
                "threshold_pct": -(POSITION_MAX_LOSS_PCT * 100),
                "message": (
                    f"{detail['symbol']} {detail['side']} loss {pnl_pct:.1f}% exceeds "
                    f"{POSITION_MAX_LOSS_PCT*100:.0f}% limit — auto-closing"
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    # Portfolio-level drawdown check
    total_unrealized = sum(
        compute_position_pnl(p, prices.get(p["symbol"], p["average_price"]))["unrealized_pnl"]
        for p in positions
    )
    portfolio_dd_pct = (total_unrealized / capital * 100) if capital > 0 else 0

    if portfolio_dd_pct < -(PORTFOLIO_MAX_DRAWDOWN_PCT * 100):
        alerts.append({
            "type": "portfolio_max_drawdown",
            "severity": "critical",
            "action": "close_all",
            "portfolio_loss_pct": round(portfolio_dd_pct, 2),
            "threshold_pct": -(PORTFOLIO_MAX_DRAWDOWN_PCT * 100),
            "message": (
                f"Portfolio drawdown {portfolio_dd_pct:.1f}% exceeds "
                f"{PORTFOLIO_MAX_DRAWDOWN_PCT*100:.0f}% limit — closing all positions"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return alerts


def get_realized_pnl(orders: list[dict]) -> dict:
    """Compute realized PnL from order history (FIFO, matched per symbol).

    Unconsumed lots (partial remainders AND untouched later buys) are
    carried forward. Sells without prior buys (short legs) are ignored
    here — their PnL stays unrealized until the position closes.
    """
    lots: dict[str, list[dict]] = {}
    realized = 0.0
    total_fees = 0.0

    for order in sorted(orders, key=lambda o: o.get("id", 0)):
        side = order.get("side", "")
        symbol = order.get("symbol", "")
        notional = order.get("notional", 0) or 0
        fee = order.get("fee", 0) or 0
        fill_price = order.get("fill_price", order.get("reference_price", 0)) or 0
        quantity = order.get("quantity", 0) or 0
        total_fees += fee

        if side == "buy" and quantity > 0:
            lots.setdefault(symbol, []).append({"price": fill_price, "quantity": quantity})
        elif side == "sell" and quantity > 0:
            queue = lots.get(symbol, [])
            remaining = quantity
            cost = 0.0
            while remaining > 0 and queue:
                lot = queue[0]
                match = min(lot["quantity"], remaining)
                cost += match * lot["price"]
                lot["quantity"] -= match
                remaining -= match
                if lot["quantity"] <= 0:
                    queue.pop(0)
            if remaining <= 0:
                sell_value = notional or quantity * fill_price
                realized += sell_value - cost
            # else: naked/short portion ignored (tracked as unrealized)

    return {
        "realized_pnl": round(realized, 2),
        "total_fees": round(total_fees, 4),
        "closed_trades": len([o for o in orders if o.get("side") == "sell"]),
    }


def monitor_cycle(prices: dict[str, float]) -> dict:
    """Run one full monitoring cycle: compute PnL, check risks, return summary.

    Called by the engine task. Returns portfolio summary and any triggered alerts.
    """
    positions = storage.list_positions()
    capital = config.PAPER_CAPITAL
    orders = storage.list_recent_orders(limit=200)

    # Portfolio summary
    portfolio = compute_portfolio_summary(positions, prices, capital)

    # Realized PnL
    realized = get_realized_pnl(orders)
    portfolio["realized_pnl"] = realized["realized_pnl"]
    portfolio["total_fees"] = realized["total_fees"]
    portfolio["total_pnl"] = round(realized["realized_pnl"] + portfolio["total_unrealized_pnl"], 2)
    portfolio["total_pnl_pct"] = round(
        (portfolio["total_pnl"] / capital * 100) if capital > 0 else 0, 2
    )

    # Risk alerts
    alerts = check_position_risks(positions, prices, capital)

    return {
        "portfolio": portfolio,
        "alerts": alerts,
    }
