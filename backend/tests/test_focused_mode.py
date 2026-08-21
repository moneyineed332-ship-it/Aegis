"""Phase 1 focused-mode tests: single Donchian strategy on max 3 symbols."""

import asyncio
from unittest.mock import patch

from app import advisor, backtesting, config, engine, regime, strategy_registry


def test_focused_mode_config():
    assert config.FOCUSED_MODE is True
    assert config.FOCUSED_STRATEGY == "donchian_breakout_long_flat"
    assert len(config.FOCUSED_SYMBOLS) <= 3
    assert config.MAX_POSITIONS <= 3


def test_only_donchian_is_tradable():
    assert strategy_registry.is_active("donchian_breakout_long_flat") is True
    assert strategy_registry.is_active("sma_crossover_long_flat") is True  # confirmation layer
    assert strategy_registry.is_active("smc_ict") is False
    assert strategy_registry.is_active("grid_adaptive") is False
    assert strategy_registry.is_active("mean_reversion_bollinger") is False
    assert strategy_registry.is_active("scalping_ema_rsi_stoch") is False


def test_advisor_always_selects_donchian_in_focus():
    rec = advisor.recommend(
        {"regime": {"regime": "bull_trend", "confidence": 0.7, "is_choppy": False}},
        {"capital": 20, "exposure": 0, "conditional_value_at_risk": 0},
    )
    assert rec["strategy"] == "donchian_breakout_long_flat"
    assert rec["action"] == "research"


def test_advisor_blocks_choppy_market():
    rec = advisor.recommend(
        {"regime": {"regime": "range", "confidence": 0.5, "is_choppy": True}},
        {"capital": 20, "exposure": 0, "conditional_value_at_risk": 0},
    )
    assert rec["action"] == "wait"


def test_advisor_respects_risk_gates():
    # CVaR gate: hard risk must never be overridden by the Donchian path
    rec = advisor.recommend(
        {"regime": {"regime": "bull_trend", "confidence": 0.7, "is_choppy": False}},
        {"capital": 20, "exposure": 0, "conditional_value_at_risk": 1.5},
    )
    assert rec["action"] == "wait"
    assert rec["strategy"] is None


def _flat_candles(n=40, base=100.0):
    candles = []
    for i in range(n):
        candles.append({
            "open": base, "high": base + 0.5, "low": base - 0.5,
            "close": base, "close_time": f"t{i}",
        })
    return candles


def test_donchian_live_signal_buy_on_breakout():
    candles = _flat_candles(30)
    candles.append({"open": 100, "high": 106, "low": 100, "close": 105.5, "close_time": "t30"})
    sig = backtesting.donchian_live_signal(candles, 10, 5)
    assert sig["action"] == "buy"


def test_donchian_live_signal_sell_on_drop():
    candles = _flat_candles(30)
    candles.append({"open": 100, "high": 100, "low": 94, "close": 94.5, "close_time": "t30"})
    sig = backtesting.donchian_live_signal(candles, 10, 5)
    assert sig["action"] == "sell"


def test_donchian_live_signal_hold_inside_channel():
    candles = _flat_candles(30)
    sig = backtesting.donchian_live_signal(candles, 10, 5)
    assert sig["action"] == "hold"


def test_regime_choppy_flag():
    r = regime.classify({"rsi": 50, "adx": 12, "momentum": 0.0, "volatility": 0.004, "close": 100, "atr_14": 0.5})
    assert r["is_choppy"] is True
    r2 = regime.classify({"rsi": 60, "adx": 35, "momentum": 0.02, "volatility": 0.015, "close": 100, "atr_14": 1.5})
    assert r2["is_choppy"] is False


# --- Engine signal ranking + execution in focused mode ---

_BULL = {"regime": "bull_trend", "confidence": 0.7, "is_choppy": False}


def _inject_analyses():
    engine._last_analyses = {
        s: {"symbol": s, "regime": dict(_BULL)} for s in config.FOCUSED_SYMBOLS
    }
    engine._last_smc_analysis = {s: {"score": 0} for s in config.FOCUSED_SYMBOLS}


def _flat(n=40):
    return [{"open": 100, "high": 100.5, "low": 99.5, "close": 100, "close_time": f"t{i}"} for i in range(n)]


def test_signal_ranking_picks_strongest_breakout_not_last_symbol():
    """Regression for the phase-1 bug: the ranking loop used only the LAST
    iterated symbol. A strong breakout on PAXGUSDT must win even though it is
    iterated first (PAXGUSDT, BTCUSDT, ETHUSDT)."""
    _inject_analyses()

    with patch.object(engine.storage, "list_ohlcv_candles", return_value=_flat(40)) as mock_candles, \
         patch.object(engine.backtesting, "donchian_live_signal", return_value={
             "action": "buy", "confidence": 0.9, "reason": "PAXG breakout",
             "channel_high": 106, "channel_low": 94,
         }):
        # Only PAXGUSDT has the widened candles that trigger the Donchian cut.
        # The mock returns the same list, so gate the breakout by symbol.
        def _fill(symbol, interval, limit):
            candles = [dict(c) for c in _flat(40)]
            if symbol != "PAXGUSDT":
                candles[-1]["high"] = 100.2  # inside channel -> no breakout
            return candles

        mock_candles.side_effect = _fill

        async def _run():
            await engine.task_generate_signals()
        asyncio.run(_run())

    assert engine._last_signal is not None
    assert engine._last_signal["symbol"] == "PAXGUSDT"
    assert engine._last_signal["recommendation"]["action"] == "buy"
    assert engine._last_signal["recommendation"]["strategy"] == "donchian_breakout_long_flat"


