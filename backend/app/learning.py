"""Learning module: trade outcome tracking, strategy scoring, adaptive tuning.

Core loop:
  1. Track each trade: signal → entry → exit → PnL → regime context
  2. Score strategies: win rate, profit factor, Sharpe, regime fit
  3. Adapt advisor: boost/penalize strategies based on performance
  4. Consolidate memory: extract patterns from winning/losing trades
"""

import math
from datetime import datetime, timezone
from statistics import fmean, stdev

from . import storage


# ============================================================
# 1. Trade Outcome Tracking
# ============================================================

def record_trade_entry(order_id: str, symbol: str, strategy: str, side: str,
                       entry_price: float, quantity: float, regime: str | None = None,
                       features: dict | None = None) -> dict:
    """Record a new trade entry for tracking."""
    outcome = {
        "order_id": order_id,
        "symbol": symbol,
        "strategy": strategy,
        "side": side,
        "entry_price": entry_price,
        "quantity": quantity,
        "regime_at_entry": regime,
        "features": features,
        "status": "open",
        "opened_at": datetime.now(timezone.utc).isoformat(),
    }
    return storage.save_trade_outcome(outcome)


def record_trade_exit(order_id: str, exit_price: float, symbol: str | None = None) -> dict:
    """Record trade exit, compute PnL, update stats.

    Looks up the open trade by order_id first; if not found, falls back
    to looking up by symbol (handles the case where the sell order_id
    differs from the original buy order_id).
    """
    outcomes = storage.list_trade_outcomes(status="open", limit=500)
    trade = next((o for o in outcomes if o["order_id"] == order_id), None)
    if not trade and symbol:
        trade = next((o for o in outcomes if o["symbol"] == symbol), None)
    if not trade:
        return {"error": f"No open trade with order_id {order_id} (symbol={symbol})"}

    # Compute PnL
    entry = trade["entry_price"]
    qty = trade["quantity"]
    side = trade["side"]

    if side == "buy":
        pnl = (exit_price - entry) * qty
        pnl_pct = (exit_price / entry - 1) * 100 if entry > 0 else 0
    else:
        pnl = (entry - exit_price) * qty
        pnl_pct = (entry / exit_price - 1) * 100 if exit_price > 0 else 0

    # Compute duration
    opened = datetime.fromisoformat(trade["opened_at"])
    duration = int((datetime.now(timezone.utc) - opened).total_seconds())

    storage.update_trade_outcome_close(order_id, exit_price, pnl, pnl_pct, duration)

    # Update strategy stats
    _update_strategy_stats(trade["strategy"], pnl, pnl_pct, trade.get("regime_at_entry"))

    return {
        "order_id": order_id,
        "symbol": trade["symbol"],
        "strategy": trade["strategy"],
        "entry_price": entry,
        "exit_price": exit_price,
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "duration_seconds": duration,
    }


# ============================================================
# 2. Strategy Performance Scoring
# ============================================================

