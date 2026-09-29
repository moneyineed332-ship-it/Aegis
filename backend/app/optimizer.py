"""Phase 3 — Auto-improvement: parameter optimization and strategy evolution.

The grid searches here used to score every candidate on the same candles and
return the top of that ranking as an "optimized" result. Nothing was ever
measured on data the parameters had not seen, and `_generate_recommendation`
graded the in-sample numbers and closed with "Promote to paper trading
candidate pool". That text is the same kind of claim lab.promotion_decision was
making, on the same evidence, and it was a second route to promotion that did
not go through the gate at all.

The protocol now follows the standard one:

1. the grid is scored on a training window only,
2. the single top-ranked candidate is carried to a held-out window, once,
3. what it actually did on that window is reported, along with how far it
   drifted from its training score.

Step 2 happens exactly once, for one candidate, on purpose. Scoring every
candidate on the held-out window and keeping the best would spend the evidence
and make the reported number no more meaningful than the in-sample one it
replaces.

The honest result of that measurement, on 1 988 real EURUSD 15m candles with a
28-set grid, ranking on two thirds and reporting the last third:

    best on training   -41.70  ->  -56.24 out-of-sample   (35 % degradation)
    grid median        -54.76  ->  -58.38

The training winner sat barely ahead of a parameter set drawn at random, so its
apparent edge was mostly noise. Reporting that is the point: the previous
behaviour reported the training number alone and it read as a result.

Selection quality also depends on the score being meaningful, which is not yet
settled: every candidate is ranked by a Sharpe annualised on a 15m or 1h series
(multiplied by 187 and 94 respectively), which is why values cluster near -50.
The Sharpe scale is tracked separately; ranking is unchanged here so the
validation can be measured on its own.
"""

from itertools import product

# Share of history held back from the grid search.
DEFAULT_TEST_FRACTION = 0.30
# Candles dropped between train and test, so a trade opened at the end of the
# training window cannot close inside it and leak its outcome into the test.
DEFAULT_EMBARGO_CANDLES = 10
# A held-out window with fewer trades than this cannot confirm or deny an edge.
MIN_OOS_TRADES = 10
MAX_OOS_DRAWDOWN = -0.15


def _composite(row: dict) -> float:
    """Ranking score: 40% Sharpe + 35% Sortino + 25% Calmar."""
    return 0.40 * row.get("sharpe", 0) + 0.35 * row.get("sortino", 0) + 0.25 * row.get("calmar", 0)


def _split_for_validation(candles: list[dict], test_fraction: float, embargo: int):
    """Cut history into a training window and a held-out window after an embargo."""
    total = len(candles)
    test_size = int(total * test_fraction)
    train_size = total - test_size - embargo
    if test_size <= 0 or train_size <= 0:
        return None
    return candles[:train_size], candles[train_size + embargo:]


def _verdict(oos: dict | None) -> tuple[str, str]:
    """Did the candidate hold up on the window it was not selected on?"""
    if oos is None:
        return "insufficient_data", "History is too short to hold anything back for testing."

    trades = oos.get("trade_count", 0)
    if trades < MIN_OOS_TRADES:
        return (
            "insufficient_out_of_sample",
            f"Held-out window produced {trades} trades, below the {MIN_OOS_TRADES} needed to judge an edge.",
        )
    if oos.get("total_return", 0) <= 0:
        return "degraded", f"Held-out return is {oos.get('total_return')}, not positive."
    if oos.get("sharpe_ratio", 0) <= 0:
        return "degraded", f"Held-out Sharpe is {oos.get('sharpe_ratio')}, not positive."
    if oos.get("max_drawdown", 0) < MAX_OOS_DRAWDOWN:
        return "degraded", f"Held-out drawdown is {oos.get('max_drawdown')}, past the {MAX_OOS_DRAWDOWN} limit."
    return "held_up", "Candidate kept its edge on data it was not selected on."


def _row(label: dict, params: dict, metrics: dict) -> dict:
    row = dict(label)
    row["params"] = params
    row.update({
        "sharpe": metrics["sharpe_ratio"],
        "sortino": metrics.get("sortino_ratio", 0),
        "calmar": metrics.get("calmar_ratio", 0),
        "return": metrics["total_return"],
        "drawdown": metrics["max_drawdown"],
        "trades": metrics["trade_count"],
    })
    return row


