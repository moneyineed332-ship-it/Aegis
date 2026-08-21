"""Binance Testnet integration via CCXT for live paper-to-real transition."""

import logging

from . import config
from .exchange import ExchangeManager, get_binance_testnet

logger = logging.getLogger(__name__)


class BinanceTestnet:
    """Binance Testnet client — paper mode only by default.

    Uses CCXT under the hood for:
    - Automatic rate limiting
    - Unified order format
    - Sandbox mode
    """

    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = True):
        self.api_key = api_key or config.BINANCE_TESTNET_API_KEY
        self.api_secret = api_secret or config.BINANCE_TESTNET_API_SECRET
        self.testnet = testnet

        self._exchange = ExchangeManager(
            exchange_id="binance",
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=testnet,
        )

    @property
    def exchange(self) -> ExchangeManager:
        return self._exchange

    # === Public Endpoints (no auth) ===

    def get_price(self, symbol: str) -> dict:
        try:
            ticker = self._exchange.fetch_ticker(_to_ccxt(symbol))
            return {"symbol": symbol, "price": str(ticker["price"])}
        except Exception as e:
            logger.debug("get_price failed for %s: %s", symbol, e, exc_info=True)
            return {"error": str(e)}

    def get_prices(self, symbols: list[str] | None = None) -> list[dict]:
        try:
            ccxt_symbols = [_to_ccxt(s) for s in symbols] if symbols else None
            tickers = self._exchange.fetch_tickers(ccxt_symbols)
            return [
                {"symbol": t["symbol"].replace("/", ""), "price": str(t["price"])}
                for t in tickers
            ]
        except Exception as e:
            logger.debug("get_prices failed: %s", e, exc_info=True)
            return []

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> list[dict]:
        try:
            candles = self._exchange.fetch_ohlcv(_to_ccxt(symbol), interval, limit)
            interval_ms = _interval_to_ms(interval)
            return [
                {
                    "symbol": symbol,
                    "interval": interval,
                    "open_time": c["timestamp"],
                    "close_time": c["timestamp"] + interval_ms - 1,
                    "open": c["open"],
                    "high": c["high"],
                    "low": c["low"],
                    "close": c["close"],
                    "volume": c["volume"],
                }
                for c in candles
            ]
        except Exception as e:
            logger.debug("get_klines failed for %s: %s", symbol, e, exc_info=True)
            return []

    def get_exchange_info(self, symbol: str | None = None) -> dict:
        try:
            info = self._exchange.get_exchange_info()
            if symbol:
                markets = self._exchange.exchange.markets
                for sym, market in markets.items():
                    if market.get("symbol") == _to_ccxt(symbol):
                        info["symbol_info"] = market
                        break
            return info
        except Exception as e:
            logger.debug("get_exchange_info failed: %s", e, exc_info=True)
            return {"error": str(e)}

    # === Signed Endpoints (trading) ===

    def get_account(self) -> dict:
        try:
            balance = self._exchange.fetch_balance()
            return {"balances": balance}
        except Exception as e:
            logger.debug("get_account failed: %s", e, exc_info=True)
            return {"error": str(e)}

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        try:
            orders = self._exchange.fetch_open_orders(_to_ccxt(symbol) if symbol else None)
            return orders
        except Exception as e:
            logger.debug("get_open_orders failed: %s", e, exc_info=True)
            return []

    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        try:
            order = self._exchange.create_market_order(_to_ccxt(symbol), side.lower(), quantity)
            return order
        except Exception as e:
            logger.debug("place_market_order failed: %s", e, exc_info=True)
            return {"error": str(e)}

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> dict:
        try:
            order = self._exchange.create_limit_order(_to_ccxt(symbol), side.lower(), quantity, price)
            return order
        except Exception as e:
            logger.debug("place_limit_order failed: %s", e, exc_info=True)
            return {"error": str(e)}

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        try:
            self._exchange.cancel_order(str(order_id), _to_ccxt(symbol))
            return {"symbol": symbol, "orderId": order_id, "status": "cancelled"}
        except Exception as e:
            logger.debug("cancel_order failed: %s", e, exc_info=True)
            return {"error": str(e)}

    def get_all_orders(self, symbol: str, limit: int = 500) -> list[dict]:
        try:
            return self._exchange.fetch_open_orders(_to_ccxt(symbol))
        except Exception as e:
            logger.debug("get_all_orders failed: %s", e, exc_info=True)
            return []

    # === Futures Endpoints ===

    def get_futures_price(self, symbol: str) -> dict:
        try:
            ticker = self._exchange.fetch_ticker(_to_ccxt(symbol))
            return {"symbol": symbol, "price": str(ticker["price"])}
        except Exception as e:
            logger.debug("get_futures_price failed for %s: %s", symbol, e, exc_info=True)
            return {"error": str(e)}

    def get_futures_account(self) -> dict:
        return self.get_account()

    def get_futures_klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> list[dict]:
        return self.get_klines(symbol, interval, limit)

    def place_futures_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        return self.place_market_order(symbol, side, quantity)

    def place_futures_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> dict:
        return self.place_limit_order(symbol, side, quantity, price)

    # === Utility ===

    def health_check(self) -> dict:
        return self._exchange.health_check()

    def test_connection(self) -> dict:
        price = self.get_price("BTCUSDT")
        return {
            "connected": not price.get("error"),
            "btc_price": price.get("price"),
            "testnet": self.testnet,
            "has_keys": bool(self.api_key and self.api_secret),
        }


def _to_ccxt(binance_symbol: str) -> str:
    """Convert 'BTCUSDT' to 'BTC/USDT'."""
    s = binance_symbol.upper()
    for quote in ("USDT", "USDC", "BUSD", "BTC", "ETH"):
        if s.endswith(quote) and len(s) > len(quote):
            base = s[: -len(quote)]
            return f"{base}/{quote}"
    return s


def _interval_to_ms(interval: str) -> int:
    """Convert interval string to milliseconds."""
    multipliers = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}
    unit = interval[-1]
    value = int(interval[:-1]) if len(interval) > 1 else 1
    return value * multipliers.get(unit, 3_600_000)
