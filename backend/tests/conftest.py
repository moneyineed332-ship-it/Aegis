"""Shared test fixtures for AEGIS AI backend tests."""

import os
import sys
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
