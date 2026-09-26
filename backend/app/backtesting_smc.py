"""SMC/ICT + Multi-Timeframe + Multi-Scale Crossover backtesting."""

import logging

from statistics import fmean

from .execution_model import assert_no_lookahead, fill_price, intrabar_exit_price
from .metrics_core import calmar_ratio, max_drawdown, periods_per_year, sharpe_ratio, signed_trade_returns, sortino_ratio

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
    return periods_per_year(interval)


def _compute_metrics(equity_curve: list[float], initial_capital: float, trades: list[dict], interval: str) -> dict:
    if not equity_curve:
        raise ValueError("No equity data generated.")
    final = equity_curve[-1]
    drawdown = max_drawdown(equity_curve)
    returns = [equity_curve[i] / equity_curve[i - 1] - 1 for i in range(1, len(equity_curve))]
    completed = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for b, s in completed if s["price"] > b["price"])
    ppy = _periods_per_year(interval)
    return {
        "final_equity": round(final, 2),
        "total_return": round(final / initial_capital - 1, 6),
        "max_drawdown": round(drawdown, 6),
        "sharpe_ratio": sharpe_ratio(returns, ppy),
        "sortino_ratio": sortino_ratio(returns, ppy),
        "calmar_ratio": calmar_ratio(final / initial_capital - 1, drawdown, len(returns), ppy),
        "trade_count": len(completed),
        "win_rate": round(wins / len(completed), 6) if completed else 0.0,
        "avg_trade_return": round(fmean([s["price"] / b["price"] - 1 for b, s in completed]), 6) if completed else 0.0,
        "trade_returns": signed_trade_returns(completed),
    }


def run_smc_ict(candles: list[dict], parameters: dict,
    trades_out: list[dict] | None = None,
) -> dict:
    from .smc_ict import generate_signal
    ic = parameters["initial_capital"]
    alloc = parameters["allocation"]
    fee = parameters["fee_bps"] / 10_000
    slip = parameters["slippage_bps"] / 10_000
    interval = parameters.get("interval", "1h")
    min_score = parameters.get("min_score", 40)
    atr_mult = parameters.get("atr_stop_multiplier", 2.0)
    lb = parameters.get("lookback", 50)
    if len(candles) < lb + 10:
        raise ValueError("Not enough candles for SMC/ICT backtest.")
    cash, qty, entry = ic, 0.0, 0.0
    sl, tp, trail, hi = 0.0, 0.0, 0.0, 0.0
    trades, eq_curve = [], []
    atr = _compute_atr(candles)
    # Bar the position was filled on. Stops and targets may only be evaluated
    # from the following bar onwards.
    fill_idx = -1
    for idx in range(lb, len(candles)):
        c, h, lo = candles[idx]["close"], candles[idx]["high"], candles[idx]["low"]
        win = candles[max(0, idx - lb):idx + 1]
        sig = generate_signal(win)
        if qty > 0:
            hi = max(hi, h)
            trail = hi - atr_mult * atr[idx]

        # --- Exits evaluated on the bar AFTER the fill ---
        if qty > 0 and idx > fill_idx:
            hit = intrabar_exit_price(candles[idx], "buy", sl, tp)
            if hit is not None:
                ep2, reason = hit
                # Intrabar trigger: the stop/target was armed on an earlier bar,
                # so the last bar known before this one is idx - 1.
                sig_idx, fill_i = idx - 1, idx
            elif c < trail:
                ep2, reason = trail, "trailing"
                sig_idx, fill_i = idx - 1, idx
            elif sig["action"] == "sell":
                ep2 = fill_price(candles, idx, "sell", slip)
                reason = "signal"
                sig_idx, fill_i = idx, idx + 1
            else:
                ep2 = None
            if ep2 is not None:
                proceeds = qty * ep2
                f2 = proceeds * fee
                cash += proceeds - f2
                trades.append({"side": "sell", "price": ep2, "time": candles[fill_i]["close_time"], "fee": f2, "signal_index": sig_idx, "fill_index": fill_i, "exit_reason": reason})
                qty = 0.0

        # --- Entry: decided on bar idx, filled at the NEXT bar's open ---
        if sig["action"] == "buy" and sig["score"] >= min_score and qty == 0:
            ep = fill_price(candles, idx, "buy", slip)
            if ep is not None:
                ov = cash * alloc
                f = ov * fee
                qty = (ov - f) / ep
                cash -= ov
                entry = ep
                hi = candles[idx + 1]["high"]
                sl = sig.get("stop_loss") or (entry * 0.97)
                tp = sig.get("take_profit") or (entry * 1.06)
                trail = entry - atr_mult * atr[idx]
                fill_idx = idx + 1
                trades.append({"side": "buy", "price": ep, "time": candles[idx + 1]["close_time"], "fee": f, "score": sig["score"], "signal_index": idx, "fill_index": idx + 1})

        eq_curve.append(cash + qty * c)
    assert_no_lookahead(trades, candles)
    if trades_out is not None:
        trades_out.extend(trades)
    metrics = _compute_metrics(eq_curve, ic, trades, interval)
    return {"strategy": "smc_ict", **metrics}