def _update_strategy_stats(strategy_id: str, pnl: float, pnl_pct: float, regime: str | None = None) -> None:
    """Update running stats for a strategy after a trade closes."""
    stats = storage.load_strategy_stats(strategy_id) or _empty_stats(strategy_id)

    stats["total_trades"] += 1
    stats["total_pnl"] = round(stats["total_pnl"] + pnl, 2)
    stats["total_pnl_pct"] = round(stats["total_pnl_pct"] + pnl_pct, 4)
    stats["pnl_history"].append(round(pnl, 2))

    if pnl > 0:
        stats["wins"] += 1
        stats["win_pnl_sum"] = round(stats.get("win_pnl_sum", 0) + pnl, 2)
    else:
        stats["losses"] += 1
        stats["loss_pnl_sum"] = round(stats.get("loss_pnl_sum", 0) + abs(pnl), 2)

    # Win rate
    stats["win_rate"] = round(stats["wins"] / max(stats["total_trades"], 1), 4)

    # Profit factor
    gross_profit = stats.get("win_pnl_sum", 0)
    gross_loss = stats.get("loss_pnl_sum", 0)
    stats["profit_factor"] = round(gross_profit / max(gross_loss, 0.01), 4)

    # Average PnL
    stats["avg_pnl"] = round(fmean(stats["pnl_history"][-100:]), 2) if stats["pnl_history"] else 0

    # Max consecutive losses
    _update_consecutive_losses(stats, pnl)

    # Regime performance
    if regime:
        if regime not in stats.get("regime_performance", {}):
            stats.setdefault("regime_performance", {})[regime] = {"trades": 0, "wins": 0, "total_pnl": 0}
        rp = stats["regime_performance"][regime]
        rp["trades"] += 1
        rp["total_pnl"] = round(rp["total_pnl"] + pnl, 2)
        if pnl > 0:
            rp["wins"] += 1
        rp["win_rate"] = round(rp["wins"] / max(rp["trades"], 1), 4)

    # Score: composite metric for advisor ranking
    stats["score"] = _compute_score(stats)

    # Keep pnl_history capped
    if len(stats["pnl_history"]) > 500:
        stats["pnl_history"] = stats["pnl_history"][-500:]

    stats["updated_at"] = datetime.now(timezone.utc).isoformat()
    storage.save_strategy_stats(strategy_id, stats)


def _update_consecutive_losses(stats: dict, pnl: float) -> None:
    """Track consecutive losses and max streak."""
    if pnl < 0:
        stats["consecutive_losses"] = stats.get("consecutive_losses", 0) + 1
        stats["max_consecutive_losses"] = max(
            stats.get("max_consecutive_losses", 0),
            stats["consecutive_losses"],
        )
    else:
        stats["consecutive_losses"] = 0


def _compute_score(stats: dict) -> float:
    """Compute a composite performance score (0-100).

    Components:
    - Win rate (30%)
    - Profit factor (30%)
    - Consistency — inverse of max consecutive losses (20%)
    - Trade count bonus (20%) — more trades = more reliable score
    """
    win_rate = stats.get("win_rate", 0)
    pf = min(stats.get("profit_factor", 0), 5)  # Cap at 5
    max_loss_streak = stats.get("max_consecutive_losses", 0)
    total_trades = stats.get("total_trades", 0)

    # Consistency: 1.0 if no losses, decreases with streaks
    consistency = max(0, 1.0 - max_loss_streak * 0.15)

    # Trade count: saturates at 50 trades
    count_factor = min(1.0, total_trades / 50)

    score = (
        win_rate * 30
        + (pf / 5) * 30
        + consistency * 20
        + count_factor * 20
    )
    return round(min(100, max(0, score)), 2)


