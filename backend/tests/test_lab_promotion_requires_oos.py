"""The paper-candidate gate judged runs with no out-of-sample evidence.

lab.promotion_decision read the metrics like this:

    metrics = backtest["metrics"].get("out_of_sample_metrics", backtest["metrics"])

When a run had no held-out portion, that fallback substituted the very numbers
its parameters had been chosen from, and the run was judged on them as if they
had survived contact with unseen data.

The gate did not merely allow that. On the 52 backtests stored in
backend/data/aegis.db it inverts the result:

    eligible on real out-of-sample evidence        0
    eligible ONLY through the in-sample fallback    7

All seven were `grid_adaptive` runs, Sharpe around 4.7 over 27 trades, while
every walk-forward run that actually had a held-out portion was refused. The
gate was promoting exactly the runs with no evidence behind them.

Missing evidence is now reported as "not demonstrated" rather than silently
substituted, and the two refusals are distinguishable: one means the strategy
failed the thresholds, the other means nobody ever tested it out-of-sample.
"""

from app import lab


def passing(**overrides):
    """Out-of-sample metrics that clear every threshold."""
    metrics = {
        "sharpe_ratio": 0.9,
        "trade_count": 31,
        "total_return": 0.08,
        "max_drawdown": -0.06,
    }
    metrics.update(overrides)
    return metrics


def in_sample_only(**overrides):
    """The shape of a plain single-window run: flat metrics, no held-out split."""
    metrics = {
        "final_equity": 12000.0,
        "sharpe_ratio": 4.75,
        "trade_count": 27,
        "total_return": 0.20,
        "max_drawdown": -0.05,
    }
    metrics.update(overrides)
    return metrics


# --- the regression ---------------------------------------------------------

def test_in_sample_only_run_cannot_promote_despite_excellent_numbers():
    """The grid_adaptive case, verbatim: great in-sample, no held-out data."""
    decision = lab.promotion_decision({"id": 51, "metrics": in_sample_only()})
    assert decision["eligible_for_paper_candidate"] is False


def test_promising_in_sample_numbers_are_shown_but_not_used():
    """The operator still sees what tempted them, flagged as not evidence."""
    decision = lab.promotion_decision({"id": 51, "metrics": in_sample_only()})
    preview = decision["in_sample_preview"]
    assert preview["sharpe_ratio"] == 4.75
    assert preview["trade_count"] == 27
    assert decision["evaluated_on"] == "none"
    assert decision["missing_evidence"] == ["out_of_sample_metrics"]
    assert "not used for the decision" in preview["note"]


def test_no_out_of_sample_key_is_reported_as_missing_not_as_failure():
    """A missing split is a different problem from a strategy that failed."""
    decision = lab.promotion_decision({"id": 51, "metrics": in_sample_only()})
    assert decision["missing_evidence"] == ["out_of_sample_metrics"]
    assert "no held-out portion" in decision["reason"]
    assert "Run the walk-forward variant" in decision["reason"]


# --- the gate still works when evidence exists ------------------------------

def test_walk_forward_run_promotes_on_out_of_sample_evidence():
    decision = lab.promotion_decision(
        {"id": 52, "metrics": {
            "out_of_sample_metrics": passing(),
            "train_metrics": passing(sharpe_ratio=2.5, trade_count=60),
        }}
    )
    assert decision["eligible_for_paper_candidate"] is True
    assert decision["evaluated_on"] == "out_of_sample"
    assert decision["missing_evidence"] == []


def test_thresholds_are_read_from_out_of_sample_not_train():
    """A weak train and a strong held-out portion must still promote.

    The inverse of the original bug: the fallback made the decision on the
    wrong metrics. This pins the decision to out_of_sample either way.
    """
    decision = lab.promotion_decision(
        {"id": 53, "metrics": {
            "out_of_sample_metrics": passing(),
            "train_metrics": passing(sharpe_ratio=0.1, trade_count=8, total_return=-0.02),
        }}
    )
    assert decision["eligible_for_paper_candidate"] is True


def test_strong_train_never_rescues_a_failing_out_of_sample():
    """The case the fallback could not see: both blocks present, OOS fails."""
    decision = lab.promotion_decision(
        {"id": 54, "metrics": {
            "out_of_sample_metrics": passing(sharpe_ratio=-1.2, total_return=-0.09),
            "train_metrics": passing(sharpe_ratio=4.7, trade_count=27),
        }}
    )
    assert decision["eligible_for_paper_candidate"] is False
    assert decision["out_of_sample"]["sharpe_ratio"] == -1.2


def test_reason_names_every_threshold_that_was_missed():
    decision = lab.promotion_decision(
        {"id": 55, "metrics": {
            "out_of_sample_metrics": passing(
                sharpe_ratio=0.1, trade_count=4, total_return=-0.01, max_drawdown=-0.30
            )
        }}
    )
    assert decision["eligible_for_paper_candidate"] is False
    reason = decision["reason"]
    for fragment in ("sharpe_ratio", "trade_count", "total_return", "max_drawdown"):
        assert fragment in reason


# --- degenerate input -------------------------------------------------------

def test_empty_and_missing_metrics_refuse_without_raising():
    for payload in (
        {"id": 1, "metrics": {}},
        {"id": 2},
        {"id": 3, "metrics": None},
        {"id": 4, "metrics": {"out_of_sample_metrics": {}}},
    ):
        decision = lab.promotion_decision(payload)
        assert decision["eligible_for_paper_candidate"] is False


def test_out_of_sample_block_that_is_not_a_dict_refuses():
    for value in (0, "", [], "oos"):
        decision = lab.promotion_decision(
            {"id": 5, "metrics": {"out_of_sample_metrics": value}}
        )
        assert decision["eligible_for_paper_candidate"] is False


def test_boundary_values_are_accepted_exactly_at_the_threshold():
    decision = lab.promotion_decision(
        {"id": 6, "metrics": {
            "out_of_sample_metrics": passing(
                sharpe_ratio=0.5, trade_count=10, total_return=0.000001, max_drawdown=-0.15
            )
        }}
    )
    assert decision["eligible_for_paper_candidate"] is True
