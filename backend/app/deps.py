"""Shared dependencies for route protection."""

import hmac

from fastapi import Header, HTTPException

from . import settings


def require_admin_token(x_aegis_admin_token: str | None = Header(default=None)) -> None:
    if not settings.ADMIN_TOKEN:
        raise HTTPException(401, "Administrator token is not configured.")
    # compare_digest() raises TypeError on non-ASCII str inputs, which would
    # surface as a 500 on a bad-token request instead of a clean 401.
    provided = (x_aegis_admin_token or "").encode("utf-8")
    expected = settings.ADMIN_TOKEN.encode("utf-8")
    if not x_aegis_admin_token or not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "Administrator token is required.")
