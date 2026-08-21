"""Smart order execution for AEGIS AI Quant.

Supports paper simulation and live trading via OMS routing.
All paper orders are simulated with slippage modeling.
Live orders route through the OMS to real exchanges.
"""

import math
from datetime import datetime, timezone

from . import config


def _simulate_fill(order: dict, current_price: float, slippage_bps: float) -> dict:
    """Simulate order fill with slippage."""
    slippage_rate = slippage_bps / 10_000
    if order["side"] == "buy":
        fill_price = current_price * (1 + slippage_rate)
    else:
        fill_price = current_price * (1 - slippage_rate)
    return {
        "fill_price": round(fill_price, 6),
        "fill_quantity": order["quantity"],
        "slippage_bps": slippage_bps,
        "filled_at": datetime.now(timezone.utc).isoformat(),
    }


def market_order(symbol: str, side: str, quantity: float, current_price: float, fee_bps: float = 10, slippage_bps: float = 5) -> dict:
    """Execute a market order at current price with slippage."""
    notional = quantity * current_price
    fill = _simulate_fill({"side": side, "quantity": quantity}, current_price, slippage_bps)
    fee = notional * fee_bps / 10_000
    return {
        "order_type": "market",
        "symbol": symbol,
        "side": side,
        "requested_quantity": quantity,
        "fill_price": fill["fill_price"],
        "fill_quantity": fill["fill_quantity"],
        "notional": round(notional, 2),
        "fee": round(fee, 4),
        "slippage_bps": slippage_bps,
        "status": "filled",
        "filled_at": fill["filled_at"],
    }


def limit_order(symbol: str, side: str, quantity: float, limit_price: float, current_price: float, fee_bps: float = 10, slippage_bps: float = 5) -> dict:
    """Simulate a limit order — fills only if price is favorable."""
    if side == "buy" and current_price > limit_price:
        return {
            "order_type": "limit",
            "symbol": symbol,
            "side": side,
            "requested_quantity": quantity,
            "limit_price": limit_price,
            "status": "pending",
            "reason": f"Current price {current_price} > limit {limit_price}",
        }
    if side == "sell" and current_price < limit_price:
        return {
            "order_type": "limit",
            "symbol": symbol,
            "side": side,
            "requested_quantity": quantity,
            "limit_price": limit_price,
            "status": "pending",
            "reason": f"Current price {current_price} < limit {limit_price}",
        }
    fill = _simulate_fill({"side": side, "quantity": quantity}, limit_price, 0)  # No slippage for limit
    notional = quantity * limit_price
    fee = notional * fee_bps / 10_000
    return {
        "order_type": "limit",
        "symbol": symbol,
        "side": side,
        "requested_quantity": quantity,
        "limit_price": limit_price,
        "fill_price": fill["fill_price"],
        "fill_quantity": fill["fill_quantity"],
        "notional": round(notional, 2),
        "fee": round(fee, 4),
        "slippage_bps": 0,
        "status": "filled",
        "filled_at": fill["filled_at"],
    }


def fractioned_order(symbol: str, side: str, total_quantity: float, current_price: float, chunks: int = 3, delay_ms: int = 500, fee_bps: float = 10, slippage_bps: float = 5) -> dict:
    """Split a large order into smaller chunks to reduce market impact."""
    chunk_size = round(total_quantity / chunks, 8)
    fills = []
    total_fee = 0.0
    total_notional = 0.0
    avg_fill_price = 0.0

    for i in range(chunks):
        remaining = total_quantity - (chunk_size * i)
        qty = min(chunk_size, remaining)
        if qty <= 0:
            break
        slippage = slippage_bps * (1 + i * 0.3)  # Increasing slippage per chunk
        fill = _simulate_fill({"side": side, "quantity": qty}, current_price, slippage)
        notional = qty * fill["fill_price"]
        fee = notional * fee_bps / 10_000
        total_fee += fee
        total_notional += notional
        avg_fill_price += fill["fill_price"] * qty
        fills.append({
            "chunk": i + 1,
            "quantity": round(qty, 8),
            "fill_price": fill["fill_price"],
            "fee": round(fee, 4),
        })

    total_filled = sum(f["quantity"] for f in fills)
    avg_fill_price = round(avg_fill_price / total_filled, 6) if total_filled > 0 else 0

    return {
        "order_type": "fractioned",
        "symbol": symbol,
        "side": side,
        "total_quantity": total_quantity,
        "chunks_requested": chunks,
        "chunks_filled": len(fills),
        "total_filled": round(total_filled, 8),
        "avg_fill_price": avg_fill_price,
        "total_notional": round(total_notional, 2),
        "total_fee": round(total_fee, 4),
        "fills": fills,
        "status": "filled" if total_filled >= total_quantity * 0.99 else "partial",
    }


