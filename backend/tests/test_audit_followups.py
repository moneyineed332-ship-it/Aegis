"""Two defects found by the local audit, both blocking rather than cosmetic.

1. XAU/USD could never open a position. The XAU/USD limit block subtracts one
   trade from the config, but the config already gives gold 1 trade per session
   against the pairs' 2, so the result was 0. The gate is
   `_trades_today >= max_trades_per_session` and 0 >= 0 is always true, so gold
   was refused every time while still being listed in active_instruments. Its
   "no signal" events were structural, not market conditions.

2. The dev server could not be opened from the URL Vite prints. CORS listed
   only http://localhost:5173, so http://127.0.0.1:5173 got a bare 400 and the
   symptom was indistinguishable from a rejected admin token.
"""

import pytest


class TestXauUsdCanTrade:
    def _limits(self):
        from app.ict_risk_manager import IctRiskManager

        return IctRiskManager(initial_capital=50.0)._limits

    def test_trade_limit_is_never_zero(self):
        limits = self._limits()
        for symbol, limit in limits.items():
            assert limit.max_trades_per_session >= 1, (
                f"{symbol} can never trade: max_trades_per_session={limit.max_trades_per_session}"
            )

    def test_gold_keeps_its_configured_limit(self):
        from app.ict_config import get_instrument_config

        cfg = get_instrument_config("XAUUSD")
        assert self._limits()["XAUUSD"].max_trades_per_session == cfg.max_trades_per_session == 1

    def test_gold_stays_more_conservative_than_the_pairs(self):
        limits = self._limits()
        assert limits["XAUUSD"].max_trades_per_session < limits["EURUSD"].max_trades_per_session

    def test_gold_is_not_blocked_before_any_trade(self):
        from app.ict_risk_manager import IctRiskManager

        rm = IctRiskManager(initial_capital=50.0)
        status = rm.check_all_limits(
            "XAUUSD", 4182.0, 4160.0, 4230.0, direction="buy", current_atr_pips=200
        )
        assert not any("trades/session" in r for r in status.blocking_reasons), (
            "gold is refused with zero trades taken"
        )

    def test_the_reduction_cannot_reach_zero_for_any_config(self, monkeypatch):
        """The guard is the clamp, not the value that happens to work today."""
        from app import ict_config
        from app.ict_risk_manager import IctRiskManager

        original = ict_config.INSTRUMENT_CONFIGS["XAUUSD"].max_trades_per_session
        try:
            ict_config.INSTRUMENT_CONFIGS["XAUUSD"].max_trades_per_session = 1
            assert IctRiskManager(initial_capital=50.0)._limits["XAUUSD"].max_trades_per_session == 1
        finally:
            ict_config.INSTRUMENT_CONFIGS["XAUUSD"].max_trades_per_session = original

    def test_other_gold_limits_are_untouched(self):
        from app.ict_config import get_instrument_config

        cfg = get_instrument_config("XAUUSD")
        limits = self._limits()["XAUUSD"]
        assert limits.max_risk_per_trade_pct == pytest.approx(cfg.risk_per_trade_pct * 0.8)
        assert limits.max_daily_drawdown_pct == pytest.approx(cfg.max_daily_drawdown_pct * 0.8)
        assert limits.max_simultaneous_positions == 1


class TestLoopbackOriginsAllowed:
    def test_both_spellings_of_the_dev_origin(self):
        from app import config

        assert "http://localhost:5173" in config.CORS_ORIGINS
        assert "http://127.0.0.1:5173" in config.CORS_ORIGINS

    def test_preview_ports_covered(self):
        from app import config

        for origin in ("http://localhost:4173", "http://127.0.0.1:4173"):
            assert origin in config.CORS_ORIGINS, f"{origin} missing"

    def test_production_origin_still_allowed(self):
        from app import config

        assert "https://aegis-orpin-xi.vercel.app" in config.CORS_ORIGINS

    def test_no_wildcard(self):
        from app import config

        assert "*" not in config.CORS_ORIGINS, "a wildcard would drop the origin check"

    @pytest.mark.parametrize("origin", [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "https://aegis-orpin-xi.vercel.app",
    ])
    def test_allowed_origins_pass_preflight(self, origin):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.options(
            "/api/v1/dashboard",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-aegis-admin-token",
            },
        )
        assert response.headers.get("access-control-allow-origin") == origin, (
            f"{origin} was refused by CORS"
        )

    def test_unrelated_origin_is_still_refused(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.options(
            "/api/v1/dashboard",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-aegis-admin-token",
            },
        )
        assert response.headers.get("access-control-allow-origin") is None

    def test_admin_token_header_is_still_allowed(self):
        """The dev origin needs the header to reach any protected endpoint."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.options(
            "/api/v1/dashboard",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-aegis-admin-token",
            },
        )
        assert "X-AEGIS-Admin-Token" in response.headers.get("access-control-allow-headers", "")
