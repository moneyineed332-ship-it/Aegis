"""Tests for the security module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch
from app import security, storage


def test_log_auth_success():
    with patch.object(storage, "log_engine_event") as mock_log:
        security.log_auth_success("test-user", "/api/v1/test")
    mock_log.assert_called_once()


def test_log_auth_failure():
    with patch.object(storage, "log_engine_event") as mock_log:
        security.log_auth_failure("test-user", "/api/v1/test", "bad_token")
    mock_log.assert_called_once()


def test_log_admin_action():
    with patch.object(storage, "log_engine_event") as mock_log:
        security.log_admin_action("engine_start", {"detail": "test"})
    mock_log.assert_called_once()


def test_log_mode_switch():
    with patch.object(storage, "log_engine_event") as mock_log:
        security.log_mode_switch("paper", "live")
    mock_log.assert_called_once()


def test_log_risk_breach():
    with patch.object(storage, "log_engine_event") as mock_log:
        security.log_risk_breach("max_drawdown", {"value": -0.25})
    mock_log.assert_called_once()


def test_log_suspicious_activity():
    with patch.object(storage, "log_engine_event") as mock_log:
        security.log_suspicious_activity("rapid_requests", {"count": 100})
    mock_log.assert_called_once()


def test_log_event_handles_exception():
    with patch.object(storage, "log_engine_event", side_effect=Exception("DB error")):
        security.log_auth_success("test", "/test")


def test_get_security_summary_empty():
    with patch.object(storage, "list_engine_logs", return_value=[]):
        result = security.get_security_summary()
    assert result["total_events"] == 0
    assert result["auth_failures"] == 0
    assert result["admin_actions"] == 0
    assert result["risk_breaches"] == 0
    assert result["suspicious_activities"] == 0


def test_get_security_summary_filters():
    logs = [
        {"event_type": "security_auth_failure", "severity": "warning", "details": {}, "created_at": "2026-01-01"},
        {"event_type": "security_admin_action", "severity": "info", "details": {}, "created_at": "2026-01-01"},
        {"event_type": "security_risk_breach", "severity": "critical", "details": {}, "created_at": "2026-01-01"},
        {"event_type": "security_suspicious_activity", "severity": "critical", "details": {}, "created_at": "2026-01-01"},
        {"event_type": "engine_cycle_complete", "severity": "info", "details": {}, "created_at": "2026-01-01"},
    ]
    with patch.object(storage, "list_engine_logs", return_value=logs):
        result = security.get_security_summary()
    assert result["total_events"] == 4
    assert result["auth_failures"] == 1
    assert result["admin_actions"] == 1
    assert result["risk_breaches"] == 1
    assert result["suspicious_activities"] == 1
