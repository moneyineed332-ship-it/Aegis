"""Tests for the learning module."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import storage

from app import learning


def test_record_trade_entry():
    result = learning.record_trade_entry(
        order_id="test_order_001",
        symbol="BTCUSDT",
        strategy="sma_crossover",
        side="buy",
        entry_price=50000,
        quantity=0.01,
        regime="trending",
    )
    assert result is not None
    assert result["order_id"] == "test_order_001"
    assert result["status"] == "open"


def test_record_trade_exit():
    learning.record_trade_entry(
        order_id="test_exit_001",
        symbol="BTCUSDT",
        strategy="sma_crossover",
        side="buy",
        entry_price=50000,
        quantity=0.01,
    )
    result = learning.record_trade_exit("test_exit_001", 51000)
    assert "pnl" in result
    assert result["pnl"] > 0


def test_record_trade_exit_loss():
    learning.record_trade_entry(
        order_id="test_loss_001",
        symbol="BTCUSDT",
        strategy="sma_crossover",
        side="buy",
        entry_price=50000,
        quantity=0.01,
    )
    result = learning.record_trade_exit("test_loss_001", 49000)
    assert result["pnl"] < 0


def test_record_trade_exit_unknown_order():
    result = learning.record_trade_exit("nonexistent_order", 50000)
    assert "error" in result


def test_strategy_scoring():
    stats = {
        "total_trades": 20,
        "wins": 12,
        "losses": 8,
        "win_rate": 0.6,
        "pnl_history": [100, -50, 200, -30, 150, -20, 80, -10, 120, -40],
        "win_pnl_sum": 650,
        "loss_pnl_sum": 150,
        "profit_factor": 4.33,
        "consecutive_losses": 0,
        "max_consecutive_losses": 2,
    }
    score = learning._compute_score(stats)
    assert 0 <= score <= 100


def test_strategy_scoring_zero_trades():
    stats = {"total_trades": 0, "wins": 0, "win_rate": 0, "pnl_history": [], "profit_factor": 0}
    score = learning._compute_score(stats)
    assert score >= 0


def test_strategy_scoring_perfect():
    stats = {
        "total_trades": 50,
        "wins": 50,
        "losses": 0,
        "win_rate": 1.0,
        "pnl_history": [100] * 50,
        "win_pnl_sum": 5000,
        "loss_pnl_sum": 0,
        "profit_factor": 5.0,
        "consecutive_losses": 0,
        "max_consecutive_losses": 0,
    }
    score = learning._compute_score(stats)
    assert score > 70


def test_update_strategy_stats():
    learning._update_strategy_stats("test_strat_update", 100.0, 2.0, "trending")
    stats = storage.load_strategy_stats("test_strat_update")
    assert stats is not None
    assert stats["total_trades"] == 1
    assert stats["total_pnl"] == 100.0


def test_update_consecutive_losses():
    stats = {"consecutive_losses": 0, "max_consecutive_losses": 0}
    learning._update_consecutive_losses(stats, -50)
    assert stats["consecutive_losses"] == 1
    assert stats["max_consecutive_losses"] == 1

    learning._update_consecutive_losses(stats, -30)
    assert stats["consecutive_losses"] == 2
    assert stats["max_consecutive_losses"] == 2

    learning._update_consecutive_losses(stats, 100)
    assert stats["consecutive_losses"] == 0


def test_rank_strategies_for_regime():
    storage.save_strategy_stats("strat_a", {
        "total_trades": 10, "wins": 7, "score": 75,
        "regime_performance": {"trending": {"trades": 5, "wins": 4, "win_rate": 0.8, "total_pnl": 200}},
    })
    storage.save_strategy_stats("strat_b", {
        "total_trades": 10, "wins": 3, "score": 35,
        "regime_performance": {"trending": {"trades": 5, "wins": 1, "win_rate": 0.2, "total_pnl": -100}},
    })
    ranked = learning.rank_strategies_for_regime("trending")
    assert len(ranked) >= 2
    assert ranked[0]["strategy_id"] == "strat_a"


def test_learning_cycle_runs():
    result = learning.learning_cycle(None, None)
    assert isinstance(result, dict)
    assert "strategies_scored" in result
