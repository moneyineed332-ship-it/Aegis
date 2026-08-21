"""CCXT unified exchange wrapper for AEGIS AI Quant.

Production-ready with retry logic, order validation, error handling,
and dual-mode support (paper/live).
"""

import json
import logging
import time
from typing import Any

from . import config

logger = logging.getLogger(__name__)

# Lazy ccxt import
_ccxt = None


def _get_ccxt():
    global _ccxt
    if _ccxt is None:
        import ccxt
        _ccxt = ccxt
    return _ccxt


class ExchangeError(Exception):
    """Exchange-specific error."""
    def __init__(self, message: str, code: str = "EXCHANGE_ERROR", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class OrderRejected(Exception):
    """Order was rejected by the exchange."""
    def __init__(self, message: str, order_id: str | None = None, reason: str = ""):
        super().__init__(message)
        self.order_id = order_id
        self.reason = reason


class ExchangeManager:
    """Unified exchange manager using CCXT.

    Features:
    - Auto-retry on rate limits (429) and transient errors
    - Order validation before submission
    - Normalized OHLCV/ticker/order data
    - Balance and position tracking
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = False,
    ):
        self.exchange_id = exchange_id
        self.testnet = testnet
        self._authenticated = bool(api_key and api_secret)

        ccxt = _get_ccxt()
        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Exchange '{exchange_id}' not supported by CCXT")

        params: dict[str, Any] = {
            "apiKey": api_key or None,
            "secret": api_secret or None,
            "enableRateLimit": True,
            "timeout": config.ORDER_TIMEOUT * 1000,  # ms
            "options": {"defaultType": "spot"},
        }

        if testnet and hasattr(exchange_class, "urls") and isinstance(getattr(exchange_class, "urls", None), dict) and "test" in exchange_class.urls:
            params["options"]["sandboxMode"] = True

        self.exchange = exchange_class(params)

        if testnet:
            try:
                self.exchange.set_sandbox_mode(True)
                logger.info("CCXT sandbox mode enabled for %s", exchange_id)
            except Exception as e:
                logger.debug("Sandbox mode not available for %s: %s", exchange_id, e, exc_info=True)

        logger.info("CCXT exchange initialized: %s (testnet=%s, auth=%s)", exchange_id, testnet, self._authenticated)

    def _retry(self, func, *args, **kwargs) -> Any:
        """Execute with retry on transient errors."""
        last_error = None
        for attempt in range(config.ORDER_RETRY_ATTEMPTS):
            try:
                return func(*args, **kwargs)
            except (_get_ccxt().NetworkError, _get_ccxt().ExchangeNotAvailable) as e:
                last_error = e
                wait = config.ORDER_RETRY_DELAY * (attempt + 1)
                logger.warning("Retryable error (attempt %d/%d): %s — waiting %.1fs",
                              attempt + 1, config.ORDER_RETRY_ATTEMPTS, e, wait)
                time.sleep(wait)
            except _get_ccxt().RateLimitExceeded as e:
                last_error = e
                wait = config.ORDER_RETRY_DELAY * (attempt + 1) * 2
                logger.warning("Rate limited (attempt %d/%d) — waiting %.1fs",
                              attempt + 1, config.ORDER_RETRY_ATTEMPTS, wait)
                time.sleep(wait)
            except _get_ccxt().ExchangeError as e:
                raise ExchangeError(str(e), code="EXCHANGE_ERROR", retryable=False) from e
        raise ExchangeError(
            f"Max retries ({config.ORDER_RETRY_ATTEMPTS}) exceeded: {last_error}",
            code="MAX_RETRIES",
            retryable=True,
        )

    # --- Market Data ---

    def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        """Fetch current ticker (price, volume, 24h change)."""
        ticker = self._retry(self.exchange.fetch_ticker, symbol)
        return {
            "symbol": ticker["symbol"],
            "price": ticker.get("last", 0),
            "bid": ticker.get("bid", 0),
            "ask": ticker.get("ask", 0),
            "high": ticker.get("high", 0),
            "low": ticker.get("low", 0),
            "volume": ticker.get("baseVolume", 0),
            "change_pct": ticker.get("percentage", 0),
            "source": f"ccxt_{self.exchange_id}",
            "timestamp": ticker.get("timestamp"),
        }

    def fetch_tickers(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        """Fetch tickers for multiple symbols."""
        tickers = self._retry(self.exchange.fetch_tickers, symbols)
        result = []
        for symbol, ticker in tickers.items():
            result.append({
                "symbol": symbol,
                "price": ticker.get("last", 0),
                "bid": ticker.get("bid", 0),
                "ask": ticker.get("ask", 0),
                "high": ticker.get("high", 0),
                "low": ticker.get("low", 0),
                "volume": ticker.get("baseVolume", 0),
                "change_pct": ticker.get("percentage", 0),
                "source": f"ccxt_{self.exchange_id}",
                "timestamp": ticker.get("timestamp"),
            })
        return result

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
        since: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch OHLCV candles."""
        candles = self._retry(self.exchange.fetch_ohlcv, symbol, timeframe, since=since, limit=limit)
        return [
            {
                "timestamp": c[0],
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
                "source": f"ccxt_{self.exchange_id}",
            }
            for c in candles
        ]

    def fetch_order_book(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        """Fetch order book (bids/asks)."""
        ob = self._retry(self.exchange.fetch_order_book, symbol, limit)
        return {
            "symbol": symbol,
            "bids": ob.get("bids", [])[:limit],
            "asks": ob.get("asks", [])[:limit],
            "spread": (ob["asks"][0][0] - ob["bids"][0][0]) if ob.get("asks") and ob.get("bids") else 0,
            "source": f"ccxt_{self.exchange_id}",
            "timestamp": ob.get("timestamp"),
        }

    # --- Order Execution ---

    def _validate_order(self, symbol: str, side: str, amount: float, price: float | None = None) -> None:
        """Validate order parameters before submission."""
        if not self._authenticated:
            raise OrderRejected("Exchange not authenticated — API key/secret required for live orders")
        if side not in ("buy", "sell"):
            raise OrderRejected(f"Invalid side: {side}")
        if amount <= 0:
            raise OrderRejected(f"Invalid amount: {amount}")
        # Check minimum notional
        if price and price * amount < config.ORDER_MIN_NOTIONAL:
            raise OrderRejected(f"Order notional ({price * amount:.2f}) below minimum ({config.ORDER_MIN_NOTIONAL})")

    def create_market_order(self, symbol: str, side: str, amount: float) -> dict[str, Any]:
        """Create a market order with validation and retry."""
        self._validate_order(symbol, side, amount)
        try:
            order = self._retry(self.exchange.create_order, symbol, "market", side, amount)
            result = self._normalize_order(order)
            logger.info("Market order filled: %s %s %s @ market (id=%s)", side, amount, symbol, result.get("id"))
            return result
        except ExchangeError:
            raise
        except Exception as e:
            raise OrderRejected(f"Market order failed: {e}", reason=str(e)) from e

    def create_limit_order(self, symbol: str, side: str, amount: float, price: float) -> dict[str, Any]:
        """Create a limit order with validation and retry."""
        self._validate_order(symbol, side, amount, price)
        try:
            order = self._retry(self.exchange.create_order, symbol, "limit", side, amount, price)
            result = self._normalize_order(order)
            logger.info("Limit order placed: %s %s %s @ %.6f (id=%s)", side, amount, symbol, price, result.get("id"))
            return result
        except ExchangeError:
            raise
        except Exception as e:
            raise OrderRejected(f"Limit order failed: {e}", reason=str(e)) from e

    def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """Cancel an open order."""
        try:
            return self._retry(self.exchange.cancel_order, order_id, symbol)
        except Exception as e:
            logger.error("Cancel order failed: %s — %s", order_id, e)
            raise ExchangeError(f"Cancel failed: {e}") from e

    def fetch_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Fetch all open orders."""
        orders = self._retry(self.exchange.fetch_open_orders, symbol)
        return [self._normalize_order(o) for o in orders]

    def fetch_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """Fetch a specific order by ID."""
        order = self._retry(self.exchange.fetch_order, order_id, symbol)
        return self._normalize_order(order)

    def fetch_balance(self) -> dict[str, Any]:
        """Fetch account balance."""
        balance = self._retry(self.exchange.fetch_balance)
        result = {}
        for currency, data in balance.get("total", {}).items():
            if data and data > 0:
                result[currency] = {
                    "total": data,
                    "free": balance.get("free", {}).get(currency, 0),
                    "used": balance.get("used", {}).get(currency, 0),
                }
        return result

    # --- Utility ---

    def get_exchange_info(self) -> dict[str, Any]:
        """Get exchange metadata."""
        return {
            "id": self.exchange_id,
            "name": self.exchange.name,
            "testnet": self.testnet,
            "authenticated": self._authenticated,
            "markets_count": len(self.exchange.markets),
            "timeframes": list(self.exchange.timeframes.keys()) if self.exchange.timeframes else [],
            "has_order_book": self.exchange.has.get("fetchOrderBook", False),
            "has_ohlcv": self.exchange.has.get("fetchOHLCV", False),
            "has_ticker": self.exchange.has.get("fetchTicker", False),
            "rate_limit": self.exchange.rateLimit,
        }

    def health_check(self) -> dict[str, Any]:
        """Check exchange connectivity."""
        try:
            self.exchange.fetch_time()
            return {"status": "ok", "exchange": self.exchange_id, "testnet": self.testnet, "authenticated": self._authenticated}
        except Exception as e:
            logger.debug("Health check failed for %s: %s", self.exchange_id, e, exc_info=True)
            return {"status": "error", "exchange": self.exchange_id, "error": str(e)}

    def _normalize_order(self, order: dict) -> dict[str, Any]:
        """Normalize CCXT order to AEGIS format."""
        return {
            "id": order.get("id"),
            "symbol": order.get("symbol"),
            "side": order.get("side"),
            "type": order.get("type"),
            "amount": order.get("amount"),
            "price": order.get("price"),
            "average": order.get("average"),
            "cost": order.get("cost", 0),
            "status": order.get("status"),
            "fee": order.get("fee"),
            "filled": order.get("filled", 0),
            "remaining": order.get("remaining", 0),
            "timestamp": order.get("timestamp"),
            "source": f"ccxt_{self.exchange_id}",
        }


# --- Factory ---

def create_exchange(
    exchange_id: str = "binance",
    testnet: bool = False,
    live: bool = False,
) -> ExchangeManager:
    """Factory to create an ExchangeManager.

    Args:
        exchange_id: Exchange ID (e.g., 'binance', 'bybit')
        testnet: Use testnet/sandbox mode
        live: Use live credentials from config (overrides testnet param)
    """
    if live and config.MODE == "live":
        # Use live credentials
        options = {}
        try:
            options = json.loads(config.LIVE_EXCHANGE_OPTIONS)
        except (json.JSONDecodeError, TypeError):
            pass
        return ExchangeManager(
            exchange_id=config.LIVE_EXCHANGE_ID,
            api_key=config.LIVE_API_KEY,
            api_secret=config.LIVE_API_SECRET,
            testnet=config.LIVE_TESTNET,
        )
    elif exchange_id == "binance":
        return ExchangeManager(
            exchange_id="binance",
            api_key=config.BINANCE_TESTNET_API_KEY,
            api_secret=config.BINANCE_TESTNET_API_SECRET,
            testnet=testnet,
        )
    return ExchangeManager(exchange_id=exchange_id, testnet=testnet)


# --- Singletons ---

_binance_testnet: ExchangeManager | None = None
_binance_public: ExchangeManager | None = None
_live_exchange: ExchangeManager | None = None


def get_binance_testnet() -> ExchangeManager:
    """Get or create Binance testnet instance (lazy singleton)."""
    global _binance_testnet
    if _binance_testnet is None:
        _binance_testnet = create_exchange("binance", testnet=True)
    return _binance_testnet


def get_binance_public() -> ExchangeManager:
    """Get or create Binance public instance for market data (no auth)."""
    global _binance_public
    if _binance_public is None:
        _binance_public = ExchangeManager(exchange_id="binance")
    return _binance_public


def get_live_exchange() -> ExchangeManager:
    """Get or create live exchange instance (lazy singleton).

    Returns the configured live exchange with real API credentials.
    Only works when MODE=live and credentials are provided.
    """
    global _live_exchange
    if _live_exchange is None:
        if not config.LIVE_API_KEY or not config.LIVE_API_SECRET:
            raise ExchangeError("Live exchange credentials not configured (AEGIS_LIVE_API_KEY / AEGIS_LIVE_API_SECRET)")
        _live_exchange = create_exchange(live=True)
    return _live_exchange
