"""Grid trading backtesting for paper research."""

import math
from statistics import fmean, stdev


def run_grid(candles: list[dict], parameters: dict) -> dict:
    """Adaptive grid strategy: place buy/sell orders at grid levels around current price.

    - When price drops to a grid level below → buy
    - When price rises to a grid level above → sell
    - Grid is re-centered when price moves outside the grid
    """
    grid_count = parameters["grid_count"]
    grid_spread = parameters["grid_spread_pct"]
    initial_capital = parameters["initial_capital"]
    allocation = parameters["allocation"]
    fee_rate = parameters["fee_bps"] / 10_000
    slippage_rate = parameters["slippage_bps"] / 10_000

    if len(candles) < 2:
        raise ValueError("Not enough candles for grid trading.")

    cash = initial_capital
    quantity = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    returns: list[float] = []

    # Initialize grid around first close
    base_price = candles[0]["close"]
    half_grid = grid_count // 2
    grid_step = base_price * grid_spread
    grid_levels = [base_price + (i - half_grid) * grid_step for i in range(grid_count)]
    # Track which levels have open buy orders (not yet filled)
    pending_buys: set[int] = set(range(half_grid))  # lower half = buy levels
    pending_sells: set[int] = set(range(half_grid + 1, grid_count))  # upper half = sell levels

    for candle in candles:
        close = candle["close"]

        # Check buy levels (price dropped to or below grid level)
        for level_idx in sorted(pending_buys):
            level = grid_levels[level_idx]
            if close <= level and cash > 0:
                order_value = min(cash, (initial_capital * allocation) / grid_count)
                execution_price = close * (1 + slippage_rate)
                fee = order_value * fee_rate
                qty = (order_value - fee) / execution_price
                if qty > 0:
                    quantity += qty
                    cash -= order_value
                    trades.append({"side": "buy", "price": execution_price, "time": candle["close_time"], "fee": fee, "grid_level": level_idx})
                    pending_buys.discard(level_idx)
                    pending_sells.add(level_idx)

        # Check sell levels (price rose to or above grid level)
        for level_idx in sorted(pending_sells):
            level = grid_levels[level_idx]
            if close >= level and quantity > 0:
                sell_value = min(quantity * close, (initial_capital * allocation) / grid_count)
                execution_price = close * (1 - slippage_rate)
                qty = sell_value / execution_price
                qty = min(qty, quantity)
                proceeds = qty * execution_price
                fee = proceeds * fee_rate
                cash += proceeds - fee
                quantity -= qty
                trades.append({"side": "sell", "price": execution_price, "time": candle["close_time"], "fee": fee, "grid_level": level_idx})
                pending_sells.discard(level_idx)
                pending_buys.add(level_idx)

        # Re-center grid if price moved outside
        if close < grid_levels[0] or close > grid_levels[-1]:
            base_price = close
            grid_levels = [base_price + (i - half_grid) * grid_step for i in range(grid_count)]
            pending_buys = set(range(half_grid))
            pending_sells = set(range(half_grid + 1, grid_count))

        equity = cash + quantity * close
        if equity_curve:
            returns.append(equity / equity_curve[-1] - 1)
        equity_curve.append(equity)

    if not equity_curve:
        return {"final_equity": initial_capital, "total_return": 0, "max_drawdown": 0, "sharpe_ratio": 0, "trade_count": 0, "win_rate": 0}

    final_equity = equity_curve[-1]
    high_water_mark = equity_curve[0]
    max_drawdown = 0.0
    for eq in equity_curve:
        high_water_mark = max(high_water_mark, eq)
        max_drawdown = min(max_drawdown, eq / high_water_mark - 1)

    completed_trades = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for buy, sell in completed_trades if sell["price"] > buy["price"])
    periods_per_year = {"5m": 105_120, "15m": 35_040, "1h": 8_760, "4h": 2_190}.get(parameters["interval"], 8_760)
    sharpe = 0.0
    if len(returns) > 1 and stdev(returns) > 0:
        sharpe = fmean(returns) / stdev(returns) * math.sqrt(periods_per_year)

    return {
        "final_equity": round(final_equity, 2),
        "total_return": round(final_equity / initial_capital - 1, 6),
        "max_drawdown": round(max_drawdown, 6),
        "sharpe_ratio": round(sharpe, 4),
        "trade_count": len(completed_trades),
        "win_rate": round(wins / len(completed_trades), 6) if completed_trades else 0.0,
    }


def run_grid_walk_forward(candles: list[dict], base_parameters: dict, candidates: list[tuple[int, float]]) -> dict:
    """Walk-forward optimization for grid (grid_count, grid_spread_pct)."""
    train_size = base_parameters["train_candles"]
    test_size = base_parameters["test_candles"]
    if len(candles) < train_size + test_size:
        raise ValueError("Not enough stored candles for the requested walk-forward split.")
    selected = candles[-(train_size + test_size):]
    train_candles = selected[:train_size]
    test_candles = selected[train_size:]
    evaluations = []
    for grid_count, grid_spread in candidates:
        metrics = run_grid(
            train_candles,
            {**base_parameters, "grid_count": grid_count, "grid_spread_pct": grid_spread},
        )
        evaluations.append({"grid_count": grid_count, "grid_spread_pct": grid_spread, "train_metrics": metrics})
    winner = max(evaluations, key=lambda item: item["train_metrics"]["sharpe_ratio"])
    out_of_sample = run_grid(
        test_candles,
        {**base_parameters, "grid_count": winner["grid_count"], "grid_spread_pct": winner["grid_spread_pct"]},
    )
    return {
        "selected_parameters": {"grid_count": winner["grid_count"], "grid_spread_pct": winner["grid_spread_pct"]},
        "train_metrics": winner["train_metrics"],
        "out_of_sample_metrics": out_of_sample,
        "candidates": evaluations,
    }
