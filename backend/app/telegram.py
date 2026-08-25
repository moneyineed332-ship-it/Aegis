"""Telegram Notifications — real-time trade alerts.

Inspired by Freqtrade's Telegram integration.
Sends alerts for trades, signals, circuit breaker events, etc.
"""

import logging
from datetime import datetime, timezone

import httpx

from . import config

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = config.TELEGRAM_CHAT_ID
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


async def send_message(text: str, parse_mode: str = "HTML") -> dict:
    """Send a message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"sent": False, "reason": "Telegram not configured"}

    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                return {"sent": True, "message_id": response.json().get("result", {}).get("message_id")}
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return {"sent": False, "error": response.text}
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return {"sent": False, "error": str(e)}


async def notify_trade(trade: dict) -> dict:
    """Send trade notification."""
    symbol = trade.get("symbol", "UNKNOWN")
    side = trade.get("side", "unknown").upper()
    quantity = trade.get("fill_quantity", trade.get("quantity", 0))
    price = trade.get("fill_price", trade.get("reference_price", 0))
    notional = trade.get("notional", quantity * price)
    strategy = trade.get("strategy", "manual")

    emoji = "🟢" if side == "BUY" else "🔴"
    text = (
        f"<b>{emoji} {side} {symbol}</b>\n\n"
        f"💰 Prix: <code>${price:,.2f}</code>\n"
        f"📊 Quantité: <code>{quantity:.6f}</code>\n"
        f"💵 Notional: <code>${notional:,.2f}</code>\n"
        f"🎯 Stratégie: {strategy}\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return await send_message(text)


async def notify_signal(signal: dict) -> dict:
    """Send signal notification."""
    symbol = signal.get("symbol", "UNKNOWN")
    action = signal.get("action", "hold").upper()
    confidence = signal.get("confidence", 0) * 100
    strategy = signal.get("strategy", "consensus")

    if action == "HOLD":
        return {"sent": False, "reason": "Hold signals not sent"}

    emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "⚪"
    text = (
        f"<b>{emoji} Signal: {action} {symbol}</b>\n\n"
        f"📊 Confidence: <code>{confidence:.1f}%</code>\n"
        f"🎯 Stratégie: {strategy}\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return await send_message(text)


async def notify_circuit_breaker(status: dict) -> dict:
    """Send circuit breaker alert."""
    if not status.get("halted"):
        return {"sent": False, "reason": "Circuit breaker not active"}

    text = (
        f"🚨 <b>CIRCUIT BREAKER ACTIVÉ</b> 🚨\n\n"
        f"⛔ Raison: {status.get('reason', 'Unknown')}\n"
        f"💰 PnL journalier: ${status.get('daily_pnl', 0):,.2f}\n"
        f"📉 Pertes consécutives: {status.get('consecutive_losses', 0)}\n"
        f"⏰ {status.get('halted_at', 'N/A')}\n\n"
        f"<i>Trading suspendu pendant 24h</i>"
    )
    return await send_message(text)


async def notify_daily_summary(summary: dict) -> dict:
    """Send daily performance summary."""
    equity = summary.get("equity", 0)
    pnl = summary.get("daily_pnl", 0)
    pnl_pct = summary.get("daily_pnl_pct", 0)
    trades = summary.get("trades_count", 0)
    win_rate = summary.get("win_rate", 0)

    emoji = "📈" if pnl >= 0 else "📉"
    text = (
        f"<b>{emoji} Résumé Quotidien</b>\n\n"
        f"💰 Équité: <code>${equity:,.2f}</code>\n"
        f"📊 PnL: <code>${pnl:,.2f} ({pnl_pct:+.2f}%)</code>\n"
        f"🎯 Trades: {trades}\n"
        f"✅ Win Rate: {win_rate:.1f}%\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    )
    return await send_message(text)


async def notify_risk_alert(alert: dict) -> dict:
    """Send risk management alert."""
    alert_type = alert.get("type", "unknown")
    message = alert.get("message", "Risk threshold exceeded")
    severity = alert.get("severity", "warning")

    emoji_map = {"warning": "⚠️", "critical": "🚨", "info": "ℹ️"}
    emoji = emoji_map.get(severity, "⚠️")

    text = (
        f"<b>{emoji} Alerte Risque: {alert_type}</b>\n\n"
        f"{message}\n\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return await send_message(text)


async def notify_position_update(position: dict) -> dict:
    """Send position update notification."""
    symbol = position.get("symbol", "UNKNOWN")
    side = position.get("side", "long").upper()
    entry = position.get("average_price", 0)
    current = position.get("current_price", 0)
    pnl_pct = ((current / entry - 1) * 100) if entry > 0 else 0

    emoji = "🟢" if pnl_pct >= 0 else "🔴"
    text = (
        f"<b>{emoji} Position: {symbol} ({side})</b>\n\n"
        f"💵 Entrée: <code>${entry:,.2f}</code>\n"
        f"📈 Actuel: <code>${current:,.2f}</code>\n"
        f"📊 PnL: <code>{pnl_pct:+.2f}%</code>\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
    )
    return await send_message(text)


async def notify_trailing_stop_triggered(stop_info: dict) -> dict:
    """Send trailing stop triggered notification."""
    symbol = stop_info.get("symbol", "UNKNOWN")
    side = stop_info.get("side", "unknown").upper()
    entry = stop_info.get("entry_price", 0)
    stop = stop_info.get("stop_price", 0)
    current = stop_info.get("current_price", 0)
    pnl_pct = stop_info.get("unrealized_pnl_pct", 0)

    emoji = "🟢" if pnl_pct >= 0 else "🔴"
    text = (
        f"<b>🛑 Trailing Stop Déclenché: {symbol}</b>\n\n"
        f"📊 Direction: {side}\n"
        f"💵 Entrée: <code>${entry:,.2f}</code>\n"
        f"🛑 Stop: <code>${stop:,.2f}</code>\n"
        f"📈 Prix actuel: <code>${current:,.2f}</code>\n"
        f"📊 PnL: <code>{pnl_pct:+.2f}%</code>\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
    )
    return await send_message(text)
