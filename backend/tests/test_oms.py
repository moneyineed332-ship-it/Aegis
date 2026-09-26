"""Tests for the Order Management System."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

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


def test_validate_sell_at_profit_allowed():
    """Closing a position above entry price must not be rejected."""
    from unittest.mock import patch
    oms = OrderManager()
    positions = [{"symbol": "BTCUSDT", "quantity": 0.0002, "average_price": 50000}]
    with patch("app.oms.storage.list_positions", return_value=positions):
        result = oms._validate_pre_trade("BTCUSDT", "sell", 0.0002, 60000)
    assert result["valid"] is True


def test_validate_naked_short_rejected():
    """Selling more than the quantity held must be refused, not netted into a short."""
    from unittest.mock import patch
    oms = OrderManager()
    positions = [{"symbol": "BTCUSDT", "quantity": 0.0001, "average_price": 50000}]
    with patch("app.oms.storage.list_positions", return_value=positions):
        result = oms._validate_pre_trade("BTCUSDT", "sell", 0.0003, 50000)
    assert result["valid"] is False
    assert "Cannot sell more than owned" in result["reason"]


def test_validate_sell_from_short_position_rejected():
    from unittest.mock import patch
    oms = OrderManager()
    positions = [{"symbol": "BTCUSDT", "quantity": -0.0002, "average_price": 50000}]
    with patch("app.oms.storage.list_positions", return_value=positions):
        result = oms._validate_pre_trade("BTCUSDT", "sell", 0.0002, 50000)
    assert result["valid"] is False
    assert "Cannot sell more than owned" in result["reason"]


def test_validate_buy_to_cover_short_allowed():
    from unittest.mock import patch
    oms = OrderManager()
    positions = [{"symbol": "BTCUSDT", "quantity": -0.0002, "average_price": 50000}]
    with patch("app.oms.storage.list_positions", return_value=positions):
        result = oms._validate_pre_trade("BTCUSDT", "buy", 0.0002, 50000)
    assert result["valid"] is True


def test_update_position_keeps_average_on_partial_close():
    """Reducing a long must not move the remaining basis (abs() bug regression)."""
    from unittest.mock import patch
    oms = OrderManager()
    positions = [{"symbol": "BTCUSDT", "quantity": 0.2, "average_price": 100.0}]
    saved = {}
    with patch("app.oms.storage.list_positions", return_value=positions), \
         patch("app.oms.storage.save_order_and_position", side_effect=lambda o, p: saved.update(position=p)), \
         patch("app.oms.execution.create_trailing_stop"), \
         patch("app.oms.storage.save_trailing_stop"), \
         patch("app.oms.execution.remove_trailing_stop"), \
         patch("app.oms.storage.remove_trailing_stop_state"):
        oms._update_position("BTCUSDT", "sell", 0.1, 120.0, {})

    position = saved["position"]
    assert position["quantity"] == pytest.approx(0.1)
    assert position["average_price"] == 100.0


def test_update_position_averages_when_adding():
    from unittest.mock import patch
    oms = OrderManager()
    positions = [{"symbol": "BTCUSDT", "quantity": 0.2, "average_price": 100.0}]
    saved = {}
    with patch("app.oms.storage.list_positions", return_value=positions), \
         patch("app.oms.storage.save_order_and_position", side_effect=lambda o, p: saved.update(position=p)), \
         patch("app.oms.execution.create_trailing_stop"), \
         patch("app.oms.storage.save_trailing_stop"), \
         patch("app.oms.execution.remove_trailing_stop"), \
         patch("app.oms.storage.remove_trailing_stop_state"):
        oms._update_position("BTCUSDT", "buy", 0.2, 120.0, {})

    position = saved["position"]
    assert position["quantity"] == pytest.approx(0.4)
    # (100*0.2 + 120*0.2) / 0.4
    assert position["average_price"] == 110.0


def test_update_position_rebases_on_flip():
    from unittest.mock import patch
    oms = OrderManager()
    positions = [{"symbol": "BTCUSDT", "quantity": 0.1, "average_price": 100.0}]
    saved = {}
    with patch("app.oms.storage.list_positions", return_value=positions), \
         patch("app.oms.storage.save_order_and_position", side_effect=lambda o, p: saved.update(position=p)), \
         patch("app.oms.execution.create_trailing_stop"), \
         patch("app.oms.storage.save_trailing_stop"), \
         patch("app.oms.execution.remove_trailing_stop"), \
         patch("app.oms.storage.remove_trailing_stop_state"):
        oms._update_position("BTCUSDT", "sell", 0.3, 90.0, {})

    position = saved["position"]
    assert position["quantity"] == pytest.approx(-0.2)
    assert position["average_price"] == 90.0


def test_update_position_short_average():
    from unittest.mock import patch
    oms = OrderManager()
    positions = [{"symbol": "BTCUSDT", "quantity": -0.2, "average_price": 100.0}]
    saved = {}
    with patch("app.oms.storage.list_positions", return_value=positions), \
         patch("app.oms.storage.save_order_and_position", side_effect=lambda o, p: saved.update(position=p)), \
         patch("app.oms.execution.create_trailing_stop"), \
         patch("app.oms.storage.save_trailing_stop"), \
         patch("app.oms.execution.remove_trailing_stop"), \
         patch("app.oms.storage.remove_trailing_stop_state"):
        oms._update_position("BTCUSDT", "sell", 0.1, 90.0, {})

    position = saved["position"]
    assert position["quantity"] == pytest.approx(-0.3)
    # (100*0.2 + 90*0.1) / 0.3
    assert position["average_price"] == pytest.approx(96.6667, abs=1e-3)


class TestNetPosition:
    """Shared netting helper used by the OMS and by every order endpoint."""

    def test_opens_a_new_position(self):
        from app.oms import net_position

        p = net_position(None, "BTCUSDT", "buy", 0.1, 50_000)
        assert p == {"symbol": "BTCUSDT", "quantity": 0.1, "average_price": 50_000}

    def test_closes_to_none(self):
        from app.oms import net_position

        current = {"symbol": "BTCUSDT", "quantity": 0.1, "average_price": 50_000}
        assert net_position(current, "BTCUSDT", "sell", 0.1, 55_000) is None

    def test_partial_close_keeps_the_basis(self):
        from app.oms import net_position

        current = {"symbol": "BTCUSDT", "quantity": 0.2, "average_price": 100.0}
        p = net_position(current, "BTCUSDT", "sell", 0.1, 120.0)
        assert p["quantity"] == pytest.approx(0.1)
        assert p["average_price"] == 100.0

    def test_adding_averages(self):
        from app.oms import net_position

        current = {"symbol": "BTCUSDT", "quantity": 0.2, "average_price": 100.0}
        p = net_position(current, "BTCUSDT", "buy", 0.2, 120.0)
        assert p["quantity"] == pytest.approx(0.4)
        assert p["average_price"] == 110.0

    def test_flip_rebases(self):
        from app.oms import net_position

        current = {"symbol": "BTCUSDT", "quantity": 0.1, "average_price": 100.0}
        p = net_position(current, "BTCUSDT", "sell", 0.3, 90.0)
        assert p["quantity"] == pytest.approx(-0.2)
        assert p["average_price"] == 90.0

    def test_short_side_averages(self):
        from app.oms import net_position

        current = {"symbol": "BTCUSDT", "quantity": -0.2, "average_price": 100.0}
        p = net_position(current, "BTCUSDT", "sell", 0.1, 90.0)
        assert p["quantity"] == pytest.approx(-0.3)
        assert p["average_price"] == pytest.approx(96.6667, abs=1e-3)

    def test_reducing_a_short_keeps_the_basis(self):
        from app.oms import net_position

        current = {"symbol": "BTCUSDT", "quantity": -0.2, "average_price": 100.0}
        p = net_position(current, "BTCUSDT", "buy", 0.1, 80.0)
        assert p["quantity"] == pytest.approx(-0.1)
        assert p["average_price"] == 100.0

    def test_does_not_mutate_the_input(self):
        from app.oms import net_position

        current = {"symbol": "BTCUSDT", "quantity": 0.2, "average_price": 100.0}
        net_position(current, "BTCUSDT", "sell", 0.1, 120.0)
        assert current == {"symbol": "BTCUSDT", "quantity": 0.2, "average_price": 100.0}


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
