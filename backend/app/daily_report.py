"""Daily Report — PnL summary, trade log, regime history, performance metrics."""

import logging
from datetime import datetime, timezone, timedelta
from statistics import fmean

from . import config, storage

logger = logging.getLogger(__name__)


def generate_daily_report(date_str: str | None = None) -> dict:
    """Generate a comprehensive daily report.

    Args:
        date_str: Date in YYYY-MM-DD format. Defaults to today (UTC).

    Returns:
        Full daily report with PnL, trades, regimes, and performance.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Parse the date
    try:
        report_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        report_date = datetime.now(timezone.utc)
        date_str = report_date.strftime("%Y-%m-%d")

    day_start = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    # Get all positions and compute portfolio state
    positions = storage.list_positions()
    snapshots = storage.list_market_snapshots(limit=100)
    prices = {s["symbol"]: s["price"] for s in snapshots}

    # Portfolio value
    capital = config.PAPER_CAPITAL
    total_unrealized_pnl = 0.0
    position_details = []

    for pos in positions:
        current_price = prices.get(pos["symbol"], pos["average_price"])
        unrealized_pnl = (current_price - pos["average_price"]) * pos["quantity"]
        total_unrealized_pnl += unrealized_pnl
        pct = ((current_price / pos["average_price"]) - 1) * 100 if pos["average_price"] > 0 else 0
        position_details.append({
            "symbol": pos["symbol"],
            "side": pos.get("side", "long"),
            "quantity": pos["quantity"],
            "entry_price": pos["average_price"],
            "current_price": current_price,
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(pct, 2),
        })

    equity = capital + total_unrealized_pnl

    # Get trade outcomes for today
    all_outcomes = storage.list_trade_outcomes(limit=100)
    daily_outcomes = [
        o for o in all_outcomes
        if o.get("closed_at") and o["closed_at"][:10] == date_str
    ]

    # Compute trade stats
    total_trades = len(daily_outcomes)
    winning_trades = sum(1 for o in daily_outcomes if (o.get("pnl") or 0) > 0)
    losing_trades = sum(1 for o in daily_outcomes if (o.get("pnl") or 0) < 0)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    total_pnl = sum(o.get("pnl") or 0 for o in daily_outcomes)
    avg_win = fmean([o["pnl"] for o in daily_outcomes if (o.get("pnl") or 0) > 0]) if winning_trades > 0 else 0
    avg_loss = fmean([o["pnl"] for o in daily_outcomes if (o.get("pnl") or 0) < 0]) if losing_trades > 0 else 0
    profit_factor = abs(avg_win * winning_trades) / abs(avg_loss * losing_trades) if losing_trades > 0 and avg_loss != 0 else float("inf")

    # Strategy breakdown
    strategy_stats: dict[str, dict] = {}
    for o in daily_outcomes:
        strat = o.get("strategy", "unknown")
        if strat not in strategy_stats:
            strategy_stats[strat] = {"trades": 0, "wins": 0, "pnl": 0.0}
        strategy_stats[strat]["trades"] += 1
        if (o.get("pnl") or 0) > 0:
            strategy_stats[strat]["wins"] += 1
        strategy_stats[strat]["pnl"] += o.get("pnl") or 0

    for strat in strategy_stats:
        s = strategy_stats[strat]
        s["win_rate"] = round(s["wins"] / s["trades"] * 100, 1) if s["trades"] > 0 else 0
        s["pnl"] = round(s["pnl"], 2)

    # Get engine events for regime history
    engine_events = storage.list_engine_logs(limit=200)
    regime_events = [
        e for e in engine_events
        if e.get("event_type") == "regime_classified"
        and e.get("created_at", "")[:10] == date_str
    ]

    regime_history = []
    for e in regime_events:
        detail = e.get("details") or {}
        if isinstance(detail, str):
            import json
            try:
                detail = json.loads(detail)
            except (json.JSONDecodeError, TypeError):
                detail = {}
        regime_history.append({
            "time": e.get("created_at"),
            "regime": detail.get("regime", "unknown"),
            "confidence": detail.get("confidence", 0),
        })

    # Get recent alerts
    alerts = storage.list_alerts(limit=50)
    daily_alerts = [a for a in alerts if a.get("created_at", "")[:10] == date_str]

    return {
        "date": date_str,
        "portfolio": {
            "equity": round(equity, 2),
            "capital": round(capital, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "position_count": len(positions),
            "positions": position_details,
        },
        "trades": {
            "total": total_trades,
            "wins": winning_trades,
            "losses": losing_trades,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "∞",
        },
        "strategies": strategy_stats,
        "regime_history": regime_history,
        "alerts": {
            "total": len(daily_alerts),
            "critical": sum(1 for a in daily_alerts if a.get("severity") == "critical"),
            "warning": sum(1 for a in daily_alerts if a.get("severity") == "warning"),
        },
        "summary": _build_summary(equity, total_pnl, win_rate, total_trades, regime_history),
    }


def _build_summary(equity: float, pnl: float, win_rate: float, trade_count: int, regimes: list) -> str:
    """Build a human-readable daily summary."""
    pnl_emoji = "📈" if pnl >= 0 else "📉"
    regime_summary = "N/A"
    if regimes:
        regime_counts: dict[str, int] = {}
        for r in regimes:
            reg = r.get("regime", "unknown")
            regime_counts[reg] = regime_counts.get(reg, 0) + 1
        regime_summary = ", ".join(f"{k}: {v}" for k, v in regime_counts.items())

    return (
        f"Équité: ${equity:,.2f} | "
        f"{pnl_emoji} PnL: ${pnl:+,.2f} | "
        f"Win Rate: {win_rate:.1f}% | "
        f"Trades: {trade_count} | "
        f"Régimes: {regime_summary}"
    )
