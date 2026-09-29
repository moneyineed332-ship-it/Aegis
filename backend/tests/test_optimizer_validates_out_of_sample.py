"""The optimiser ranked candidates on in-sample data and promoted from it.

`optimizer.optimize_sma` and its three siblings scored every candidate on the
same candles, sorted by a composite, and returned the top of that ranking as
`"status": "optimized"`. Nothing was ever measured on data the parameters had
not seen.

Worse, `_generate_recommendation` graded those in-sample numbers and, on
EXCELLENT or GOOD, closed with:

    "Recommendation: Promote to paper trading candidate pool."

That is the same claim lab.promotion_decision was making, on the same evidence,
through a second route that never touched the promotion gate. A run that scored
Sharpe 5.0 in-sample and lost money afterwards was told to promote itself.

The protocol now scores the grid on a training window, carries the single
top-ranked candidate across an embargo to a held-out window, and reports what
happened there. Measured on real data the gap is large: on 1 988 EURUSD 15m
candles with a 28-set grid, the training winner went -41.70 -> -56.24 against a
grid median of -58.38, so most of its edge was noise.
"""

import pytest

from app import optimizer


def _series(n):
    """One contiguous run of candles, timestamps 0..n-1."""
    return [
        {"open": 1.0, "high": 1.01, "low": 0.99, "close": 1.0,
         "volume": 1, "timestamp": i, "close_time": i}
        for i in range(n)
    ]


def _window(candles):
    """The training window is the one starting at the very first candle."""
    return "train" if candles[0]["timestamp"] == 0 else "test"


def _metrics(sharpe, ret, trades=20, drawdown=-0.05):
    return {
        "sharpe_ratio": sharpe,
        "sortino_ratio": sharpe,
        "calmar_ratio": sharpe,
        "total_return": ret,
        "max_drawdown": drawdown,
        "trade_count": trades,
    }


def _fake_runner(train_score, test_score, trades=20):
    """Scores the training window well and the held-out window badly."""
    def run(candles, params):
        if _window(candles) == "train":
            return _metrics(train_score, 0.10, trades)
        return _metrics(test_score, 0.10 * test_score, trades)
    return run


@pytest.fixture
def patched(monkeypatch):
    def apply(runner):
        monkeypatch.setattr("app.backtesting.run_sma_crossover", runner)
    return apply


# --- the regression ---------------------------------------------------------

def test_in_sample_excellence_no_longer_reads_as_a_promotable_result(patched):
    """Sharpe 5.0 in-sample, negative out-of-sample.

    The old code graded this EXCELLENT and told the operator to promote.
    """
    patched(_fake_runner(5.0, -2.0))
    result = optimizer.optimize_sma(_series(4000))

    assert result["validated"] is False
    assert result["verdict"] == "degraded"


def test_recommendation_never_says_promote(patched):
    """No verdict path may close with the promotion instruction."""
    for train_score, test_score in ((5.0, -2.0), (0.1, 0.1), (5.0, 5.0), (-1.0, -1.0)):
        patched(_fake_runner(train_score, test_score))
        result = optimizer.optimize_sma(_series(4000))
        assert "Promote to paper" not in result["recommendation"]


def test_recommendation_is_graded_on_the_held_out_window(patched):
    """Great in-sample numbers must not colour the grade."""
    patched(_fake_runner(5.0, -2.0))
    result = optimizer.optimize_sma(_series(4000))

    assert "NOT VALIDATED" in result["recommendation"]
    assert "training score" in result["recommendation"]


def test_degradation_is_named_as_degradation(patched):
    """Degradation and missing evidence are different problems."""
    patched(_fake_runner(5.0, -2.0))
    result = optimizer.optimize_sma(_series(4000))

    assert result["verdict"] == "degraded"
    assert "Held-out" in result["verdict_detail"]


# --- the protocol -----------------------------------------------------------

def test_the_grid_is_scored_on_training_and_the_winner_carried_over(patched):
    patched(_fake_runner(3.0, 1.0))
    result = optimizer.optimize_sma(_series(4000))

    assert result["train_metrics"]["sharpe_ratio"] == 3.0
    assert result["out_of_sample_metrics"]["sharpe_ratio"] == 1.0
    assert result["validated"] is True
    assert result["verdict"] == "held_up"


