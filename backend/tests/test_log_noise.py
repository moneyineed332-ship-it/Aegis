"""A missing optional dependency is a configuration, not a failure.

Measured on a 20-minute local container-style run:
    total log lines                    1 246
    "MetaTrader5 not available"  ERROR   237
    "MT5 unavailable, using Yahoo"     985
    => 98% of the volume was one expected condition

MetaTrader5 is a Windows-only package, so on Fly/Docker it is never present and
never will be. Logging that at ERROR on every call buried real errors and would
trip any alerting keyed on error counts.
"""

import inspect
import logging

import pytest

from app import market_data, mt5_connector


class TestMissingPackageIsNotAnError:
    def test_import_time_message_is_info_and_once(self):
        src = inspect.getsource(mt5_connector)
        assert "logger.error" in src  # there are genuine errors in this module
        assert "MetaTrader5 not available. Install with" not in src, (
            "the missing-package message still exists and will repeat"
        )

    def test_initialize_does_not_log_the_absent_package(self):
        body = inspect.getsource(mt5_connector.MT5Connector.initialize)
        assert "MT5_AVAILABLE" in body
        assert "logger.error" not in body.split("if not MT5_AVAILABLE")[1].split("return False")[0], (
            "the absent-package branch still logs an error"
        )


class TestSpotPricesUseTheSameProbe:
    """The OHLCV path was fixed; the tick path was left on is-not-None."""

    def test_fetch_spot_prices_probes_usability(self):
        src = inspect.getsource(market_data.fetch_spot_prices)
        assert "_mt5_is_usable(" in src, "fetch_spot_prices still uses a bare is-not-None check"
        assert "if mt5_conn is not None:" not in src

    def test_no_bare_is_not_none_gate_on_the_mt5_path(self):
        src = inspect.getsource(market_data)
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("if mt5_conn is not None"):
                pytest.fail(f"bare MT5 gate still present: {stripped}")


class TestFallbackIsLoggedOnce:
    def test_helper_dedupes_on_reason_symbol_interval(self, caplog):
        market_data._LOGGED_FALLBACKS.clear()
        with caplog.at_level(logging.INFO, logger="app.market_data"):
            for _ in range(50):
                market_data._log_fallback_once(
                    "mt5_unusable", "EURUSD", "1h",
                    "MT5 unavailable, using Yahoo Finance fallback for %s %s",
                )
        assert sum("MT5 unavailable" in r.message for r in caplog.records) == 1

    def test_distinct_pairs_are_each_logged(self, caplog):
        market_data._LOGGED_FALLBACKS.clear()
        with caplog.at_level(logging.INFO, logger="app.market_data"):
            for interval in ("1h", "15m", "4h", "5m"):
                market_data._log_fallback_once(
                    "mt5_unusable", "EURUSD", interval,
                    "MT5 unavailable, using Yahoo Finance fallback for %s %s",
                )
        assert sum("MT5 unavailable" in r.message for r in caplog.records) == 4

    def test_reason_is_part_of_the_key(self, caplog):
        market_data._LOGGED_FALLBACKS.clear()
        with caplog.at_level(logging.INFO, logger="app.market_data"):
            market_data._log_fallback_once("mt5_unusable", "EURUSD", "1h", "a %s %s")
            market_data._log_fallback_once("mt5_empty", "EURUSD", "1h", "b %s %s")
        assert len(caplog.records) == 2

    def test_ohlcv_path_uses_the_helper(self):
        src = inspect.getsource(market_data._fetch_ohlcv_mt5)
        assert "_log_fallback_once(" in src
        assert 'logger.info("MT5 unavailable' not in src
        assert 'logger.info("MT5 returned no candles' not in src


class TestRealFallbacksAreNotSilent:
    """Deduplication must not hide a source that changes or breaks."""

    def test_a_new_symbol_is_still_reported(self, caplog):
        market_data._LOGGED_FALLBACKS.clear()
        with caplog.at_level(logging.INFO, logger="app.market_data"):
            market_data._log_fallback_once("mt5_unusable", "EURUSD", "1h", "%s %s")
            market_data._log_fallback_once("mt5_unusable", "XAUUSD", "1h", "%s %s")
        assert {r.args for r in caplog.records} == {("EURUSD", "1h"), ("XAUUSD", "1h")}

    def test_data_source_is_reported_on_the_candles(self, monkeypatch):
        """The fallback must still be visible in the data, not only in logs."""
        monkeypatch.setattr(market_data, "_get_mt5_connector", lambda: None)
        monkeypatch.setattr(
            market_data, "_fetch_ohlcv_yahoo",
            lambda *a, **k: [{"symbol": "EURUSD", "interval": "1h", "close": 1.08,
                              "source": "yahoo_finance", "open_time": 0, "close_time": 1,
                              "open": 1.0, "high": 1.1, "low": 0.9, "volume": 0.0}],
        )
        candles = market_data._fetch_ohlcv_mt5("EURUSD", "1h", 10)
        assert candles and candles[0]["source"] == "yahoo_finance"
