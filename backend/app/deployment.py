"""Deployment pipeline: validates strategies through stages before promotion.

Pipeline: idea → simulation → backtest → walk_forward → paper_trading → validation → deployment
"""

from datetime import datetime, timezone

from . import storage as _storage

PIPELINE_STAGES = [
    "idea",
    "simulation",
    "backtest",
    "walk_forward",
    "paper_trading",
    "validation",
    "deployment",
]

# Minimum thresholds to pass each stage
STAGE_THRESHOLDS = {
    "simulation": {"min_candles": 100},
    "backtest": {"min_sharpe": 0.0, "min_trades": 5},
    "walk_forward": {"min_sharpe": 0.3, "min_trades": 10, "max_drawdown": -0.20},
    "paper_trading": {"min_sharpe": 0.5, "min_trades": 20, "max_drawdown": -0.15},
    "validation": {"min_sharpe": 0.7, "min_trades": 30, "max_drawdown": -0.12},
}


def create_pipeline(strategy_id: str, symbol: str, parameters: dict) -> dict:
    """Create a new deployment pipeline for a strategy."""
    pipeline = {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "parameters": parameters,
        "current_stage": "idea",
        "stages": {stage: {"status": "pending", "started_at": None, "completed_at": None, "result": None} for stage in PIPELINE_STAGES},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _persist_pipeline(pipeline)
    return pipeline


def advance_stage(pipeline: dict, stage: str, result: dict) -> dict:
    """Advance a pipeline stage with validation result."""
    if stage != pipeline["current_stage"]:
        return {**pipeline, "error": f"Expected stage {pipeline['current_stage']}, got {stage}"}

    stages = pipeline["stages"].copy()
    stages[stage] = {
        "status": "passed" if result.get("passed", False) else "failed",
        "started_at": stages[stage]["started_at"] or datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }

    # Determine next stage
    stage_idx = PIPELINE_STAGES.index(stage)
    if result.get("passed", False) and stage_idx < len(PIPELINE_STAGES) - 1:
        next_stage = PIPELINE_STAGES[stage_idx + 1]
        stages[next_stage] = {**stages[next_stage], "status": "in_progress", "started_at": datetime.now(timezone.utc).isoformat()}
        current_stage = next_stage
    elif result.get("passed", False) and stage_idx == len(PIPELINE_STAGES) - 1:
        current_stage = "completed"
    else:
        current_stage = "failed"

    pipeline_out = {
        **pipeline,
        "current_stage": current_stage,
        "stages": stages,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _persist_pipeline(pipeline_out)
    return pipeline_out


def validate_backtest(metrics: dict, stage: str = "backtest") -> dict:
    """Validate backtest metrics against stage thresholds."""
    thresholds = STAGE_THRESHOLDS.get(stage, {})
    errors = []

    sharpe = metrics.get("sharpe_ratio", 0)
    trades = metrics.get("trade_count", 0)
    drawdown = metrics.get("max_drawdown", 0)

    if sharpe < thresholds.get("min_sharpe", -999):
        errors.append(f"Sharpe {sharpe:.2f} < minimum {thresholds['min_sharpe']}")
    if trades < thresholds.get("min_trades", 0):
        errors.append(f"Trade count {trades} < minimum {thresholds['min_trades']}")
    if drawdown < thresholds.get("max_drawdown", -999):
        errors.append(f"Drawdown {drawdown*100:.1f}% < maximum {thresholds['max_drawdown']*100:.0f}%")

    passed = len(errors) == 0
    return {
        "passed": passed,
        "stage": stage,
        "metrics": {
            "sharpe": round(sharpe, 4),
            "return": round(metrics.get("total_return", 0) * 100, 2),
            "drawdown": round(drawdown * 100, 2),
            "trades": trades,
        },
        "thresholds": thresholds,
        "errors": errors,
    }


def rollback(pipeline: dict, reason: str) -> dict:
    """Rollback a pipeline to the previous stage."""
    current_idx = PIPELINE_STAGES.index(pipeline["current_stage"]) if pipeline["current_stage"] in PIPELINE_STAGES else len(PIPELINE_STAGES) - 1
    if current_idx > 0:
        prev_stage = PIPELINE_STAGES[current_idx - 1]
        stages = pipeline["stages"].copy()
        stages[pipeline["current_stage"]] = {**stages[pipeline["current_stage"]], "status": "rolled_back"}
        stages[prev_stage] = {**stages[prev_stage], "status": "in_progress"}
        pipeline_out = {
            **pipeline,
            "current_stage": prev_stage,
            "stages": stages,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "rollback_reason": reason,
        }
        _persist_pipeline(pipeline_out)
        return pipeline_out
    return pipeline


def get_pipeline_status(pipeline: dict) -> dict:
    """Get a human-readable status of the pipeline."""
    stage = pipeline["current_stage"]
    if stage == "completed":
        return {"status": "ready_for_deployment", "message": "All stages passed. Strategy is ready for deployment."}
    if stage == "failed":
        failed_stages = [s for s, v in pipeline["stages"].items() if v["status"] == "failed"]
        return {"status": "blocked", "message": f"Failed at stage(s): {', '.join(failed_stages)}"}
    return {"status": "in_progress", "current_stage": stage, "message": f"Currently at stage: {stage}"}


# --- Persistence helpers ---

def _persist_pipeline(pipeline: dict) -> None:
    """Save pipeline to DB (best-effort)."""
    try:
        _storage.save_pipeline(pipeline)
    except Exception:
        pass


def restore_pipelines() -> list[dict]:
    """Restore all pipelines from DB on engine startup."""
    return _storage.list_pipelines()