def estimate_slippage(order_value: float, market_depth_usd: float = 100_000) -> float:
    """Estimate slippage based on order size vs market depth."""
    if market_depth_usd <= 0:
        return 0.0
    impact = order_value / market_depth_usd
    return round(min(0.05, impact * 0.1) * 10_000, 2)  # Return in bps


# --- Trailing Stop Loss ---
class TrailingStop:
    """Dynamic stop loss that follows price upward for long positions (downward for shorts)."""

    def __init__(self, symbol: str, side: str, entry_price: float, trail_pct: float = 0.05):
        """
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' (long) or 'sell' (short)
            entry_price: Price when position was opened
            trail_pct: Trailing distance as decimal (0.05 = 5%)
        """
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.trail_pct = trail_pct
        self.highest_price = entry_price if side == "buy" else None
        self.lowest_price = entry_price if side == "sell" else None
        self.stop_price = self._calculate_stop(entry_price)

    def _calculate_stop(self, reference_price: float) -> float:
        """Calculate stop price based on reference price and trail percentage."""
        if self.side == "buy":
            return reference_price * (1 - self.trail_pct)
        else:
            return reference_price * (1 + self.trail_pct)

    def update(self, current_price: float) -> dict:
        """Update trailing stop with current price. Returns dict with status."""
        if self.side == "buy":
            # For longs: track highest price, move stop up
            if current_price > (self.highest_price or 0):
                self.highest_price = current_price
                new_stop = self._calculate_stop(current_price)
                if new_stop > self.stop_price:
                    self.stop_price = new_stop
        else:
            # For shorts: track lowest price, move stop down
            if self.lowest_price is None or current_price < self.lowest_price:
                self.lowest_price = current_price
                new_stop = self._calculate_stop(current_price)
                if new_stop < self.stop_price:
                    self.stop_price = new_stop

        # Check if stop is hit
        triggered = False
        if self.side == "buy" and current_price <= self.stop_price:
            triggered = True
        elif self.side == "sell" and current_price >= self.stop_price:
            triggered = True

        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "highest_price": self.highest_price,
            "lowest_price": self.lowest_price,
            "current_price": current_price,
            "stop_price": round(self.stop_price, 6),
            "trail_pct": self.trail_pct,
            "triggered": triggered,
            "unrealized_pnl_pct": round(
                (current_price / self.entry_price - 1) * 100 if self.side == "buy"
                else (self.entry_price / current_price - 1) * 100, 2
            ),
        }


# Active trailing stops registry
_trailing_stops: dict[str, TrailingStop] = {}


def create_trailing_stop(symbol: str, side: str, entry_price: float, trail_pct: float = 0.05) -> dict:
    """Create a new trailing stop for a position."""
    key = f"{symbol}:{side}"
    stop = TrailingStop(symbol, side, entry_price, trail_pct)
    _trailing_stops[key] = stop
    return {"created": True, **stop.update(entry_price)}


def restore_trailing_stop(symbol: str, side: str, entry_price: float, trail_pct: float,
                         highest_price: float | None, lowest_price: float | None,
                         stop_price: float) -> dict:
    """Restore a trailing stop from persisted DB state."""
    key = f"{symbol}:{side}"
    stop = TrailingStop(symbol, side, entry_price, trail_pct)
    stop.highest_price = highest_price
    stop.lowest_price = lowest_price
    stop.stop_price = stop_price
    _trailing_stops[key] = stop
    return {"restored": True, **stop.update(highest_price or lowest_price or entry_price)}


def update_trailing_stop(symbol: str, side: str, current_price: float) -> dict:
    """Update trailing stop with current price."""
    key = f"{symbol}:{side}"
    stop = _trailing_stops.get(key)
    if not stop:
        return {"error": f"No trailing stop for {symbol} {side}"}
    return stop.update(current_price)


