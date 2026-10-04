"""Exhaustive inventory of route protection.

Enumerates every registered route and asserts its expected auth state. The point
is not that today's list is correct but that the list has to be updated
deliberately: adding a financial GET now fails this test instead of shipping
unauthenticated, and removing a dependency fails it too.

The boundary being enforced:
  - Account and trading state (positions, orders, risk, PnL, journal, engine,
    learning, ICT dashboard) requires the admin token.
  - Public market data and the liveness probe stay open: an orchestrator health
    check cannot carry a token, and price/candle data is not account state.
"""

import re

import pytest
from fastapi.routing import APIRoute

from app.main import app

# Deliberately not inferred from the app: a hard-coded expectation is what makes
# this a test rather than a mirror of the implementation.
PUBLIC_PATHS = {
    # liveness: the orchestrator probes this without credentials
    "/health",
    "/api/v1/health",
    # market data: prices and candles reveal no account state
    "/api/v1/ohlcv",
    "/api/v1/fear-greed",
    "/api/v1/funding-rates",
    "/api/v1/open-interest",
    "/api/v1/market-snapshots",
    # The crypto surface is gone. /assets/*, /free/*, /binance/testnet/* and
    # /portfolio/correlation were removed with the multi-asset engine, so the
    # public list is short on purpose: Forex candles and the liveness probe.
    # /api/v1/fear-greed, /funding-rates and /open-interest are still listed
    # because routers/market.py still serves them; they go when the remaining
    # crypto fetchers in market_data.py are stripped.
}
# NOTE: /docs, /redoc and /openapi.json are FastAPI built-ins, not APIRoute
# instances, so they stay outside this inventory either way. They used to be
# served without a token, which published the full endpoint map including every
# admin route. They are now absent unless AEGIS_EXPOSE_API_DOCS is set, pinned by
# test_api_docs_are_off_by_default.py. This inventory cannot see them, so that
# file is the only thing standing between them and the public.

# Endpoints that are neither financial nor plain market data, listed explicitly
# so an accidental protection is caught too.
EXPLICIT = {
    "/api/v1/health/detailed": True,
    "/api/v1/metrics": True,
    "/api/v1/ai/status": True,
    "/api/v1/execution/estimate-slippage": True,
    "/api/v1/data-quality/ohlcv": True,
}


def _is_protected(route: APIRoute) -> bool:
    """True when the route requires the admin token, directly or via its router."""
    candidates = list(getattr(route, "dependant", None).dependencies if route.dependant else [])
    for dep in candidates:
        name = getattr(dep.call, "__name__", "")
        if "require_admin_token" in name:
            return True
        # Router-level dependencies are nested one level down.
        for sub in getattr(dep, "dependencies", []) or []:
            if "require_admin_token" in getattr(sub.call, "__name__", ""):
                return True
    return False


