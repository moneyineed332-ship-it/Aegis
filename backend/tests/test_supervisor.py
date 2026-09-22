"""Tests for the supervisor module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch
from app import supervisor, storage, config


def test_status_healthy():
    with patch.object(storage, "get_kill_switch", return_value=False), \
         patch.object(storage, "list_positions", return_value=[]), \
         patch.object(storage, "list_strategy_stats", return_value=[]), \
         patch.object(storage, "list_alerts", return_value=[]):
        result = supervisor.status(False)
    assert result["status"] == "healthy"
    assert result["kill_switch_active"] is False
    assert "health_checks" in result
    assert "portfolio" in result


def test_status_critical_on_kill_switch():
    with patch.object(storage, "get_kill_switch", return_value=True), \
         patch.object(storage, "list_positions", return_value=[]), \
         patch.object(storage, "list_strategy_stats", return_value=[]), \
         patch.object(storage, "list_alerts", return_value=[]):
        result = supervisor.status(True)
    assert result["status"] == "critical"
    assert result["kill_switch_active"] is True
    assert result["critical_count"] >= 1


def test_check_drawdown_ok():
    with patch.object(storage, "list_positions", return_value=[]), \
         patch.object(config, "PAPER_CAPITAL", 10000):
        result = supervisor._check_drawdown()
    assert result["status"] == "ok"


def test_check_exposure_ok():
    with patch.object(storage, "list_positions", return_value=[]):
        result = supervisor._check_exposure()
    assert result["status"] == "ok"


def test_check_consecutive_losses_ok():
    with patch.object(storage, "list_strategy_stats", return_value=[
        {"consecutive_losses": 2},
        {"consecutive_losses": 1},
    ]):
        result = supervisor._check_consecutive_losses()
    assert result["status"] == "ok"
    assert result["value"] == 2


def test_check_consecutive_losses_critical():
    with patch.object(storage, "list_strategy_stats", return_value=[
        {"consecutive_losses": 5},
    ]):
        result = supervisor._check_consecutive_losses()
    assert result["status"] == "critical"
    assert result["value"] == 5


def test_check_kill_switch_active():
    with patch.object(storage, "get_kill_switch", return_value=True):
        result = supervisor._check_kill_switch()
    assert result["status"] == "critical"
    assert result["active"] is True


def test_position_loss_critical_on_market_drop():
    positions = [{"symbol": "BTCUSDT", "quantity": 0.001, "average_price": 60000}]
    snapshots = [{"symbol": "BTCUSDT", "price": 50000}]
    with patch.object(storage, "list_positions", return_value=positions), \
         patch.object(storage, "list_market_snapshots", return_value=snapshots):
        alerts = supervisor._check_position_losses()
    assert any(a["severity"] == "critical" and a["symbol"] == "BTCUSDT" for a in alerts)


def test_position_loss_ok_without_drop():
    positions = [{"symbol": "BTCUSDT", "quantity": 0.001, "average_price": 60000}]
    snapshots = [{"symbol": "BTCUSDT", "price": 61000}]
    with patch.object(storage, "list_positions", return_value=positions), \
         patch.object(storage, "list_market_snapshots", return_value=snapshots):
        alerts = supervisor._check_position_losses()
    assert not [a for a in alerts if a["severity"] == "critical"]


def test_flatten_all_positions_closes_and_records():
    positions = [{"symbol": "BTCUSDT", "quantity": 0.001, "average_price": 60000}]
    snapshots = [{"symbol": "BTCUSDT", "price": 59000}]
    saved = []
    with patch.object(storage, "list_positions", return_value=positions), \
         patch.object(storage, "list_market_snapshots", return_value=snapshots), \
         patch.object(storage, "save_order_and_position",
                      side_effect=lambda order, position: saved.append((order, position))):
        closed = supervisor.flatten_all_positions(reason="test")
    assert closed == [{"symbol": "BTCUSDT", "closed": True, "quantity": 0.001, "price": 59000}]
    order, position = saved[0]
    assert order["side"] == "sell" and position is None


def test_auto_intervention_flattens_before_kill_switch():
    positions = [{"symbol": "BTCUSDT", "quantity": 0.001, "average_price": 60000}]
    snapshots = [{"symbol": "BTCUSDT", "price": 40000}]
    with patch.object(storage, "list_positions", return_value=positions), \
         patch.object(storage, "list_market_snapshots", return_value=snapshots), \
         patch.object(storage, "list_strategy_stats", return_value=[]), \
         patch.object(storage, "list_alerts", return_value=[]), \
         patch.object(storage, "get_kill_switch", return_value=False), \
         patch.object(storage, "set_kill_switch") as mock_stop, \
         patch.object(storage, "save_order_and_position") as mock_save, \
         patch.object(storage, "list_recent_orders", return_value=[]), \
         patch.object(storage, "list_engine_logs", return_value=[]):
        actions = supervisor.evaluate_auto_intervention()
    kinds = [a["action"] for a in actions]
    assert "positions_flattened" in kinds
    assert "kill_switch_activated" in kinds
    assert mock_save.called and mock_stop.called


def test_check_kill_switch_inactive():
    with patch.object(storage, "get_kill_switch", return_value=False):
        result = supervisor._check_kill_switch()
    assert result["status"] == "ok"
    assert result["active"] is False


def test_evaluate_auto_intervention_no_action():
    with patch.object(storage, "get_kill_switch", return_value=False), \
         patch.object(storage, "list_positions", return_value=[]), \
         patch.object(storage, "list_strategy_stats", return_value=[]), \
         patch.object(storage, "list_alerts", return_value=[]):
        actions = supervisor.evaluate_auto_intervention()
    assert actions == []


def test_get_system_summary():
    with patch.object(storage, "list_positions", return_value=[
        {"symbol": "BTC/USDT", "quantity": 0.01, "average_price": 60000}
    ]), \
         patch.object(config, "PAPER_CAPITAL", 10000), \
         patch.object(storage, "get_kill_switch", return_value=False), \
         patch.object(storage, "list_recent_orders", return_value=[{}, {}]):
        result = supervisor.get_system_summary()
    assert "mode" in result
    assert "portfolio" in result
    assert result["portfolio"]["position_count"] == 1


def test_health_checks_include_all():
    with patch.object(storage, "get_kill_switch", return_value=False), \
         patch.object(storage, "list_positions", return_value=[]), \
         patch.object(storage, "list_strategy_stats", return_value=[]), \
         patch.object(storage, "list_alerts", return_value=[]):
        result = supervisor.status(False)
    check_names = {c["name"] for c in result["health_checks"]}
    assert "kill_switch" in check_names
    assert "drawdown" in check_names
    assert "exposure" in check_names
    assert "consecutive_losses" in check_names
