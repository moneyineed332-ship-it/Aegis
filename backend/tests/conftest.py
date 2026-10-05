"""Shared test fixtures for AEGIS AI backend tests."""

import os
import sys
from datetime import datetime, timezone
import tempfile

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Each test gets a fresh temporary database and admin token."""
    db_path = str(tmp_path / "test_aegis.db")
    monkeypatch.setattr("app.config.DB_PATH", db_path)
    monkeypatch.setattr("app.config.ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setattr("app.settings.ADMIN_TOKEN", "test-admin-token")
    # Reset the storage module's connection so it picks up the new path
    import app.storage as storage
    storage._db_connection = None
    storage._initialized = False
    storage.initialize()
    # Reset module-global trading guards so tests are order-independent
    # (e.g. a halted circuit breaker in one test must not reject orders
    # validated in a later test).
    import app.risk as risk_mod
    risk_mod._circuit_breaker.update({
        "halted": False,
        "reason": None,
        "halted_at": None,
        "daily_pnl": 0.0,
        "consecutive_losses": 0,
        "trade_history": [],
    })
    # regime.classify keeps hysteresis state between calls, so a test that runs
    # a full analysis cycle leaves a confident regime behind that silently
    # overrides the next call's result. Reset it so classify() is
    # order-independent under test, the way a fresh process would be.
    import app.regime as regime_mod
    regime_mod._HYSTERESIS.clear()
    regime_mod._prev_regime = None
    regime_mod._prev_confidence = 0.0

    # Pin the trading-session clock for every test.
    #
    # The risk manager's session gate reads a wall clock unless a `now` is
    # passed, and trading hours are 08:00-22:00 UTC. Three tests that assert
    # can_trade is True therefore only passed inside that window; at 22:50 UTC
    # they failed with "Hors session (prochaine dans 579min)" while nothing was
    # broken. Two of them now pass `now` explicitly, but 29 other calls across
    # the ICT suites do not, and any of them would become flaky the moment an
    # assertion changed to True.
    #
    # Injecting the time here rather than at 29 call sites keeps one place to
    # change, and the real session logic still runs: only the hour is fixed. A
    # test that needs a specific session passes `now` itself, which wins.
    #
    # INSIDE_LONDON is a Thursday at 10:00 UTC, inside london (08:00-17:00) and
    # inside new_york (13:00-22:00 is not yet open, but london alone satisfies
    # DEFAULT_ENABLED_SESSIONS).
    import app.ict_risk_manager as risk_manager_mod

    inside_session = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)

    # Wrap the module-level names the risk manager calls, so a None `now`
    # anywhere inside it becomes the pinned hour.
    _real_allowed = risk_manager_mod.is_trading_allowed
    _real_status = risk_manager_mod.get_session_status

    def _allowed(instrument, now=None):
        return _real_allowed(instrument, now=now if now is not None else inside_session)

    def _status(instrument, now=None):
        return _real_status(instrument, now=now if now is not None else inside_session)

    monkeypatch.setattr(risk_manager_mod, "is_trading_allowed", _allowed)
    monkeypatch.setattr(risk_manager_mod, "get_session_status", _status)

    yield
    # Cleanup: close connection and remove temp DB
    if storage._db_connection:
        storage._db_connection.close()
        storage._db_connection = None
    storage._initialized = False


@pytest.fixture
def client():
    """FastAPI test client with isolated DB."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Headers with valid admin token for protected endpoints."""
    return {"X-AEGIS-Admin-Token": "test-admin-token"}