def test_train_and_test_windows_are_separated_by_exactly_the_embargo(patched):
    seen = {}

    def run(candles, params):
        seen.setdefault(_window(candles), candles)
        return _metrics(1.0, 0.05)

    patched(run)
    embargo = 25
    optimizer.optimize_sma(_series(4000), embargo=embargo)

    train, test = seen["train"], seen["test"]
    # Windows are cut positionally from one contiguous run, so the invariants
    # worth pinning are: a strict prefix, a strict suffix, no overlap, and
    # exactly `embargo` candles thrown away between them.
    assert train[0]["timestamp"] == 0
    assert train[-1]["timestamp"] < test[0]["timestamp"]
    assert test[0]["timestamp"] - train[-1]["timestamp"] == embargo + 1
    assert len(train) + embargo + len(test) == 4000


def test_only_the_winner_is_carried_to_the_held_out_window(patched):
    """Scoring every candidate on the test set would spend the evidence."""
    windows = []

    def run(candles, params):
        windows.append(_window(candles))
        return _metrics(1.0, 0.05)

    patched(run)
    optimizer.optimize_sma(_series(4000))

    assert windows.count("test") == 1
    assert windows.count("train") > 1


def test_drift_between_training_and_held_out_is_reported(patched):
    patched(_fake_runner(8.0, 2.0))
    result = optimizer.optimize_sma(_series(4000))

    assert result["out_of_sample_metrics"]["sharpe_drift"] == pytest.approx(-6.0)


# --- honest failure modes ---------------------------------------------------

def test_history_too_short_reports_insufficient_data_rather_than_validating(patched):
    """Too little history to carve out a test window at all.

    The length guard is deliberately coarse: it only fires when the split is
    arithmetically impossible. The guard that does the real work is the trade
    count on the held-out window, tested separately below.
    """
    patched(_fake_runner(5.0, 5.0))
    result = optimizer.optimize_sma(_series(12))

    assert result["verdict"] == "insufficient_data"
    assert result["validated"] is False
    assert result["out_of_sample_metrics"] is None
    assert "NOT VALIDATED" in result["recommendation"]


def test_a_length_that_can_be_split_still_has_to_earn_the_verdict(patched):
    """60 candles splits fine, so the trade count is what must stop it."""
    patched(_fake_runner(5.0, 5.0))
    assert optimizer.optimize_sma(_series(60))["verdict"] != "insufficient_data"


def test_held_out_window_too_small_to_trade_is_not_a_pass(patched):
    """Two trades cannot confirm an edge, and must not read as one."""
    def run(candles, params):
        if _window(candles) == "train":
            return _metrics(5.0, 0.10, trades=50)
        return _metrics(5.0, 0.10, trades=2)

    patched(run)
    result = optimizer.optimize_sma(_series(4000))

    assert result["verdict"] == "insufficient_out_of_sample"
    assert result["validated"] is False
    assert "2 trades" in result["verdict_detail"]


def test_a_sign_flip_is_reported_as_drift_not_hidden(patched):
    patched(_fake_runner(4.0, -4.0))
    result = optimizer.optimize_sma(_series(4000))

    assert result["out_of_sample_metrics"]["sharpe_drift"] < 0
    assert result["validated"] is False


# --- the gate can now read the output ---------------------------------------

def test_optimizer_output_carries_metrics_the_lab_gate_accepts(patched):
    """The two fixes compose: what the optimiser emits is what the gate reads."""
    from app import lab

    patched(_fake_runner(3.0, 1.0))
    result = optimizer.optimize_sma(_series(4000))

    decision = lab.promotion_decision({"id": 1, "metrics": result})
    assert decision["evaluated_on"] == "out_of_sample"


def test_compare_strategies_names_no_winner_when_nothing_held_up(patched):
    patched(_fake_runner(5.0, -2.0))
    weak = optimizer.optimize_sma(_series(4000))
    comparison = optimizer.compare_strategies({"sma": weak})

    assert comparison["best_overall"] is None
    assert "degraded" in comparison["note"]


def test_compare_strategies_names_a_winner_only_after_validation(patched):
    patched(_fake_runner(3.0, 1.0))
    good = optimizer.optimize_sma(_series(4000))
    comparison = optimizer.compare_strategies({"sma": good})

    assert comparison["best_overall"] == "sma"
