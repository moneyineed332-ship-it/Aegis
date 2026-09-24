"""Public market-data collection via CCXT and MT5.

This module never sends trading requests.
Uses CCXT for unified exchange access (100+ exchanges supported).
Uses MT5 for Forex data (EURUSD, GBPUSD, XAUUSD).
"""

import logging
from datetime import datetime, timezone

import httpx

from . import config
from .exchange import get_binance_public

logger = logging.getLogger(__name__)

# CCXT-based instance (lazy)
_binance = None

# Shared httpx client for non-CCXT APIs
_http_client: httpx.Client | None = None

# MT5 connector for Forex data
_mt5_connector = None


def _get_http_client() -> httpx.Client:
    """Get or create a shared httpx client with connection pooling."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=config.HTTP_TIMEOUT,
            headers={"User-Agent": "AEGIS-AI-Quant/0.1"},
            follow_redirects=True,
        )
    return _http_client


def _get_exchange():
    global _binance
    if _binance is None:
        _binance = get_binance_public()
    return _binance


def _get_mt5_connector():
    """Get or create MT5 connector for Forex data."""
    global _mt5_connector
    if _mt5_connector is None:
        try:
            from .mt5_connector import mt5_connector
            _mt5_connector = mt5_connector
        except ImportError:
            logger.warning("MT5 connector not available")
            _mt5_connector = None
    return _mt5_connector


# Fallback: raw Binance API for Fear & Greed (not on CCXT)
FEAR_GREED_URL = config.FEAR_GREED_URL

# Forex symbols for ICT/SMC bot
FOREX_SYMBOLS = ("EURUSD", "GBPUSD", "XAUUSD")

# Yahoo Finance fallback when MT5 is unavailable (Linux/Docker — MT5 is
# Windows-only and not in requirements). No API key required.
_YAHOO_SYMBOLS = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "XAUUSD": "GC=F"}
_YAHOO_INTERVALS = {"5m": "5m", "15m": "15m", "1h": "60m", "4h": "60m"}


def _fetch_yahoo_chart(yahoo_symbol: str, yahoo_interval: str) -> dict | None:
    """Raw Yahoo Finance v8 chart payload (or None on failure)."""
    try:
        client = _get_http_client()
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        response = client.get(url, params={"interval": yahoo_interval, "range": "1mo"})
        response.raise_for_status()
        results = (response.json().get("chart") or {}).get("result") or []
        return results[0] if results else None
    except Exception as e:
        logger.debug("Yahoo chart fetch failed for %s: %s", yahoo_symbol, e)
        return None


def _fetch_ohlcv_yahoo(symbol: str, interval: str, limit: int) -> list[dict]:
    """Forex OHLCV via Yahoo Finance (MT5 unavailable)."""
    yahoo_symbol = _YAHOO_SYMBOLS.get(symbol)
    yahoo_interval = _YAHOO_INTERVALS.get(interval)
    if not yahoo_symbol or not yahoo_interval:
        return []
    result = _fetch_yahoo_chart(yahoo_symbol, yahoo_interval)
    if not result:
        return []
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    rows = []
    for i, ts in enumerate(timestamps):
        try:
            o = (quotes.get("open") or [])[i]
            h = (quotes.get("high") or [])[i]
            lo = (quotes.get("low") or [])[i]
            c = (quotes.get("close") or [])[i]
            if None in (o, h, lo, c):
                continue
            rows.append({
                "open_time": int(ts * 1000),
                "open": float(o), "high": float(h),
                "low": float(lo), "close": float(c),
                "volume": float((quotes.get("volume") or [0] * len(timestamps))[i] or 0),
            })
        except (IndexError, TypeError, ValueError):
            continue
    # NOTE: end_time is not supported by the Yahoo fallback (always latest).
    # For 4h resampling keep 4x rows so the output still covers ~limit candles.
    keep = (limit * 4 + 8) if interval == "4h" else limit
    rows = rows[-keep:] if keep > 0 else rows
    if interval == "4h":
        # Resample 60m buckets into 4h candles.
        resampled = []
        for j in range(0, len(rows), 4):
            chunk = rows[j:j + 4]
            if not chunk:
                continue
            resampled.append({
                "open_time": chunk[0]["open_time"],
                "open": chunk[0]["open"], "high": max(r["high"] for r in chunk),
                "low": min(r["low"] for r in chunk), "close": chunk[-1]["close"],
                "volume": sum(r["volume"] for r in chunk),
            })
        rows = resampled[-limit:] if limit > 0 else resampled
    interval_ms = _interval_to_ms(interval)
    return [
        {
            "symbol": symbol,
            "interval": interval,
            "open_time": r["open_time"],
            "close_time": r["open_time"] + interval_ms - 1,
            "open": r["open"], "high": r["high"], "low": r["low"],
            "close": r["close"], "volume": r["volume"],
            "source": "yahoo_finance",
        }
        for r in rows
    ]


def _fetch_forex_spot_yahoo(symbol: str, collected_at: str) -> dict | None:
    """Single forex spot price via Yahoo Finance (MT5 unavailable)."""
    yahoo_symbol = _YAHOO_SYMBOLS.get(symbol)
    if not yahoo_symbol:
        return None
    result = _fetch_yahoo_chart(yahoo_symbol, "5m")
    if not result:
        return None
    try:
        closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
        valid = [c for c in closes if c]
        if not valid:
            return None
        return {
            "symbol": symbol,
            "price": float(valid[-1]),
            "collected_at": collected_at,
            "source": "yahoo_finance",
        }
    except (TypeError, ValueError):
        return None

# Focused mode: price collection restricted to the focused universe.
if config.ICT_MODE and hasattr(config, 'ICT_SYMBOLS'):
    SYMBOLS = tuple(config.ICT_SYMBOLS)
elif config.FOCUSED_MODE:
    SYMBOLS = tuple(config.FOCUSED_SYMBOLS)
else:
    SYMBOLS = tuple(config.SYMBOLS)


def _is_forex_symbol(symbol: str) -> bool:
    """Check if symbol is a Forex symbol."""
    return symbol in FOREX_SYMBOLS


def _get(url: str, params: dict | None = None) -> dict | list:
    """Single GET helper with httpx (connection pooling)."""
    client = _get_http_client()
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def fetch_spot_prices() -> list[dict]:
    """Fetch spot prices for all configured symbols via MT5 (Forex) and CCXT (crypto)."""
    collected_at = datetime.now(timezone.utc).isoformat()
    snapshots = []
    
    # Separate Forex and crypto symbols
    forex_symbols = [s for s in SYMBOLS if _is_forex_symbol(s)]
    crypto_symbols = [s for s in SYMBOLS if not _is_forex_symbol(s)]
    
    # Fetch Forex prices via MT5 (Yahoo fallback when unavailable)
    if forex_symbols:
        mt5_conn = _get_mt5_connector()
        if mt5_conn is not None:
            for symbol in forex_symbols:
                try:
                    tick = mt5_conn.fetch_tick(symbol)
                    if tick:
                        snapshots.append({
                            "symbol": symbol,
                            "price": tick["bid"],  # Use bid for Forex
                            "collected_at": collected_at,
                            "source": "mt5_forex",
                        })
                except Exception as e:
                    logger.debug("MT5 tick fetch failed for %s: %s", symbol, e, exc_info=True)
        have = {s["symbol"] for s in snapshots}
        for symbol in forex_symbols:
            if symbol not in have:
                try:
                    fallback = _fetch_forex_spot_yahoo(symbol, collected_at)
                    if fallback:
                        snapshots.append(fallback)
                except Exception as e:
                    logger.debug("Yahoo spot fetch failed for %s: %s", symbol, e, exc_info=True)
    
    # Fetch crypto prices via CCXT
    if crypto_symbols:
        ex = _get_exchange()
        try:
            # CCXT format: 'BTC/USDT' not 'BTCUSDT'.
            # fetch_tickers returns a list of {"symbol": ccxt_symbol, "price": ...},
            # so match by symbol instead of zipping dict values (order not guaranteed).
            ccxt_symbols = [_to_ccxt_symbol(s) for s in crypto_symbols]
            tickers = ex.fetch_tickers(ccxt_symbols)
            by_symbol = {t.get("symbol"): t for t in tickers if isinstance(t, dict)}
            for symbol, ccxt_symbol in zip(crypto_symbols, ccxt_symbols):
                ticker = by_symbol.get(ccxt_symbol)
                price = (ticker or {}).get("price")
                if price:
                    snapshots.append({
                        "symbol": symbol,
                        "price": float(price),
                        "collected_at": collected_at,
                        "source": f"ccxt_{ex.exchange_id}",
                    })
                else:
                    fallback_data = _fetch_single_price_fallback(symbol, collected_at)
                    if fallback_data:
                        snapshots.append(fallback_data)
        except Exception as e:
            logger.debug("CCXT fetch_tickers failed, falling back to raw API: %s", e, exc_info=True)
            # Fallback for crypto
            for symbol in crypto_symbols:
                try:
                    fallback_data = _fetch_single_price_fallback(symbol, collected_at)
                    if fallback_data:
                        snapshots.append(fallback_data)
                except Exception as fallback_error:
                    logger.debug("Fallback price fetch failed for %s: %s", symbol, fallback_error, exc_info=True)
    
    return snapshots


def _fetch_single_price_fallback(symbol: str, collected_at: str) -> dict | None:
    """Fallback for single symbol price fetch."""
    client = _get_http_client()
    try:
        url = f"{config.BINANCE_SPOT_URL}/ticker/price"
        response = client.get(url, params={"symbol": symbol})
        response.raise_for_status()
        payload = response.json()
        return {
            "symbol": payload["symbol"],
            "price": float(payload["price"]),
            "collected_at": collected_at,
            "source": "binance_spot_public",
        }
    except Exception as e:
        logger.debug("Fallback price fetch failed for %s: %s", symbol, e, exc_info=True)
        return None


def fetch_ohlcv(symbol: str, interval: str, limit: int, end_time: int | None = None) -> list[dict]:
    """Fetch OHLCV candles via MT5 for Forex, CCXT for crypto."""
    
    # Route to MT5 for Forex symbols
    if _is_forex_symbol(symbol):
        return _fetch_ohlcv_mt5(symbol, interval, limit, end_time)
    
    # Use CCXT for crypto symbols
    ccxt_symbol = _to_ccxt_symbol(symbol)
    # Map Binance intervals to CCXT timeframes
    tf = _interval_to_timeframe(interval)
    ex = _get_exchange()
    try:
        since = end_time - (limit * _interval_to_ms(interval)) if end_time else None
        candles = ex.fetch_ohlcv(ccxt_symbol, tf, limit=limit, since=since)
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
                "source": f"ccxt_{ex.exchange_id}",
            }
            for c in candles
        ]
    except Exception as e:
        logger.debug("CCXT fetch_ohlcv failed for %s: %s", symbol, e, exc_info=True)
        return _fetch_ohlcv_fallback(symbol, interval, limit, end_time)


def _fetch_ohlcv_mt5(symbol: str, interval: str, limit: int, end_time: int | None = None) -> list[dict]:
    """Fetch OHLCV candles via MT5 for Forex symbols (Yahoo fallback on Linux)."""
    mt5_conn = _get_mt5_connector()
    if mt5_conn is None:
        logger.info("MT5 unavailable, using Yahoo Finance fallback for %s %s", symbol, interval)
        return _fetch_ohlcv_yahoo(symbol, interval, limit)
    
    try:
        # Convert end_time to datetime if provided
        end_date = None
        if end_time is not None:
            end_date = datetime.fromtimestamp(end_time / 1000, tz=timezone.utc)
        
        # Fetch from MT5
        candles = mt5_conn.fetch_ohlcv(symbol, interval, limit, None, end_date)
        
        if not candles:
            logger.warning(f"No MT5 data for {symbol} {interval}")
            return []
        
        # Convert to standard format
        interval_ms = _interval_to_ms(interval)
        return [
            {
                "symbol": symbol,
                "interval": interval,
                "open_time": int(datetime.fromisoformat(c["time"].replace("Z", "+00:00")).timestamp() * 1000),
                "close_time": int(datetime.fromisoformat(c["time"].replace("Z", "+00:00")).timestamp() * 1000) + interval_ms - 1,
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c["volume"],
                "source": "mt5_forex",
            }
            for c in candles
        ]
    except Exception as e:
        logger.error("MT5 fetch_ohlcv failed for %s: %s", symbol, e, exc_info=True)
        return _fetch_ohlcv_yahoo(symbol, interval, limit)


def _fetch_ohlcv_fallback(symbol: str, interval: str, limit: int, end_time: int | None) -> list[dict]:
    """Fallback: raw Binance klines API."""
    client = _get_http_client()
    url = f"{config.BINANCE_SPOT_URL}/klines"
    params: dict = {"symbol": symbol, "interval": interval, "limit": limit}
    if end_time is not None:
        params["endTime"] = end_time
    response = client.get(url, params=params)
    response.raise_for_status()
    payload = response.json()
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
    """Fetch current and predicted funding rates via CCXT."""
    collected_at = datetime.now(timezone.utc).isoformat()
    ccxt_symbol = _to_ccxt_symbol(symbol)
    ex = _get_exchange()
    try:
        # CCXT funding rate
        funding = ex.fetch_funding_rate(ccxt_symbol)
        return {
            "symbol": symbol,
            "mark_price": funding.get("markPrice", 0),
            "index_price": funding.get("indexPrice", 0),
            "funding_rate": funding.get("fundingRate", 0),
            "next_funding_time": funding.get("fundingTimestamp"),
            "source": f"ccxt_{ex.exchange_id}",
            "collected_at": collected_at,
        }
    except Exception as e:
        logger.debug("CCXT fetch_funding_rate failed for %s: %s", symbol, e, exc_info=True)
        return _fetch_funding_rates_fallback(symbol, collected_at)


def _fetch_funding_rates_fallback(symbol: str, collected_at: str) -> dict:
    """Fallback: raw Binance Futures premium API."""
    client = _get_http_client()
    url = f"{config.BINANCE_FUTURES_URL}/premiumIndex"
    response = client.get(url, params={"symbol": symbol})
    response.raise_for_status()
    payload = response.json()
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
    """Fetch current open interest via CCXT."""
    collected_at = datetime.now(timezone.utc).isoformat()
    ccxt_symbol = _to_ccxt_symbol(symbol)
    ex = _get_exchange()
    try:
        oi = ex.fetch_open_interest(ccxt_symbol)
        ticker = ex.fetch_ticker(ccxt_symbol)
        price = ticker.get("last", 0)
        oi_value = (oi.get("openInterestAmount", 0) or 0) * price
        return {
            "symbol": symbol,
            "open_interest": oi.get("openInterestAmount", 0),
            "open_interest_usd": round(oi_value, 2),
            "price": price,
            "source": f"ccxt_{ex.exchange_id}",
            "collected_at": collected_at,
        }
    except Exception as e:
        logger.debug("CCXT fetch_open_interest failed for %s: %s", symbol, e, exc_info=True)
        return _fetch_open_interest_fallback(symbol, collected_at)


def _fetch_open_interest_fallback(symbol: str, collected_at: str) -> dict:
    """Fallback: raw Binance Futures open interest API."""
    client = _get_http_client()
    url_oi = f"{config.BINANCE_FUTURES_URL}/openInterest"
    url_ticker = f"{config.BINANCE_SPOT_URL}/ticker/price"
    resp_oi = client.get(url_oi, params={"symbol": symbol})
    resp_oi.raise_for_status()
    payload_oi = resp_oi.json()
    resp_ticker = client.get(url_ticker, params={"symbol": symbol})
    resp_ticker.raise_for_status()
    payload_ticker = resp_ticker.json()
    price = float(payload_ticker["price"])
    oi_value = float(payload_oi["openInterest"]) * price
    return {
        "symbol": symbol,
        "open_interest": float(payload_oi["openInterest"]),
        "open_interest_usd": round(oi_value, 2),
        "price": price,
        "source": "binance_futures_public",
        "collected_at": collected_at,
    }


# --- Helpers ---

def _to_ccxt_symbol(binance_symbol: str) -> str:
    """Convert 'BTCUSDT' to 'BTC/USDT'."""
    s = binance_symbol.upper()
    for quote in ("USDT", "USDC", "BUSD", "BTC", "ETH"):
        if s.endswith(quote) and len(s) > len(quote):
            base = s[: -len(quote)]
            return f"{base}/{quote}"
    return s


def _interval_to_timeframe(interval: str) -> str:
    """Convert Binance interval ('1h') to CCXT timeframe ('1h') or MT5 format."""
    mapping = {
        # Binance/Standard format
        "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h",
        "12h": "12h", "1d": "1d", "3d": "3d", "1w": "1w", "1M": "1M",
        # MT5 format (for ICT/SMC bot)
        "M5": "5m", "M15": "15m", "H1": "1h", "H4": "4h", "D1": "1d",
    }
    return mapping.get(interval, interval)


def _interval_to_ms(interval: str) -> int:
    """Convert interval string to milliseconds."""
    multipliers = {
        "m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000,
    }
    unit = interval[-1]
    value = int(interval[:-1]) if len(interval) > 1 else 1
    return value * multipliers.get(unit, 3_600_000)
