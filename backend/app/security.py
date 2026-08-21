"""Security audit logging for AEGIS AI Quant.

Tracks all security-relevant events:
- Authentication attempts (success/failure)
- Admin actions (mode switches, engine control)
- Risk threshold breaches
- Unusual patterns (rapid requests, invalid tokens)
"""

import logging
from datetime import datetime, timezone

from . import storage

logger = logging.getLogger("aegis.security")


def log_auth_success(identifier: str, endpoint: str) -> None:
    """Log successful authentication."""
    _log_event("auth_success", "info", {
        "identifier": identifier,
        "endpoint": endpoint,
    })


def log_auth_failure(identifier: str, endpoint: str, reason: str = "invalid_token") -> None:
    """Log failed authentication attempt."""
    _log_event("auth_failure", "warning", {
        "identifier": identifier,
        "endpoint": endpoint,
        "reason": reason,
    })
    logger.warning("Auth failure: %s on %s — %s", identifier, endpoint, reason)


def log_admin_action(action: str, details: dict, identifier: str = "admin") -> None:
    """Log an admin action (mode switch, engine control, etc.)."""
    _log_event("admin_action", "info", {
        "action": action,
        "identifier": identifier,
        **details,
    })
    logger.info("Admin action: %s by %s — %s", action, identifier, details)


def log_mode_switch(old_mode: str, new_mode: str, identifier: str = "admin") -> None:
    """Log execution mode switch."""
    _log_event("mode_switch", "warning", {
        "old_mode": old_mode,
        "new_mode": new_mode,
        "identifier": identifier,
    })
    logger.warning("Mode switch: %s → %s by %s", old_mode, new_mode, identifier)


def log_risk_breach(breach_type: str, details: dict) -> None:
    """Log a risk threshold breach."""
    _log_event("risk_breach", "critical", {
        "breach_type": breach_type,
        **details,
    })
    logger.critical("Risk breach: %s — %s", breach_type, details)


def log_suspicious_activity(activity_type: str, details: dict) -> None:
    """Log suspicious activity (rapid requests, invalid tokens, etc.)."""
    _log_event("suspicious_activity", "critical", {
        "activity_type": activity_type,
        **details,
    })
    logger.critical("Suspicious activity: %s — %s", activity_type, details)


def _log_event(event_type: str, severity: str, details: dict) -> None:
    """Write event to engine log and security log."""
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        storage.log_engine_event(
            cycle_id=f"sec-{int(datetime.now(timezone.utc).timestamp())}",
            event_type=f"security_{event_type}",
            details=details,
            severity=severity,
        )
    except Exception:
        pass  # Don't fail if logging fails


def get_security_summary(limit: int = 100) -> dict:
    """Get a summary of recent security events."""
    logs = storage.list_engine_logs(limit=limit)
    security_logs = [l for l in logs if l.get("event_type", "").startswith("security_")]

    auth_failures = [l for l in security_logs if "auth_failure" in l.get("event_type", "")]
    admin_actions = [l for l in security_logs if "admin_action" in l.get("event_type", "")]
    risk_breaches = [l for l in security_logs if "risk_breach" in l.get("event_type", "")]
    suspicious = [l for l in security_logs if "suspicious" in l.get("event_type", "")]

    return {
        "total_events": len(security_logs),
        "auth_failures": len(auth_failures),
        "admin_actions": len(admin_actions),
        "risk_breaches": len(risk_breaches),
        "suspicious_activities": len(suspicious),
        "recent_events": security_logs[:20],
    }
