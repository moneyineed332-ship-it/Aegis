"""Advanced backtesting: walk-forward optimization and Monte Carlo simulation."""

import math
import random
from itertools import product

from .metrics_core import max_drawdown, sharpe_ratio


def _sharpe(returns: list[float], periods_per_year: int) -> float:
    return sharpe_ratio(returns, periods_per_year)


def _max_drawdown(equity_curve: list[float]) -> float:
    return round(max_drawdown(equity_curve), 6)


def _run_simple_backtest(candles: list[dict], strategy_fn, params: dict) -> dict:
    """Generic backtest runner for any strategy function."""
    return strategy_fn(candles, params)


# === Walk-Forward Optimization ===

def walk_forward_optimize(
    candles: list[dict],
    strategy_fn,
    base_params: dict,
    param_grid: dict[str, list],
    train_ratio: float = 0.7,
    n_splits: int = 3,
    objective: str = "sharpe_ratio",
) -> dict:
    """Walk-forward optimization with multiple train/test splits.

    Args:
        candles: Full OHLCV dataset
        strategy_fn: Backtest function(candles, params) -> metrics
        base_params: Base parameters to override
        param_grid: Dict of parameter_name -> list of values to try
        train_ratio: Fraction of data for training
        n_splits: Number of walk-forward splits
        objective: Metric to optimize (sharpe_ratio, total_return, etc.)
    """
    total_len = len(candles)
    split_size = total_len // n_splits
    all_results = []

    for split_idx in range(n_splits):
        start = split_idx * split_size
        end = min(start + split_size, total_len)
        split_candles = candles[start:end]

        train_end = int(len(split_candles) * train_ratio)
        train = split_candles[:train_end]
        test = split_candles[train_end:]

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        best_score = -float("inf")
        best_params = {}
        all_candidates = []

        for combo in product(*param_values):
            candidate_params = {**base_params, **dict(zip(param_names, combo))}
            try:
                metrics = strategy_fn(train, candidate_params)
                score = metrics.get(objective, 0)
                all_candidates.append({
                    "params": dict(zip(param_names, combo)),
                    "train_score": score,
                    "train_metrics": metrics,
                })
                if score > best_score:
                    best_score = score
                    best_params = dict(zip(param_names, combo))
            except (ValueError, ZeroDivisionError):
                continue

        if best_params:
            oos_params = {**base_params, **best_params}
            try:
                oos_metrics = strategy_fn(test, oos_params)
            except (ValueError, ZeroDivisionError):
                oos_metrics = {"sharpe_ratio": 0, "total_return": 0, "max_drawdown": 0, "trade_count": 0}

            all_results.append({
                "split": split_idx + 1,
                "train_size": len(train),
                "test_size": len(test),
                "best_params": best_params,
                "best_train_score": round(best_score, 6),
                "oos_metrics": oos_metrics,
                "candidates_tested": len(all_candidates),
            })

    avg_oos_sharpe = fmean([r["oos_metrics"].get("sharpe_ratio", 0) for r in all_results]) if all_results else 0
    avg_oos_return = fmean([r["oos_metrics"].get("total_return", 0) for r in all_results]) if all_results else 0

    return {
        "splits": all_results,
        "n_splits": n_splits,
        "avg_oos_sharpe": round(avg_oos_sharpe, 4),
        "avg_oos_return": round(avg_oos_return, 6),
        "robustness": "strong" if avg_oos_sharpe > 0.5 else "moderate" if avg_oos_sharpe > 0 else "weak",
        "objective": objective,
    }


# === Monte Carlo Simulation ===

