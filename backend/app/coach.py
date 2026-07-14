"""AI Coach: analyzes backtest history and proposes improvements."""

from statistics import fmean


def review(backtests: list[dict]) -> dict:
    """Analyze backtests and produce actionable recommendations."""
    if not backtests:
        return {"reviewed_backtests": 0, "recommendations": [], "summary": "No backtests to review."}

    recommendations = []
    strategy_stats: dict[str, dict] = {}

    for backtest in backtests:
        metrics = backtest["metrics"].get("out_of_sample_metrics", backtest["metrics"])
        strategy = backtest.get("strategy", "unknown")
        backtest_id = backtest["id"]

        if strategy not in strategy_stats:
            strategy_stats[strategy] = {"returns": [], "sharpes": [], "drawdowns": [], "trade_counts": [], "ids": []}

        strategy_stats[strategy]["returns"].append(metrics.get("total_return", 0))
        strategy_stats[strategy]["sharpes"].append(metrics.get("sharpe_ratio", 0))
        strategy_stats[strategy]["drawdowns"].append(metrics.get("max_drawdown", 0))
        strategy_stats[strategy]["trade_counts"].append(metrics.get("trade_count", 0))
        strategy_stats[strategy]["ids"].append(backtest_id)

        # Per-backtest recommendation
        sharpe = metrics.get("sharpe_ratio", 0)
        total_return = metrics.get("total_return", 0)
        max_dd = metrics.get("max_drawdown", 0)
        trade_count = metrics.get("trade_count", 0)

        if sharpe <= 0 or total_return <= 0:
            action = "reject_for_paper_trading"
            reason = f"Negative return ({total_return*100:.1f}%) or Sharpe ({sharpe:.2f})"
        elif trade_count < 5:
            action = "collect_more_history"
            reason = f"Only {trade_count} trades — need more data"
        elif max_dd < -0.20:
            action = "reduce_allocation"
            reason = f"Drawdown {max_dd*100:.1f}% exceeds 20% threshold"
        elif sharpe >= 1.0 and total_return > 0.05:
            action = "promote_to_paper_candidate"
            reason = f"Strong Sharpe ({sharpe:.2f}) and return ({total_return*100:.1f}%)"
        else:
            action = "collect_more_history"
            reason = "Performance is acceptable but needs more validation"

        recommendations.append({
            "backtest_id": backtest_id,
            "strategy": strategy,
            "action": action,
            "reason": reason,
            "metrics_snapshot": {
                "sharpe": round(sharpe, 4),
                "return": round(total_return * 100, 2),
                "drawdown": round(max_dd * 100, 2),
                "trades": trade_count,
            },
        })

    # Strategy-level analysis
    strategy_analysis = []
    for strat, stats in strategy_stats.items():
        avg_return = fmean(stats["returns"])
        avg_sharpe = fmean(stats["sharpes"])
        avg_dd = fmean(stats["drawdowns"])
        total_trades = sum(stats["trade_counts"])

        if avg_sharpe >= 0.5 and avg_return > 0:
            health = "healthy"
        elif avg_sharpe <= 0:
            health = "underperforming"
        else:
            health = "developing"

        strategy_analysis.append({
            "strategy": strat,
            "backtest_count": len(stats["ids"]),
            "avg_return": round(avg_return * 100, 2),
            "avg_sharpe": round(avg_sharpe, 4),
            "avg_drawdown": round(avg_dd * 100, 2),
            "total_trades": total_trades,
            "health": health,
        })

    # Global summary
    all_sharpes = [s["avg_sharpe"] for s in strategy_analysis]
    overall_health = "healthy" if fmean(all_sharpes) > 0.3 else "needs_attention" if fmean(all_sharpes) > 0 else "critical"

    return {
        "reviewed_backtests": len(backtests),
        "recommendations": recommendations,
        "strategy_analysis": strategy_analysis,
        "overall_health": overall_health,
        "summary": f"{len(backtests)} backtests across {len(strategy_stats)} strategies. Overall health: {overall_health}.",
    }


def propose_improvements(strategy_analysis: list[dict]) -> list[dict]:
    """Generate improvement proposals based on strategy analysis."""
    proposals = []
    for sa in strategy_analysis:
        if sa["health"] == "underperforming":
            proposals.append({
                "strategy": sa["strategy"],
                "proposal": "Consider adjusting parameters or pausing this strategy",
                "priority": "high",
                "reason": f"Avg Sharpe {sa['avg_sharpe']:.2f} is negative over {sa['backtest_count']} backtests",
            })
        elif sa["health"] == "developing" and sa["total_trades"] < 20:
            proposals.append({
                "strategy": sa["strategy"],
                "proposal": "Collect more historical data before promotion",
                "priority": "medium",
                "reason": f"Only {sa['total_trades']} trades — needs more validation",
            })
        elif sa["health"] == "healthy" and sa["avg_sharpe"] >= 1.0:
            proposals.append({
                "strategy": sa["strategy"],
                "proposal": "Eligible for paper trading candidate pool",
                "priority": "low",
                "reason": f"Strong performance: Sharpe {sa['avg_sharpe']:.2f}, return {sa['avg_return']:.1f}%",
            })
    return proposals
