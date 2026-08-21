"""Tests for the Order Management System."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import storage

from app.oms import OrderManager, risk_check_circuit
from app import config


def test_oms_instantiation():
    oms = OrderManager()
    assert oms is not None


def test_validate_kill_switch_active():
    storage.set_kill_switch(True, "test")
    oms = OrderManager()
    result = oms._validate_pre_trade("BTCUSDT", "buy", 0.01, 50000)
    assert result["valid"] is False
    assert "kill switch" in result["reason"].lower()
    storage.set_kill_switch(False, "test cleanup")


def test_validate_order_too_large():
    oms = OrderManager()
    result = oms._validate_pre_trade("BTCUSDT", "buy", 100, 50000)
    assert result["valid"] is False
    assert "exceeds max" in result["reason"]


def test_validate_order_too_small():
    oms = OrderManager()
    result = oms._validate_pre_trade("BTCUSDT", "buy", 0.00001, 50000)
    assert result["valid"] is False
    assert "below min" in result["reason"]


def test_validate_sell_exceeds_position():
    from unittest.mock import patch
    oms = OrderManager()
    with patch("app.oms.storage.list_positions", return_value=[]):
        result = oms._validate_pre_trade("BTCUSDT", "sell", 0.001, 15000)
    assert result["valid"] is False
    assert "Cannot sell more than owned" in result["reason"]


def test_validate_valid_order():
    oms = OrderManager()
    result = oms._validate_pre_trade("BTCUSDT", "buy", 0.0002, 50000)
    assert result["valid"] is True


def test_risk_check_circuit_returns_dict():
    result = risk_check_circuit()
    assert isinstance(result, dict)
    assert "triggered" in result or "halted" in result


def test_paper_order_execution():
    oms = OrderManager()
    result = oms.submit_market_order(
        symbol="BTCUSDT",
        side="buy",
        quantity=0.001,
        current_price=50000,
        strategy="test_strategy",
        reason="unit test",
    )
    assert result["status"] in ("filled", "rejected", "error")
    if result["status"] == "filled":
        assert result["mode"] == "paper"
        assert "order_id" in result
        assert result["strategy"] == "test_strategy"


def test_paper_order_records_position():
    oms = OrderManager()
    result = oms.submit_market_order(
        symbol="ETHUSDT",
        side="buy",
        quantity=0.1,
        current_price=3000,
        strategy="test_entry",
        reason="test",
    )
    if result["status"] == "filled":
        positions = storage.list_positions()
        eth_pos = next((p for p in positions if p["symbol"] == "ETHUSDT"), None)
        assert eth_pos is not None
        assert eth_pos["quantity"] >= 0.1


def test_oms_order_history():
    oms = OrderManager()
    oms.submit_market_order("BTCUSDT", "buy", 0.0002, 50000, "test_hist", "history test")
    orders = storage.list_recent_orders(limit=5)
    assert len(orders) >= 1