def _all_api_routes():
    return [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api")]


def _all_routes():
    """Includes /health, /docs and the other non-/api framework paths."""
    return [r for r in app.routes if isinstance(r, APIRoute)]


def test_public_surface_is_exactly_the_allowlist():
    """The regression this file exists for.

    Anything served without a token must appear in PUBLIC_PATHS. Checking the
    direction that matters (public -> allowlisted) rather than enumerating all
    140 routes keeps the test honest without mirroring the implementation: a new
    endpoint is public by default, so it has to be classified deliberately.
    """
    public = {r.path for r in _all_routes() if not _is_protected(r)}
    unexpected = public - PUBLIC_PATHS
    assert not unexpected, (
        f"newly public API routes (add each to PUBLIC_PATHS only if it exposes "
        f"no account state): {sorted(unexpected)}"
    )
    stale = PUBLIC_PATHS - {r.path for r in _all_routes()}
    assert not stale, f"PUBLIC_PATHS lists routes that no longer exist: {sorted(stale)}"


def test_no_financial_state_is_public():
    """The regression this file exists for: financial GETs served unauthenticated."""
    leaks = sorted(r.path for r in _all_api_routes() if not _is_protected(r) and r.path in EXPLICIT)
    assert not leaks, f"should require the admin token: {leaks}"


def test_public_surface_stays_small():
    """A broad public surface is how the previous exposure happened."""
    public_api = {r.path for r in _all_api_routes() if not _is_protected(r)}
    assert not (public_api - PUBLIC_PATHS)


def test_financial_reads_are_protected():
    """Named explicitly: these are the endpoints that leaked account state."""
    financial = [
        "/api/v1/dashboard",
        "/api/v1/positions/pnl",
        "/api/v1/positions/monitor",
        "/api/v1/positions/risks",
        "/api/v1/orders/open",
        "/api/v1/oms/open",
        "/api/v1/oms/orders",
        "/api/v1/oms/status",
        "/api/v1/oms/mode",
        "/api/v1/risk/summary",
        "/api/v1/risk/var",
        "/api/v1/risk/concentration",
        "/api/v1/supervisor",
        "/api/v1/portfolio/daily-report",
        "/api/v1/engine/status",
        "/api/v1/engine/stats",
        "/api/v1/engine/logs",
        "/api/v1/engine/signals",
        "/api/v1/journal/analysis",
        "/api/v1/journal/outcomes",
        "/api/v1/decisions",
        "/api/v1/strategies",
        "/api/v1/alerts/history",
        "/api/v1/alerts/thresholds",
        "/api/v1/trailing-stops",
        "/api/v1/trailing-stops/check",
        "/api/v1/learning/summary",
        "/api/v1/learning/trades",
        "/api/ict/dashboard/capital",
        "/api/ict/dashboard/positions",
        "/api/ict/dashboard/risk",
        "/api/ict/dashboard/summary",
        "/api/ict/dashboard/journal",
    ]
    for path in financial:
        route = next(r for r in _all_api_routes() if r.path == path)
        assert _is_protected(route), f"{path} is served without authentication"


def test_protected_surface_actually_depends():
    """Guard against a route listed as protected whose dependency was dropped."""
    for path, _ in EXPLICIT.items():
        route = next(r for r in _all_api_routes() if r.path == path)
        assert _is_protected(route), f"{path} is no longer protected"


def test_no_route_accepts_a_token_in_the_query_string():
    """Tokens in URLs leak into proxy logs and browser history."""
    offenders = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        params = {p.name for p in route.dependant.query_params}
        if params & {"token", "admin_token", "api_key", "access_token"}:
            offenders.append(route.path)
    assert not offenders, f"token accepted as a query parameter: {offenders}"


class TestHealthSurface:
    """The liveness probe must stay usable; the detailed one must not be."""

    def test_liveness_is_public(self):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/health").status_code == 200

    def test_detailed_health_requires_a_token(self):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        assert client.get("/api/v1/health/detailed").status_code == 401

    def test_detailed_health_no_longer_leaks_account_shape(self):
        """Even with a token, the payload must not be the reason it was open."""
        from fastapi.testclient import TestClient
        from app import settings

        if not settings.ADMIN_TOKEN:
            pytest.skip("ADMIN_TOKEN not configured")
        client = TestClient(app)
        body = client.get(
            "/api/v1/health/detailed",
            headers={"X-AEGIS-Admin-Token": settings.ADMIN_TOKEN},
        ).json()
        assert "disk" in body["checks"], "should still report disk to an admin"
        # The whole point of the change: the position count is behind auth now.
        assert "positions" in body["checks"]


class TestIctDashboardIsClosed:
    def test_capital_endpoint_requires_a_token(self):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        for path in (
            "/api/ict/dashboard/capital",
            "/api/ict/dashboard/risk",
            "/api/ict/dashboard/positions",
            "/api/ict/dashboard/summary",
            "/api/ict/dashboard/journal",
        ):
            assert client.get(path).status_code == 401, f"{path} is public"

    def test_router_level_dependency_covers_every_endpoint(self):
        routes = [r for r in _all_api_routes() if r.path.startswith("/api/ict/dashboard")]
        assert routes, "ICT dashboard router disappeared"
        unprotected = [r.path for r in routes if not _is_protected(r)]
        assert not unprotected, f"unprotected ICT endpoints: {unprotected}"


class TestRiskRouterIsClosed:
    def test_every_risk_endpoint_requires_a_token(self):
        routes = [
            r for r in _all_api_routes()
            if re.match(r"^/api/v1/(risk/|trailing-stop|consensus)", r.path)
        ]
        assert routes, "risk routes disappeared"
        unprotected = sorted({r.path for r in routes if not _is_protected(r)})
        assert not unprotected, f"unprotected risk endpoints: {unprotected}"
