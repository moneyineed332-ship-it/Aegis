"""/docs, /redoc and /openapi.json published the whole endpoint map.

FastAPI serves those three by default, without a token. On this app that meant
anyone who found the host could enumerate every admin route: the optimiser
endpoints, the lab promotion gate, the position and order management surface,
the ICT dashboard. The route auth inventory in test_route_auth_inventory.py
deliberately could not catch it, and said so in a comment: the three are
Starlette built-ins rather than APIRoute instances, so they sat outside the
allowlist the inventory checks.

Hiding them is not the same as losing the contract. `app.openapi()` builds the
full document in-process with no server listening, so
`python -m app.export_openapi openapi.json` produces the same schema for CI or
for generating a client, without exposing a route.

AEGIS_EXPOSE_API_DOCS turns the three back on for local work. It is read at
import time, so the opt-in test runs a subprocess rather than reloading the app
in-process.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.export_openapi import build_schema, main as export_main
from app.main import app

BACKEND = Path(__file__).resolve().parent.parent

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


@pytest.fixture
def client():
    return TestClient(app)


# --- off by default ---------------------------------------------------------

@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_are_absent_by_default(client, path):
    """404 rather than 403: the routes should not exist at all."""
    assert client.get(path).status_code == 404


def test_disabling_docs_did_not_take_the_liveness_probe_with_it(client):
    """The one route that must stay reachable without a token."""
    assert client.get("/health").status_code == 200


def test_the_schema_is_not_reachable_by_any_equivalent_path(client):
    """Guessing the path must not be a way around it."""
    for path in ("/openapi", "/api/openapi.json", "/api/v1/openapi.json", "/schema"):
        assert client.get(path).status_code == 404, path


def test_no_route_serves_the_schema(client):
    """Nothing in the route table hands out the document."""
    for route in app.routes:
        if not hasattr(route, "path"):
            continue
        assert route.path not in DOC_PATHS, f"{route.path} is still routed"


# --- the opt-in -------------------------------------------------------------

def _subprocess_env_docs(value):
    """Probe the docs routes in a fresh interpreter, since the flag binds at import."""
    script = (
        "import sys;"
        f"sys.path.insert(0, {str(BACKEND)!r});"
        "from fastapi.testclient import TestClient;"
        "from app.main import app;"
        "c = TestClient(app);"
        "print(' '.join(str(c.get(p).status_code) for p in %r))" % (list(DOC_PATHS),)
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=180,
        env={**os.environ, "AEGIS_EXPOSE_API_DOCS": value},
        cwd=str(BACKEND),
    )
    return result.stdout.strip().split()


def test_the_opt_in_serves_all_three():
    assert _subprocess_env_docs("1") == ["200", "200", "200"]


def test_the_opt_in_is_off_for_any_other_value():
    """Only an explicit truthy value turns it on. A typo must fail closed."""
    for value in ("0", "false", "no", "", "maybe", "trueish"):
        assert _subprocess_env_docs(value) == ["404", "404", "404"], value


# --- the contract is still obtainable --------------------------------------

def test_the_schema_builds_in_process_without_a_server():
    schema = build_schema()
    assert schema["openapi"].startswith("3.")
    assert len(schema["paths"]) > 50


def test_the_schema_contains_the_admin_surface():
    """The point of exporting it: the contract is complete, not pruned."""
    paths = build_schema()["paths"]
    assert any("/optimizer/" in p for p in paths)
    assert any("/lab/promotions" in p for p in paths)


def test_export_writes_a_file(tmp_path):
    target = tmp_path / "nested" / "openapi.json"
    assert export_main([str(target)]) == 0
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written == build_schema()


def test_export_to_stdout(capsys):
    assert export_main(["-"]) == 0
    assert json.loads(capsys.readouterr().out) == build_schema()


# --- the inventory comment is now wrong -------------------------------------

def test_the_inventory_comment_no_longer_claims_they_are_public():
    """The note in test_route_auth_inventory.py said they stayed reachable.

    If it is still there, a future reader will trust it and assume the gap is
    known and accepted rather than closed.
    """
    source = (BACKEND / "tests" / "test_route_auth_inventory.py").read_text(encoding="utf-8")
    stale = [
        line for line in source.splitlines()
        if ("/docs" in line or "/redoc" in line)
        and ("remain publicly reachable" in line or "separate finding" in line)
    ]
    assert not stale, f"stale note still claims the docs are public: {stale}"