def monte_carlo_simulation(
    candles: list[dict],
    strategy_fn,
    params: dict,
    n_simulations: int = 1000,
    confidence_levels: list[float] | None = None,
    seed: int | None = None,
    annualization: int = 8760,
) -> dict:
    """Monte Carlo simulation by resampling REAL trade returns with replacement.

    The trade series comes from ``base_metrics["trade_returns"]``, which the
    backtesters publish. Resampling that series is the only way to estimate
    path dependence: order matters for drawdown and for compounding, and a
    synthetic distribution built from ``avg_trade_return`` cannot reproduce
    either. The previous implementation set ``win = 1.2 x avg`` and
    ``loss = -0.8 x avg``, which at a 50% win rate manufactured a +20% edge
    out of a breakeven strategy and reported a Sharpe inflated by sqrt(365).

    Returns a ``no_trade_returns`` status when the strategy did not publish a
    per-trade series, instead of silently substituting a guess.
    """
    if confidence_levels is None:
        confidence_levels = [5, 25, 50, 75, 95]
    rng = random.Random(seed)

    try:
        base_metrics = strategy_fn(candles, params)
    except (ValueError, ZeroDivisionError):
        return {"status": "backtest_failed", "error": "Base backtest failed"}

    if not base_metrics.get("trade_count"):
        return {"status": "no_trades", "base_metrics": base_metrics}

    trade_returns = list(base_metrics.get("trade_returns") or [])
    if not trade_returns:
        return {
            "status": "no_trade_returns",
            "error": (
                "Strategy did not publish the 'trade_returns' key. "
                "Monte-Carlo needs the real per-trade series; it will not "
                "substitute a synthetic distribution."
            ),
            "base_metrics": base_metrics,
        }

    trade_count = len(trade_returns)
    simulated_returns: list[float] = []
    simulated_drawdowns: list[float] = []
    simulated_sharpes: list[float] = []
    simulated_win_rates: list[float] = []

    for _ in range(n_simulations):
        returns = [trade_returns[rng.randrange(trade_count)] for _ in range(trade_count)]
        equity = 1.0
        peak = 1.0
        worst_dd = 0.0
        for trade_ret in returns:
            equity *= (1 + trade_ret)
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = equity / peak - 1
                if dd < worst_dd:
                    worst_dd = dd

        simulated_returns.append(equity - 1)
        simulated_drawdowns.append(worst_dd)
        # Annualized on the TRADE series, not on per-period returns: the factor
        # below is trades-per-year, supplied by the caller.
        simulated_sharpes.append(sharpe_ratio(returns, annualization))
        simulated_win_rates.append(sum(1 for r in returns if r > 0) / trade_count)

    simulated_returns.sort()
    simulated_drawdowns.sort()
    simulated_sharpes.sort()

    def percentile(data: list[float], pct: float) -> float:
        idx = int(len(data) * pct / 100)
        return data[min(idx, len(data) - 1)]

    percentiles_return = {f"p{int(p)}": round(percentile(simulated_returns, p), 6) for p in confidence_levels}
    percentiles_dd = {f"p{int(p)}": round(percentile(simulated_drawdowns, p), 6) for p in confidence_levels}
    percentiles_sharpe = {f"p{int(p)}": round(percentile(simulated_sharpes, p), 4) for p in confidence_levels}

    prob_profit = sum(1 for r in simulated_returns if r > 0) / n_simulations
    prob_ruin = sum(1 for dd in simulated_drawdowns if dd < -0.5) / n_simulations
    mean_sim = sum(simulated_returns) / len(simulated_returns)
    var_sim = sum((r - mean_sim) ** 2 for r in simulated_returns) / len(simulated_returns)

    return {
        "n_simulations": n_simulations,
        "trades_per_simulation": trade_count,
        "base_metrics": base_metrics,
        "return_distribution": {
            "mean": round(mean_sim, 6),
            "std": round(math.sqrt(var_sim), 6),
            "percentiles": percentiles_return,
        },
        "drawdown_distribution": {
            "mean": round(sum(simulated_drawdowns) / len(simulated_drawdowns), 6),
            "worst": round(min(simulated_drawdowns), 6),
            "percentiles": percentiles_dd,
        },
        "sharpe_distribution": {
            "mean": round(sum(simulated_sharpes) / len(simulated_sharpes), 4),
            "percentiles": percentiles_sharpe,
        },
        "win_rate_distribution": {
            "mean": round(sum(simulated_win_rates) / len(simulated_win_rates), 6),
        },
        "probability_of_profit": round(prob_profit, 4),
        "probability_of_ruin": round(prob_ruin, 4),
    }


# === Sensitivity Analysis ===

def sensitivity_analysis(
    candles: list[dict],
    strategy_fn,
    base_params: dict,
    param_name: str,
    param_range: list,
) -> dict:
    """Test how sensitive a strategy is to a single parameter."""
    results = []
    for value in param_range:
        params = {**base_params, param_name: value}
        try:
            metrics = strategy_fn(candles, params)
            results.append({"value": value, "metrics": metrics})
        except (ValueError, ZeroDivisionError):
            results.append({"value": value, "metrics": None, "error": "failed"})

    valid = [r for r in results if r.get("metrics")]
    if not valid:
        return {"param": param_name, "status": "all_failed", "results": results}

    sharpes = [r["metrics"]["sharpe_ratio"] for r in valid]
    returns = [r["metrics"]["total_return"] for r in valid]

    return {
        "param": param_name,
        "results": results,
        "best_sharpe": {"value": valid[sharpes.index(max(sharpes))]["value"], "sharpe": max(sharpes)},
        "best_return": {"value": valid[returns.index(max(returns))]["value"], "return": max(returns)},
        "stability": "stable" if len(sharpes) < 2 or stdev(sharpes) < 0.5 else "volatile",
    }
