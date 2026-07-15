"""Free API collectors — CoinGecko, DeFiLlama, PerpFinder, Mempool, DexScreener, etc."""

import json
import urllib.request
import urllib.error
from typing import Any


def _get(url: str, timeout: int = 15) -> dict | list | None:
    req = urllib.request.Request(url, headers={"User-Agent": "AEGIS-AI-Quant/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


# ── CoinGecko (no key) ──────────────────────────────────────────────

def coingecko_global() -> dict:
    data = _get("https://api.coingecko.com/api/v3/global")
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
    data = _get("https://api.coingecko.com/api/v3/search/trending")
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
    data = _get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h")
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
    data = _get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h")
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
    data = _get("https://api.llama.fi/v2/historicalChainTvl")
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
    data = _get("https://api.llama.fi/v2/chains")
    if not data or not isinstance(data, list):
        return []
    return [
        {"name": c.get("name"), "tvl": c.get("tvl"), "chain_id": c.get("chainId")}
        for c in sorted(data, key=lambda x: x.get("tvl", 0), reverse=True)[:15]
    ]


def defillama_top_protocols() -> list[dict]:
    data = _get("https://api.llama.fi/protocols")
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
    data = _get("https://yields.llama.fi/pools")
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
    data = _get("https://api.perpfinder.com/data/funding-rates")
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
    data = _get("https://api.perpfinder.com/data/open-interest")
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
    data = _get("https://api.perpfinder.com/data/liquidations")
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
    data = _get("https://mempool.space/api/v1/fees/recommended")
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
    data = _get("https://mempool.space/api/mempool")
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
    data = _get("https://api.dexscreener.com/token-boosts/latest/v1")
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
    data = _get(f"https://api.dexscreener.com/latest/dex/pairs/{chain}/trending")
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
    data = _get("https://api.coinpaprika.com/v1/global")
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
    data = _get(f"https://api.frankfurter.app/latest?from={base}")
    if not data or "rates" not in data:
        return {"error": "Frankfurter unavailable"}
    return {
        "base": data.get("base"),
        "date": data.get("date"),
        "rates": data.get("rates"),
    }


# ── Polymarket (no key) ─────────────────────────────────────────────

def polymarket_crypto_markets() -> list[dict]:
    data = _get("https://gamma-api.polymarket.com/markets?limit=20&active=true&tag=Crypto")
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
    data = _get("https://api.coinlore.net/api/tickers/?limit=50")
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
    data = _get("https://terminalfeed.io/api/briefing")
    if not data:
        return {"error": "TerminalFeed unavailable"}
    return data


def terminalfeed_funding_rates() -> list[dict]:
    data = _get("https://terminalfeed.io/api/funding-rates")
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
    data = _get("https://blockstream.info/api/blocks/tip/height")
    if data is None:
        return {"error": "Blockstream unavailable"}
    return {"block_height": data}


# ── Alternative.me (already in market_data, but adding historical) ──

def fear_greed_historical(limit: int = 30) -> list[dict]:
    data = _get(f"https://api.alternative.me/fng/?limit={limit}&format=json")
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


# ── Aggregate all free API data ─────────────────────────────────────

def get_all_free_data() -> dict:
    return {
        "coingecko_global": coingecko_global(),
        "coingecko_trending": coingecko_trending(),
        "coingecko_top_gainers": coingecko_top_gainers(),
        "coingecko_top_losers": coingecko_top_losers(),
        "defillama_tvl": defillama_tvl(),
        "defillama_top_protocols": defillama_top_protocols(),
        "defillama_yields": defillama_yields(),
        "defillama_chains": defillama_chains(),
        "perpfinder_funding": perpfinder_funding_rates(),
        "perpfinder_open_interest": perpfinder_open_interest(),
        "perpfinder_liquidations": perpfinder_liquidations(),
        "mempool_fees": mempool_fees(),
        "mempool_mempool": mempool_mempool(),
        "dexscreener_trending": dexscreener_trending(),
        "coinpaprika_global": coinpaprika_global(),
        "coinlore_movers": coinlore_movers(),
        "polymarket_crypto": polymarket_crypto_markets(),
        "terminalfeed_briefing": terminalfeed_briefing(),
        "blockstream": blockstream_info(),
        "fear_greed_historical": fear_greed_historical(),
    }