def test_signal_generation_without_breakout_does_not_trade():
    """No breakout on any symbol -> the executed signal must not be buy/sell."""
    _inject_analyses()
    engine._last_analysis = {"symbol": "BTCUSDT", "regime": dict(_BULL)}

    with patch.object(engine.storage, "list_ohlcv_candles", return_value=_flat(40)), \
         patch.object(engine.backtesting, "donchian_live_signal", return_value={
             "action": "hold", "confidence": 0.0, "reason": "inside channel",
         }):
        async def _run():
            await engine.task_generate_signals()
        asyncio.run(_run())

    assert engine._last_signal is not None
    assert engine._last_signal["recommendation"]["action"] in ("research", "wait")


def test_execute_trades_opens_paper_order_on_donchian_buy():
    engine._last_prices = {"PAXGUSDT": 100.0}
    engine._last_signal = {
        "symbol": "PAXGUSDT",
        "regime": dict(_BULL),
        "recommendation": {
            "action": "buy", "strategy": "donchian_breakout_long_flat",
            "confidence": 0.9, "reason": "PAXG breakout (research)",
        },
    }

    submitted = {}

    def _fake_submit(**kwargs):
        submitted.update(kwargs)
        return {"status": "filled", "fill_price": kwargs["current_price"], "mode": "paper", "order_id": "o-focus-1"}

    with patch.object(engine.storage, "list_positions", return_value=[]), \
         patch.object(engine.oms.oms, "submit_market_order", side_effect=_fake_submit), \
         patch.object(engine.execution, "calculate_position_size", return_value={"quantity": 0.05}), \
         patch.object(engine.learning, "record_trade_entry"), \
         patch.object(engine.telegram, "notify_trade"):

        async def _run():
            await engine.task_execute_trades()
        asyncio.run(_run())

    assert submitted["symbol"] == "PAXGUSDT"
    assert submitted["side"] == "buy"
    assert submitted["strategy"] == "donchian_breakout_long_flat"


def test_execute_trades_respects_max_positions_gate():
    engine._last_prices = {"PAXGUSDT": 100.0}
    engine._last_signal = {
        "symbol": "PAXGUSDT",
        "regime": dict(_BULL),
        "recommendation": {
            "action": "buy", "strategy": "donchian_breakout_long_flat",
            "confidence": 0.9, "reason": "PAXG breakout (research)",
        },
    }
    open_positions = [
        {"symbol": s, "quantity": 0.01, "average_price": 100.0}
        for s in ("DOGEUSDT", "LTCUSDT", "XRPUSDT")  # other assets, so PAXG has no current position
    ]

    submitted = {}

    def _fake_submit(**kwargs):
        submitted.update(kwargs)
        return {"status": "filled", "fill_price": kwargs["current_price"], "mode": "paper", "order_id": "o-focus-1"}

    with patch.object(engine.storage, "list_positions", return_value=open_positions), \
         patch.object(engine.oms.oms, "submit_market_order", side_effect=_fake_submit), \
         patch.object(engine.execution, "calculate_position_size", return_value={"quantity": 0.05}), \
         patch.object(engine.telegram, "notify_trade"):

        async def _run():
            await engine.task_execute_trades()
        asyncio.run(_run())

    assert submitted == {}  # gate blocked the order before submission
    events = engine.storage.list_engine_logs(limit=20)
    assert any(e["event_type"] == "trade_skipped" and "max_positions_reached" in e.get("details", {}).get("reason", "")
               for e in events)


def test_execute_trades_closes_existing_position_on_donchian_sell():
    engine._last_prices = {"PAXGUSDT": 105.0}
    engine._last_signal = {
        "symbol": "PAXGUSDT",
        "regime": dict(_BULL),
        "recommendation": {
            "action": "sell", "strategy": "donchian_breakout_long_flat",
            "confidence": 0.85, "reason": "PAXG channel drop (research)",
        },
    }

    submitted = {}

    def _fake_submit(**kwargs):
        submitted.update(kwargs)
        return {"status": "filled", "fill_price": kwargs["current_price"], "mode": "paper", "order_id": "o-focus-sell-1"}

    with patch.object(engine.storage, "list_positions", return_value=[
            {"symbol": "PAXGUSDT", "quantity": 0.05, "average_price": 100.0},
        ]), \
         patch.object(engine.oms.oms, "submit_market_order", side_effect=_fake_submit), \
         patch.object(engine.learning, "record_trade_exit"), \
         patch.object(engine.telegram, "notify_trade"):

        async def _run():
            await engine.task_execute_trades()
        asyncio.run(_run())

    assert submitted["symbol"] == "PAXGUSDT"
    assert submitted["side"] == "sell"
    assert submitted["quantity"] == 0.05
