"""Multi-asset support: Forex, Commodities, Stocks via public APIs."""

import logging
from datetime import datetime, timezone

import httpx

from . import config

logger = logging.getLogger(__name__)

# Shared httpx client for connection pooling
_http_client: httpx.Client | None = None


def _get_http_client() -> httpx.Client:
    """Get or create a shared httpx client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=config.HTTP_TIMEOUT,
            headers={"User-Agent": "AEGIS-AI-Quant/0.1 multi-asset"},
            follow_redirects=True,
        )
    return _http_client


# === Supported Asset Classes ===

ASSET_CLASSES = {
    "crypto": {
        "name": "Crypto",
        "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"],
        "source": "binance",
    },
    "forex": {
        "name": "Forex",
        "symbols": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF"],
        "source": "exchangerate_api",
    },
    "commodities": {
        "name": "Commodities",
        "symbols": ["GOLD", "SILVER", "OIL", "NATGAS", "COPPER", "PLATINUM"],
        "source": "metals_api",
    },
    "stocks": {
        "name": "Stocks",
        "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"],
        "source": "yahoo",
    },
}


def _get(url: str, params: dict | None = None) -> dict | list:
    client = _get_http_client()
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


# === Forex ===

def fetch_forex_rates(base: str = "USD") -> dict:
    """Fetch forex rates from exchangerate-api (free tier)."""
    url = f"{config.FOREX_API_URL}/{base}"
    try:
        data = _get(url)
        if data.get("result") == "success":
            return {
                "base": base,
                "rates": data.get("rates", {}),
                "source": "open_er_api",
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        logger.debug("Forex rate fetch failed: %s", e, exc_info=True)
    return {"base": base, "rates": {}, "source": "open_er_api", "error": "fetch_failed"}


def fetch_forex_ohlcv(pair: str, interval: str = "1h", limit: int = 100) -> list[dict]:
    """Fetch forex OHLCV from Twelve Data (free tier limited)."""
    url = f"{config.TWELVEDATA_URL}/time_series"
    try:
        data = _get(url, {"symbol": pair, "interval": interval, "outputsize": limit})
        values = data.get("values", [])
        return [
            {
                "symbol": pair,
                "interval": interval,
                "open_time": int(datetime.fromisoformat(v["datetime"].replace("Z", "+00:00")).timestamp() * 1000),
                "close_time": int(datetime.fromisoformat(v["datetime"].replace("Z", "+00:00")).timestamp() * 1000),
                "open": float(v["open"]),
                "high": float(v["high"]),
                "low": float(v["low"]),
                "close": float(v["close"]),
                "volume": float(v.get("volume", 0)),
                "source": "twelve_data",
            }
            for v in values
        ]
    except Exception as e:
        logger.debug("Forex OHLCV fetch failed: %s", e, exc_info=True)
        return []


# === Commodities ===

def fetch_commodity_prices() -> list[dict]:
    """Fetch commodity prices from metals-api or fallback."""
    collected_at = datetime.now(timezone.utc).isoformat()
    prices = []

    yahoo_symbols = {
        "GOLD": "GC=F",
        "SILVER": "SI=F",
        "OIL": "CL=F",
        "NATGAS": "NG=F",
        "COPPER": "HG=F",
        "PLATINUM": "PL=F",
    }

    for name, yahoo_sym in yahoo_symbols.items():
        try:
            url = f"{config.YAHOO_FINANCE_URL}/{yahoo_sym}"
            data = _get(url, {"interval": "1d", "range": "1d"})
            meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
            price = meta.get("regularMarketPrice", 0)
            if price:
                prices.append({
                    "symbol": name,
                    "price": float(price),
                    "currency": "USD",
                    "source": "yahoo_finance",
                    "collected_at": collected_at,
                })
        except Exception as e:
            logger.debug("Commodity price fetch failed for %s: %s", name, e, exc_info=True)
            continue

    return prices


def fetch_commodity_ohlcv(symbol: str, interval: str = "1d", limit: int = 100) -> list[dict]:
    """Fetch commodity OHLCV from Yahoo Finance."""
    yahoo_map = {
        "GOLD": "GC=F", "SILVER": "SI=F", "OIL": "CL=F",
        "NATGAS": "NG=F", "COPPER": "HG=F", "PLATINUM": "PL=F",
    }
    yahoo_sym = yahoo_map.get(symbol, symbol)
    try:
        url = f"{config.YAHOO_FINANCE_URL}/{yahoo_sym}"
        data = _get(url, {"interval": interval, "range": f"{limit}d"})
        result = data.get("chart", {}).get("result", [{}])[0]
        timestamps = result.get("timestamp", [])
        ohlcv = result.get("indicators", {}).get("quote", [{}])[0]

        candles = []
        for i in range(len(timestamps)):
            if ohlcv.get("open") and ohlcv["open"][i] is not None:
                candles.append({
                    "symbol": symbol,
                    "interval": interval,
                    "open_time": timestamps[i] * 1000,
                    "close_time": timestamps[i] * 1000,
                    "open": float(ohlcv["open"][i]),
                    "high": float(ohlcv["high"][i]),
                    "low": float(ohlcv["low"][i]),
                    "close": float(ohlcv["close"][i]),
                    "volume": float(ohlcv.get("volume", [0])[i] or 0),
                    "source": "yahoo_finance",
                })
        return candles[-limit:]
    except Exception as e:
        logger.debug("Commodity OHLCV fetch failed for %s: %s", symbol, e, exc_info=True)
        return []


# === Stocks ===

def _finnhub_get(endpoint: str, params: dict | None = None) -> dict | list | None:
    """Internal helper for Finnhub API requests."""
    if not config.FINNHUB_API_KEY:
        return None
    params = params or {}
    params["token"] = config.FINNHUB_API_KEY
    url = f"{config.FINNHUB_URL}{endpoint}"
    try:
        client = _get_http_client()
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.debug("Finnhub request failed: %s", e, exc_info=True)
        return None


def fetch_stock_price(symbol: str) -> dict:
    """Fetch stock price — Finnhub primary, Yahoo fallback."""
    collected_at = datetime.now(timezone.utc).isoformat()

    # Try Finnhub first
    if config.FINNHUB_API_KEY:
        data = _finnhub_get("/quote", {"symbol": symbol})
        if data and data.get("c") is not None and data["c"] != 0:
            return {
                "symbol": symbol,
                "price": float(data["c"]),
                "bid": float(data.get("b", 0)),
                "ask": float(data.get("dp", 0)),
                "open": float(data.get("o", 0)),
                "high": float(data.get("h", 0)),
                "low": float(data.get("l", 0)),
                "previous_close": float(data.get("pc", 0)),
                "change": float(data.get("d", 0)),
                "change_percent": float(data.get("dp", 0)),
                "currency": "USD",
                "source": "finnhub",
                "collected_at": collected_at,
            }

    # Fallback to Yahoo Finance
    try:
        url = f"{config.YAHOO_FINANCE_URL}/{symbol}"
        data = _get(url, {"interval": "1d", "range": "1d"})
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        return {
            "symbol": symbol,
            "price": float(meta.get("regularMarketPrice", 0)),
            "currency": meta.get("currency", "USD"),
            "source": "yahoo_finance",
            "collected_at": collected_at,
        }
    except Exception as e:
        logger.debug("Stock price fetch failed for %s: %s", symbol, e, exc_info=True)
        return {"symbol": symbol, "price": 0, "error": "fetch_failed"}


def fetch_stock_ohlcv(symbol: str, interval: str = "1d", limit: int = 100) -> list[dict]:
    """Fetch stock OHLCV — Finnhub primary, Yahoo fallback."""
    # Try Finnhub first
    if config.FINNHUB_API_KEY:
        resolution_map = {
            "1m": "1", "5m": "5", "15m": "15", "30m": "30",
            "1h": "60", "1d": "D", "1w": "W", "1M": "M",
        }
        resolution = resolution_map.get(interval, "D")
        import time
        to_ts = int(time.time())
        from_ts = to_ts - (limit * 86400) if resolution == "D" else to_ts - (limit * 3600)
        data = _finnhub_get("/stock/candle", {
            "symbol": symbol, "resolution": resolution,
            "from": str(from_ts), "to": str(to_ts),
        })
        if data and data.get("s") == "ok" and len(data.get("c", [])) > 0:
            count = len(data["c"])
            return [
                {
                    "symbol": symbol,
                    "interval": interval,
                    "open_time": data["t"][i] * 1000,
                    "close_time": data["t"][i] * 1000,
                    "open": data["o"][i],
                    "high": data["h"][i],
                    "low": data["l"][i],
                    "close": data["c"][i],
                    "volume": data["v"][i],
                    "source": "finnhub",
                }
                for i in range(count)
            ]

    # Fallback to Yahoo Finance
    try:
        url = f"{config.YAHOO_FINANCE_URL}/{symbol}"
        data = _get(url, {"interval": interval, "range": f"{limit}d"})
        result = data.get("chart", {}).get("result", [{}])[0]
        timestamps = result.get("timestamp", [])
        ohlcv = result.get("indicators", {}).get("quote", [{}])[0]

        candles = []
        for i in range(len(timestamps)):
            if ohlcv.get("open") and ohlcv["open"][i] is not None:
                candles.append({
                    "symbol": symbol,
                    "interval": interval,
                    "open_time": timestamps[i] * 1000,
                    "close_time": timestamps[i] * 1000,
                    "open": float(ohlcv["open"][i]),
                    "high": float(ohlcv["high"][i]),
                    "low": float(ohlcv["low"][i]),
                    "close": float(ohlcv["close"][i]),
                    "volume": float(ohlcv.get("volume", [0])[i] or 0),
                    "source": "yahoo_finance",
                })
        return candles[-limit:]
    except Exception as e:
        logger.debug("Stock OHLCV fetch failed for %s: %s", symbol, e, exc_info=True)
        return []


def fetch_stock_recommendations(symbol: str) -> list[dict]:
    """Fetch analyst recommendations for a stock (Finnhub)."""
    if not config.FINNHUB_API_KEY:
        return []
    data = _finnhub_get("/stock/recommendation", {"symbol": symbol})
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "period": item.get("period"),
            "strong_buy": item.get("strongBuy", 0),
            "buy": item.get("buy", 0),
            "hold": item.get("hold", 0),
            "sell": item.get("sell", 0),
            "strong_sell": item.get("strongSell", 0),
        }
        for item in data[:5]
    ]


def fetch_stock_earnings(symbol: str, limit: int = 8) -> list[dict]:
    """Fetch earnings history for a stock (Finnhub)."""
    if not config.FINNHUB_API_KEY:
        return []
    data = _finnhub_get("/stock/earnings", {"symbol": symbol})
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "symbol": symbol,
            "period": item.get("period"),
            "surprise": item.get("surprise"),
            "surprise_percent": item.get("surprisePercent"),
            "actual": item.get("actual"),
            "estimate": item.get("estimate"),
            "year": item.get("year"),
            "quarter": item.get("quarter"),
        }
        for item in data[:limit]
    ]


def fetch_stock_insider(symbol: str, days_back: int = 30) -> dict:
    """Fetch insider transactions for a stock (Finnhub)."""
    if not config.FINNHUB_API_KEY:
        return {"error": "Finnhub API key required", "symbol": symbol}
    import time
    to_date = time.strftime("%Y-%m-%d")
    from_date = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days_back * 86400))
    data = _finnhub_get("/stock/insider-transactions", {
        "symbol": symbol, "from": from_date, "to": to_date,
    })
    if not data or "data" not in data:
        return {"error": "Finnhub insider data unavailable", "symbol": symbol}
    return {
        "symbol": symbol,
        "total_transactions": len(data["data"]),
        "transactions": [
            {
                "name": t.get("name"),
                "share": t.get("share"),
                "change": t.get("change"),
                "transaction_price": t.get("transactionPrice"),
                "transaction_quantity": t.get("transactionQuantity"),
                "transaction_date": t.get("transactionDate"),
                "transaction_code": t.get("transactionCode"),
            }
            for t in data["data"][:15]
        ],
        "source": "finnhub",
    }


# === Unified Interface ===

def fetch_asset_price(symbol: str, asset_class: str | None = None) -> dict:
    """Unified price fetcher that auto-detects asset class."""
    if asset_class is None:
        asset_class = _detect_asset_class(symbol)

    if asset_class == "crypto":
        from .market_data import fetch_spot_prices
        prices = fetch_spot_prices()
        for p in prices:
            if p["symbol"] == symbol:
                return p
        return {"symbol": symbol, "price": 0, "error": "not_found"}
    elif asset_class == "forex":
        rates = fetch_forex_rates()
        pair = symbol.replace("USD", "")
        if pair in rates.get("rates", {}):
            return {"symbol": symbol, "price": 1 / rates["rates"][pair], "source": "open_er_api"}
        return {"symbol": symbol, "price": 0, "error": "not_found"}
    elif asset_class == "commodities":
        prices = fetch_commodity_prices()
        for p in prices:
            if p["symbol"] == symbol:
                return p
        return {"symbol": symbol, "price": 0, "error": "not_found"}
    elif asset_class == "stocks":
        return fetch_stock_price(symbol)
    return {"symbol": symbol, "price": 0, "error": "unknown_asset_class"}


def fetch_asset_ohlcv(symbol: str, interval: str = "1h", limit: int = 200, asset_class: str | None = None) -> list[dict]:
    """Unified OHLCV fetcher."""
    if asset_class is None:
        asset_class = _detect_asset_class(symbol)

    if asset_class == "crypto":
        from .market_data import fetch_ohlcv
        return fetch_ohlcv(symbol, interval, limit)
    elif asset_class == "forex":
        return fetch_forex_ohlcv(symbol, interval, limit)
    elif asset_class == "commodities":
        return fetch_commodity_ohlcv(symbol, interval, limit)
    elif asset_class == "stocks":
        return fetch_stock_ohlcv(symbol, interval, limit)
    return []


def _detect_asset_class(symbol: str) -> str:
    """Auto-detect asset class from symbol."""
    sym = symbol.upper()
    if sym.endswith("USDT") or sym.endswith("BTC") or sym.endswith("ETH"):
        return "crypto"
    if len(sym) == 6 and sym[:3] == "USD" or sym[3:] == "USD":
        return "forex"
    if sym in ASSET_CLASSES["commodities"]["symbols"]:
        return "commodities"
    if sym.isalpha() and len(sym) <= 5:
        return "stocks"
    return "crypto"


def get_asset_classes() -> dict:
    """Return all supported asset classes and their symbols."""
    return ASSET_CLASSES


def get_supported_symbols() -> list[str]:
    """Return all supported symbols across all asset classes."""
    symbols = []
    for cls in ASSET_CLASSES.values():
        symbols.extend(cls["symbols"])
    return symbols
