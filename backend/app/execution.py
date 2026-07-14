"""Smart order execution simulation for paper trading.

Supports market orders, limit orders, and fractioned execution.
All orders are simulated — no real exchange interaction.
"""

import math
from datetime import datetime, timezone


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
