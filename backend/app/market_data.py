"""Public market-data collection; this module never sends trading requests."""

import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
BINANCE_OI_URL = "https://fapi.binance.com/fapi/v1/openInterest"
BINANCE_PREMIUM_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1&format=json"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def _get(url: str, params: dict | None = None) -> dict | list:
    """Single GET helper with standard headers."""
    query = urlencode(params) if params else ""
    full_url = f"{url}?{query}" if query else url
    request = Request(full_url, headers={"User-Agent": "AEGIS-AI-Quant/0.1 market-data collector"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_spot_prices() -> list[dict]:
    collected_at = datetime.now(timezone.utc).isoformat()
    snapshots = []
    for symbol in SYMBOLS:
        payload = _get(BINANCE_TICKER_URL, {"symbol": symbol})
        snapshots.append(
            {
                "symbol": payload["symbol"],
                "price": float(payload["price"]),
                "source": "binance_spot_public",
                "collected_at": collected_at,
            }
        )
    return snapshots


def fetch_ohlcv(symbol: str, interval: str, limit: int, end_time: int | None = None) -> list[dict]:
    parameters: dict = {"symbol": symbol, "interval": interval, "limit": limit}
    if end_time is not None:
        parameters["endTime"] = end_time
    payload = _get(BINANCE_KLINES_URL, parameters)
    return [
        {
            "symbol": symbol,
            "interval": interval,
            "open_time": item[0],
            "close_time": item[6],
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
            "source": "binance_spot_public",
        }
        for item in payload
    ]


def fetch_fear_greed() -> dict:
    """Fetch the Fear & Greed Index from alternative.me."""
    collected_at = datetime.now(timezone.utc).isoformat()
    payload = _get(FEAR_GREED_URL)
    data = payload["data"][0]
    return {
        "value": int(data["value"]),
        "classification": data["value_classification"],
        "source": "alternative_me",
        "collected_at": collected_at,
    }


def fetch_funding_rates(symbol: str) -> dict:
    """Fetch current and predicted funding rates from Binance Futures."""
    collected_at = datetime.now(timezone.utc).isoformat()
    payload = _get(BINANCE_PREMIUM_URL, {"symbol": symbol})
    last_funding_time = int(payload.get("lastFundingTime", 0))
    return {
        "symbol": symbol,
        "mark_price": float(payload.get("markPrice", 0)),
        "index_price": float(payload.get("indexPrice", 0)),
        "funding_rate": float(payload.get("lastFundingRate", 0)),
        "next_funding_time": int(payload.get("nextFundingTime", 0)),
        "source": "binance_futures_public",
        "collected_at": collected_at,
    }


def fetch_open_interest(symbol: str) -> dict:
    """Fetch current open interest from Binance Futures."""
    collected_at = datetime.now(timezone.utc).isoformat()
    payload = _get(BINANCE_OI_URL, {"symbol": symbol})
    ticker = _get(BINANCE_TICKER_URL, {"symbol": symbol})
    price = float(ticker["price"])
    oi_value = float(payload["openInterest"]) * price
    return {
        "symbol": symbol,
        "open_interest": float(payload["openInterest"]),
        "open_interest_usd": round(oi_value, 2),
        "price": price,
        "source": "binance_futures_public",
        "collected_at": collected_at,
    }