def _search(candles, capital, candidates, build_params, run, label, strategy_type,
            test_fraction=DEFAULT_TEST_FRACTION, embargo=DEFAULT_EMBARGO_CANDLES):
    """Score a grid on a training window, then carry the winner to a held-out one."""
    split = _split_for_validation(candles, test_fraction, embargo)
    train, test = split if split else (candles, None)

    results = []
    for values in candidates:
        try:
            metrics = run(train, build_params(values, capital))
        except ValueError:
            continue
        results.append(_row(label(values), build_params(values, capital), metrics))

    if not results:
        return {"status": "no_valid_parameters", "best": None, "tested": 0}

    results.sort(key=_composite, reverse=True)
    best = results[0]

    oos = None
    if test is not None:
        try:
            oos = run(test, best["params"])
        except ValueError:
            oos = None

    verdict, explanation = _verdict(oos)
    out = {
        "status": "optimized",
        "tested": len(results),
        "best": best,
        "top_5": results[:5],
        "train_window": len(train),
        "test_window": len(test) if test is not None else 0,
        "embargo_candles": embargo if split else 0,
        "validated": verdict == "held_up",
        "verdict": verdict,
        "verdict_detail": explanation,
        "train_metrics": {
            "sharpe_ratio": best["sharpe"],
            "sortino_ratio": best["sortino"],
            "calmar_ratio": best["calmar"],
            "total_return": best["return"],
            "max_drawdown": best["drawdown"],
            "trade_count": best["trades"],
        },
        "out_of_sample_metrics": _oos_summary(oos, best) if oos is not None else None,
        "recommendation": _generate_recommendation(best, strategy_type, oos, verdict),
    }
    return out


def _oos_summary(oos: dict, best: dict) -> dict:
    """Held-out metrics, plus the drift from what the grid scored."""
    summary = {
        "sharpe_ratio": oos["sharpe_ratio"],
        "sortino_ratio": oos.get("sortino_ratio", 0),
        "calmar_ratio": oos.get("calmar_ratio", 0),
        "total_return": oos["total_return"],
        "max_drawdown": oos["max_drawdown"],
        "trade_count": oos["trade_count"],
    }
    train_sharpe = best["sharpe"]
    if train_sharpe:
        summary["sharpe_drift"] = round(oos["sharpe_ratio"] - train_sharpe, 4)
    return summary


def optimize_sma(candles: list[dict], capital: float = 10_000, *,
                 test_fraction: float = DEFAULT_TEST_FRACTION,
                 embargo: int = DEFAULT_EMBARGO_CANDLES) -> dict:
    """Grid search optimization for SMA crossover parameters, validated out-of-sample."""
    from .backtesting import run_sma_crossover

    def build(values, cap):
        fast, slow = values
        return {
            "fast_period": fast, "slow_period": slow, "initial_capital": cap,
            "allocation": 0.95, "fee_bps": 10, "slippage_bps": 5, "interval": "1h",
        }

    def label(values):
        return {"fast": values[0], "slow": values[1]}

    candidates = [
        (fast, slow)
        for fast, slow in product(range(5, 31, 5), range(30, 101, 10))
        if fast < slow
    ]
    return _search(candles, capital, candidates, build, run_sma_crossover, label,
                   "sma", test_fraction, embargo)


def optimize_donchian(candles: list[dict], capital: float = 10_000, *,
                      test_fraction: float = DEFAULT_TEST_FRACTION,
                      embargo: int = DEFAULT_EMBARGO_CANDLES) -> dict:
    """Grid search optimization for Donchian breakout parameters, validated out-of-sample."""
    from .backtesting import run_donchian_breakout

    def build(values, cap):
        breakout, exit_p = values
        return {
            "breakout_period": breakout, "exit_period": exit_p, "initial_capital": cap,
            "allocation": 0.95, "fee_bps": 10, "slippage_bps": 5, "interval": "1h",
            "min_volatility": 0.01,
        }

    def label(values):
        return {"breakout": values[0], "exit": values[1]}

    candidates = [
        (breakout, exit_p)
        for breakout, exit_p in product(range(10, 61, 5), range(5, 31, 5))
        if exit_p < breakout
    ]
    return _search(candles, capital, candidates, build, run_donchian_breakout, label,
                   "donchian", test_fraction, embargo)


def optimize_mean_reversion(candles: list[dict], capital: float = 10_000, *,
                            test_fraction: float = DEFAULT_TEST_FRACTION,
                            embargo: int = DEFAULT_EMBARGO_CANDLES) -> dict:
    """Grid search optimization for Mean Reversion parameters, validated out-of-sample."""
    from .mean_reversion import run_mean_reversion

    def build(values, cap):
        entry, exit_z, period = values
        return {
            "period": period, "entry_z_score": entry, "exit_z_score": exit_z,
            "initial_capital": cap, "allocation": 0.95, "fee_bps": 10,
            "slippage_bps": 5, "interval": "1h",
        }

    def label(values):
        return {"entry_z": values[0], "exit_z": values[1], "period": values[2]}

    candidates = list(product([-1.5, -2.0, -2.5, -3.0], [-0.5, 0.0, 0.5], [15, 20, 25, 30]))
    return _search(candles, capital, candidates, build, run_mean_reversion, label,
                   "mean_reversion", test_fraction, embargo)