def run_multi_timeframe(candles: list[dict], parameters: dict,
    trades_out: list[dict] | None = None,
) -> dict:
    from .multi_timeframe import analyze_multi_timeframe
    ic = parameters["initial_capital"]
    alloc = parameters["allocation"]
    fee = parameters["fee_bps"] / 10_000
    slip = parameters["slippage_bps"] / 10_000
    interval = parameters.get("interval", "1h")
    min_conf = parameters.get("min_confluence", 40)
    atr_mult = parameters.get("atr_stop_multiplier", 2.5)
    if len(candles) < 100:
        raise ValueError("Not enough candles for multi-timeframe backtest.")

    def resample(cl, factor):
        r = []
        for i in range(0, len(cl), factor):
            ch = cl[i:i + factor]
            if not ch:
                continue
            r.append({"open": ch[0]["open"], "high": max(c["high"] for c in ch),
                       "low": min(c["low"] for c in ch), "close": ch[-1]["close"],
                       "volume": sum(c.get("volume", 0) for c in ch), "close_time": ch[-1]["close_time"]})
        return r

    cash, qty, entry = ic, 0.0, 0.0
    trail, hi = 0.0, 0.0
    trades, eq_curve = [], []
    atr = _compute_atr(candles)
    fill_idx = -1
    for idx in range(100, len(candles)):
        c, h = candles[idx]["close"], candles[idx]["high"]
        c1h = candles[max(0, idx - 100):idx + 1]
        c4h = resample(c1h, 4)
        c1d = resample(c1h, 24)
        mtf = analyze_multi_timeframe({"1h": c1h, "4h": c4h, "1d": c1d})
        trend, score = mtf.get("overall_trend", "neutral"), mtf.get("confluence_score", 0)
        if qty > 0:
            hi = max(hi, h)
            trail = hi - atr_mult * atr[idx]

        if qty > 0 and idx > fill_idx:
            if c < trail:
                # Trailing stop: intrabar trigger on this bar, armed earlier.
                ep2, sig_idx, fill_i = trail, idx - 1, idx
            elif trend == "bearish":
                # Signal decided on this bar -> filled at the next bar's open.
                ep2, sig_idx, fill_i = fill_price(candles, idx, "sell", slip), idx, idx + 1
            else:
                ep2, sig_idx, fill_i = None, idx, idx
            if ep2 is not None:
                proceeds = qty * ep2
                f2 = proceeds * fee
                cash += proceeds - f2
                trades.append({"side": "sell", "price": ep2, "time": candles[fill_i]["close_time"], "fee": f2, "signal_index": sig_idx, "fill_index": fill_i})
                qty = 0.0

        if trend == "bullish" and score >= min_conf and qty == 0:
            ep = fill_price(candles, idx, "buy", slip)
            if ep is not None:
                ov = cash * alloc
                f = ov * fee
                qty = (ov - f) / ep
                cash -= ov
                entry = ep
                hi = candles[idx + 1]["high"]
                trail = entry - atr_mult * atr[idx]
                fill_idx = idx + 1
                trades.append({"side": "buy", "price": ep, "time": candles[idx + 1]["close_time"], "fee": f, "score": score, "signal_index": idx, "fill_index": idx + 1})

        eq_curve.append(cash + qty * c)
    assert_no_lookahead(trades, candles)
    if trades_out is not None:
        trades_out.extend(trades)
    metrics = _compute_metrics(eq_curve, ic, trades, interval)
    return {"strategy": "multi_timeframe_confluence", **metrics}


