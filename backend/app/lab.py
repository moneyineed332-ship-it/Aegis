"""Promotion gate for research strategies; never places orders."""

from typing import Any

# Minimum evidence for a strategy to be a paper candidate. Applied to
# out-of-sample metrics only.
MIN_TOTAL_RETURN = 0.0
MIN_SHARPE = 0.5
MIN_TRADES = 10
MAX_DRAWDOWN = -0.15


def _fails_thresholds(metrics: dict) -> list[str]:
    """Which thresholds the given metrics miss."""
    missed: list[str] = []
    if metrics.get("total_return", 0) <= MIN_TOTAL_RETURN:
        missed.append(f"total_return {metrics.get('total_return')} <= {MIN_TOTAL_RETURN}")
    if metrics.get("sharpe_ratio", 0) < MIN_SHARPE:
        missed.append(f"sharpe_ratio {metrics.get('sharpe_ratio')} < {MIN_SHARPE}")
    if metrics.get("trade_count", 0) < MIN_TRADES:
        missed.append(f"trade_count {metrics.get('trade_count')} < {MIN_TRADES}")
    if metrics.get("max_drawdown", 0) < MAX_DRAWDOWN:
        missed.append(f"max_drawdown {metrics.get('max_drawdown')} < {MAX_DRAWDOWN}")
    return missed


def promotion_decision(backtest: dict) -> dict:
    """Decide whether a backtest makes a strategy a paper candidate.

    Only out-of-sample metrics count. The previous version did
    ``metrics.get("out_of_sample_metrics", metrics)``, so a run with no
    held-out portion was judged on the same data its parameters were chosen
    from.

    Measured on the stored backtests, that inverted the gate entirely:

        eligible on real out-of-sample evidence     0
        eligible ONLY through the in-sample fallback 7

    All seven were `grid_adaptive` runs, Sharpe around 4.7 over 27 trades. The
    gate was promoting precisely the runs with no evidence behind them, while
    refusing every walk-forward run that actually had a held-out portion.

    Missing evidence is reported as "not demonstrated", not as "refused for
    being bad": the distinction matters, because the fix is to run a walk-forward
    pass, not to abandon the strategy.
    """
    backtest_id = backtest.get("id")
    all_metrics = backtest.get("metrics")
    if not isinstance(all_metrics, dict):
        all_metrics = {}
    oos = all_metrics.get("out_of_sample_metrics")
    in_sample = all_metrics.get("train_metrics", all_metrics)
    if not isinstance(in_sample, dict):
        in_sample = {}

    # Metrics come back from JSON in the backtests table, so a malformed block
    # has to read as absent evidence rather than raise.
    if not isinstance(oos, dict):
        return {
            "backtest_id": backtest_id,
            "eligible_for_paper_candidate": False,
            "evaluated_on": "none",
            "reason": (
                "No out-of-sample metrics: this run has no held-out portion, so "
                "it cannot promote a strategy. Run the walk-forward variant to "
                "produce evidence."
            ),
            "missing_evidence": ["out_of_sample_metrics"],
            "in_sample_preview": {
                "sharpe_ratio": in_sample.get("sharpe_ratio"),
                "trade_count": in_sample.get("trade_count"),
                "total_return": in_sample.get("total_return"),
                "note": "shown for context only; not used for the decision",
            },
        }

    missed = _fails_thresholds(oos)
    accepted = not missed
    return {
        "backtest_id": backtest_id,
        "eligible_for_paper_candidate": accepted,
        "evaluated_on": "out_of_sample",
        "reason": (
            "Meets minimum out-of-sample research thresholds."
            if accepted
            else "Out-of-sample evidence does not meet thresholds: " + "; ".join(missed)
        ),
        "missing_evidence": [],
        "out_of_sample": {
            "sharpe_ratio": oos.get("sharpe_ratio"),
            "trade_count": oos.get("trade_count"),
            "total_return": oos.get("total_return"),
            "max_drawdown": oos.get("max_drawdown"),
        },
    }
