"""Multi-asset support: Forex, Commodities, Stocks via public APIs."""

import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


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
    query = urlencode(params) if params else ""
    full_url = f"{url}?{query}" if query else url
    request = Request(full_url, headers={"User-Agent": "AEGIS-AI-Quant/0.1 multi-asset"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


# === Forex ===

def fetch_forex_rates(base: str = "USD") -> dict:
    """Fetch forex rates from exchangerate-api (free tier)."""
    url = f"https://open.er-api.com/v6/latest/{base}"
    try:
        data = _get(url)
        if data.get("result") == "success":
            return {
                "base": base,
                "rates": data.get("rates", {}),
                "source": "open_er_api",
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception:
        pass
    return {"base": base, "rates": {}, "source": "open_er_api", "error": "fetch_failed"}


def fetch_forex_ohlcv(pair: str, interval: str = "1h", limit: int = 100) -> list[dict]:
    """Fetch forex OHLCV from Twelve Data (free tier limited)."""
    url = f"https://api.twelvedata.com/time_series"
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
    except Exception:
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
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}"
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
        except Exception:
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
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}"
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
    except Exception:
        return []


# === Stocks ===

def fetch_stock_price(symbol: str) -> dict:
    """Fetch stock price from Yahoo Finance."""
    collected_at = datetime.now(timezone.utc).isoformat()
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        data = _get(url, {"interval": "1d", "range": "1d"})
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        return {
            "symbol": symbol,
            "price": float(meta.get("regularMarketPrice", 0)),
            "currency": meta.get("currency", "USD"),
            "source": "yahoo_finance",
            "collected_at": collected_at,
        }
    except Exception:
        return {"symbol": symbol, "price": 0, "error": "fetch_failed"}


def fetch_stock_ohlcv(symbol: str, interval: str = "1d", limit: int = 100) -> list[dict]:
    """Fetch stock OHLCV from Yahoo Finance."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
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
    except Exception:
        return []


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
