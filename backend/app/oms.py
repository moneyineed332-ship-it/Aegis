"""Order Management System (OMS) for AEGIS AI Quant.

Handles the full lifecycle of orders:
  1. Pre-trade validation (balance, exposure, risk limits)
  2. Order routing (paper vs live)
  3. Fill tracking and reconciliation
  4. Position management
  5. Audit trail

The OMS is the single entry point for all order execution.
"""

import logging
import time
from datetime import datetime, timezone

from . import config, execution, storage
from .exchange import ExchangeError, OrderRejected, get_live_exchange

logger = logging.getLogger(__name__)

# --- Order status constants ---
ORDER_PENDING = "pending"
ORDER_SUBMITTED = "submitted"
ORDER_FILLED = "filled"
ORDER_PARTIAL = "partial"
ORDER_CANCELLED = "cancelled"
ORDER_REJECTED = "rejected"
ORDER_EXPIRED = "expired"


class OrderManager:
    """Manages order lifecycle: validate → submit → track → reconcile."""

    def __init__(self):
        self._order_counter = 0

    def submit_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        current_price: float,
        strategy: str = "manual",
        reason: str = "",
    ) -> dict:
        """Submit a market order through the full pipeline.

        Returns:
            Order result with status, fill details, and position update.
        """
        self._order_counter += 1
        order_id = f"AEGIS-{int(time.time())}-{self._order_counter}"

        # 1. Pre-trade validation
        validation = self._validate_pre_trade(symbol, side, quantity, current_price)
        if not validation["valid"]:
            self._log_order_event(order_id, symbol, side, "rejected", validation["reason"], strategy)
            return {
                "order_id": order_id,
                "status": ORDER_REJECTED,
                "reason": validation["reason"],
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
            }

        # 2. Route to paper or live
        if config.MODE == "live":
            result = self._execute_live(symbol, side, quantity, current_price, order_id, strategy)
        else:
            result = self._execute_paper(symbol, side, quantity, current_price, order_id, strategy)

        # 3. Update position
        if result["status"] in (ORDER_FILLED, ORDER_PARTIAL):
            self._update_position(symbol, side, quantity, result.get("fill_price", current_price), result)

        # 4. Log audit trail
        self._log_order_event(order_id, symbol, side, result["status"],
                              result.get("reason", ""), strategy, result)

        return result

    def _validate_pre_trade(self, symbol: str, side: str, quantity: float, price: float) -> dict:
        """Validate order against risk limits before submission."""
        # Kill switch check
        if storage.get_kill_switch():
            return {"valid": False, "reason": "Kill switch is active"}

        notional = quantity * price

        # Max order notional
        if notional > config.MAX_ORDER_NOTIONAL:
            return {"valid": False, "reason": f"Order notional ({notional:.2f}) exceeds max ({config.MAX_ORDER_NOTIONAL})"}

        # Min order notional
        if notional < config.ORDER_MIN_NOTIONAL:
            return {"valid": False, "reason": f"Order notional ({notional:.2f}) below min ({config.ORDER_MIN_NOTIONAL})"}

        # Total exposure check
        positions = storage.list_positions()
        current_exposure = sum(abs(p["quantity"] * p["average_price"]) for p in positions)
        if side == "buy":
            new_exposure = current_exposure + notional
        else:
            new_exposure = current_exposure - notional

        if new_exposure < 0:
            return {"valid": False, "reason": "Cannot sell more than owned"}

        if new_exposure > config.MAX_TOTAL_EXPOSURE:
            return {"valid": False, "reason": f"Total exposure ({new_exposure:.2f}) would exceed max ({config.MAX_TOTAL_EXPOSURE})"}

        # Circuit breaker check
        circuit = risk_check_circuit()
        if circuit.get("halted") or circuit.get("triggered"):
            return {"valid": False, "reason": f"Circuit breaker active: {circuit.get('reason')}"}

        return {"valid": True}

    def _execute_paper(self, symbol: str, side: str, quantity: float, price: float, order_id: str, strategy: str) -> dict:
        """Execute order in paper mode (simulation)."""
        result = execution.market_order(symbol, side, quantity, price)
        result["order_id"] = order_id
        result["strategy"] = strategy
        result["mode"] = "paper"
        return result

    def _execute_live(self, symbol: str, side: str, quantity: float, price: float, order_id: str, strategy: str) -> dict:
        """Execute order on real exchange."""
        try:
            exchange = get_live_exchange()
            # Convert symbol format: BTCUSDT → BTC/USDT
            ccxt_symbol = _to_ccxt_symbol(symbol)
            order = exchange.create_market_order(ccxt_symbol, side, quantity)

            result = {
                "order_id": order_id,
                "exchange_order_id": order.get("id"),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "fill_price": order.get("average") or order.get("price") or price,
                "notional": order.get("cost", quantity * price),
                "fee": order.get("fee", {}).get("cost", 0) if order.get("fee") else 0,
                "status": ORDER_FILLED if order.get("status") == "closed" else ORDER_PARTIAL,
                "strategy": strategy,
                "mode": "live",
                "filled_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.info("Live order executed: %s %s %s @ %.6f (exchange_id=%s)",
                       side, quantity, symbol, result["fill_price"], order.get("id"))
            return result

        except OrderRejected as e:
            logger.error("Live order rejected: %s", e)
            return {
                "order_id": order_id,
                "status": ORDER_REJECTED,
                "reason": str(e),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "strategy": strategy,
                "mode": "live",
            }
        except ExchangeError as e:
            logger.error("Exchange error: %s", e)
            return {
                "order_id": order_id,
                "status": ORDER_REJECTED,
                "reason": f"Exchange error: {e}",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "strategy": strategy,
                "mode": "live",
            }
        except Exception as e:
            logger.error("Unexpected error in live execution: %s", e, exc_info=True)
            return {
                "order_id": order_id,
                "status": ORDER_REJECTED,
                "reason": f"Execution error: {e}",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "strategy": strategy,
                "mode": "live",
            }

    def _update_position(self, symbol: str, side: str, quantity: float, fill_price: float, result: dict) -> None:
        """Update position after a fill."""
        positions = storage.list_positions()
        current = next((p for p in positions if p["symbol"] == symbol), None)
        current_qty = current["quantity"] if current else 0

        signed_qty = quantity if side == "buy" else -quantity
        new_qty = signed_qty + current_qty

        if new_qty == 0:
            new_avg = 0
            position = None
        else:
            if current:
                total_cost = current["average_price"] * current["quantity"] + fill_price * signed_qty
                new_avg = abs(total_cost / new_qty)
            else:
                new_avg = fill_price
            position = {"symbol": symbol, "quantity": new_qty, "average_price": new_avg}

        notional = fill_price * quantity
        order_data = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "reference_price": fill_price,
            "notional": notional,
        }
        storage.save_order_and_position(order_data, position)

        # Create trailing stop for new long positions
        if side == "buy" and new_qty > 0:
            execution.create_trailing_stop(symbol, "buy", fill_price, 0.05)
            storage.save_trailing_stop(symbol, "buy", fill_price, 0.05, fill_price * 0.95)

        # Remove trailing stop if position closed
        if position is None:
            execution.remove_trailing_stop(symbol, "buy")
            storage.remove_trailing_stop_state(symbol, "buy")

    def _log_order_event(self, order_id: str, symbol: str, side: str, status: str, reason: str, strategy: str, details: dict | None = None) -> None:
        """Log order event to engine log."""
        event_data = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "status": status,
            "strategy": strategy,
            "reason": reason,
        }
        if details:
            event_data.update(details)

        severity = "error" if status == ORDER_REJECTED else "warning" if status in (ORDER_CANCELLED, ORDER_EXPIRED) else "info"
        storage.log_engine_event(f"order-{order_id}", "order_event", event_data, severity)

    def submit_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        limit_price: float,
        current_price: float,
        strategy: str = "manual",
        reason: str = "",
    ) -> dict:
        """Submit a limit order through the full pipeline.

        In paper mode, simulates immediate fill if price is favorable, otherwise records as pending.
        In live mode, places a real limit order on the exchange.

        Returns:
            Order result with status, fill details, and position update.
        """
        self._order_counter += 1
        order_id = f"AEGIS-LMT-{int(time.time())}-{self._order_counter}"

        # 1. Pre-trade validation
        validation = self._validate_pre_trade(symbol, side, quantity, limit_price)
        if not validation["valid"]:
            self._log_order_event(order_id, symbol, side, "rejected", validation["reason"], strategy)
            return {
                "order_id": order_id,
                "status": ORDER_REJECTED,
                "reason": validation["reason"],
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": "limit",
            }

        # 2. Route to paper or live
        if config.MODE == "live":
            result = self._execute_live_limit(symbol, side, quantity, limit_price, order_id, strategy)
        else:
            result = self._execute_paper_limit(symbol, side, quantity, limit_price, current_price, order_id, strategy)

        # 3. Update position (only if filled)
        if result["status"] in (ORDER_FILLED, ORDER_PARTIAL):
            self._update_position(symbol, side, quantity, result.get("fill_price", limit_price), result)

        # 4. Log audit trail
        self._log_order_event(order_id, symbol, side, result["status"],
                              result.get("reason", ""), strategy, result)

        return result

    def _execute_paper_limit(self, symbol: str, side: str, quantity: float, limit_price: float, current_price: float, order_id: str, strategy: str) -> dict:
        """Execute limit order in paper mode.

        If the limit price is already favorable (buy: current <= limit, sell: current >= limit),
        fills immediately at limit price. Otherwise, records as pending open order.
        """
        can_fill = False
        if side == "buy" and current_price <= limit_price:
            can_fill = True
        elif side == "sell" and current_price >= limit_price:
            can_fill = True

        if can_fill:
            fill_price = limit_price
            fee = quantity * fill_price * 0.001  # 0.1% fee
            result = {
                "order_id": order_id,
                "status": ORDER_FILLED,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "fill_price": fill_price,
                "notional": quantity * fill_price,
                "fee": round(fee, 6),
                "slippage_bps": 0,
                "order_type": "limit",
                "strategy": strategy,
                "mode": "paper",
                "filled_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.info("Paper limit order filled: %s %s %.8f @ %.6f (limit=%s)", side, symbol, quantity, fill_price, limit_price)
            return result
        else:
            # Record as pending open order
            storage.save_open_order(order_id, symbol, side, quantity, limit_price, strategy)
            result = {
                "order_id": order_id,
                "status": ORDER_PENDING,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "limit_price": limit_price,
                "current_price": current_price,
                "order_type": "limit",
                "strategy": strategy,
                "mode": "paper",
                "reason": f"Pending: {side} {symbol} @ {limit_price} (current={current_price})",
            }
            logger.info("Paper limit order pending: %s %s %.8f @ %.6f (current=%.6f)", side, symbol, quantity, limit_price, current_price)
            return result

    def _execute_live_limit(self, symbol: str, side: str, quantity: float, limit_price: float, order_id: str, strategy: str) -> dict:
        """Execute limit order on real exchange."""
        try:
            exchange = get_live_exchange()
            ccxt_symbol = _to_ccxt_symbol(symbol)
            order = exchange.create_limit_order(ccxt_symbol, side, quantity, limit_price)

            result = {
                "order_id": order_id,
                "exchange_order_id": order.get("id"),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "limit_price": limit_price,
                "fill_price": order.get("average") or order.get("price") or limit_price,
                "notional": order.get("cost", quantity * limit_price),
                "fee": order.get("fee", {}).get("cost", 0) if order.get("fee") else 0,
                "status": ORDER_FILLED if order.get("status") == "closed" else ORDER_PENDING,
                "order_type": "limit",
                "strategy": strategy,
                "mode": "live",
                "filled_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.info("Live limit order placed: %s %s %s @ %.6f (exchange_id=%s)", side, quantity, symbol, limit_price, order.get("id"))
            return result

        except OrderRejected as e:
            logger.error("Live limit order rejected: %s", e)
            return {
                "order_id": order_id,
                "status": ORDER_REJECTED,
                "reason": str(e),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": "limit",
                "strategy": strategy,
                "mode": "live",
            }
        except ExchangeError as e:
            logger.error("Exchange error on limit order: %s", e)
            return {
                "order_id": order_id,
                "status": ORDER_REJECTED,
                "reason": f"Exchange error: {e}",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": "limit",
                "strategy": strategy,
                "mode": "live",
            }
        except Exception as e:
            logger.error("Unexpected error in live limit execution: %s", e, exc_info=True)
            return {
                "order_id": order_id,
                "status": ORDER_REJECTED,
                "reason": f"Execution error: {e}",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": "limit",
                "strategy": strategy,
                "mode": "live",
            }

    def get_order_history(self, limit: int = 50) -> list[dict]:
        """Get recent order history from storage."""
        return storage.list_recent_orders(limit)

    def get_open_orders(self) -> list[dict]:
        """Get all open/pending orders."""
        if config.MODE == "live":
            try:
                exchange = get_live_exchange()
                return exchange.fetch_open_orders()
            except Exception as e:
                logger.error("Failed to fetch open orders: %s", e)
                return []
        return []

    def reconcile_positions(self) -> dict:
        """Reconcile local positions with exchange state.

        In live mode, fetches real balance and compares with local.
        In paper mode, returns current local positions.
        """
        positions = storage.list_positions()

        if config.MODE == "live":
            try:
                exchange = get_live_exchange()
                balance = exchange.fetch_balance()
                reconciliation = {
                    "mode": "live",
                    "local_positions": positions,
                    "exchange_balance": balance,
                    "matched": True,
                    "discrepancies": [],
                }
                # Basic reconciliation: check if we have positions that don't match
                for pos in positions:
                    currency = pos["symbol"].replace("USDT", "")
                    exchange_balance = balance.get(currency, {}).get("total", 0)
                    if abs(pos["quantity"]) > abs(exchange_balance) * 1.1:  # 10% tolerance
                        reconciliation["matched"] = False
                        reconciliation["discrepancies"].append({
                            "symbol": pos["symbol"],
                            "local_qty": pos["quantity"],
                            "exchange_qty": exchange_balance,
                        })
                return reconciliation
            except Exception as e:
                logger.error("Reconciliation failed: %s", e)
                return {"mode": "live", "error": str(e), "positions": positions}

        return {"mode": "paper", "positions": positions, "matched": True}

    def get_status(self) -> dict:
        """Get OMS status summary."""
        positions = storage.list_positions()
        orders = storage.list_recent_orders(limit=20)
        total_exposure = sum(abs(p["quantity"] * p["average_price"]) for p in positions)

        return {
            "mode": config.MODE,
            "positions_count": len(positions),
            "total_exposure": total_exposure,
            "max_exposure": config.MAX_TOTAL_EXPOSURE,
            "recent_orders": len(orders),
            "kill_switch": storage.get_kill_switch(),
        }


def _to_ccxt_symbol(symbol: str) -> str:
    """Convert AEGIS symbol to CCXT format.

    BTCUSDT → BTC/USDT
    ETHUSDT → ETH/USDT
    """
    # Common quote currencies
    for quote in ("USDT", "USDC", "BTC", "ETH", "BUSD"):
        if symbol.endswith(quote) and len(symbol) > len(quote):
            base = symbol[:-len(quote)]
            return f"{base}/{quote}"
    return symbol


def risk_check_circuit() -> dict:
    """Check circuit breaker status (equity valued at market prices)."""
    try:
        from . import risk, supervisor
        capital = config.PAPER_CAPITAL
        equity = supervisor.portfolio_equity(capital)
        return risk.check_circuit_breaker(capital, equity)
    except Exception:
        return {"halted": False, "triggered": False}


# Global OMS instance
oms = OrderManager()
