"""WebSocket real-time alerts for risk thresholds and regime changes."""

import asyncio
import json
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect
from typing import Any


class AlertManager:
    """Manages WebSocket connections and broadcasts alerts."""

    def __init__(self):
        self.connections: list[WebSocket] = []
        self.alert_history: list[dict] = []
        self.thresholds = {
            "max_drawdown_pct": 15.0,
            "var_95_pct": 5.0,
            "rsi_overbought": 75.0,
            "rsi_oversold": 25.0,
            "volatility_spike": 0.05,
            "regime_change": True,
            "position_limit_pct": 80.0,
            "funding_rate_extreme": 0.001,
        }
        self._last_regime: str | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, alert: dict):
        self.alert_history.append(alert)
        if len(self.alert_history) > 500:
            self.alert_history = self.alert_history[-500:]
        disconnected = []
        for connection in self.connections:
            try:
                await connection.send_json(alert)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    def check_features(self, features: dict, positions: list[dict], capital: float) -> list[dict]:
        """Check features against thresholds and return triggered alerts."""
        alerts = []

        rsi = features.get("rsi_14", 50)
        if rsi > self.thresholds["rsi_overbought"]:
            alerts.append({
                "type": "rsi_overbought",
                "severity": "warning",
                "message": f"RSI at {rsi:.1f} — overbought territory",
                "value": rsi,
                "threshold": self.thresholds["rsi_overbought"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        elif rsi < self.thresholds["rsi_oversold"]:
            alerts.append({
                "type": "rsi_oversold",
                "severity": "warning",
                "message": f"RSI at {rsi:.1f} — oversold territory",
                "value": rsi,
                "threshold": self.thresholds["rsi_oversold"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        volatility = features.get("volatility_20", 0)
        if volatility > self.thresholds["volatility_spike"]:
            alerts.append({
                "type": "volatility_spike",
                "severity": "critical",
                "message": f"Volatility spike: {volatility*100:.2f}% exceeds {self.thresholds['volatility_spike']*100:.2f}%",
                "value": volatility,
                "threshold": self.thresholds["volatility_spike"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        total_exposure = sum(abs(p["quantity"] * p["average_price"]) for p in positions)
        exposure_pct = (total_exposure / capital * 100) if capital > 0 else 0
        if exposure_pct > self.thresholds["position_limit_pct"]:
            alerts.append({
                "type": "position_limit",
                "severity": "warning",
                "message": f"Total exposure at {exposure_pct:.1f}% — approaching limit",
                "value": exposure_pct,
                "threshold": self.thresholds["position_limit_pct"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return alerts

    def check_regime(self, regime_data: dict) -> dict | None:
        """Check for regime change."""
        current = regime_data.get("regime", "range")
        if self._last_regime is not None and current != self._last_regime:
            alert = {
                "type": "regime_change",
                "severity": "info",
                "message": f"Regime changed: {self._last_regime} → {current}",
                "from": self._last_regime,
                "to": current,
                "confidence": regime_data.get("confidence", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._last_regime = current
            return alert
        self._last_regime = current
        return None

    def check_drawdown(self, equity_curve: list[dict]) -> dict | None:
        """Check max drawdown from equity curve."""
        if len(equity_curve) < 2:
            return None
        peak = equity_curve[0]["equity"]
        max_dd = 0
        for point in equity_curve:
            peak = max(peak, point["equity"])
            dd = (point["equity"] / peak - 1) * 100
            max_dd = min(max_dd, dd)
        if abs(max_dd) > self.thresholds["max_drawdown_pct"]:
            return {
                "type": "max_drawdown",
                "severity": "critical",
                "message": f"Max drawdown at {max_dd:.1f}% — exceeds {self.thresholds['max_drawdown_pct']}% limit",
                "value": max_dd,
                "threshold": self.thresholds["max_drawdown_pct"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        return None

    def check_funding_rate(self, funding_data: dict) -> dict | None:
        """Check for extreme funding rates."""
        rate = abs(funding_data.get("funding_rate", 0))
        if rate > self.thresholds["funding_rate_extreme"]:
            direction = "positive (longs pay)" if funding_data["funding_rate"] > 0 else "negative (shorts pay)"
            return {
                "type": "funding_rate_extreme",
                "severity": "warning",
                "message": f"Extreme funding rate: {funding_data['funding_rate']*100:.4f}% {direction}",
                "value": funding_data["funding_rate"],
                "threshold": self.thresholds["funding_rate_extreme"],
                "symbol": funding_data.get("symbol"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        return None


manager = AlertManager()