def remove_trailing_stop(symbol: str, side: str) -> dict:
    """Remove a trailing stop."""
    key = f"{symbol}:{side}"
    if key in _trailing_stops:
        del _trailing_stops[key]
        return {"removed": True}
    return {"error": f"No trailing stop for {symbol} {side}"}


def get_all_trailing_stops() -> list[dict]:
    """Get status of all active trailing stops."""
    return [stop.update(stop.highest_price or stop.lowest_price or stop.entry_price)
            for stop in _trailing_stops.values()]


def check_trailing_stops(prices: dict[str, float]) -> list[dict]:
    """Check all trailing stops against current prices, return triggered ones."""
    triggered = []
    for key, stop in list(_trailing_stops.items()):
        price = prices.get(stop.symbol)
        if price:
            result = stop.update(price)
            if result.get("triggered"):
                triggered.append(result)
    return triggered


# --- Position Sizing ---
def calculate_position_size(
    capital: float,
    risk_per_trade_pct: float = 0.02,
    entry_price: float = 0,
    stop_loss_price: float = 0,
    max_position_pct: float = 0.25,
) -> dict:
    """Calculate optimal position size based on risk management.

    Rules:
    - Max 2% of capital risked per trade
    - Max 25% of capital in any single position
    - If stop loss provided, size based on risk distance

    Args:
        capital: Total trading capital
        risk_per_trade_pct: Max risk per trade (default 2%)
        entry_price: Expected entry price
        stop_loss_price: Stop loss price
        max_position_pct: Max position as % of capital (default 25%)
    """
    max_risk_amount = capital * risk_per_trade_pct
    max_position_value = capital * max_position_pct

    if entry_price <= 0:
        return {
            "quantity": 0,
            "risk_amount": 0,
            "position_value": 0,
            "error": "Invalid entry price",
        }

    # If stop loss provided, calculate based on risk distance
    if stop_loss_price > 0 and entry_price != stop_loss_price:
        risk_per_unit = abs(entry_price - stop_loss_price)
        risk_based_qty = max_risk_amount / risk_per_unit
        risk_based_value = risk_based_qty * entry_price
        # Cap at max position
        if risk_based_value > max_position_value:
            risk_based_qty = max_position_value / entry_price
            risk_based_value = max_position_value
    else:
        # No stop loss: use max position
        risk_based_qty = max_position_value / entry_price
        risk_based_value = max_position_value

    quantity = round(risk_based_qty, 8)
    position_value = round(quantity * entry_price, 2)

    return {
        "quantity": quantity,
        "position_value": position_value,
        "risk_amount": round(max_risk_amount, 2),
        "risk_per_trade_pct": risk_per_trade_pct * 100,
        "max_position_pct": max_position_pct * 100,
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
    }


# --- Mode-Aware Execution ---

def execute_market_order(
    symbol: str,
    side: str,
    quantity: float,
    current_price: float,
    strategy: str = "manual",
    reason: str = "",
) -> dict:
    """Execute a market order through the appropriate channel.

    In paper mode: simulates fill with slippage.
    In live mode: routes through OMS to real exchange.

    Returns standardized order result.
    """
    from . import oms as _oms
    return _oms.oms.submit_market_order(
        symbol=symbol,
        side=side,
        quantity=quantity,
        current_price=current_price,
        strategy=strategy,
        reason=reason,
    )


def execute_limit_order(
    symbol: str,
    side: str,
    quantity: float,
    limit_price: float,
    current_price: float,
    strategy: str = "manual",
) -> dict:
    """Execute a limit order through the OMS.

    In paper mode: fills immediately if price is favorable, otherwise recorded as pending.
    In live mode: places a real limit order on the exchange.
    """
    from . import oms as _oms
    return _oms.oms.submit_limit_order(
        symbol=symbol,
        side=side,
        quantity=quantity,
        limit_price=limit_price,
        current_price=current_price,
        strategy=strategy,
        reason=f"limit_order@{limit_price}",
    )


def get_execution_mode() -> dict:
    """Get current execution mode info."""
    return {
        "mode": config.MODE,
        "exchange": config.LIVE_EXCHANGE_ID if config.MODE == "live" else "paper",
        "testnet": config.LIVE_TESTNET if config.MODE == "live" else True,
        "max_order_notional": config.MAX_ORDER_NOTIONAL,
        "max_total_exposure": config.MAX_TOTAL_EXPOSURE,
        "order_min_notional": config.ORDER_MIN_NOTIONAL,
    }
