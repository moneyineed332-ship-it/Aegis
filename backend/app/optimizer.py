"""Phase 3 — Auto-improvement: parameter optimization and strategy evolution."""

import math
from statistics import fmean, stdev
from itertools import product


def optimize_sma(candles: list[dict], capital: float = 10_000) -> dict:
    """Grid search optimization for SMA crossover parameters."""
    from app.backtesting import run_sma_crossover

    fast_range = range(5, 31, 5)  # 5, 10, 15, 20, 25, 30
    slow_range = range(30, 101, 10)  # 30, 40, 50, 60, 70, 80, 90, 100

    results = []
    for fast, slow in product(fast_range, slow_range):
        if fast >= slow:
            continue
        try:
            metrics = run_sma_crossover(candles, {
                "fast_period": fast,
                "slow_period": slow,
                "initial_capital": capital,
                "allocation": 0.95,
                "fee_bps": 10,
                "slippage_bps": 5,
                "interval": "1h",
            })
            results.append({
                "fast": fast,
                "slow": slow,
                "sharpe": metrics["sharpe_ratio"],
                "sortino": metrics.get("sortino_ratio", 0),
                "calmar": metrics.get("calmar_ratio", 0),
                "return": metrics["total_return"],
                "drawdown": metrics["max_drawdown"],
                "trades": metrics["trade_count"],
            })
        except ValueError:
            continue

    if not results:
        return {"status": "no_valid_parameters", "best": None, "tested": 0}

    # Sort by composite score: 40% Sharpe + 35% Sortino + 25% Calmar
    def composite(r: dict) -> float:
        return 0.40 * r.get("sharpe", 0) + 0.35 * r.get("sortino", 0) + 0.25 * r.get("calmar", 0)
    results.sort(key=composite, reverse=True)
    best = results[0]

    return {
        "status": "optimized",
        "tested": len(results),
        "best": best,
        "top_5": results[:5],
        "recommendation": _generate_recommendation(best, "sma"),
    }


def optimize_donchian(candles: list[dict], capital: float = 10_000) -> dict:
    """Grid search optimization for Donchian breakout parameters."""
    from app.backtesting import run_donchian_breakout

    breakout_range = range(10, 61, 5)  # 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60
    exit_range = range(5, 31, 5)  # 5, 10, 15, 20, 25, 30

    results = []
    for breakout, exit_p in product(breakout_range, exit_range):
        if exit_p >= breakout:
            continue
        try:
            metrics = run_donchian_breakout(candles, {
                "breakout_period": breakout,
                "exit_period": exit_p,
                "initial_capital": capital,
                "allocation": 0.95,
                "fee_bps": 10,
                "slippage_bps": 5,
                "interval": "1h",
                "min_volatility": 0.01,
            })
            results.append({
                "breakout": breakout,
                "exit": exit_p,
                "sharpe": metrics["sharpe_ratio"],
                "sortino": metrics.get("sortino_ratio", 0),
                "calmar": metrics.get("calmar_ratio", 0),
                "return": metrics["total_return"],
                "drawdown": metrics["max_drawdown"],
                "trades": metrics["trade_count"],
            })
        except ValueError:
            continue

    if not results:
        return {"status": "no_valid_parameters", "best": None, "tested": 0}

    results.sort(key=lambda x: 0.40 * x.get("sharpe", 0) + 0.35 * x.get("sortino", 0) + 0.25 * x.get("calmar", 0), reverse=True)
    best = results[0]

    return {
        "status": "optimized",
        "tested": len(results),
        "best": best,
        "top_5": results[:5],
        "recommendation": _generate_recommendation(best, "donchian"),
    }


def optimize_mean_reversion(candles: list[dict], capital: float = 10_000) -> dict:
    """Grid search optimization for Mean Reversion parameters."""
    from app.mean_reversion import run_mean_reversion

    entry_range = [-1.5, -2.0, -2.5, -3.0]
    exit_range = [-0.5, 0.0, 0.5]
    period_range = [15, 20, 25, 30]

    results = []
    for entry, exit_z, period in product(entry_range, exit_range, period_range):
        try:
            metrics = run_mean_reversion(candles, {
                "period": period,
                "entry_z_score": entry,
                "exit_z_score": exit_z,
                "initial_capital": capital,
                "allocation": 0.95,
                "fee_bps": 10,
                "slippage_bps": 5,
                "interval": "1h",
            })
            results.append({
                "entry_z": entry,
                "exit_z": exit_z,
                "period": period,
                "sharpe": metrics["sharpe_ratio"],
                "sortino": metrics.get("sortino_ratio", 0),
                "calmar": metrics.get("calmar_ratio", 0),
                "return": metrics["total_return"],
                "drawdown": metrics["max_drawdown"],
                "trades": metrics["trade_count"],
            })
        except ValueError:
            continue

    if not results:
        return {"status": "no_valid_parameters", "best": None, "tested": 0}

    results.sort(key=lambda x: 0.40 * x.get("sharpe", 0) + 0.35 * x.get("sortino", 0) + 0.25 * x.get("calmar", 0), reverse=True)
    best = results[0]

    return {
        "status": "optimized",
        "tested": len(results),
        "best": best,
        "top_5": results[:5],
        "recommendation": _generate_recommendation(best, "mean_reversion"),
    }


