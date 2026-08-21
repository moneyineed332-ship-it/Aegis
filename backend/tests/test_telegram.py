"""Tests for Telegram notifications."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, AsyncMock, MagicMock

from app.telegram import (
    send_message, notify_trade, notify_signal, notify_circuit_breaker,
    notify_daily_summary, notify_risk_alert, notify_position_update,
    notify_trailing_stop_triggered,
)


def _run(coro):
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_send_message_no_config():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        result = _run(send_message("test"))
        assert result["sent"] is False
        assert result["reason"] == "Telegram not configured"


def test_send_message_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {"message_id": 123}}

    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response

    with patch("app.telegram.TELEGRAM_BOT_TOKEN", "fake-token"), \
         patch("app.telegram.TELEGRAM_CHAT_ID", "12345"), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = mock_client_instance
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = _run(send_message("Hello"))
        assert result["sent"] is True
        assert result["message_id"] == 123


def test_send_message_api_error():
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response

    with patch("app.telegram.TELEGRAM_BOT_TOKEN", "fake-token"), \
         patch("app.telegram.TELEGRAM_CHAT_ID", "12345"), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = mock_client_instance
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = _run(send_message("Hello"))
        assert result["sent"] is False
        assert "error" in result


def test_send_message_exception():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", "fake-token"), \
         patch("app.telegram.TELEGRAM_CHAT_ID", "12345"), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = Exception("Connection refused")
        mock_client_cls.return_value = mock_client_instance
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = _run(send_message("Hello"))
        assert result["sent"] is False
        assert "error" in result
        assert "Connection refused" in result["error"]


def test_notify_trade():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        trade = {"symbol": "BTCUSDT", "side": "buy", "fill_quantity": 0.001, "fill_price": 65000, "notional": 65, "strategy": "sma"}
        result = _run(notify_trade(trade))
        assert result["sent"] is False


def test_notify_signal_hold_skipped():
    result = _run(notify_signal({"action": "hold", "symbol": "BTCUSDT"}))
    assert result["sent"] is False
    assert result["reason"] == "Hold signals not sent"


def test_notify_signal_buy():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        result = _run(notify_signal({"action": "buy", "symbol": "BTCUSDT", "confidence": 0.85, "strategy": "smc_ict"}))
        assert result["sent"] is False


def test_notify_signal_sell():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        result = _run(notify_signal({"action": "sell", "symbol": "ETHUSDT", "confidence": 0.7, "strategy": "rsi"}))
        assert result["sent"] is False


def test_notify_circuit_breaker_not_halted():
    result = _run(notify_circuit_breaker({"halted": False}))
    assert result["sent"] is False
    assert result["reason"] == "Circuit breaker not active"


def test_notify_circuit_breaker_halted():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        result = _run(notify_circuit_breaker({
            "halted": True, "reason": "Daily loss limit", "daily_pnl": -500, "consecutive_losses": 5, "halted_at": "2026-01-15T10:00:00Z"
        }))
        assert result["sent"] is False


def test_notify_daily_summary():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        result = _run(notify_daily_summary({
            "equity": 20000, "daily_pnl": 150, "daily_pnl_pct": 0.75, "trades_count": 5, "win_rate": 60.0
        }))
        assert result["sent"] is False


def test_notify_risk_alert_warning():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        result = _run(notify_risk_alert({
            "type": "max_drawdown", "message": "Drawdown exceeded", "severity": "warning"
        }))
        assert result["sent"] is False


def test_notify_risk_alert_critical():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        result = _run(notify_risk_alert({
            "type": "circuit_breaker", "message": "Halted", "severity": "critical"
        }))
        assert result["sent"] is False


def test_notify_risk_alert_info():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        result = _run(notify_risk_alert({
            "type": "info", "message": "System info", "severity": "info"
        }))
        assert result["sent"] is False


def test_notify_position_update():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        result = _run(notify_position_update({
            "symbol": "BTCUSDT", "side": "long", "average_price": 65000, "current_price": 67000
        }))
        assert result["sent"] is False


def test_notify_trailing_stop():
    with patch("app.telegram.TELEGRAM_BOT_TOKEN", ""), patch("app.telegram.TELEGRAM_CHAT_ID", ""):
        result = _run(notify_trailing_stop_triggered({
            "symbol": "BTCUSDT", "side": "long", "entry_price": 65000, "stop_price": 64000, "current_price": 63500, "unrealized_pnl_pct": -2.31
        }))
        assert result["sent"] is False


if __name__ == "__main__":
    test_send_message_no_config()
    test_send_message_success()
    test_send_message_api_error()
    test_send_message_exception()
    test_notify_trade()
    test_notify_signal_hold_skipped()
    test_notify_signal_buy()
    test_notify_signal_sell()
    test_notify_circuit_breaker_not_halted()
    test_notify_circuit_breaker_halted()
    test_notify_daily_summary()
    test_notify_risk_alert_warning()
    test_notify_risk_alert_critical()
    test_notify_risk_alert_info()
    test_notify_position_update()
    test_notify_trailing_stop()
    print("All telegram tests passed.")
