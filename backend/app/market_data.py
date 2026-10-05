"""Public Forex market-data collection via MT5, with Yahoo Finance as fallback.

This module never sends trading requests.
On Linux and in containers MT5 is never present, so the Yahoo path is the one that actually runs.
Uses MT5 for Forex data (EURUSD, GBPUSD, XAUUSD).
"""

import logging
from datetime import datetime, timezone

import httpx

from . import config

logger = logging.getLogger(__name__)

# Shared httpx client for the Yahoo fallback and the other HTTP sources
_http_client: httpx.Client | None = None

# MT5 connector for Forex data
_mt5_connector = None

# Data-source fallbacks already reported, as (reason, symbol, interval). The
# source on a given host does not change between cycles, so re-logging the same
# fallback every time only buries the messages that carry new information.
_LOGGED_FALLBACKS: set[tuple[str, str, str]] = set()


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
    """Forex OHLCV via Yahoo Finance.

    Never raises. This is the last-resort source for every host without
    MetaTrader5, so a network error here must degrade to an empty list instead
    of propagating into the engine's scheduled task and being logged as a
    cycle failure.
    """
    yahoo_symbol = _YAHOO_SYMBOLS.get(symbol)
    yahoo_interval = _YAHOO_INTERVALS.get(interval)
    if not yahoo_symbol or not yahoo_interval:
        logger.warning("No Yahoo mapping for %s %s", symbol, interval)
        return []
    try:
        return _fetch_ohlcv_yahoo_inner(symbol, interval, yahoo_symbol, yahoo_interval, limit)
    except Exception as e:
        logger.warning("Yahoo Finance fetch failed for %s %s: %s", symbol, interval, e)
        return []


def _fetch_ohlcv_yahoo_inner(
    symbol: str,
    interval: str,
    yahoo_symbol: str,
    yahoo_interval: str,
    limit: int,
) -> list[dict]:
    """Build candles from a Yahoo chart payload.

    ``interval`` is the AEGIS interval (drives the 4h resampling and the output
    rows); ``yahoo_interval`` is what Yahoo expects.
    """
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

# Price collection universe. Every branch now resolves to a Forex list: the
# focused list defaults to the ICT instruments too, and the last fallback was
# config.SYMBOLS, whose default was a crypto triple. fetch_ohlcv refuses
# anything outside FOREX_SYMBOLS, so a crypto entry here would raise rather than
# quietly return nothing.
if config.FOCUSED_MODE and not config.ICT_MODE:
    SYMBOLS = tuple(config.FOCUSED_SYMBOLS)
else:
    SYMBOLS = tuple(config.ICT_SYMBOLS)


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
    """Fetch spot prices for the configured Forex instruments via MT5."""
    collected_at = datetime.now(timezone.utc).isoformat()
    snapshots = []
    
    forex_symbols = [s for s in SYMBOLS if _is_forex_symbol(s)]
    
    # Fetch Forex prices via MT5 (Yahoo fallback when unavailable)
    if forex_symbols:
        mt5_conn = _get_mt5_connector()
        # Must be the same usability probe as _fetch_ohlcv_mt5. The plain
        # `is not None` check left fetch_tick calling initialize() on every
        # symbol of every cycle, and initialize() logs an ERROR when the
        # MetaTrader5 package is missing: 237 ERROR lines on a container where
        # MT5 can never be present, which is what a missing dependency looks
        # like, not a failure.
        if _mt5_is_usable(mt5_conn):
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

    return snapshots



def fetch_ohlcv(symbol: str, interval: str, limit: int, end_time: int | None = None) -> list[dict]:
    """Fetch OHLCV candles for a Forex instrument via MT5, Yahoo as fallback.

    A non-Forex symbol is refused rather than routed elsewhere. There is no
    second data source any more: crypto is gone, and silently returning an
    empty list would let the engine read that as "no signal" instead of
    "misconfigured instrument".
    """
    if not _is_forex_symbol(symbol):
        raise ValueError(
            f"{symbol} is not a Forex instrument. Supported: {", ".join(FOREX_SYMBOLS)}."
        )
    return _fetch_ohlcv_mt5(symbol, interval, limit, end_time)


def _log_fallback_once(reason: str, symbol: str, interval: str, template: str) -> None:
    """Log a data-source fallback once per (reason, symbol, timeframe).

    The fallback itself is reported per call, not per call per symbol: on a
    container the source never changes, so repeating the line every cycle only
    hides the lines that matter.
    """
    key = (reason, symbol, interval)
    if key in _LOGGED_FALLBACKS:
        return
    _LOGGED_FALLBACKS.add(key)
    logger.info(template, symbol, interval)


def _mt5_is_usable(mt5_conn) -> bool:
    """True when the connector exists AND the terminal is actually connected.

    ``_get_mt5_connector()`` returns a live object even when the MetaTrader5
    package is missing, so a plain ``is not None`` check never detected the
    Fly.io / Docker case. ``is_connected()`` is the real signal.
    """
    if mt5_conn is None:
        return False
    probe = getattr(mt5_conn, "is_connected", None)
    if probe is None:
        # No probe available: optimistically try, and let the empty-result
        # check below route us to the fallback if it yields nothing.
        return True
    try:
        return bool(probe())
    except Exception:
        logger.debug("MT5 is_connected() probe failed", exc_info=True)
        return True


def _fetch_ohlcv_mt5(symbol: str, interval: str, limit: int, end_time: int | None = None) -> list[dict]:
    """Fetch OHLCV candles for a Forex symbol.

    Source order: MetaTrader5, then Yahoo Finance.

    An empty MT5 result is treated as a FAILURE, not as "no data". The
    connector swallows its own connection error and returns ``[]``, so the
    previous ``if not candles: return []`` short-circuited above both
    fallbacks and left the Forex feed permanently empty on any host without
    MetaTrader5 — which is every container deployment.
    """
    mt5_conn = _get_mt5_connector()
    if not _mt5_is_usable(mt5_conn):
        # Logged once per symbol and timeframe, not once per call. At 3 symbols
        # x 4 timeframes on a 5-minute analysis cycle this was 12 lines every
        # cycle, which was 985 of the 1 246 lines in a 20-minute local run.
        _log_fallback_once("mt5_unusable", symbol, interval,
                           "MT5 unavailable, using Yahoo Finance fallback for %s %s")
        return _fetch_ohlcv_yahoo(symbol, interval, limit)

    try:
        end_date = datetime.fromtimestamp(end_time / 1000, tz=timezone.utc) if end_time is not None else None
        candles = mt5_conn.fetch_ohlcv(symbol, interval, limit, None, end_date)

        if not candles:
            _log_fallback_once("mt5_empty", symbol, interval,
                               "MT5 returned no candles for %s %s, using Yahoo Finance fallback")
            return _fetch_ohlcv_yahoo(symbol, interval, limit)

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
        logger.warning("MT5 fetch_ohlcv failed for %s %s: %s — using Yahoo Finance fallback", symbol, interval, e)
        return _fetch_ohlcv_yahoo(symbol, interval, limit)





# --- Helpers ---

def _interval_to_timeframe(interval: str) -> str:
    """Map a candle interval onto an MT5 timeframe name."""
    mapping = {
    # Standard interval names, which is what MT5 expects
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