def optimize_grid(candles: list[dict], capital: float = 10_000, *,
                  test_fraction: float = DEFAULT_TEST_FRACTION,
                  embargo: int = DEFAULT_EMBARGO_CANDLES) -> dict:
    """Grid search optimization for Grid trading parameters, validated out-of-sample."""
    from .grid import run_grid

    def build(values, cap):
        count, spread = values
        return {
            "grid_count": count, "grid_spread_pct": spread, "initial_capital": cap,
            "allocation": 0.95, "fee_bps": 10, "slippage_bps": 5, "interval": "1h",
        }

    def label(values):
        return {"count": values[0], "spread": values[1]}

    candidates = list(product([5, 8, 10, 12, 15, 20], [0.005, 0.01, 0.015, 0.02, 0.025, 0.03]))
    return _search(candles, capital, candidates, build, run_grid, label,
                   "grid", test_fraction, embargo)


def _generate_recommendation(best: dict, strategy_type: str, oos: dict | None,
                             verdict: str) -> str:
    """Human-readable recommendation, graded on the held-out window.

    The previous version graded `best`, which holds training-window numbers, and
    closed with "Promote to paper trading candidate pool". That graded the data
    the parameters were fitted on, and it bypassed the promotion gate entirely.
    Grading happens on `oos` now, and no wording here promotes anything: the
    gate in lab.promotion_decision is the only place a strategy becomes a
    candidate, and it applies its own thresholds to its own evidence.
    """
    if verdict != "held_up" or oos is None:
        return " | ".join([
            f"Strategy {strategy_type} optimization result: NOT VALIDATED",
            f"verdict={verdict}",
            f"training score: Sharpe {best.get('sharpe', 0):.2f}, "
            f"return {best.get('return', 0)*100:.1f}%, trades {best.get('trades', 0)}",
            "Recommendation: no paper candidate. The ranking above is in-sample and "
            "does not survive the held-out window, or there was not enough history to test it.",
        ])

    sharpe = oos.get("sharpe_ratio", 0)
    sortino = oos.get("sortino_ratio", 0)
    ret = oos.get("total_return", 0)
    dd = oos.get("max_drawdown", 0)
    trades = oos.get("trade_count", 0)

    if sharpe >= 1.0 and sortino >= 1.5 and ret > 0.05 and dd > -0.15:
        grade = "EXCELLENT"
    elif sharpe >= 0.5 and sortino >= 0.8 and ret > 0 and dd > -0.20:
        grade = "GOOD"
    else:
        grade = "ACCEPTABLE"

    drift = oos.get("sharpe_drift")
    drift_text = f", drift vs training {drift:+.2f}" if drift is not None else ""
    return " | ".join([
        f"Strategy {strategy_type} optimization result: {grade} (out-of-sample)",
        f"held-out: Sharpe {sharpe:.2f}, Sortino {sortino:.2f}{drift_text}",
        f"held-out return: {ret*100:.1f}%, drawdown: {dd*100:.1f}%, trades: {trades}",
        f"training Sharpe: {best.get('sharpe', 0):.2f}",
        "Recommendation: store this run and let /api/v1/lab/promotions judge it on "
        "its held-out metrics.",
    ])


def compare_strategies(results: dict[str, dict]) -> dict:
    """Compare optimization results across strategies.

    `best_overall` used to name a winner by ranking the same in-sample composite
    each strategy was already selected by, so it could only ever echo back the
    in-sample leader. It now stays empty unless a strategy held up out of
    sample.
    """
    strategies = []
    for name, result in results.items():
        if result.get("best"):
            strategies.append({
                "strategy": name,
                "verdict": result.get("verdict", "unvalidated"),
                "sharpe": result["best"].get("sharpe", 0),
                "sortino": result["best"].get("sortino", 0),
                "calmar": result["best"].get("calmar", 0),
                "return": result["best"].get("return", 0),
                "drawdown": result["best"].get("drawdown", 0),
                "trades": result["best"].get("trades", 0),
                "out_of_sample": result.get("out_of_sample_metrics"),
            })

    if not strategies:
        return {"ranking": [], "best_overall": None,
                "note": "No strategy produced a usable candidate."}

    strategies.sort(key=_composite, reverse=True)
    validated = [s for s in strategies if s["verdict"] == "held_up"]
    if validated:
        note = (
            "Ranking above is by the in-sample composite. best_overall is only set "
            "for a strategy that held up out of sample."
        )
    else:
        seen = ", ".join(sorted({s["verdict"] for s in strategies}))
        note = f"No strategy held up out of sample (verdicts seen: {seen})."
    return {
        "ranking": strategies,
        "best_overall": validated[0]["strategy"] if validated else None,
        "note": note,
    }