def _empty_stats(strategy_id: str) -> dict:
    """Return empty stats structure for a new strategy."""
    return {
        "strategy_id": strategy_id,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0,
        "total_pnl": 0,
        "total_pnl_pct": 0,
        "avg_pnl": 0,
        "profit_factor": 0,
        "score": 0,
        "consecutive_losses": 0,
        "max_consecutive_losses": 0,
        "win_pnl_sum": 0,
        "loss_pnl_sum": 0,
        "pnl_history": [],
        "regime_performance": {},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_strategy_stats(strategy_id: str) -> dict:
    """Get stats for a single strategy."""
    return storage.load_strategy_stats(strategy_id) or _empty_stats(strategy_id)


def get_all_strategy_stats() -> list[dict]:
    """Get stats for all strategies, sorted by score."""
    stats = storage.list_strategy_stats()
    if not stats:
        return []
    return sorted(stats, key=lambda s: s.get("score", 0), reverse=True)


# ============================================================
# 3. Adaptive Strategy Ranking
# ============================================================

def rank_strategies_for_regime(regime: str) -> list[dict]:
    """Rank strategies by their performance in a given regime.

    Returns list sorted by regime-specific score.
    """
    all_stats = storage.list_strategy_stats()
    ranked = []
    for stats in all_stats:
        regime_perf = stats.get("regime_performance", {}).get(regime, {})
        regime_trades = regime_perf.get("trades", 0)
        regime_win_rate = regime_perf.get("win_rate", 0)
        regime_pnl = regime_perf.get("total_pnl", 0)

        # Regime-specific score
        if regime_trades >= 3:
            regime_score = (
                regime_win_rate * 50
                + min(1.0, regime_pnl / max(abs(regime_pnl) + 100, 1)) * 30
                + min(1.0, regime_trades / 20) * 20
            )
        else:
            # Not enough regime data — fall back to global score
            regime_score = stats.get("score", 0) * 0.5  # Penalize for lack of regime data

        ranked.append({
            "strategy_id": stats.get("strategy_id", "unknown"),
            "global_score": stats.get("score", 0),
            "regime_score": round(regime_score, 2),
            "regime_trades": regime_trades,
            "regime_win_rate": round(regime_win_rate, 4),
            "win_rate": stats.get("win_rate", 0),
            "profit_factor": stats.get("profit_factor", 0),
            "total_trades": stats.get("total_trades", 0),
        })

    ranked.sort(key=lambda s: s["regime_score"], reverse=True)
    return ranked


def get_advisor_weights(regime: str) -> dict:
    """Get strategy recommendation weights for the current regime.

    Returns dict of {strategy_id: weight} where weight is 0-1.
    Strategies with no data get a neutral weight of 0.3.
    """
    ranking = rank_strategies_for_regime(regime)
    if not ranking:
        return {}

    weights = {}
    for r in ranking:
        sid = r["strategy_id"]
        # Map regime_score (0-100) to weight (0.1 - 1.0)
        # Below 20 = avoid, 20-50 = neutral, 50+ = prefer
        score = r["regime_score"]
        if score < 20:
            weight = 0.1
        elif score < 50:
            weight = 0.3 + (score - 20) / 30 * 0.3  # 0.3 - 0.6
        else:
            weight = 0.6 + min(1.0, (score - 50) / 50) * 0.4  # 0.6 - 1.0
        weights[sid] = round(weight, 3)

    return weights


# ============================================================
# 4. Memory Consolidation
# ============================================================

def consolidate_memory(symbol: str) -> dict:
    """Analyze closed trades and extract patterns.

    Identifies:
    - Most profitable regimes for this symbol
    - Most profitable strategies for this symbol
    - Common features in winning vs losing trades
    """
    outcomes = storage.list_trade_outcomes(symbol=symbol, status="closed", limit=200)
    if not outcomes:
        return {"symbol": symbol, "patterns": [], "summary": "No closed trades yet"}

    # By regime
    regime_stats = {}
    for o in outcomes:
        regime = o.get("regime_at_entry", "unknown")
        if regime not in regime_stats:
            regime_stats[regime] = {"trades": 0, "wins": 0, "total_pnl": 0}
        regime_stats[regime]["trades"] += 1
        regime_stats[regime]["total_pnl"] = round(regime_stats[regime]["total_pnl"] + (o.get("pnl") or 0), 2)
        if (o.get("pnl") or 0) > 0:
            regime_stats[regime]["wins"] += 1

    for r in regime_stats:
        regime_stats[r]["win_rate"] = round(regime_stats[r]["wins"] / max(regime_stats[r]["trades"], 1), 4)

    # By strategy
    strategy_stats = {}
    for o in outcomes:
        strat = o.get("strategy", "unknown")
        if strat not in strategy_stats:
            strategy_stats[strat] = {"trades": 0, "wins": 0, "total_pnl": 0}
        strategy_stats[strat]["trades"] += 1
        strategy_stats[strat]["total_pnl"] = round(strategy_stats[strat]["total_pnl"] + (o.get("pnl") or 0), 2)
        if (o.get("pnl") or 0) > 0:
            strategy_stats[strat]["wins"] += 1

    for s in strategy_stats:
        strategy_stats[s]["win_rate"] = round(strategy_stats[s]["wins"] / max(strategy_stats[s]["trades"], 1), 4)

    # Feature patterns in winning vs losing trades
    winning_features = []
    losing_features = []
    for o in outcomes:
        feats = o.get("features")
        if not feats:
            continue
        if (o.get("pnl") or 0) > 0:
            winning_features.append(feats)
        else:
            losing_features.append(feats)

    feature_patterns = _extract_feature_patterns(winning_features, losing_features)

    # Best regime
    best_regime = max(regime_stats.items(), key=lambda x: x[1]["total_pnl"]) if regime_stats else None
    best_strategy = max(strategy_stats.items(), key=lambda x: x[1]["total_pnl"]) if strategy_stats else None

    patterns = []
    if best_regime and best_regime[1]["total_pnl"] > 0:
        patterns.append({
            "type": "best_regime",
            "regime": best_regime[0],
            "pnl": best_regime[1]["total_pnl"],
            "win_rate": best_regime[1]["win_rate"],
            "trades": best_regime[1]["trades"],
        })
    if best_strategy and best_strategy[1]["total_pnl"] > 0:
        patterns.append({
            "type": "best_strategy",
            "strategy": best_strategy[0],
            "pnl": best_strategy[1]["total_pnl"],
            "win_rate": best_strategy[1]["win_rate"],
            "trades": best_strategy[1]["trades"],
        })
    if feature_patterns:
        patterns.append({"type": "feature_patterns", **feature_patterns})

    return {
        "symbol": symbol,
        "total_trades": len(outcomes),
        "regime_breakdown": regime_stats,
        "strategy_breakdown": strategy_stats,
        "patterns": patterns,
        "consolidated_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_feature_patterns(winning: list[dict], losing: list[dict]) -> dict | None:
    """Extract distinguishing features between winning and losing trades."""
    if len(winning) < 3 or len(losing) < 3:
        return None

    key_features = ["rsi_14", "volatility_20", "momentum_20", "sma_20", "adx"]
    patterns = {}

    for feat_name in key_features:
        win_vals = [w.get(feat_name, 0) for w in winning if feat_name in w]
        loss_vals = [l.get(feat_name, 0) for l in losing if feat_name in l]
        if win_vals and loss_vals:
            win_avg = fmean(win_vals)
            loss_avg = fmean(loss_vals)
            if abs(win_avg - loss_avg) > 0.01 * max(abs(win_avg), abs(loss_avg), 1):
                patterns[feat_name] = {
                    "winning_avg": round(win_avg, 4),
                    "losing_avg": round(loss_avg, 4),
                    "direction": "higher" if win_avg > loss_avg else "lower",
                }

    return patterns if patterns else None


# ============================================================
# 5. Learning Cycle (called by engine)
# ============================================================

def learning_cycle(last_analysis: dict | None, last_signal: dict | None) -> dict:
    """Run one full learning cycle.

    Called by engine task_learning. Returns summary of what was learned.
    """
    from . import journal

    results = {
        "trades_tracked": 0,
        "strategies_scored": 0,
        "patterns_found": 0,
        "advisor_weights_updated": False,
    }

    # 1. Analyze recent decisions
    decisions = storage.list_recent_decisions(limit=50)
    snapshots = storage.list_market_snapshots(limit=10)
    prices = {s["symbol"]: s["price"] for s in snapshots}
    if decisions and prices:
        journal.analyze_decisions(decisions, prices)

    # 2. Score all strategies
    all_stats = get_all_strategy_stats()
    results["strategies_scored"] = len(all_stats)

    # 3. Consolidate memory for active symbols
    from . import config
    total_patterns = 0
    for symbol in config.SYMBOLS:
        consolidation = consolidate_memory(symbol)
        total_patterns += len(consolidation.get("patterns", []))
    results["patterns_found"] = total_patterns

    # 4. Get current regime for adaptive weights
    if last_analysis:
        regime = last_analysis.get("regime", {}).get("regime", "range")
        weights = get_advisor_weights(regime)
        if weights:
            results["advisor_weights_updated"] = True
            results["regime"] = regime
            results["strategy_weights"] = weights

    return results
