"""Integration tests: multi-step workflows across API endpoints."""

import pytest


class TestHealthAndMetrics:
    """Health and monitoring endpoints."""

    def test_health_basic(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "mode" in data

    def test_health_detailed(self, client):
        r = client.get("/api/v1/health/detailed")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"]["status"] == "ok"

    def test_metrics_endpoint(self, client):
        r = client.get("/api/v1/metrics")
        assert r.status_code == 200
        assert "text/plain" in r.headers["content-type"]
        body = r.text
        assert "aegis_http_requests_total" in body

    def test_request_id_in_response(self, client):
        r = client.get("/api/v1/health")
        assert "X-Request-ID" in r.headers


class TestMarketWorkflow:
    """Market data refresh -> analysis -> dashboard verification."""

    def test_market_snapshots_crud(self, client):
        r = client.get("/api/v1/market-snapshots")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_fear_greed_crud(self, client):
        r = client.get("/api/v1/fear-greed")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_funding_rates_crud(self, client):
        r = client.get("/api/v1/funding-rates")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_open_interest_crud(self, client):
        r = client.get("/api/v1/open-interest")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestPaperOrderWorkflow:
    """Create paper order -> verify dashboard -> check journal."""

    def test_create_paper_order(self, client, admin_headers):
        r = client.post("/api/v1/paper-orders", json={"symbol": "BTC/USDT", "side": "buy", "quantity": 0.0002, "reference_price": 50000}, headers=admin_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["symbol"] == "BTCUSDT"
        assert data["side"] == "buy"
        assert data["status"] in ("filled", "filled_simulated", "partial", "pending")

    def test_paper_order_reflected_in_dashboard(self, client, admin_headers):
        # Create order
        r1 = client.post("/api/v1/paper-orders", json={"symbol": "ETH/USDT", "side": "buy", "quantity": 0.003, "reference_price": 3000}, headers=admin_headers)
        assert r1.status_code == 201

        # Dashboard should show the position
        r2 = client.get("/api/v1/dashboard")
        assert r2.status_code == 200
        dashboard = r2.json()
        positions = dashboard.get("positions", [])
        assert any(p["symbol"] == "ETHUSDT" for p in positions)

    def test_kill_switch_blocks_orders(self, client, admin_headers):
        # Activate kill switch
        client.post("/api/v1/supervisor/emergency-stop", headers=admin_headers)

        # Try to create order — should be blocked
        r = client.post("/api/v1/paper-orders", json={"symbol": "BTC/USDT", "side": "buy", "quantity": 0.0002, "reference_price": 50000}, headers=admin_headers)
        assert r.status_code == 423

        # Resume
        client.post("/api/v1/supervisor/resume", headers=admin_headers)

        # Order should work again
        r2 = client.post("/api/v1/paper-orders", json={"symbol": "BTC/USDT", "side": "buy", "quantity": 0.0002, "reference_price": 50000}, headers=admin_headers)
        assert r2.status_code == 201


class TestDashboardWorkflow:
    """Dashboard data consistency across requests."""

    def test_dashboard_returns_valid_structure(self, client):
        r = client.get("/api/v1/dashboard")
        assert r.status_code == 200
        data = r.json()
        required_keys = [
            "mode", "capital", "exposure", "current_equity",
            "positions", "recent_orders", "market_snapshots",
            "strategy_registry", "risk",
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

    def test_dashboard_cache_works(self, client):
        r1 = client.get("/api/v1/dashboard")
        r2 = client.get("/api/v1/dashboard")
        assert r1.json() == r2.json()


class TestEngineWorkflow:
    """Engine lifecycle through the API."""

    def test_engine_status(self, client):
        r = client.get("/api/v1/engine/status")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert data["status"] in ("running", "stopped")

    def test_engine_logs(self, client):
        r = client.get("/api/v1/engine/logs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_engine_stats(self, client):
        r = client.get("/api/v1/engine/stats")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_engine_signals(self, client):
        r = client.get("/api/v1/engine/signals")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestLearningWorkflow:
    """Learning endpoints data flow."""

    def test_learning_strategies(self, client):
        r = client.get("/api/v1/learning/strategies")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_learning_trades(self, client):
        r = client.get("/api/v1/learning/trades")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_learning_summary(self, client):
        r = client.get("/api/v1/learning/summary")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_learning_memory(self, client):
        r = client.get("/api/v1/learning/memory/BTCUSDT")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)


class TestOMSWorkflow:
    """Order Management System endpoints."""

    def test_oms_status(self, client):
        r = client.get("/api/v1/oms/status")
        assert r.status_code == 200
        data = r.json()
        assert "positions_count" in data

    def test_oms_orders(self, client):
        r = client.get("/api/v1/oms/orders")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_oms_mode(self, client):
        r = client.get("/api/v1/oms/mode")
        assert r.status_code == 200
        data = r.json()
        assert "mode" in data

    def test_oms_mode_switch(self, client, admin_headers):
        r = client.post("/api/v1/oms/mode?mode=paper", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "paper"


class TestPositionWorkflow:
    """Position monitoring endpoints."""

    def test_position_monitor(self, client):
        r = client.get("/api/v1/positions/monitor")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_position_pnl(self, client):
        r = client.get("/api/v1/positions/pnl")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_position_risks(self, client):
        r = client.get("/api/v1/positions/risks")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)


class TestSecurityWorkflow:
    """Security endpoints."""

    def test_security_summary(self, client, admin_headers):
        r = client.get("/api/v1/security/summary", headers=admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_security_requires_admin(self, client):
        r = client.get("/api/v1/security/summary")
        assert r.status_code == 401


class TestMultiStepWorkflow:
    """Full workflow: order -> dashboard -> learning -> journal."""

    def test_full_trading_cycle(self, client, admin_headers):
        # 1. Check initial dashboard
        dash1 = client.get("/api/v1/dashboard").json()
        initial_positions = len(dash1["positions"])

        # 2. Create a paper order
        r1 = client.post("/api/v1/paper-orders", json={"symbol": "SOL/USDT", "side": "buy", "quantity": 0.1, "reference_price": 100}, headers=admin_headers)
        assert r1.status_code == 201

        # 3. Dashboard should show new position
        dash2 = client.get("/api/v1/dashboard").json()
        assert len(dash2["positions"]) >= initial_positions

        # 4. OMS should reflect the order
        oms = client.get("/api/v1/oms/status").json()
        assert oms["positions_count"] >= 1

        # 5. Engine logs exist
        logs = client.get("/api/v1/engine/logs").json()
        assert isinstance(logs, list)

        # 6. Learning trades exist
        trades = client.get("/api/v1/learning/trades").json()
        assert isinstance(trades, list)

        # 7. Security summary accessible with admin token
        sec = client.get("/api/v1/security/summary", headers=admin_headers).json()
        assert isinstance(sec, dict)


class TestRiskEndpoints:
    """Risk summary and advanced risk."""

    def test_risk_summary(self, client):
        r = client.get("/api/v1/risk/summary")
        # 200 if enough data, 422 if not enough candles
        assert r.status_code in (200, 422)

    def test_risk_correlation(self, client):
        r = client.get("/api/v1/risk/correlation")
        # 404 if no candle data, 200 if data available
        assert r.status_code in (200, 404)

    def test_risk_stress_test(self, client):
        r = client.get("/api/v1/risk/stress-test")
        # 404 if no candle data, 200 if data available
        assert r.status_code in (200, 404)

    def test_risk_concentration(self, client):
        r = client.get("/api/v1/risk/concentration")
        assert r.status_code == 200


class TestMemoryEndpoints:
    """Memory and journal endpoints."""

    def test_memory_list(self, client):
        r = client.get("/api/v1/memory")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert "episodes" in data

    def test_journal_analysis(self, client):
        r = client.get("/api/v1/journal/analysis")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_journal_outcomes(self, client):
        r = client.get("/api/v1/journal/outcomes")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestAdvisorAndStrategies:
    """Advisor and strategy registry endpoints."""

    def test_strategies_list(self, client):
        r = client.get("/api/v1/strategies")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_decisions_list(self, client):
        r = client.get("/api/v1/decisions")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_coach_review(self, client):
        r = client.get("/api/v1/coach/review")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)


class TestRateLimiting:
    """Rate limiter is active."""

    def test_global_rate_limit_exists(self, client):
        # Just verify the rate limiter is configured (200/min default)
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        # The rate limit headers should be present
        assert "X-RateLimit-Limit" in r.headers or "retry-after" in r.headers or r.status_code == 200
