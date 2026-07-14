"""Decision journal with feedback loop: tracks outcomes of past decisions."""

from datetime import datetime, timezone
from statistics import fmean


def track_outcome(decision: dict, current_price: float, entry_price: float | None = None) -> dict:
    """Track the outcome of a past decision by comparing with current market state.

    Each decision should have: {analysis, risk, recommendation, created_at}.
    """
    recommendation = decision.get("recommendation", {})
    action = recommendation.get("action", "unknown")
    strategy = recommendation.get("strategy")

    # Calculate performance since decision
    decision_time = decision.get("created_at", "")
    pnl = None
    hit_rate = None

    if entry_price and current_price and entry_price > 0:
        if action == "research" and strategy:
            # Assume a long entry was taken
            pnl = (current_price - entry_price) / entry_price
        elif action == "wait":
            # No position taken — compare with what would have happened
            pnl = 0  # No gain, no loss

    return {
        "decision_id": decision.get("id"),
        "action": action,
        "strategy": strategy,
        "decision_time": decision_time,
        "entry_price": entry_price,
        "current_price": current_price,
        "pnl_since_decision": round(pnl, 6) if pnl is not None else None,
        "outcome": _classify_outcome(pnl, action),
    }


def _classify_outcome(pnl: float | None, action: str) -> str:
    """Classify whether the decision was correct in hindsight."""
    if pnl is None:
        return "unknown"
    if action == "wait":
        if pnl < -0.02:
            return "good_wait"  # Price dropped, waiting was correct
        elif pnl > 0.02:
            return "missed_opportunity"  # Price rose, should have entered
        return "neutral_wait"
    if action == "research":
        if pnl > 0:
            return "correct_entry"
        elif pnl < 0:
            return "wrong_entry"
        return "neutral_entry"
    return "unknown"


def analyze_decisions(decisions: list[dict], current_prices: dict[str, float]) -> dict:
    """Analyze all past decisions and compute aggregate metrics."""
    if not decisions:
        return {
            "total_decisions": 0,
            "accuracy": None,
            "avg_pnl": None,
            "best_decision": None,
            "worst_decision": None,
            "by_action": {},
        }

    outcomes = []
    for dec in decisions:
        symbol = dec.get("symbol", "BTCUSDT")
        current_price = current_prices.get(symbol, 0)
        entry_price = dec.get("decision", {}).get("risk", {}).get("entry_price")
        tracked = track_outcome(dec, current_price, entry_price)
        outcomes.append({**tracked, "symbol": symbol})

    # Aggregate metrics
    valid_outcomes = [o for o in outcomes if o["pnl_since_decision"] is not None]
    pnls = [o["pnl_since_decision"] for o in valid_outcomes]

    correct = sum(1 for o in outcomes if o["outcome"] in ("correct_entry", "good_wait"))
    total_classifiable = sum(1 for o in outcomes if o["outcome"] not in ("unknown",))
    accuracy = correct / total_classifiable if total_classifiable > 0 else None

    # By action breakdown
    by_action = {}
    for o in outcomes:
        action = o["action"]
        if action not in by_action:
            by_action[action] = {"count": 0, "correct": 0, "avg_pnl": []}
        by_action[action]["count"] += 1
        if o["outcome"] in ("correct_entry", "good_wait"):
            by_action[action]["correct"] += 1
        if o["pnl_since_decision"] is not None:
            by_action[action]["avg_pnl"].append(o["pnl_since_decision"])

    for action in by_action:
        pnl_list = by_action[action]["avg_pnl"]
        by_action[action]["avg_pnl"] = round(fmean(pnl_list), 6) if pnl_list else None
        by_action[action]["accuracy"] = round(by_action[action]["correct"] / max(by_action[action]["count"], 1), 4)

    # Best and worst
    if valid_outcomes:
        best = max(valid_outcomes, key=lambda o: o["pnl_since_decision"])
        worst = min(valid_outcomes, key=lambda o: o["pnl_since_decision"])
    else:
        best = worst = None

    return {
        "total_decisions": len(decisions),
        "accuracy": round(accuracy, 4) if accuracy is not None else None,
        "avg_pnl": round(fmean(pnls), 6) if pnls else None,
        "total_pnl": round(sum(pnls), 6) if pnls else None,
        "best_decision": best,
        "worst_decision": worst,
        "by_action": by_action,
        "outcomes": outcomes[:20],
    }


def feedback_summary(analyses: list[dict]) -> dict:
    """Generate a human-readable feedback summary."""
    if not analyses:
        return {"message": "No decisions to analyze.", "grade": "N/A", "strengths": [], "weaknesses": []}

    accuracy = analyses.get("accuracy")
    avg_pnl = analyses.get("avg_pnl")

    if accuracy is None:
        grade = "Insufficient data"
    elif accuracy >= 0.7:
        grade = "A — Strong decision-making"
    elif accuracy >= 0.5:
        grade = "B — Decent, room for improvement"
    elif accuracy >= 0.3:
        grade = "C — Needs significant improvement"
    else:
        grade = "D — Poor decision quality"

    strengths = []
    weaknesses = []
    by_action = analyses.get("by_action", {})

    if by_action.get("wait", {}).get("accuracy", 0) >= 0.7:
        strengths.append("Good at identifying when to stay out")
    if by_action.get("research", {}).get("accuracy", 0) >= 0.7:
        strengths.append("Strong strategy selection when entering")
    if by_action.get("wait", {}).get("accuracy", 0) < 0.5:
        weaknesses.append("Missing too many opportunities when waiting")
    if by_action.get("research", {}).get("accuracy", 0) < 0.5:
        weaknesses.append("Entering positions at wrong times")

    if avg_pnl is not None and avg_pnl > 0:
        strengths.append(f"Positive average PnL ({avg_pnl*100:.2f}%)")
    elif avg_pnl is not None and avg_pnl < 0:
        weaknesses.append(f"Negative average PnL ({avg_pnl*100:.2f}%)")

    return {
        "message": f"Based on {analyses['total_decisions']} decisions",
        "grade": grade,
        "strengths": strengths,
        "weaknesses": weaknesses,
    }
