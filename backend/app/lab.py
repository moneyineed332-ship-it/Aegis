"""Promotion gate for research strategies; never places orders."""


def promotion_decision(backtest: dict) -> dict:
    metrics = backtest["metrics"].get("out_of_sample_metrics", backtest["metrics"])
    accepted = metrics.get("total_return", 0) > 0 and metrics.get("sharpe_ratio", 0) >= 0.5 and metrics.get("trade_count", 0) >= 10 and metrics.get("max_drawdown", 0) >= -0.15
    return {"backtest_id": backtest["id"], "eligible_for_paper_candidate": accepted, "reason": "Meets minimum out-of-sample research thresholds." if accepted else "Does not meet minimum out-of-sample research thresholds."}
