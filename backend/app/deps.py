"""Shared dependencies for route protection."""

import hmac
import secrets
import time

from fastapi import Header, HTTPException

from . import settings

# Single-use, short-lived tickets for the alerts WebSocket.
#
# A browser cannot set headers on a WebSocket, so the token has to travel in the
# URL -- and a URL is what the reverse proxy writes to its access log. The
# admin token is long-lived and grants every financial endpoint, so it must not
# be the thing that lands there.
#
# The ticket is minted over an authenticated POST, expires after a few seconds,
# and is consumed on first use. What reaches the proxy log is a value that is
# already worthless and already spent.
_TICKET_TTL_SECONDS = 20
_TICKET_PREFIX = "wst1_"
_tickets: dict[str, float] = {}


def _prune_tickets(now: float) -> None:
    for code in [c for c, exp in _tickets.items() if exp <= now]:
        _tickets.pop(code, None)


def issue_ws_ticket() -> str:
    """Mint a single-use WebSocket ticket. Caller must already be authenticated."""
    now = time.monotonic()
    _prune_tickets(now)
    code = _TICKET_PREFIX + secrets.token_urlsafe(32)
    _tickets[code] = now + _TICKET_TTL_SECONDS
    return code


def consume_ws_ticket(code: str) -> bool:
    """Redeem a ticket. False when unknown, already used, or expired.

    Compared against the stored value with compare_digest, like the admin token.
    """
    if not code or not code.startswith(_TICKET_PREFIX):
        return False
    now = time.monotonic()
    _prune_tickets(now)
    expires = _tickets.get(code)
    if expires is None:
        return False
    # Removed whatever the outcome: a ticket that failed the digest check is
    # either a guess or a collision, and neither should stay replayable.
    _tickets.pop(code, None)
    return expires > now


def active_ticket_count() -> int:
    """Outstanding tickets, for tests and for diagnostics."""
    _prune_tickets(time.monotonic())
    return len(_tickets)


def require_admin_token(x_aegis_admin_token: str | None = Header(default=None)) -> None:
    if not settings.ADMIN_TOKEN:
        raise HTTPException(401, "Administrator token is not configured.")
    # compare_digest() raises TypeError on non-ASCII str inputs, which would
    # surface as a 500 on a bad-token request instead of a clean 401.
    provided = (x_aegis_admin_token or "").encode("utf-8")
    expected = settings.ADMIN_TOKEN.encode("utf-8")
    if not x_aegis_admin_token or not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "Administrator token is required.")