def optimize_grid(candles: list[dict], capital: float = 10_000) -> dict:
    """Grid search optimization for Grid trading parameters."""
    from app.grid import run_grid

    count_range = [5, 8, 10, 12, 15, 20]
    spread_range = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03]

    results = []
    for count, spread in product(count_range, spread_range):
        try:
            metrics = run_grid(candles, {
                "grid_count": count,
                "grid_spread_pct": spread,
                "initial_capital": capital,
                "allocation": 0.95,
                "fee_bps": 10,
                "slippage_bps": 5,
                "interval": "1h",
            })
            results.append({
                "count": count,
                "spread": spread,
                "sharpe": metrics["sharpe_ratio"],
                "sortino": metrics.get("sortino_ratio", 0),
                "calmar": metrics.get("calmar_ratio", 0),
                "return": metrics["total_return"],
                "drawdown": metrics["max_drawdown"],
                "trades": metrics["trade_count"],
            })
        except ValueError:
            continue

    if not results:
        return {"status": "no_valid_parameters", "best": None, "tested": 0}

    results.sort(key=lambda x: 0.40 * x.get("sharpe", 0) + 0.35 * x.get("sortino", 0) + 0.25 * x.get("calmar", 0), reverse=True)
    best = results[0]

    return {
        "status": "optimized",
        "tested": len(results),
        "best": best,
        "top_5": results[:5],
        "recommendation": _generate_recommendation(best, "grid"),
    }


def _generate_recommendation(best: dict, strategy_type: str) -> str:
    """Generate a human-readable recommendation from optimization results."""
    sharpe = best.get("sharpe", 0)
    sortino = best.get("sortino", 0)
    calmar = best.get("calmar", 0)
    ret = best.get("return", 0)
    dd = best.get("drawdown", 0)
    trades = best.get("trades", 0)

    if sharpe >= 1.0 and sortino >= 1.5 and ret > 0.05 and dd > -0.15:
        grade = "EXCELLENT"
    elif sharpe >= 0.5 and sortino >= 0.8 and ret > 0 and dd > -0.20:
        grade = "GOOD"
    elif sharpe > 0 and ret > 0:
        grade = "ACCEPTABLE"
    else:
        grade = "WEAK"

    parts = [f"Strategy {strategy_type} optimization result: {grade}"]
    parts.append(f"Sharpe: {sharpe:.2f}, Sortino: {sortino:.2f}, Calmar: {calmar:.2f}")
    parts.append(f"Return: {ret*100:.1f}%, Drawdown: {dd*100:.1f}%, Trades: {trades}")

    if grade in ("EXCELLENT", "GOOD"):
        parts.append("Recommendation: Promote to paper trading candidate pool.")
    elif grade == "ACCEPTABLE":
        parts.append("Recommendation: Collect more history before promotion.")
    else:
        parts.append("Recommendation: Review parameters or pause strategy.")

    return " | ".join(parts)


def compare_strategies(results: dict[str, dict]) -> dict:
    """Compare optimization results across strategies."""
    strategies = []
    for name, result in results.items():
        if result.get("best"):
            strategies.append({
                "strategy": name,
                "sharpe": result["best"].get("sharpe", 0),
                "sortino": result["best"].get("sortino", 0),
                "calmar": result["best"].get("calmar", 0),
                "return": result["best"].get("return", 0),
                "drawdown": result["best"].get("drawdown", 0),
                "trades": result["best"].get("trades", 0),
            })

    if not strategies:
        return {"ranking": [], "best_overall": None}

    strategies.sort(key=lambda x: 0.40 * x["sharpe"] + 0.35 * x["sortino"] + 0.25 * x["calmar"], reverse=True)
    return {
        "ranking": strategies,
        "best_overall": strategies[0]["strategy"] if strategies else None,
    }
