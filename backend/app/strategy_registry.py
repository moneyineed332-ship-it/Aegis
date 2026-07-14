STRATEGIES = [
    {"id": "sma_crossover_long_flat", "name": "SMA Crossover", "type": "trend_following", "status": "research"},
    {"id": "donchian_breakout_long_flat", "name": "Donchian Breakout", "type": "trend_following", "status": "research"},
    {"id": "mean_reversion_bollinger", "name": "Mean Reversion Bollinger", "type": "mean_reversion", "status": "research"},
    {"id": "grid_adaptive", "name": "Grid Adaptatif", "type": "grid", "status": "research"},
]


def list_strategies() -> list[dict]:
    return STRATEGIES