def run_multi_scale_crossover(candles: list[dict], parameters: dict,
    trades_out: list[dict] | None = None,
) -> dict:
    from .indicators import multi_scale_crossover as msc_analyze
    ic = parameters["initial_capital"]
    alloc = parameters["allocation"]
    fee = parameters["fee_bps"] / 10_000
    slip = parameters["slippage_bps"] / 10_000
    interval = parameters.get("interval", "1h")
    min_score = parameters.get("min_score", 40)
    atr_mult = parameters.get("atr_stop_multiplier", 2.5)
    if len(candles) < 60:
        raise ValueError("Not enough candles for multi-scale crossover backtest.")
    cash, qty, entry = ic, 0.0, 0.0
    trail, hi = 0.0, 0.0
    trades, eq_curve = [], []
    atr = _compute_atr(candles)
    fill_idx = -1
    for idx in range(50, len(candles)):
        c, h = candles[idx]["close"], candles[idx]["high"]
        win = candles[max(0, idx - 50):idx + 1]
        msc = msc_analyze(win)
        if qty > 0:
            hi = max(hi, h)
            trail = hi - atr_mult * atr[idx]

        if qty > 0 and idx > fill_idx:
            if c < trail:
                # Trailing stop: intrabar trigger on this bar, armed earlier.
                ep2, sig_idx, fill_i = trail, idx - 1, idx
            elif msc["signal"] == "bearish":
                # Signal decided on this bar -> filled at the next bar's open.
                ep2, sig_idx, fill_i = fill_price(candles, idx, "sell", slip), idx, idx + 1
            else:
                ep2, sig_idx, fill_i = None, idx, idx
            if ep2 is not None:
                proceeds = qty * ep2
                f2 = proceeds * fee
                cash += proceeds - f2
                trades.append({"side": "sell", "price": ep2, "time": candles[fill_i]["close_time"], "fee": f2, "signal_index": sig_idx, "fill_index": fill_i})
                qty = 0.0

        if msc["signal"] == "bullish" and msc["score"] >= min_score and qty == 0:
            ep = fill_price(candles, idx, "buy", slip)
            if ep is not None:
                ov = cash * alloc
                f = ov * fee
                qty = (ov - f) / ep
                cash -= ov
                entry = ep
                hi = candles[idx + 1]["high"]
                trail = entry - atr_mult * atr[idx]
                fill_idx = idx + 1
                trades.append({"side": "buy", "price": ep, "time": candles[idx + 1]["close_time"], "fee": f, "score": msc["score"], "signal_index": idx, "fill_index": idx + 1})

        eq_curve.append(cash + qty * c)
    assert_no_lookahead(trades, candles)
    if trades_out is not None:
        trades_out.extend(trades)
    metrics = _compute_metrics(eq_curve, ic, trades, interval)
    return {"strategy": "multi_scale_crossover", **metrics}


def run_smc_ict_walk_forward(candles: list[dict], base_parameters: dict, candidates: list[dict]) -> dict:
    """Walk-forward with embargo for SMC/ICT."""
    train_size = base_parameters["train_candles"]
    test_size = base_parameters["test_candles"]
    embargo = base_parameters.get("embargo_candles", 10)
    if len(candles) < train_size + test_size + embargo:
        raise ValueError("Not enough candles for SMC/ICT walk-forward.")
    train = candles[-(train_size + embargo + test_size):-test_size - embargo]
    test = candles[-test_size:]
    evaluations = []
    for params in candidates:
        try:
            merged = {**base_parameters, **params}
            metrics = run_smc_ict(train, merged)
            evaluations.append({**params, "train_metrics": metrics})
        except Exception as e:
            logger.debug("SMC/ICT walk-forward candidate failed: %s — %s", params, e, exc_info=True)
            continue
    if not evaluations:
        raise ValueError("All SMC/ICT candidates failed.")
    winner = max(evaluations, key=lambda e: e["train_metrics"]["sharpe_ratio"])
    oos = run_smc_ict(test, {**base_parameters, **{k: v for k, v in winner.items() if k != "train_metrics"}})
    return {"selected_parameters": {k: v for k, v in winner.items() if k != "train_metrics"}, "train_metrics": winner["train_metrics"], "out_of_sample_metrics": oos, "candidates": evaluations}


def run_multi_timeframe_walk_forward(candles: list[dict], base_parameters: dict, candidates: list[dict]) -> dict:
    """Walk-forward with embargo for Multi-Timeframe."""
    train_size = base_parameters["train_candles"]
    test_size = base_parameters["test_candles"]
    embargo = base_parameters.get("embargo_candles", 10)
    if len(candles) < train_size + test_size + embargo:
        raise ValueError("Not enough candles for MTF walk-forward.")
    train = candles[-(train_size + embargo + test_size):-test_size - embargo]
    test = candles[-test_size:]
    evaluations = []
    for params in candidates:
        try:
            merged = {**base_parameters, **params}
            metrics = run_multi_timeframe(train, merged)
            evaluations.append({**params, "train_metrics": metrics})
        except Exception as e:
            logger.debug("MTF walk-forward candidate failed: %s — %s", params, e, exc_info=True)
            continue
    if not evaluations:
        raise ValueError("All MTF candidates failed.")
    winner = max(evaluations, key=lambda e: e["train_metrics"]["sharpe_ratio"])
    oos = run_multi_timeframe(test, {**base_parameters, **{k: v for k, v in winner.items() if k != "train_metrics"}})
    return {"selected_parameters": {k: v for k, v in winner.items() if k != "train_metrics"}, "train_metrics": winner["train_metrics"], "out_of_sample_metrics": oos, "candidates": evaluations}
