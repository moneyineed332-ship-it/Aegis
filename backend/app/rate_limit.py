"""Shared rate limiter.

Lives in its own module so that both ``main`` and the routers can reach the same
limiter instance. Defining it in ``main`` would make it unreachable from
``routers/market.py`` without a circular import, and the liveness endpoints
need to override the default limit (see ``LIVENESS_LIMIT``).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Applied to every route that does not declare its own limit.
DEFAULT_LIMITS = ["200/minute"]

limiter = Limiter(key_func=get_remote_address, default_limits=DEFAULT_LIMITS)

# A liveness probe must never be able to fail because a client is polling fast.
# Overriding the default here keeps the orchestrator's health check working even
# under a burst: a rate-limited probe turns a traffic spike into a restart storm.
LIVENESS_LIMIT = "10000/minute"
