"""The dev server must not silently operate a real account.

Every financial endpoint is authenticated with the single admin token, which is
typed into the browser at runtime. With VITE_API_URL pointing at the deployment,
`npm run dev` signs in to the real machine and the order, emergency-stop and
mode endpoints act on it, while looking exactly like local work.

The repository .env had VITE_API_URL=https://aegis-jn6oxq.fly.dev, so this was
the default state of a fresh clone.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
API_TS = ROOT / "src" / "lib" / "api.ts"


@pytest.fixture(scope="module")
def api_source():
    return API_TS.read_text(encoding="utf-8")


class TestDevServerRefusesRemoteBackend:
    def test_guard_exists(self, api_source):
        assert "import.meta.env.DEV" in api_source, "no dev-only guard on VITE_API_URL"
        assert "VITE_ALLOW_REMOTE_API" in api_source, "no escape hatch for intentional staging"

    def test_guard_runs_before_any_request(self, api_source):
        """The check has to be at module load, not in a component."""
        guard_at = api_source.index("VITE_ALLOW_REMOTE_API")
        first_fetch = api_source.index("fetch(")
        assert guard_at < first_fetch, "the guard runs after the first request"

    def test_local_hosts_are_accepted(self, api_source):
        for host in ("localhost", "127.0.0.1", '"::1"'):
            assert host.strip('"') in api_source, f"{host} would be rejected by the guard"

    def test_guard_is_dev_only(self, api_source):
        """A production build must not inherit the check."""
        assert re.search(r"import\.meta\.env\.DEV\s*&&", api_source), (
            "the guard is not scoped to development"
        )

    def test_error_names_the_offending_host(self, api_source):
        assert "pointe sur un hôte distant" in api_source
        assert "hostname" in api_source, "the message does not report the host it refused"

    def test_websocket_reuses_the_validated_url(self):
        """The socket must not be a second, unguarded path to the deployment."""
        provider = (ROOT / "src" / "app" / "components" / "AlertWebSocketProvider.tsx").read_text(
            encoding="utf-8"
        )
        assert "VITE_API_URL" in provider
        assert "VITE_ALLOW_REMOTE_API" not in provider, (
            "the socket must rely on the guard in api.ts, not add its own remote fallback"
        )


class TestExampleEnvLeadsLocally:
    def test_example_defaults_to_local(self):
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        m = re.search(r"^VITE_API_URL=(.+)$", example, re.MULTILINE)
        assert m, "VITE_API_URL missing from .env.example"
        assert "localhost" in m.group(1), (
            f"the example still leads with a remote host: {m.group(1)}"
        )

    def test_example_never_mentions_the_admin_token(self):
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        assigned = re.findall(r"^\s*(VITE_ADMIN_TOKEN\s*=.*)$", example, re.MULTILINE)
        assert not assigned, f"the token must never be assigned: {assigned}"
