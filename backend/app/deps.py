"""Shared dependencies for route protection."""

import hmac

from fastapi import Header, HTTPException

from . import settings


def require_admin_token(x_aegis_admin_token: str | None = Header(default=None)) -> None:
    if not settings.ADMIN_TOKEN:
        raise HTTPException(401, "Administrator token is not configured.")
    if not x_aegis_admin_token or not hmac.compare_digest(x_aegis_admin_token, settings.ADMIN_TOKEN):
        raise HTTPException(401, "Administrator token is required.")
