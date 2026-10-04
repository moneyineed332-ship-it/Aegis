"""Integration tests: multi-step workflows across API endpoints."""

import pytest


class TestHealthAndMetrics:
    """Health and monitoring endpoints."""

    def test_health_basic(self, client, admin_headers):
        r = client.get("/api/v1/health", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "mode" in data

    def test_health_detailed(self, client, admin_headers):
        r = client.get("/api/v1/health/detailed", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"]["status"] == "ok"

    def test_metrics_endpoint(self, client, admin_headers):
        r = client.get("/api/v1/metrics", headers=admin_headers)
        assert r.status_code == 200
        assert "text/plain" in r.headers["content-type"]
        body = r.text
        assert "aegis_http_requests_total" in body

    def test_request_id_in_response(self, client, admin_headers):
        r = client.get("/api/v1/health", headers=admin_headers)
        assert "X-Request-ID" in r.headers


class TestMarketWorkflow:
    """Market data refresh -> analysis -> dashboard verification."""

    def test_market_snapshots_crud(self, client, admin_headers):
        r = client.get("/api/v1/market-snapshots", headers=admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
