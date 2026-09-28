"""The economic-news gate has never been able to block a trade.

There is no calendar source in the codebase. The only producer is
_generate_mock_calendar(), and is_trading_blocked() deliberately skips events
with source == "mock" so approximate dates cannot stop real trading. That design
choice is right and is kept; the consequence is that the §"filtre economique"
check has been reporting a protection it never performs, and nothing anywhere
said so.

These tests pin the honest state and stop it being quietly "fixed" by wiring the
simulated calendar in, which would look like protection while blocking on invented
dates.
"""

import pytest

from app.news_filter import default_news_filter


class TestGateIsNotArmed:
    def test_reports_itself_as_disarmed(self):
        armed, reason = default_news_filter.is_armed()
        assert armed is False
        assert reason, "an unarmed gate must say why"

    def test_no_real_source_is_configured(self):
        armed, reason = default_news_filter.is_armed()
        assert "no economic calendar source" in reason.lower()

    def test_mock_events_would_not_arm_it(self):
        """Wiring the simulated calendar must not be mistaken for a fix."""
        events = default_news_filter._generate_mock_calendar(7)
        assert events, "the mock generator should produce something"
        assert all(e.source == "mock" for e in events), (
            "a non-mock event in the simulated calendar would start blocking on "
            "invented dates"
        )
        real = [e for e in events if e.source != "mock"]
        assert not real

    def test_mock_is_never_blocking(self):
        from app.news_filter import is_news_blocking

        default_news_filter._load_cache()
        # With only simulated events loaded, the gate must let everything through.
        for instrument in ("EURUSD", "GBPUSD", "XAUUSD"):
            assert is_news_blocking(instrument) is False


class TestStatusIsHonest:
    def test_status_separates_armed_from_blocked(self):
        from app.news_filter import get_news_status

        status = get_news_status("EURUSD")
        assert status["news_filter_armed"] is False
        assert status["news_filter_armed_reason"]
        # Not blocked and not protected are different statements.
        assert status["trading_blocked"] is False
        assert status["news_protection_active"] is False

    def test_existing_keys_are_preserved(self):
        from app.news_filter import get_news_status

        status = get_news_status("EURUSD")
        for key in ("instrument", "check_time_utc", "news_filter_enabled",
                    "trading_blocked", "block_reason", "blocking_event",
                    "upcoming_events"):
            assert key in status, f"{key} disappeared from the status payload"


class TestRiskManagerSurfacesTheGap:
    def test_warns_once_not_once_per_signal(self, caplog):
        import logging

        from app.ict_risk_manager import IctRiskManager

        rm = IctRiskManager(initial_capital=50.0)
        with caplog.at_level(logging.WARNING, logger="app.ict_risk_manager"):
            for _ in range(5):
                rm.check_all_limits("EURUSD", 1.1370, 1.1330, 1.1450, direction="buy")
        warnings = [r for r in caplog.records if "news" in r.getMessage().lower()]
        assert len(warnings) == 1, f"the warning repeated {len(warnings)} times"
        assert "NOT armed" in warnings[0].getMessage()

    def test_the_gap_is_visible_even_though_trading_is_allowed(self, caplog):
        import logging

        from app.ict_risk_manager import IctRiskManager

        rm = IctRiskManager(initial_capital=50.0)
        with caplog.at_level(logging.WARNING, logger="app.ict_risk_manager"):
            status = rm.check_all_limits("XAUUSD", 4182.0, 4160.0, 4230.0,
                                         direction="buy", current_atr_pips=200)
        # Fails open on purpose: a permanently empty calendar must not halt the
        # bot for good. The warning is what makes that a decision rather than an
        # accident.
        assert any("news" in r.getMessage().lower() for r in caplog.records)
        assert isinstance(status.can_trade, bool)

    def test_does_not_block_trading(self, caplog):
        """Explicit: the chosen behaviour is visible, not fail-closed."""
        import logging

        from app.ict_risk_manager import IctRiskManager

        rm = IctRiskManager(initial_capital=50.0)
        with caplog.at_level(logging.WARNING, logger="app.ict_risk_manager"):
            status = rm.check_all_limits("EURUSD", 1.1370, 1.1330, 1.1450,
                                         direction="buy", current_atr_pips=30)
        assert not any("news" in r.lower() for r in status.blocking_reasons)
        assert status.can_trade is True


class TestEndpointExists:
    def test_news_status_endpoint_is_registered_and_protected(self):
        from fastapi.routing import APIRoute
        from app.main import app

        route = next(
            (r for r in app.routes
             if isinstance(r, APIRoute) and r.path == "/api/ict/dashboard/news-status"),
            None,
        )
        assert route is not None, "the news-status endpoint is missing"
        assert "GET" in route.methods

    def test_it_requires_the_admin_token(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        assert client.get("/api/ict/dashboard/news-status").status_code == 401
