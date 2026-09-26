"""API integration tests for all AEGIS endpoints."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app import storage

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# === Health ===

def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data


# === Dashboard ===

def test_dashboard():
    r = client.get("/api/v1/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "paper"
    assert "capital" in data
    assert "positions" in data
    assert "recent_backtests" in data
    assert "data_quality" in data
    assert "strategy_registry" in data
    assert "fear_greed" in data
    assert "funding_rates" in data
    assert "open_interest" in data
    assert "memory" in data
    assert "journal" in data
    assert "stress_test" in data
    assert "correlation" in data
    assert "concentration" in data


# === Paper Orders ===

def test_create_paper_order(client, admin_headers):
    r = client.post("/api/v1/paper-orders", json={
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 0.0001,
        "reference_price": 50000,
    }, headers=admin_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "filled_simulated"


def test_paper_order_exceeds_limit(client, admin_headers):
    r = client.post("/api/v1/paper-orders", json={
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 10,
        "reference_price": 50000,
    }, headers=admin_headers)
    assert r.status_code == 422


def test_paper_order_requires_auth(client):
    r = client.post("/api/v1/paper-orders", json={
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 0.0001,
        "reference_price": 50000,
    })
    assert r.status_code == 401


def test_protected_posts_require_auth(client):
    """Writes and heavy compute endpoints must reject anonymous callers."""
    for path in (
        "/api/v1/backtests/sma-crossover/walk-forward",
        "/api/v1/optimizer/sma",
        "/api/v1/decisions/recommendation",
        "/api/v1/memory/remember",
        "/api/v1/ohlcv/refresh",
        "/api/v1/alerts/check",
        "/api/v1/market-snapshots/refresh",
        "/api/v1/ai/analyze-market",
        "/api/v1/deployment/validate-backtest",
        "/api/v1/supervisor/emergency-stop",
    ):
        r = client.post(path)
        assert r.status_code == 401, path
    r = client.get("/api/v1/free/all")
    assert r.status_code == 401


# === Admin token verification (used by the dashboard login screen) ===

def test_auth_verify_requires_token(client):
    assert client.get("/api/v1/auth/verify").status_code == 401


def test_auth_verify_accepts_valid_token(client, admin_headers):
    r = client.get("/api/v1/auth/verify", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["authenticated"] is True


def test_non_ascii_token_returns_401_not_500():
    """compare_digest() raises on non-ASCII str input, which surfaced as a 500."""
    from fastapi import HTTPException
    from app.deps import require_admin_token

    for bad in ("tökén-échec", "токен", "1234"):
        with pytest.raises(HTTPException) as exc:
            require_admin_token(bad)
        assert exc.value.status_code == 401
        assert "required" in exc.value.detail


# === Market Snapshots ===

def test_market_snapshots():
    r = client.get("/api/v1/market-snapshots")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_refresh_market_snapshots(admin_headers):
    r = client.post("/api/v1/market-snapshots/refresh", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


# === OHLCV ===

def test_ohlcv():
    r = client.get("/api/v1/ohlcv")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_refresh_ohlcv(admin_headers):
    r = client.post("/api/v1/ohlcv/refresh", params={"symbol": "BTCUSDT", "interval": "1h", "limit": 100}, headers=admin_headers)
    assert r.status_code == 201
    data = r.json()
    assert "stored" in data


# === Data Quality ===

def test_data_quality():
    r = client.get("/api/v1/data-quality/ohlcv")
    assert r.status_code == 200
    data = r.json()
    assert "valid" in data
    assert "candle_count" in data


# === Risk ===

def test_risk_summary():
    r = client.get("/api/v1/risk/summary")
    assert r.status_code in (200, 422)


def test_risk_stress_test():
    r = client.get("/api/v1/risk/stress-test")
    assert r.status_code in (200, 404, 422)


def test_risk_correlation():
    r = client.get("/api/v1/risk/correlation")
    assert r.status_code in (200, 404, 422)


def test_risk_concentration():
    r = client.get("/api/v1/risk/concentration")
    assert r.status_code == 200
    data = r.json()
    assert "total_exposure" in data


# === Market Analysis ===

def test_market_analysis():
    r = client.get("/api/v1/market-analysis")
    assert r.status_code in (200, 422)


# === Decisions ===

def test_recommendation(admin_headers):
    r = client.post("/api/v1/decisions/recommendation", headers=admin_headers)
    assert r.status_code in (201, 422)


def test_decisions_list():
    r = client.get("/api/v1/decisions")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# === Strategies ===

def test_strategies():
    r = client.get("/api/v1/strategies")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 4


# === Coach ===

def test_coach_review():
    r = client.get("/api/v1/coach/review")
    assert r.status_code == 200
    data = r.json()
    assert "reviewed_backtests" in data
    assert "improvement_proposals" in data


# === Lab ===

def test_lab_promotions():
    r = client.get("/api/v1/lab/promotions")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# === Supervisor ===

def test_supervisor_status():
    r = client.get("/api/v1/supervisor")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "kill_switch_active" in data


# === Fear & Greed ===

def test_fear_greed():
    r = client.get("/api/v1/fear-greed")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_refresh_fear_greed(admin_headers):
    r = client.post("/api/v1/fear-greed/refresh", headers=admin_headers)
    assert r.status_code in (200, 201, 502)


# === Funding Rates ===

def test_funding_rates():
    r = client.get("/api/v1/funding-rates")
    assert r.status_code == 200


def test_refresh_funding_rates(admin_headers):
    r = client.post("/api/v1/funding-rates/refresh", headers=admin_headers)
    assert r.status_code in (200, 201, 502)


# === Open Interest ===

def test_open_interest():
    r = client.get("/api/v1/open-interest")
    assert r.status_code == 200


def test_refresh_open_interest(admin_headers):
    r = client.post("/api/v1/open-interest/refresh", headers=admin_headers)
    assert r.status_code in (200, 201, 502)


# === Memory ===

def test_memory_list():
    r = client.get("/api/v1/memory")
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "episodes" in data


def test_memory_remember(admin_headers):
    r = client.post("/api/v1/memory/remember", headers=admin_headers)
    assert r.status_code in (201, 422)


def test_memory_compare():
    r = client.get("/api/v1/memory/compare")
    assert r.status_code in (200, 422)


# === Journal ===

def test_journal_analysis():
    r = client.get("/api/v1/journal/analysis")
    assert r.status_code == 200
    data = r.json()
    assert "total_decisions" in data
    assert "feedback" in data


def test_journal_outcomes():
    r = client.get("/api/v1/journal/outcomes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# === Backtests SMA ===

def test_sma_backtest(admin_headers):
    r = client.post("/api/v1/backtests/sma-crossover", headers=admin_headers, json={
        "symbol": "BTCUSDT",
        "interval": "1h",
        "fast_period": 10,
        "slow_period": 30,
    })
    assert r.status_code in (200, 201, 400, 422)


def test_sma_walk_forward(admin_headers):
    r = client.post("/api/v1/backtests/sma-crossover/walk-forward", headers=admin_headers)
    assert r.status_code in (200, 201, 400, 404, 422)


# === Backtests Donchian ===

def test_donchian_walk_forward(admin_headers):
    r = client.post("/api/v1/backtests/donchian-breakout/walk-forward", headers=admin_headers)
    assert r.status_code in (200, 201, 400, 404, 422)


# === Backtests Mean Reversion ===

def test_mean_reversion_backtest(admin_headers):
    r = client.post("/api/v1/backtests/mean-reversion", headers=admin_headers, json={
        "symbol": "BTCUSDT",
        "interval": "1h",
    })
    assert r.status_code in (200, 201, 400, 422)


def test_mean_reversion_walk_forward(admin_headers):
    r = client.post("/api/v1/backtests/mean-reversion/walk-forward", headers=admin_headers)
    assert r.status_code in (200, 201, 400, 404, 422)


# === Backtests Grid ===

def test_grid_backtest(admin_headers):
    r = client.post("/api/v1/backtests/grid", headers=admin_headers, json={
        "symbol": "BTCUSDT",
        "interval": "1h",
    })
    assert r.status_code in (200, 201, 400, 422)


def test_grid_walk_forward(admin_headers):
    r = client.post("/api/v1/backtests/grid/walk-forward", headers=admin_headers)
    assert r.status_code in (200, 201, 400, 404, 422)


# === Backtests SMC/ICT ===

def test_smc_ict_backtest(admin_headers):
    r = client.post("/api/v1/backtests/smc-ict", headers=admin_headers, json={
        "symbol": "BTCUSDT",
        "interval": "1h",
    })
    assert r.status_code in (200, 201, 400, 422)


def test_multi_timeframe_backtest(admin_headers):
    r = client.post("/api/v1/backtests/multi-timeframe", headers=admin_headers, json={
        "symbol": "BTCUSDT",
        "interval": "1h",
    })
    assert r.status_code in (200, 201, 400, 422)


def test_multi_scale_crossover_backtest(admin_headers):
    r = client.post("/api/v1/backtests/multi-scale-crossover", headers=admin_headers, json={
        "symbol": "BTCUSDT",
        "interval": "1h",
    })
    assert r.status_code in (200, 201, 400, 422)


# === Execution ===

def test_market_order(admin_headers):
    client.post("/api/v1/market-snapshots/refresh", headers=admin_headers)
    r = client.post("/api/v1/execution/market-order", params={
        "symbol": "BTCUSDT",
        "side": "buy",
        "quantity": 0.001,
    })
    assert r.status_code in (201, 401, 422, 423)


def test_limit_order():
    r = client.post("/api/v1/execution/limit-order", params={
        "symbol": "BTCUSDT",
        "side": "buy",
        "quantity": 0.0001,
        "limit_price": 50000,
    })
    assert r.status_code in (201, 401)


def test_fractioned_order():
    r = client.post("/api/v1/execution/fractioned-order", params={
        "symbol": "BTCUSDT",
        "side": "buy",
        "quantity": 0.0002,
        "chunks": 3,
    })
    assert r.status_code in (201, 401, 422, 423)


def test_estimate_slippage():
    r = client.post("/api/v1/execution/estimate-slippage", params={"order_value": 100})
    assert r.status_code == 200
    data = r.json()
    assert "estimated_slippage_bps" in data


# === Phase 3: Optimization ===

def test_optimize_sma(admin_headers):
    r = client.post("/api/v1/optimizer/sma", headers=admin_headers)
    assert r.status_code in (200, 422)


def test_optimize_donchian(admin_headers):
    r = client.post("/api/v1/optimizer/donchian", headers=admin_headers)
    assert r.status_code in (200, 422)


def test_optimize_mean_reversion(admin_headers):
    r = client.post("/api/v1/optimizer/mean-reversion", headers=admin_headers)
    assert r.status_code in (200, 422)


def test_optimize_grid(admin_headers):
    r = client.post("/api/v1/optimizer/grid", headers=admin_headers)
    assert r.status_code in (200, 422)


def test_compare_strategies(admin_headers):
    r = client.post("/api/v1/optimizer/compare", headers=admin_headers)
    assert r.status_code in (200, 422)


# === Phase 4: WebSocket Alerts ===

def test_alert_history():
    r = client.get("/api/v1/alerts/history")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_alert_thresholds():
    r = client.get("/api/v1/alerts/thresholds")
    assert r.status_code == 200
    data = r.json()
    assert "max_drawdown_pct" in data


def test_check_alerts(admin_headers):
    r = client.post("/api/v1/alerts/check", headers=admin_headers)
    assert r.status_code == 200


# === Phase 4: Advanced Backtesting ===

def test_advanced_walk_forward(admin_headers):
    r = client.post("/api/v1/backtests/advanced/walk-forward", headers=admin_headers)
    assert r.status_code in (200, 201, 422)


def test_monte_carlo(admin_headers):
    r = client.post("/api/v1/backtests/advanced/monte-carlo", headers=admin_headers)
    assert r.status_code in (200, 201, 422)


def test_sensitivity(admin_headers):
    r = client.post("/api/v1/backtests/advanced/sensitivity", headers=admin_headers)
    assert r.status_code in (200, 201, 422)


# === Phase 4: ML Regime ===

def test_ml_regime_summary():
    r = client.get("/api/v1/ml/regime/summary")
    assert r.status_code == 200
    data = r.json()
    assert "trained" in data


def test_ml_regime_predict():
    r = client.get("/api/v1/ml/regime/predict")
    assert r.status_code in (200, 422)


# === Phase 4: Binance Testnet ===

def test_binance_testnet_health():
    r = client.get("/api/v1/binance/testnet/health")
    assert r.status_code == 200


def test_binance_testnet_status():
    r = client.get("/api/v1/binance/testnet/status")
    assert r.status_code == 200


def test_binance_testnet_price():
    r = client.get("/api/v1/binance/testnet/price?symbol=BTCUSDT")
    assert r.status_code == 200


# === Phase 4: Multi-Asset ===

def test_asset_classes():
    r = client.get("/api/v1/assets/classes")
    assert r.status_code == 200
    data = r.json()
    assert "crypto" in data


def test_supported_symbols():
    r = client.get("/api/v1/assets/symbols")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_forex_rates():
    r = client.get("/api/v1/assets/forex")
    assert r.status_code in (200, 422)


def test_commodity_prices():
    r = client.get("/api/v1/assets/commodities")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# === Deployment ===

def test_create_pipeline():
    r = client.post("/api/v1/deployment/pipeline")
    assert r.status_code in (201, 401)
    if r.status_code == 201:
        data = r.json()
        assert data["current_stage"] == "idea"


def test_validate_backtest(admin_headers):
    r = client.post("/api/v1/deployment/validate-backtest", headers=admin_headers)
    assert r.status_code in (200, 422)


# === New Endpoint Tests ===

def test_close_position_not_found(client, admin_headers):
    r = client.post("/api/v1/positions/close", json={"symbol": "FAKE/USDT"}, headers=admin_headers)
    assert r.status_code == 404


def test_close_position_has_position(client, admin_headers):
    r_order = client.post("/api/v1/paper-orders", json={"symbol": "BTC/USDT", "side": "buy", "quantity": 0.0002, "reference_price": 60000}, headers=admin_headers)
    assert r_order.status_code == 201
    storage.save_market_snapshots([{"symbol": "BTC/USDT", "price": 65000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    r = client.post("/api/v1/positions/close", json={"symbol": "BTC/USDT"}, headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "closed" in data
    assert "order" in data


def test_manual_order_market(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTC/USDT", "price": 65000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    r = client.post("/api/v1/orders/manual", json={"symbol": "BTC/USDT", "side": "buy", "order_type": "market", "quantity": 0.001}, headers=admin_headers)
    assert r.status_code == 201
    data = r.json()
    assert "status" in data


def test_manual_order_limit(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTC/USDT", "price": 65000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    r = client.post("/api/v1/orders/manual", json={"symbol": "BTC/USDT", "side": "buy", "order_type": "limit", "quantity": 0.0002, "limit_price": 50000}, headers=admin_headers)
    assert r.status_code == 201


def test_manual_order_limit_missing_price(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTC/USDT", "price": 65000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    r = client.post("/api/v1/orders/manual", json={"symbol": "BTC/USDT", "side": "buy", "order_type": "limit", "quantity": 0.001}, headers=admin_headers)
    assert r.status_code == 422


def test_supervisor_health(client):
    r = client.get("/api/v1/supervisor")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "health_checks" in data
    assert "portfolio" in data


def test_list_open_orders_empty(client):
    r = client.get("/api/v1/orders/open")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 0
    assert data["orders"] == []


def test_limit_order_fills_immediately(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTC/USDT", "price": 50000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    r = client.post("/api/v1/orders/manual", json={"symbol": "BTC/USDT", "side": "buy", "order_type": "limit", "quantity": 0.0002, "limit_price": 60000}, headers=admin_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "filled"
    assert data["order_type"] == "limit"
    assert data["fill_price"] == 60000


def test_limit_order_pending_when_unfavorable(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTC/USDT", "price": 65000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    r = client.post("/api/v1/orders/manual", json={"symbol": "BTC/USDT", "side": "buy", "order_type": "limit", "quantity": 0.0002, "limit_price": 50000}, headers=admin_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending"
    assert data["order_type"] == "limit"


def test_cancel_open_order(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTC/USDT", "price": 65000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    r = client.post("/api/v1/orders/manual", json={"symbol": "BTC/USDT", "side": "buy", "order_type": "limit", "quantity": 0.0002, "limit_price": 50000}, headers=admin_headers)
    order_id = r.json()["order_id"]
    r2 = client.post(f"/api/v1/orders/cancel/{order_id}", headers=admin_headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "cancelled"
    r3 = client.get("/api/v1/orders/open")
    assert r3.json()["count"] == 0


# === Kill switch must block EVERY order entry point ===
#
# /api/v1/execution/limit-order used to call the raw simulator directly, so it
# honoured no kill switch, no notional limit, no exposure limit, and persisted
# neither the fill nor the pending order.

ORDER_ENTRY_POINTS = [
    ("/api/v1/execution/limit-order", {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.0002, "limit_price": 50000}),
    ("/api/v1/execution/market-order", {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.0002}),
    ("/api/v1/execution/fractioned-order", {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.0002, "chunks": 2}),
    ("/api/v1/paper-orders", {"symbol": "BTC/USDT", "side": "buy", "quantity": 0.0002, "reference_price": 50000}),
    ("/api/v1/orders/manual", {"symbol": "BTC/USDT", "side": "buy", "order_type": "market", "quantity": 0.0002}),
    ("/api/v1/orders/manual", {"symbol": "BTC/USDT", "side": "buy", "order_type": "limit", "quantity": 0.0002, "limit_price": 50000}),
]


def test_kill_switch_blocks_every_order_endpoint(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTC/USDT", "price": 50000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    storage.save_market_snapshots([{"symbol": "BTCUSDT", "price": 50000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    storage.set_kill_switch(True, "regression test")
    try:
        for path, payload in ORDER_ENTRY_POINTS:
            r = client.post(path, params=payload, json=payload, headers=admin_headers)
            assert r.status_code == 423, f"{path} accepted an order while the kill switch was active"
    finally:
        storage.set_kill_switch(False, "regression cleanup")


def test_kill_switch_blocks_limit_order_specifically(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTCUSDT", "price": 50000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    storage.set_kill_switch(True, "regression test")
    try:
        r = client.post(
            "/api/v1/execution/limit-order",
            params={"symbol": "BTCUSDT", "side": "buy", "quantity": 0.0002, "limit_price": 40000},
            headers=admin_headers,
        )
        assert r.status_code == 423
    finally:
        storage.set_kill_switch(False, "regression cleanup")


def test_kill_switch_does_not_persist_a_pending_order(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTCUSDT", "price": 65000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    storage.set_kill_switch(True, "regression test")
    try:
        client.post(
            "/api/v1/execution/limit-order",
            params={"symbol": "BTCUSDT", "side": "buy", "quantity": 0.0002, "limit_price": 50000},
            headers=admin_headers,
        )
        assert client.get("/api/v1/orders/open").json()["count"] == 0
    finally:
        storage.set_kill_switch(False, "regression cleanup")


# === Oversized orders are rejected BEFORE any fill is simulated or booked ===

def test_limit_order_respects_max_notional(client, admin_headers):
    """Before the fix this endpoint had no notional check at all."""
    storage.save_market_snapshots([{"symbol": "BTCUSDT", "price": 50000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    before = len(storage.list_positions())
    r = client.post(
        "/api/v1/execution/limit-order",
        params={"symbol": "BTCUSDT", "side": "buy", "quantity": 10, "limit_price": 40000},
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert len(storage.list_positions()) == before, "a rejected order still moved the book"


def test_market_order_rejects_before_simulating(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTCUSDT", "price": 50000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    before = len(storage.list_positions())
    r = client.post(
        "/api/v1/execution/market-order",
        params={"symbol": "BTCUSDT", "side": "buy", "quantity": 10},
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert len(storage.list_positions()) == before


def test_fractioned_order_rejects_before_chunking(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTCUSDT", "price": 50000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    before = len(storage.list_positions())
    r = client.post(
        "/api/v1/execution/fractioned-order",
        params={"symbol": "BTCUSDT", "side": "buy", "quantity": 5, "chunks": 3},
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert len(storage.list_positions()) == before


def test_limit_order_now_persists_a_fill(client, admin_headers):
    """The endpoint used to return a fill without recording anything."""
    storage.save_market_snapshots([{"symbol": "BTCUSDT", "price": 50000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    r = client.post(
        "/api/v1/execution/limit-order",
        params={"symbol": "BTCUSDT", "side": "buy", "quantity": 0.0002, "limit_price": 60000},
        headers=admin_headers,
    )
    assert r.status_code == 201
    assert r.json()["status"] == "filled"
    positions = storage.list_positions()
    btc = next((p for p in positions if p["symbol"] == "BTCUSDT"), None)
    assert btc is not None, "a filled limit order left no position"
    assert btc["average_price"] == 60000


def test_limit_order_persists_a_pending_order(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTCUSDT", "price": 65000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    r = client.post(
        "/api/v1/execution/limit-order",
        params={"symbol": "BTCUSDT", "side": "buy", "quantity": 0.0002, "limit_price": 50000},
        headers=admin_headers,
    )
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert client.get("/api/v1/orders/open").json()["count"] >= 1


def test_limit_order_rejects_non_positive_quantity(client, admin_headers):
    storage.save_market_snapshots([{"symbol": "BTCUSDT", "price": 50000, "source": "test", "collected_at": "2026-01-15T10:00:00Z"}])
    r = client.post(
        "/api/v1/execution/limit-order",
        params={"symbol": "BTCUSDT", "side": "buy", "quantity": 0, "limit_price": 50000},
        headers=admin_headers,
    )
    assert r.status_code == 422


if False:  # Manual __main__ runner disabled — use pytest instead
    tests = [
        test_health, test_dashboard,
        test_create_paper_order, test_paper_order_exceeds_limit,
        test_market_snapshots, test_refresh_market_snapshots,
        test_ohlcv, test_refresh_ohlcv,
        test_data_quality,
        test_risk_summary, test_risk_stress_test, test_risk_correlation, test_risk_concentration,
        test_market_analysis,
        test_recommendation, test_decisions_list,
        test_strategies,
        test_coach_review, test_lab_promotions,
        test_supervisor_status,
        test_fear_greed, test_refresh_fear_greed,
        test_funding_rates, test_refresh_funding_rates,
        test_open_interest, test_refresh_open_interest,
        test_memory_list, test_memory_remember, test_memory_compare,
        test_journal_analysis, test_journal_outcomes,
        test_sma_backtest, test_sma_walk_forward,
        test_donchian_walk_forward,
        test_mean_reversion_backtest, test_mean_reversion_walk_forward,
        test_grid_backtest, test_grid_walk_forward,
        test_smc_ict_backtest, test_multi_timeframe_backtest, test_multi_scale_crossover_backtest,
        test_market_order, test_limit_order, test_fractioned_order, test_estimate_slippage,
        test_optimize_sma, test_optimize_donchian, test_optimize_mean_reversion, test_optimize_grid, test_compare_strategies,
        test_alert_history, test_alert_thresholds, test_check_alerts,
        test_advanced_walk_forward, test_monte_carlo, test_sensitivity,
        test_ml_regime_summary, test_ml_regime_predict,
        test_binance_testnet_health, test_binance_testnet_status, test_binance_testnet_price,
        test_asset_classes, test_supported_symbols, test_forex_rates, test_commodity_prices,
        test_create_pipeline, test_validate_backtest,
        test_close_position_not_found, test_close_position_has_position,
        test_manual_order_market, test_manual_order_limit, test_manual_order_limit_missing_price,
        test_supervisor_health,
        test_list_open_orders_empty, test_limit_order_fills_immediately,
        test_limit_order_pending_when_unfavorable, test_cancel_open_order,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test.__name__} — {e}")
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
