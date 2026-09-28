"""The admin token must never appear in a URL.

A WebSocket cannot carry an Authorization header, so its credential has to ride
in the query string -- and the query string is what the reverse proxy records in
its access log. The admin token is long-lived and unlocks every financial
endpoint, so it must not be that value.

The WebSocket now takes a single-use ticket, minted over an authenticated POST
and expired after seconds, so what lands in the log is already spent.
"""

import re
import time as time_mod
from pathlib import Path

import pytest

from app import deps

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _clear_tickets():
    deps._tickets.clear()
    yield
    deps._tickets.clear()


class TestTicketLifecycle:
    def test_issued_ticket_is_accepted_once(self):
        code = deps.issue_ws_ticket()
        assert deps.consume_ws_ticket(code) is True
        assert deps.consume_ws_ticket(code) is False, "a ticket was replayable"

    def test_distinct_tickets_are_independent(self):
        a, b = deps.issue_ws_ticket(), deps.issue_ws_ticket()
        assert a != b
        assert deps.consume_ws_ticket(a) is True
        assert deps.consume_ws_ticket(b) is True

    def test_unknown_ticket_is_rejected(self):
        assert deps.consume_ws_ticket("wst1_nope") is False
        assert deps.consume_ws_ticket("") is False

    def test_admin_token_is_not_a_valid_ticket(self):
        """The old URL form must stop working, not silently keep working."""
        from app import settings

        assert deps.consume_ws_ticket(settings.ADMIN_TOKEN) is False

    def test_ticket_is_prefixed_and_long_enough_to_be_unguessable(self):
        code = deps.issue_ws_ticket()
        assert code.startswith("wst1_")
        assert len(code) > 30

    def test_expired_ticket_is_rejected(self, monkeypatch):
        code = deps.issue_ws_ticket()
        real = time_mod.monotonic
        monkeypatch.setattr(deps.time, "monotonic", lambda: real() + 3600)
        assert deps.consume_ws_ticket(code) is False

    def test_issued_tickets_are_pruned(self, monkeypatch):
        for _ in range(5):
            deps.issue_ws_ticket()
        assert deps.active_ticket_count() == 5
        real = time_mod.monotonic
        deps._prune_tickets(real() + 3600)
        assert deps.active_ticket_count() == 0


class TestEndpointShape:
    def test_no_websocket_reads_the_token_from_the_query_string(self):
        source = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
        assert 'query_params.get("ticket"' in source
        assert 'query_params.get("token"' not in source, (
            "a WebSocket still accepts the admin token from the query string"
        )

    def test_both_websockets_are_covered(self):
        source = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
        for path in ('@app.websocket("/ws/alerts")', '@app.websocket("/ws/positions")'):
            assert path in source, f"{path} disappeared"
            body = source.split(path, 1)[1][:1200]
            assert "consume_ws_ticket(" in body, f"{path} does not validate a ticket"
        # One call per socket, no more: a third would mean a socket nobody audits.
        assert source.count("consume_ws_ticket(") == 2


    def test_minting_endpoint_requires_the_admin_token(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app import settings

        client = TestClient(app)
        assert client.post("/api/v1/auth/ws-ticket").status_code == 401
        if not settings.ADMIN_TOKEN:
            pytest.skip("no token configured")
        ok = client.post(
            "/api/v1/auth/ws-ticket",
            headers={"X-AEGIS-Admin-Token": settings.ADMIN_TOKEN},
        )
        assert ok.status_code == 200
        assert ok.json()["ticket"].startswith("wst1_")


class TestFrontendNeverPutsTheTokenInTheUrl:
    def _source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_provider_uses_the_ticket(self):
        src = self._source("src/app/components/AlertWebSocketProvider.tsx")
        assert "fetchWsTicket" in src
        assert "/ws/alerts?ticket=" in src
        assert "getAdminToken()}" not in src, "the admin token is still interpolated into the URL"
        assert "?token=${" not in src

    def test_positions_section_uses_the_ticket(self):
        """A second socket had the same exposure and was found by the scan below."""
        src = self._source("src/app/sections/PositionMonitorSection.tsx")
        assert "fetchWsTicket" in src
        assert "/ws/positions?ticket=" in src
        assert "?token=${" not in src

    def test_api_exposes_the_ticket_fetcher(self):
        src = self._source("src/lib/api.ts")
        assert "export async function fetchWsTicket" in src
        assert "/api/v1/auth/ws-ticket" in src

    def test_ticket_is_fetched_with_the_admin_header(self):
        src = self._source("src/lib/api.ts")
        block = re.search(
            r"export async function fetchWsTicket.*?\n\}", src, re.S
        )
        assert block, "fetchWsTicket not found"
        assert "getAdminHeaders()" in block.group(0), (
            "the ticket must be minted over an authenticated request"
        )

    def test_no_source_file_puts_the_admin_token_in_a_query_string(self):
        offenders = []
        for pattern in ("src/**/*.ts", "src/**/*.tsx"):
            for path in ROOT.rglob(pattern):
                if "node_modules" in str(path):
                    continue
                text = path.read_text(encoding="utf-8")
                for match in re.finditer(r"[?&]token=\$\{", text):
                    line = text[: match.start()].count("\n") + 1
                    offenders.append(f"{path.name}:{line}")
        assert not offenders, f"admin token interpolated into a URL: {offenders}"

