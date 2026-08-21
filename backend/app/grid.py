"""Enhanced grid trading with volatility-adaptive grid steps and max drawdown protection.

Improvements:
- Grid step adapts to current volatility (ATR-based)
- Max drawdown protection (auto-close if drawdown exceeds threshold)
- Grid step recalculated on re-center
- Sortino/Calmar ratios
"""

import logging
import math
from statistics import fmean, stdev

logger = logging.getLogger(__name__)


def _compute_atr(candles: list[dict], period: int = 14) -> list[float]:
    if len(candles) < period + 1:
        return [0.0] * len(candles)
    true_ranges = [0.0]
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        true_ranges.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr_series = [0.0] * period
    atr_val = fmean(true_ranges[1:period + 1])
    atr_series.append(atr_val)
    for i in range(period + 1, len(true_ranges)):
        atr_val = (atr_val * (period - 1) + true_ranges[i]) / period
        atr_series.append(atr_val)
    return atr_series


def _periods_per_year(interval: str) -> int:
    return {"5m": 105_120, "15m": 35_040, "1h": 8_760, "4h": 2_190, "1d": 365}.get(interval, 8_760)


def _sortino_ratio(returns: list[float], ppy: int) -> float:
    if len(returns) < 2:
        return 0.0
    downside = [r for r in returns if r < 0]
    if len(downside) < 2:
        return 0.0
    ds = stdev(downside)
    return round(fmean(returns) / ds * math.sqrt(ppy), 4) if ds > 0 else 0.0


def run_grid(candles: list[dict], parameters: dict) -> dict:
    """Adaptive grid with volatility-based step and max drawdown protection."""
    grid_count = parameters["grid_count"]
    grid_spread = parameters["grid_spread_pct"]
    initial_capital = parameters["initial_capital"]
    allocation = parameters["allocation"]
    fee_rate = parameters["fee_bps"] / 10_000
    slippage_rate = parameters["slippage_bps"] / 10_000
    interval = parameters.get("interval", "1h")
    max_drawdown_limit = parameters.get("max_drawdown_limit", -0.25)
    use_atr_grid = parameters.get("use_atr_grid", True)
    atr_mult = parameters.get("atr_grid_multiplier", 0.5)

    if len(candles) < 2:
        raise ValueError("Not enough candles for grid trading.")

    atr_series = _compute_atr(candles)
    cash = initial_capital
    quantity = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    returns: list[float] = []

    # Initialize grid
    base_price = candles[0]["close"]
    half_grid = grid_count // 2
    grid_step = base_price * grid_spread
    grid_levels = [base_price + (i - half_grid) * grid_step for i in range(grid_count)]
    pending_buys: set[int] = set(range(half_grid))
    pending_sells: set[int] = set(range(half_grid + 1, grid_count))
    peak_equity = initial_capital
    drawdown_halt = False

    for idx, candle in enumerate(candles):
        close = candle["close"]

        if drawdown_halt:
            equity = cash + quantity * close
            if equity_curve:
                returns.append(equity / equity_curve[-1] - 1)
            equity_curve.append(equity)
            continue

        # Volatility-adaptive grid step
        if use_atr_grid and atr_series[idx] > 0:
            grid_step = atr_series[idx] * atr_mult * close / max(close, 1)
            grid_levels = [base_price + (i - half_grid) * grid_step for i in range(grid_count)]

        # Check buy levels
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

        # Check sell levels
        for level_idx in sorted(pending_sells):
            level = grid_levels[level_idx]
            if close >= level and quantity > 0:
                sell_value = min(quantity * close, (initial_capital * allocation) / grid_count)
                execution_price = close * (1 - slippage_rate)
                qty = min(sell_value / execution_price, quantity)
                proceeds = qty * execution_price
                fee = proceeds * fee_rate
                cash += proceeds - fee
                quantity -= qty
                trades.append({"side": "sell", "price": execution_price, "time": candle["close_time"], "fee": fee, "grid_level": level_idx})
                pending_sells.discard(level_idx)
                pending_buys.add(level_idx)

        # Re-center grid with recalculated step
        if close < grid_levels[0] or close > grid_levels[-1]:
            base_price = close
            if use_atr_grid and atr_series[idx] > 0:
                grid_step = atr_series[idx] * atr_mult
            grid_levels = [base_price + (i - half_grid) * grid_step for i in range(grid_count)]
            pending_buys = set(range(half_grid))
            pending_sells = set(range(half_grid + 1, grid_count))

        equity = cash + quantity * close
        peak_equity = max(peak_equity, equity)
        dd = equity / peak_equity - 1
        if dd < max_drawdown_limit:
            drawdown_halt = True
            trades.append({"side": "drawdown_exit", "price": close, "time": candle["close_time"], "fee": 0, "grid_level": -1})
            cash += quantity * close * (1 - fee_rate)
            quantity = 0.0
            equity = cash

        if equity_curve:
            returns.append(equity / equity_curve[-1] - 1)
        equity_curve.append(equity)

    if not equity_curve:
        return {"final_equity": initial_capital, "total_return": 0, "max_drawdown": 0, "sharpe_ratio": 0, "sortino_ratio": 0, "trade_count": 0, "win_rate": 0}

    final_equity = equity_curve[-1]
    peak, max_drawdown = equity_curve[0], 0.0
    for eq in equity_curve:
        peak = max(peak, eq)
        max_drawdown = min(max_drawdown, eq / peak - 1)

    completed = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for b, s in completed if s["side"] != "drawdown_exit" and s["price"] > b["price"])
    ppy = _periods_per_year(interval)
    sharpe = fmean(returns) / stdev(returns) * math.sqrt(ppy) if len(returns) > 1 and stdev(returns) > 0 else 0.0
    sortino = _sortino_ratio(returns, ppy)

    return {
        "final_equity": round(final_equity, 2),
        "total_return": round(final_equity / initial_capital - 1, 6),
        "max_drawdown": round(max_drawdown, 6),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": sortino,
        "trade_count": len([t for t in trades if t["side"] != "drawdown_exit"]),
        "win_rate": round(wins / max(len(completed), 1), 6),
    }


