"""Free API collectors — CoinGecko, DeFiLlama, PerpFinder, Mempool, DexScreener, etc."""

import concurrent.futures
import json
import logging

import httpx

logger = logging.getLogger(__name__)
from typing import Any

from . import config

# Shared httpx client for connection pooling
_http_client: httpx.Client | None = None


def _get_http_client() -> httpx.Client:
    """Get or create a shared httpx client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=config.HTTP_TIMEOUT,
            headers={"User-Agent": "AEGIS-AI-Quant/1.0", "Accept": "application/json"},
            follow_redirects=True,
        )
    return _http_client


def _get(url: str, timeout: int = config.HTTP_TIMEOUT) -> dict | list | None:
    client = _get_http_client()
    try:
        response = client.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning(f"API request failed: {e}")
        return None


# ── CoinGecko (no key) ──────────────────────────────────────────────

def coingecko_global() -> dict:
    data = _get(f"{config.COINGECKO_URL}/global")
    if not data or "data" not in data:
        return {"error": "CoinGecko unavailable"}
    d = data["data"]
    return {
        "total_market_cap_usd": d.get("total_market_cap", {}).get("usd"),
        "total_volume_usd": d.get("total_volume", {}).get("usd"),
        "btc_dominance": d.get("market_cap_percentage", {}).get("btc"),
        "eth_dominance": d.get("market_cap_percentage", {}).get("eth"),
        "active_cryptos": d.get("active_cryptocurrencies"),
        "markets": d.get("markets"),
        "market_cap_change_24h": d.get("market_cap_change_percentage_24h_usd"),
    }


def coingecko_trending() -> list[dict]:
    data = _get(f"{config.COINGECKO_URL}/search/trending")
    if not data or "coins" not in data:
        return []
    return [
        {
            "name": c["item"].get("name"),
            "symbol": c["item"].get("symbol"),
            "market_cap_rank": c["item"].get("market_cap_rank"),
            "score": c["item"].get("score"),
        }
        for c in data["coins"][:10]
    ]


def coingecko_top_gainers() -> list[dict]:
    data = _get(f"{config.COINGECKO_URL}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h")
    if not data or not isinstance(data, list):
        return []
    sorted_data = sorted(data, key=lambda x: x.get("price_change_percentage_24h") or 0, reverse=True)
    return [
        {
            "symbol": c.get("symbol", "").upper(),
            "name": c.get("name"),
            "price": c.get("current_price"),
            "change_24h": c.get("price_change_percentage_24h"),
            "market_cap": c.get("market_cap"),
            "volume": c.get("total_volume"),
        }
        for c in sorted_data[:10]
    ]


def coingecko_top_losers() -> list[dict]:
    data = _get(f"{config.COINGECKO_URL}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h")
    if not data or not isinstance(data, list):
        return []
    sorted_data = sorted(data, key=lambda x: x.get("price_change_percentage_24h") or 0)
    return [
        {
            "symbol": c.get("symbol", "").upper(),
            "name": c.get("name"),
            "price": c.get("current_price"),
            "change_24h": c.get("price_change_percentage_24h"),
            "market_cap": c.get("market_cap"),
            "volume": c.get("total_volume"),
        }
        for c in sorted_data[:10]
    ]


# ── DeFiLlama (no key) ──────────────────────────────────────────────

def defillama_tvl() -> dict:
    data = _get(f"{config.DEFILLAMA_URL}/v2/historicalChainTvl")
    if not data or not isinstance(data, list):
        return {"error": "DeFiLlama unavailable"}
    latest = data[-1] if data else {}
    prev = data[-2] if len(data) > 1 else {}
    return {
        "total_tvl": latest.get("tvl"),
        "prev_tvl": prev.get("tvl"),
        "change_pct": round(((latest.get("tvl", 0) - prev.get("tvl", 1)) / prev.get("tvl", 1)) * 100, 2) if prev.get("tvl") else 0,
    }


def defillama_chains() -> list[dict]:
    data = _get(f"{config.DEFILLAMA_URL}/v2/chains")
    if not data or not isinstance(data, list):
        return []
    return [
        {"name": c.get("name"), "tvl": c.get("tvl"), "chain_id": c.get("chainId")}
        for c in sorted(data, key=lambda x: x.get("tvl", 0), reverse=True)[:15]
    ]


def defillama_top_protocols() -> list[dict]:
    data = _get(f"{config.DEFILLAMA_URL}/protocols")
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "name": p.get("name"),
            "symbol": p.get("symbol"),
            "tvl": p.get("tvl"),
            "chain": p.get("chain"),
            "category": p.get("category"),
            "change_1d": p.get("change_1d"),
            "change_7d": p.get("change_7d"),
        }
        for p in sorted(data, key=lambda x: x.get("tvl", 0), reverse=True)[:20]
    ]


def defillama_yields() -> list[dict]:
    data = _get(f"{config.DEFILLAMA_YIELDS_URL}/pools")
    if not data or "data" not in data:
        return []
    pools = data["data"]
    return [
        {
            "pool": p.get("pool"),
            "project": p.get("project"),
            "symbol": p.get("symbol"),
            "chain": p.get("chain"),
            "tvl_usd": p.get("tvlUsd"),
            "apy": p.get("apy"),
            "apy_base": p.get("apyBase"),
            "apy_reward": p.get("apyReward"),
            "il_risk": p.get("ilRisk"),
            "stablecoin": p.get("stablecoin"),
        }
        for p in sorted(pools, key=lambda x: x.get("tvlUsd", 0) or 0, reverse=True)[:20]
    ]


# ── PerpFinder (no key) ─────────────────────────────────────────────

def perpfinder_funding_rates() -> list[dict]:
    data = _get(f"{config.PERPFINDER_URL}/data/funding-rates")
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "symbol": p.get("symbol"),
            "exchange": p.get("exchange"),
            "rate": p.get("rate"),
            "rate_annualized": p.get("rateAnnualized"),
            "next_funding": p.get("nextFunding"),
        }
        for p in data[:20]
    ]


def perpfinder_open_interest() -> list[dict]:
    data = _get(f"{config.PERPFINDER_URL}/data/open-interest")
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "symbol": p.get("symbol"),
            "exchange": p.get("exchange"),
            "open_interest": p.get("openInterest"),
            "change_24h": p.get("change24h"),
        }
        for p in data[:20]
    ]


def perpfinder_liquidations() -> list[dict]:
    data = _get(f"{config.PERPFINDER_URL}/data/liquidations")
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "symbol": p.get("symbol"),
            "total_24h": p.get("total24h"),
            "longs": p.get("longs"),
            "shorts": p.get("shorts"),
            "dominant": p.get("dominant"),
        }
        for p in data[:20]
    ]


# ── Mempool.space (no key) ──────────────────────────────────────────

def mempool_fees() -> dict:
    data = _get(f"{config.MEMPOOL_URL}/v1/fees/recommended")
    if not data:
        return {"error": "Mempool unavailable"}
    return {
        "fastest_fee": data.get("fastestFee"),
        "half_hour_fee": data.get("halfHourFee"),
        "hour_fee": data.get("hourFee"),
        "economy_fee": data.get("economyFee"),
        "minimum_fee": data.get("minimumFee"),
    }


def mempool_mempool() -> dict:
    data = _get(f"{config.MEMPOOL_URL}/mempool")
    if not data:
        return {"error": "Mempool unavailable"}
    return {
        "count": data.get("count"),
        "vsize": data.get("vsize"),
        "total_fee": data.get("total_fee"),
        "fee_histogram": data.get("fee_histogram", [])[:10],
    }


# ── DexScreener (no key) ────────────────────────────────────────────

def dexscreener_trending() -> list[dict]:
    data = _get(f"{config.DEXSCREENER_URL}/token-boosts/latest/v1")
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "chainId": t.get("chainId"),
            "tokenAddress": t.get("tokenAddress"),
            "url": t.get("url"),
            "description": t.get("description"),
        }
        for t in data[:15]
    ]


def dexscreener_pairs(chain: str = "ethereum") -> list[dict]:
    data = _get(f"{config.DEXSCREENER_URL}/latest/dex/pairs/{chain}/trending")
    if not data or "pairs" not in data:
        return []
    return [
        {
            "base_token": p.get("baseToken", {}).get("symbol"),
            "quote_token": p.get("quoteToken", {}).get("symbol"),
            "price_usd": p.get("priceUsd"),
            "volume_24h": p.get("volume", {}).get("h24"),
            "price_change_24h": p.get("priceChange", {}).get("h24"),
            "liquidity_usd": p.get("liquidity", {}).get("usd"),
        }
        for p in data["pairs"][:15]
    ]


# ── CoinPaprika (no key) ────────────────────────────────────────────

def coinpaprika_global() -> dict:
    data = _get(f"{config.COINPAPRIKA_URL}/v1/global")
    if not data:
        return {"error": "CoinPaprika unavailable"}
    return {
        "market_cap_usd": data.get("market_cap_usd"),
        "volume_24h_usd": data.get("volume_24h_usd"),
        "btc_dominance": data.get("btc_dominance"),
        "eth_dominance": data.get("eth_dominance"),
        "cryptocurrencies_number": data.get("cryptocurrencies_number"),
        "market_cap_ath_value": data.get("market_cap_ath_value"),
        "market_cap_ath_date": data.get("market_cap_ath_date"),
    }


# ── Frankfurter Forex (no key) ──────────────────────────────────────

def frankfurter_forex(base: str = "USD") -> dict:
    data = _get(f"{config.FRANKFURTER_URL}/latest?from={base}")
    if not data or "rates" not in data:
        return {"error": "Frankfurter unavailable"}
    return {
        "base": data.get("base"),
        "date": data.get("date"),
        "rates": data.get("rates"),
    }


# ── Polymarket (no key) ─────────────────────────────────────────────

def polymarket_crypto_markets() -> list[dict]:
    data = _get(f"{config.POLYMARKET_URL}/markets?limit=20&active=true&tag=Crypto")
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "question": m.get("question"),
            "slug": m.get("slug"),
            "outcomes": m.get("outcomes"),
            "outcome_prices": m.get("outcomePrices"),
            "volume": m.get("volume"),
            "liquidity": m.get("liquidity"),
        }
        for m in data[:15]
    ]


# ── CoinLore (no key) ──────────────────────────────────────────────

def coinlore_movers() -> dict:
    data = _get(f"{config.COINLORE_URL}/api/tickers/?limit=50")
    if not data or "data" not in data:
        return {"error": "CoinLore unavailable"}
    coins = data["data"]
    sorted_up = sorted(coins, key=lambda x: x.get("percent_change_24h", 0), reverse=True)[:5]
    sorted_down = sorted(coins, key=lambda x: x.get("percent_change_24h", 0))[:5]
    return {
        "top_gainers": [
            {"symbol": c.get("symbol"), "name": c.get("name"), "price": c.get("price_usd"), "change_24h": c.get("percent_change_24h")}
            for c in sorted_up
        ],
        "top_losers": [
            {"symbol": c.get("symbol"), "name": c.get("name"), "price": c.get("price_usd"), "change_24h": c.get("percent_change_24h")}
            for c in sorted_down
        ],
    }


# ── TerminalFeed (no key) ────────────────────────────────────────────

def terminalfeed_briefing() -> dict:
    data = _get(f"{config.TERMINALFEED_URL}/api/briefing")
    if not data:
        return {"error": "TerminalFeed unavailable"}
    return data


def terminalfeed_funding_rates() -> list[dict]:
    data = _get(f"{config.TERMINALFEED_URL}/api/funding-rates")
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "symbol": f.get("symbol"),
            "rate": f.get("rate"),
            "rate_annualized": f.get("rateAnnualized"),
            "exchange": f.get("exchange"),
        }
        for f in data[:20]
    ]


# ── Blockstream (no key) ────────────────────────────────────────────

def blockstream_info() -> dict:
    data = _get(f"{config.BLOCKSTREAM_URL}/blocks/tip/height")
    if data is None:
        return {"error": "Blockstream unavailable"}
    return {"block_height": data}


# ── Alternative.me (already in market_data, but adding historical) ──

def fear_greed_historical(limit: int = 30) -> list[dict]:
    data = _get(f"{config.FEAR_GREED_URL}?limit={limit}&format=json")
    if not data or "data" not in data:
        return []
    return [
        {
            "value": int(d.get("value", 0)),
            "classification": d.get("value_classification"),
            "timestamp": d.get("timestamp"),
        }
        for d in data["data"]
    ]


# ── Finnhub (requires free API key) ──────────────────────────────────

def _finnhub_get(endpoint: str, params: dict | None = None) -> dict | list | None:
    """Internal helper for Finnhub API requests."""
    if not config.FINNHUB_API_KEY:
        return None
    params = params or {}
    params["token"] = config.FINNHUB_API_KEY
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{config.FINNHUB_URL}{endpoint}?{query}"
    return _get(url)


def finnhub_stock_quote(symbol: str) -> dict:
    """Fetch real-time stock quote (bid/ask/last)."""
    data = _finnhub_get("/quote", {"symbol": symbol})
    if not data or data.get("c") is None:
        return {"error": "Finnhub quote unavailable", "symbol": symbol}
    return {
        "symbol": symbol,
        "current_price": data.get("c", 0),
        "open": data.get("o", 0),
        "high": data.get("h", 0),
        "low": data.get("l", 0),
        "previous_close": data.get("pc", 0),
        "change": data.get("d", 0),
        "change_percent": data.get("dp", 0),
        "source": "finnhub",
    }


def finnhub_stock_ohlcv(symbol: str, resolution: str = "D", days_back: int = 30) -> list[dict]:
    """Fetch stock OHLCV candles.

    resolution: '1','5','15','30','60','D','W','M'
    """
    import time as _time
    to_ts = int(_time.time())
    from_ts = to_ts - (days_back * 86400)
    data = _finnhub_get("/stock/candle", {
        "symbol": symbol, "resolution": resolution,
        "from": str(from_ts), "to": str(to_ts),
    })
    if not data or data.get("s") != "ok":
        return []
    count = len(data.get("c", []))
    return [
        {
            "timestamp": data["t"][i] * 1000,
            "open": data["o"][i],
            "high": data["h"][i],
            "low": data["l"][i],
            "close": data["c"][i],
            "volume": data["v"][i],
            "source": "finnhub",
        }
        for i in range(count)
    ]


def finnhub_company_news(symbol: str, days_back: int = 7) -> list[dict]:
    """Fetch company news from Finnhub."""
    import time as _time
    to_date = _time.strftime("%Y-%m-%d")
    from_date = _time.strftime("%Y-%m-%d", _time.gmtime(_time.time() - days_back * 86400))
    data = _finnhub_get("/company-news", {
        "symbol": symbol, "from": from_date, "to": to_date,
    })
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "headline": item.get("headline"),
            "summary": item.get("summary", "")[:200],
            "source": item.get("source"),
            "url": item.get("url"),
            "published": item.get("datetime"),
            "category": item.get("category"),
        }
        for item in data[:20]
    ]


def finnhub_earnings(symbol: str, limit: int = 8) -> list[dict]:
    """Fetch earnings history for a stock."""
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


def finnhub_insider_sentiment(symbol: str, days_back: int = 30) -> dict:
    """Fetch insider sentiment for a stock."""
    import time as _time
    to_date = _time.strftime("%Y-%m-%d")
    from_date = _time.strftime("%Y-%m-%d", _time.gmtime(_time.time() - days_back * 86400))
    data = _finnhub_get("/stock/insider-transactions", {
        "symbol": symbol, "from": from_date, "to": to_date,
    })
    if not data or "data" not in data:
        return {"error": "Finnhub insider data unavailable", "symbol": symbol}
    transactions = data["data"]
    total_buy = sum(1 for t in transactions if t.get("transactionPrice") and t.get("transactionQuantity"))
    return {
        "symbol": symbol,
        "total_transactions": len(transactions),
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
            for t in transactions[:15]
        ],
        "source": "finnhub",
    }


def finnhub_general_news(category: str = "general") -> list[dict]:
    """Fetch general market news from Finnhub."""
    data = _finnhub_get("/news", {"category": category})
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "headline": item.get("headline"),
            "summary": item.get("summary", "")[:200],
            "source": item.get("source"),
            "url": item.get("url"),
            "published": item.get("datetime"),
            "category": item.get("category"),
            "image": item.get("image"),
        }
        for item in data[:20]
    ]


def finnhub_recommendations(symbol: str) -> list[dict]:
    """Fetch analyst recommendation trends for a stock."""
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


def finnhub_forex_rates(base: str = "USD") -> dict:
    """Fetch forex rates from Finnhub."""
    data = _finnhub_get("/forex/rates", {"base": base})
    if not data or "rates" not in data:
        return {"error": "Finnhub forex unavailable"}
    return {
        "base": base,
        "rates": {r.get("quote"): r.get("rate") for r in data["rates"] if r.get("quote")},
        "source": "finnhub",
    }


# ── Aggregate all free API data ─────────────────────────────────────

def get_all_free_data() -> dict:
    """Aggregate all free API data in parallel."""
    functions = [
        ("coingecko_global", coingecko_global),
        ("coingecko_trending", coingecko_trending),
        ("coingecko_top_gainers", coingecko_top_gainers),
        ("coingecko_top_losers", coingecko_top_losers),
        ("defillama_tvl", defillama_tvl),
        ("defillama_top_protocols", defillama_top_protocols),
        ("defillama_yields", defillama_yields),
        ("defillama_chains", defillama_chains),
        ("perpfinder_funding", perpfinder_funding_rates),
        ("perpfinder_open_interest", perpfinder_open_interest),
        ("perpfinder_liquidations", perpfinder_liquidations),
        ("mempool_fees", mempool_fees),
        ("mempool_mempool", mempool_mempool),
        ("dexscreener_trending", dexscreener_trending),
        ("coinpaprika_global", coinpaprika_global),
        ("coinlore_movers", coinlore_movers),
        ("polymarket_crypto", polymarket_crypto_markets),
        ("terminalfeed_briefing", terminalfeed_briefing),
        ("blockstream", blockstream_info),
        ("fear_greed_historical", fear_greed_historical),
        ("finnhub_quote_aapl", lambda: finnhub_stock_quote("AAPL")),
        ("finnhub_news", lambda: finnhub_general_news("general")),
        ("finnhub_forex", finnhub_forex_rates),
    ]

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.FREE_API_WORKERS) as executor:
        future_to_name = {executor.submit(fn): name for name, fn in functions}
        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results[name] = future.result()
            except Exception as e:
                logger.debug("Free API worker failed for %s: %s", name, e, exc_info=True)
                results[name] = None

    return results
