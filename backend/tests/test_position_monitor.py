"""Tests for the position monitoring module."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import storage

from app import position_monitor, config


def test_compute_position_pnl_long_profit():
    position = {"symbol": "BTCUSDT", "quantity": 1.0, "average_price": 50000}
    result = position_monitor.compute_position_pnl(position, 55000)
    assert result["side"] == "long"
    assert result["unrealized_pnl"] == 5000
    assert result["unrealized_pnl_pct"] > 0


def test_compute_position_pnl_long_loss():
    position = {"symbol": "BTCUSDT", "quantity": 1.0, "average_price": 50000}
    result = position_monitor.compute_position_pnl(position, 45000)
    assert result["side"] == "long"
    assert result["unrealized_pnl"] == -5000
    assert result["unrealized_pnl_pct"] < 0


def test_compute_position_pnl_short_profit():
    position = {"symbol": "BTCUSDT", "quantity": -1.0, "average_price": 50000}
    result = position_monitor.compute_position_pnl(position, 45000)
    assert result["side"] == "short"
    assert result["unrealized_pnl"] == 5000


def test_compute_position_pnl_short_loss():
    position = {"symbol": "BTCUSDT", "quantity": -1.0, "average_price": 50000}
    result = position_monitor.compute_position_pnl(position, 55000)
    assert result["side"] == "short"
    assert result["unrealized_pnl"] == -5000


def test_compute_position_pnl_zero_quantity():
    position = {"symbol": "BTCUSDT", "quantity": 0, "average_price": 50000}
    result = position_monitor.compute_position_pnl(position, 55000)
    assert result["side"] == "flat"
    assert result["unrealized_pnl"] == 0


def test_compute_portfolio_summary():
    positions = [
        {"symbol": "BTCUSDT", "quantity": 1.0, "average_price": 50000},
        {"symbol": "ETHUSDT", "quantity": 10.0, "average_price": 3000},
    ]
    prices = {"BTCUSDT": 55000, "ETHUSDT": 3200}
    summary = position_monitor.compute_portfolio_summary(positions, prices, 100000)
    assert summary["position_count"] == 2
    assert summary["capital"] == 100000
    assert summary["total_unrealized_pnl"] > 0
    assert summary["equity"] > 100000
    assert summary["total_exposure"] > 0


def test_compute_portfolio_summary_empty():
    summary = position_monitor.compute_portfolio_summary([], {}, 100000)
    assert summary["position_count"] == 0
    assert summary["total_unrealized_pnl"] == 0
    assert summary["equity"] == 100000


def test_check_position_risks_no_alerts():
    positions = [{"symbol": "BTCUSDT", "quantity": 0.001, "average_price": 50000}]
    prices = {"BTCUSDT": 51000}
    alerts = position_monitor.check_position_risks(positions, prices, 100000)
    assert isinstance(alerts, list)
    assert len(alerts) == 0


def test_check_position_risks_large_loss():
    positions = [{"symbol": "BTCUSDT", "quantity": 1.0, "average_price": 50000}]
    prices = {"BTCUSDT": 44000}
    alerts = position_monitor.check_position_risks(positions, prices, 100000)
    assert len(alerts) > 0
    assert alerts[0]["action"] == "auto_close"


def test_check_position_risks_portfolio_drawdown():
    positions = [{"symbol": "BTCUSDT", "quantity": 10.0, "average_price": 50000}]
    prices = {"BTCUSDT": 35000}
    alerts = position_monitor.check_position_risks(positions, prices, 100000)
    close_all = [a for a in alerts if a.get("action") == "close_all"]
    assert len(close_all) > 0


def test_monitor_cycle_runs():
    result = position_monitor.monitor_cycle({"BTCUSDT": 50000})
    assert "portfolio" in result
    assert "alerts" in result
    assert "positions" in result["portfolio"]


def test_monitor_cycle_empty_prices():
    from unittest.mock import patch
    with patch("app.position_monitor.storage.list_positions", return_value=[]):
        result = position_monitor.monitor_cycle({})
    assert "portfolio" in result
    assert result["portfolio"]["position_count"] == 0


def test_config_thresholds():
    assert config.POSITION_MAX_LOSS_PCT > 0
    assert config.POSITION_MAX_DRAWDOWN_PCT > 0
    assert config.PORTFOLIO_MAX_DRAWDOWN_PCT > 0
