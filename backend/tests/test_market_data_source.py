"""Tests for the Forex OHLCV source selection.

On any machine without MetaTrader5 — which includes every Docker and Fly.io
deployment — the Forex candle feed returned an empty list and the Yahoo
fallback was unreachable:

1. ``_get_mt5_connector()`` returns a connector object even when the
   ``MetaTrader5`` package is missing, so the ``mt5_conn is None`` branch that
   picks Yahoo never ran.
2. ``MT5Connector.fetch_ohlcv`` swallows the connection failure and returns
   ``[]`` instead of raising, so the ``except`` fallback never ran either.
3. ``if not candles: return []`` returned early, above both fallbacks.

Net effect in production: zero Forex candles, so ``smc_ict.analyze`` never ran,
``_last_smc_analysis`` stayed empty, ``task_generate_signals`` returned before
``_init_ict_pipeline()``, the ICT risk manager was never created and the whole
ICT trading pipeline was dead. These tests pin the fix.
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import market_data


def _yahoo_candles(symbol="EURUSD", interval="1h", n=60):
    return [
        {
            "symbol": symbol, "interval": interval,
            "open_time": 1_700_000_000_000 + i * 3_600_000,
            "close_time": 1_700_000_000_000 + (i + 1) * 3_600_000 - 1,
            "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105,
            "volume": 1000, "source": "yahoo_finance",
        }
        for i in range(n)
    ]


class _DeadConnector:
    """An MT5 connector that exists but cannot connect — the Fly.io case."""

    def is_connected(self):
        return False

    def fetch_ohlcv(self, *args, **kwargs):
        # Mirrors the real connector: logs and returns an empty list.
        return []


class _SilentConnector:
    """An MT5 connector that looks healthy but yields no data."""

    def is_connected(self):
        return True

    def fetch_ohlcv(self, *args, **kwargs):
        return []


class _RaisingConnector:
    def is_connected(self):
        return True

    def fetch_ohlcv(self, *args, **kwargs):
        raise RuntimeError("terminal not running")


class _WorkingConnector:
    def is_connected(self):
        return True

    def fetch_ohlcv(self, *args, **kwargs):
        return [
            {"time": "2026-01-01T00:00:00Z", "open": 1.1, "high": 1.2,
             "low": 1.0, "close": 1.15, "volume": 500}
        ]


class TestMissingMetaTrader5FallsBackToYahoo:
    """The regression: a dead connector must not return an empty list."""

    def test_dead_connector_uses_yahoo(self):
        with patch.object(market_data, "_get_mt5_connector", return_value=_DeadConnector()), \
             patch.object(market_data, "_fetch_ohlcv_yahoo", return_value=_yahoo_candles()) as yahoo:
            candles = market_data._fetch_ohlcv_mt5("EURUSD", "1h", 60)

        assert len(candles) == 60, "Forex feed returned nothing without MT5"
        assert candles[0]["source"] == "yahoo_finance"
        yahoo.assert_called_once()

    def test_fetch_ohlcv_public_helper_also_falls_back(self):
        with patch.object(market_data, "_get_mt5_connector", return_value=_DeadConnector()), \
             patch.object(market_data, "_fetch_ohlcv_yahoo", return_value=_yahoo_candles()):
            assert len(market_data.fetch_ohlcv("EURUSD", "1h", 60)) == 60

    def test_no_connector_uses_yahoo(self):
        with patch.object(market_data, "_get_mt5_connector", return_value=None), \
             patch.object(market_data, "_fetch_ohlcv_yahoo", return_value=_yahoo_candles()):
            assert len(market_data._fetch_ohlcv_mt5("EURUSD", "1h", 60)) == 60


class TestEmptyOrFailingConnectorFallsBack:
    """An empty result is a failure, not a valid 'no data' answer."""

    def test_connected_but_empty_falls_back(self):
        with patch.object(market_data, "_get_mt5_connector", return_value=_SilentConnector()), \
             patch.object(market_data, "_fetch_ohlcv_yahoo", return_value=_yahoo_candles()) as yahoo:
            candles = market_data._fetch_ohlcv_mt5("EURUSD", "1h", 60)

        assert len(candles) == 60
        yahoo.assert_called_once()

    def test_raising_connector_falls_back(self):
        with patch.object(market_data, "_get_mt5_connector", return_value=_RaisingConnector()), \
             patch.object(market_data, "_fetch_ohlcv_yahoo", return_value=_yahoo_candles()):
            assert len(market_data._fetch_ohlcv_mt5("GBPUSD", "1h", 60)) == 60


class TestWorkingMTSuppressesFallback:
    """When MT5 answers, Yahoo must not be called."""

    def test_mt5_data_is_used(self):
        with patch.object(market_data, "_get_mt5_connector", return_value=_WorkingConnector()), \
             patch.object(market_data, "_fetch_ohlcv_yahoo") as yahoo:
            candles = market_data._fetch_ohlcv_mt5("EURUSD", "1h", 60)

        assert len(candles) == 1
        assert candles[0]["source"] == "mt5_forex"
        assert candles[0]["close"] == 1.15
        yahoo.assert_not_called()


class TestForexNeverFallsBackToCrypto:
    """There is no crypto data path left to fall back to.

    This used to patch market_data._fetch_ohlcv_fallback and assert it was never
    called for a Forex symbol, which caught the live bug where a dead MT5 sent
    EURUSD to Binance and got an empty list. That function no longer exists, so
    there is nothing left to call: fetch_ohlcv refuses any symbol outside
    FOREX_SYMBOLS before it reaches any source at all.

    Asserting the absence rather than mocking it means a future edit that
    reintroduces a second data source has to come back here first.
    """

    def test_the_crypto_fallbacks_are_gone(self):
        assert not hasattr(market_data, "_fetch_ohlcv_fallback")
        assert not hasattr(market_data, "_get_exchange")
        assert not hasattr(market_data, "_to_ccxt_symbol")

    def test_a_crypto_symbol_is_refused_rather_than_routed(self):
        with pytest.raises(ValueError, match="not a Forex instrument"):
            market_data.fetch_ohlcv("BTCUSDT", "1h", 60)

    def test_the_forex_path_still_reaches_yahoo(self):
        with patch.object(market_data, "_get_mt5_connector", return_value=_DeadConnector()), \
             patch.object(market_data, "_fetch_ohlcv_yahoo", return_value=_yahoo_candles()):
            assert market_data.fetch_ohlcv("XAUUSD", "1h", 60)


class TestEveryForexSymbolAndInterval:
    """The prod universe: 3 symbols x 4 intervals must all produce candles."""

    SYMBOLS = ("EURUSD", "GBPUSD", "XAUUSD")
    INTERVALS = ("5m", "15m", "1h", "4h")

    @pytest.mark.parametrize("symbol", SYMBOLS)
    @pytest.mark.parametrize("interval", INTERVALS)
    def test_no_empty_feed(self, symbol, interval):
        with patch.object(market_data, "_get_mt5_connector", return_value=_DeadConnector()), \
             patch.object(market_data, "_fetch_ohlcv_yahoo", return_value=_yahoo_candles(symbol, interval)) as yahoo:
            candles = market_data.fetch_ohlcv(symbol, interval, 60)
        assert candles, f"{symbol} {interval} returned no candles"
        yahoo.assert_called_once()

    def test_unmapped_interval_is_reported_not_silently_empty(self):
        """Yahoo has no mapping for e.g. 2h; that must be visible, not empty."""
        with patch.object(market_data, "_get_mt5_connector", return_value=_DeadConnector()):
            assert market_data._fetch_ohlcv_mt5("EURUSD", "2h", 60) == []


class TestYahooFailureIsNotFatal:
    """If both sources fail, return empty rather than raise into the engine loop."""

    def test_both_sources_failing_returns_empty(self):
        # Patch the real network boundary (_fetch_yahoo_chart), not
        # _fetch_ohlcv_yahoo, so the guard under test is actually exercised.
        with patch.object(market_data, "_get_mt5_connector", return_value=_DeadConnector()), \
             patch.object(market_data, "_fetch_yahoo_chart", side_effect=RuntimeError("network down")):
            assert market_data._fetch_ohlcv_mt5("EURUSD", "1h", 60) == []

    def test_yahoo_error_is_logged_not_raised(self):
        with patch.object(market_data, "_fetch_yahoo_chart", side_effect=RuntimeError("network down")):
            assert market_data._fetch_ohlcv_yahoo("EURUSD", "1h", 60) == []
