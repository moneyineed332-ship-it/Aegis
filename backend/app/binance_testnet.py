"""Binance Testnet integration for live paper-to-real transition."""

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class BinanceTestnet:
    """Binance Testnet client — paper mode only by default."""

    TESTNET_SPOT = "https://testnet.binance.vision/api/v3"
    TESTNET_FUTURES = "https://testnet.binancefuture.com/fapi/v1"
    TESTNET_SPOT_WS = "wss://testnet.binance.vision/ws"
    TESTNET_FUTURES_WS = "wss://testnet.binancefuture.com/ws"

    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = True):
        self.api_key = api_key or os.getenv("BINANCE_TESTNET_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_TESTNET_API_SECRET", "")
        self.testnet = testnet
        self.base_url = self.TESTNET_SPOT if testnet else "https://api.binance.com/api/v3"
        self.futures_url = self.TESTNET_FUTURES if testnet else "https://fapi.binance.com/fapi/v1"

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        signature = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature
        return params

    def _request(self, method: str, url: str, params: dict | None = None, signed: bool = False) -> dict:
        params = params or {}
        headers = {"X-MBX-APIKEY": self.api_key}

        if signed:
            params = self._sign(params)

        if method == "GET":
            query = urlencode(params) if params else ""
            full_url = f"{url}?{query}" if query else url
            request = Request(full_url, headers=headers)
        else:
            data = urlencode(params).encode() if params else None
            request = Request(url, data=data, headers=headers, method=method)

        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            return {"error": str(e)}

    # === Public Endpoints (no auth) ===

    def get_price(self, symbol: str) -> dict:
        url = f"{self.base_url}/ticker/price"
        return self._request("GET", url, {"symbol": symbol})

    def get_prices(self, symbols: list[str] | None = None) -> list[dict]:
        url = f"{self.base_url}/ticker/price"
        result = self._request("GET", url)
        if isinstance(result, list) and not symbols:
            return result
        if isinstance(result, list):
            return [r for r in result if r.get("symbol") in symbols] if symbols else result
        return []

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> list[dict]:
        url = f"{self.base_url}/klines"
        result = self._request("GET", url, {"symbol": symbol, "interval": interval, "limit": limit})
        if not isinstance(result, list):
            return []
        return [
            {
                "symbol": symbol, "interval": interval,
                "open_time": k[0], "close_time": k[6],
                "open": float(k[1]), "high": float(k[2]),
                "low": float(k[3]), "close": float(k[4]),
                "volume": float(k[5]),
            }
            for k in result
        ]

    def get_exchange_info(self, symbol: str | None = None) -> dict:
        url = f"{self.base_url}/exchangeInfo"
        result = self._request("GET", url)
        if symbol and isinstance(result, dict):
            symbols = result.get("symbols", [])
            for s in symbols:
                if s.get("symbol") == symbol:
                    return s
        return result

    # === Signed Endpoints (trading) ===

    def get_account(self) -> dict:
        url = f"{self.base_url}/account"
        return self._request("GET", url, signed=True)

    def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        url = f"{self.base_url}/openOrders"
        params = {"symbol": symbol} if symbol else {}
        result = self._request("GET", url, params, signed=True)
        return result if isinstance(result, list) else []

    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        url = f"{self.base_url}/order"
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": f"{quantity:.8f}",
        }
        return self._request("POST", url, params, signed=True)

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> dict:
        url = f"{self.base_url}/order"
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": f"{quantity:.8f}",
            "price": f"{price:.2f}",
        }
        return self._request("POST", url, params, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        url = f"{self.base_url}/order"
        params = {"symbol": symbol, "orderId": order_id}
        return self._request("DELETE", url, params, signed=True)

    def get_all_orders(self, symbol: str, limit: int = 500) -> list[dict]:
        url = f"{self.base_url}/allOrders"
        result = self._request("GET", url, {"symbol": symbol, "limit": limit}, signed=True)
        return result if isinstance(result, list) else []

    # === Futures Endpoints ===

    def get_futures_price(self, symbol: str) -> dict:
        url = f"{self.futures_url}/ticker/price"
        return self._request("GET", url, {"symbol": symbol})

    def get_futures_account(self) -> dict:
        url = f"{self.futures_url}/account"
        return self._request("GET", url, signed=True)

    def get_futures_klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> list[dict]:
        url = f"{self.futures_url}/klines"
        result = self._request("GET", url, {"symbol": symbol, "interval": interval, "limit": limit})
        if not isinstance(result, list):
            return []
        return [
            {
                "symbol": symbol, "interval": interval,
                "open_time": k[0], "close_time": k[6],
                "open": float(k[1]), "high": float(k[2]),
                "low": float(k[3]), "close": float(k[4]),
                "volume": float(k[5]),
            }
            for k in result
        ]

    def place_futures_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        url = f"{self.futures_url}/order"
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": f"{quantity:.8f}",
        }
        return self._request("POST", url, params, signed=True)

    def place_futures_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> dict:
        url = f"{self.futures_url}/order"
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": f"{quantity:.8f}",
            "price": f"{price:.2f}",
        }
        return self._request("POST", url, params, signed=True)

    # === Utility ===

    def health_check(self) -> dict:
        try:
            result = self._request("GET", f"{self.base_url}/ping")
            return {"status": "ok" if not result.get("error") else "error", "detail": result}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def test_connection(self) -> dict:
        price = self.get_price("BTCUSDT")
        return {
            "connected": not price.get("error"),
            "btc_price": price.get("price"),
            "testnet": self.testnet,
            "has_keys": bool(self.api_key and self.api_secret),
        }