def run_grid_walk_forward(candles: list[dict], base_parameters: dict, candidates: list[tuple[int, float]]) -> dict:
    """Walk-forward with embargo for grid."""
    train_size = base_parameters["train_candles"]
    test_size = base_parameters["test_candles"]
    embargo = base_parameters.get("embargo_candles", 10)
    if len(candles) < train_size + test_size + embargo:
        raise ValueError("Not enough candles.")
    selected = candles[-(train_size + embargo + test_size):]
    train_candles = selected[:train_size]
    test_candles = selected[train_size + embargo:]
    evaluations = []
    for gc, gs in candidates:
        try:
            metrics = run_grid(train_candles, {**base_parameters, "grid_count": gc, "grid_spread_pct": gs})
            evaluations.append({"grid_count": gc, "grid_spread_pct": gs, "train_metrics": metrics})
        except Exception as e:
            logger.debug("Grid walk-forward candidate failed: gc=%s gs=%s — %s", gc, gs, e, exc_info=True)
            continue
    if not evaluations:
        raise ValueError("All candidates failed.")
    winner = max(evaluations, key=lambda e: e["train_metrics"]["sharpe_ratio"])
    oos = run_grid(test_candles, {**base_parameters, "grid_count": winner["grid_count"], "grid_spread_pct": winner["grid_spread_pct"]})
    return {
        "selected_parameters": {"grid_count": winner["grid_count"], "grid_spread_pct": winner["grid_spread_pct"]},
        "train_metrics": winner["train_metrics"],
        "out_of_sample_metrics": oos,
        "candidates": evaluations,
    }
