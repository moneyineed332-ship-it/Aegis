"""Tests for daily report generation."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone
from app.daily_report import generate_daily_report, _build_summary


def test_daily_report_structure():
    report = generate_daily_report("2026-01-15")
    assert "date" in report
    assert "portfolio" in report
    assert "trades" in report
    assert "strategies" in report
    assert "regime_history" in report
    assert "alerts" in report
    assert "summary" in report


def test_daily_report_portfolio():
    report = generate_daily_report("2026-01-15")
    portfolio = report["portfolio"]
    assert "equity" in portfolio
    assert "capital" in portfolio
    assert "unrealized_pnl" in portfolio
    assert "position_count" in portfolio
    assert portfolio["capital"] > 0
    assert isinstance(portfolio["positions"], list)


def test_daily_report_portfolio_with_positions():
    from app import storage
    from datetime import datetime, timezone
    storage.save_order_and_position(
        {"order_id": "o_test_1", "symbol": "BTCUSDT", "side": "buy", "quantity": 0.001,
         "reference_price": 65000, "notional": 65, "status": "filled_simulated", "strategy": "sma"},
        {"symbol": "BTCUSDT", "quantity": 0.001, "average_price": 65000.0, "side": "long"},
    )
    storage.save_market_snapshots([{"symbol": "BTCUSDT", "price": 67000, "source": "test", "collected_at": datetime.now(timezone.utc).isoformat()}])
    report = generate_daily_report("2026-01-15")
    portfolio = report["portfolio"]
    assert portfolio["position_count"] >= 1
    assert len(portfolio["positions"]) >= 1
    pos = portfolio["positions"][0]
    assert pos["symbol"] == "BTCUSDT"
    assert pos["current_price"] == 67000
    assert pos["unrealized_pnl"] > 0


def test_daily_report_trades():
    report = generate_daily_report("2026-01-15")
    trades = report["trades"]
    assert "total" in trades
    assert "wins" in trades
    assert "losses" in trades
    assert "win_rate" in trades
    assert "total_pnl" in trades
    assert "profit_factor" in trades


def test_daily_report_strategies_empty():
    report = generate_daily_report("2026-01-15")
    assert isinstance(report["strategies"], dict)


def test_daily_report_regime_history_empty():
    report = generate_daily_report("2026-01-15")
    assert isinstance(report["regime_history"], list)


def test_daily_report_alerts():
    report = generate_daily_report("2026-01-15")
    alerts = report["alerts"]
    assert "total" in alerts
    assert "critical" in alerts
    assert "warning" in alerts


def test_daily_report_date_format():
    report = generate_daily_report("2026-01-15")
    assert report["date"] == "2026-01-15"


def test_daily_report_default_date():
    report = generate_daily_report()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert report["date"] == today


def test_daily_report_invalid_date_fallback():
    report = generate_daily_report("not-a-date")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert report["date"] == today


def test_build_summary():
    summary = _build_summary(20000, 150, 66.7, 6, [
        {"regime": "bull_trend", "confidence": 0.8},
        {"regime": "bull_trend", "confidence": 0.9},
    ])
    assert "$20,000" in summary
    assert "$+150" in summary
    assert "66.7%" in summary
    assert "6" in summary
    assert "bull_trend" in summary


def test_build_summary_negative_pnl():
    summary = _build_summary(19000, -200, 33.3, 3, [])
    assert "$19,000" in summary
    assert "$-200" in summary


def test_build_summary_empty_regimes():
    summary = _build_summary(20000, 0, 0, 0, [])
    assert "N/A" in summary


def test_daily_report_with_trade_outcomes():
    from app import storage
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    closed_at = datetime.now(timezone.utc).isoformat()

    storage.save_trade_outcome({
        "order_id": "o_outcome_1", "symbol": "BTCUSDT", "strategy": "sma",
        "side": "buy", "entry_price": 65000, "exit_price": 67000, "quantity": 0.001,
        "pnl": 2.0, "pnl_pct": 3.08, "duration_seconds": 3600,
        "regime_at_entry": "bull_trend", "status": "closed",
        "opened_at": closed_at, "closed_at": closed_at,
    })
    storage.save_trade_outcome({
        "order_id": "o_outcome_2", "symbol": "ETHUSDT", "strategy": "rsi",
        "side": "sell", "entry_price": 3500, "exit_price": 3400, "quantity": 0.01,
        "pnl": 1.0, "pnl_pct": 2.86, "duration_seconds": 1800,
        "regime_at_entry": "bear_trend", "status": "closed",
        "opened_at": closed_at, "closed_at": closed_at,
    })
    storage.save_trade_outcome({
        "order_id": "o_outcome_3", "symbol": "SOLUSDT", "strategy": "sma",
        "side": "buy", "entry_price": 150, "exit_price": 145, "quantity": 0.1,
        "pnl": -0.5, "pnl_pct": -3.33, "duration_seconds": 2400,
        "regime_at_entry": "sideways", "status": "closed",
        "opened_at": closed_at, "closed_at": closed_at,
    })

    report = generate_daily_report(today)
    strategies = report["strategies"]
    assert "sma" in strategies
    assert "rsi" in strategies
    assert strategies["sma"]["trades"] == 2
    assert strategies["rsi"]["trades"] == 1
    assert strategies["sma"]["wins"] == 1
    assert strategies["rsi"]["wins"] == 1
    assert strategies["sma"]["win_rate"] == 50.0

    trades = report["trades"]
    assert trades["total"] == 3
    assert trades["wins"] == 2
    assert trades["losses"] == 1
    assert trades["total_pnl"] == 2.5


def test_daily_report_regime_history():
    from app.storage import connection
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).isoformat()

    with connection() as db:
        db.execute(
            """INSERT INTO engine_log (cycle_id, event_type, details_json, severity, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("cycle_test_1", "regime_classified", '{"regime": "bull_trend", "confidence": 0.85}', "info", now_iso),
        )
        db.execute(
            """INSERT INTO engine_log (cycle_id, event_type, details_json, severity, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("cycle_test_2", "regime_classified", '{"regime": "bear_trend", "confidence": 0.70}', "info", now_iso),
        )
        db.execute(
            """INSERT INTO engine_log (cycle_id, event_type, details_json, severity, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("cycle_test_3", "regime_classified", '{"regime": "sideways", "confidence": 0.55}', "info", now_iso),
        )

    report = generate_daily_report(today)
    regime_history = report["regime_history"]
    assert len(regime_history) >= 3
    regimes = [r["regime"] for r in regime_history]
    assert "bull_trend" in regimes
    assert "bear_trend" in regimes
    assert "sideways" in regimes


def test_daily_report_regime_history_string_details():
    from app.storage import connection
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).isoformat()

    with connection() as db:
        db.execute(
            """INSERT INTO engine_log (cycle_id, event_type, details_json, severity, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("cycle_str_1", "regime_classified", '{"regime": "high_vol", "confidence": 0.90}', "info", now_iso),
        )

    report = generate_daily_report(today)
    regime_history = report["regime_history"]
    assert len(regime_history) >= 1
    assert regime_history[-1]["regime"] == "high_vol"


def test_daily_report_regime_history_malformed_details():
    from unittest.mock import patch
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    mock_logs = [
        {"id": 1, "cycle_id": "c1", "event_type": "regime_classified",
         "details": '{"regime": "recovered_str", "confidence": 0.7}', "severity": "info",
         "created_at": f"{today}T10:00:00Z"},
        {"id": 2, "cycle_id": "c2", "event_type": "regime_classified",
         "details": "NOT_VALID_JSON", "severity": "info",
         "created_at": f"{today}T11:00:00Z"},
        {"id": 3, "cycle_id": "c3", "event_type": "regime_classified",
         "details": None, "severity": "info",
         "created_at": f"{today}T12:00:00Z"},
        {"id": 4, "cycle_id": "c4", "event_type": "other_event",
         "details": {"regime": "bull_trend"}, "severity": "info",
         "created_at": f"{today}T13:00:00Z"},
    ]

    with patch("app.daily_report.storage") as mock_storage:
        mock_storage.list_positions.return_value = []
        mock_storage.list_market_snapshots.return_value = []
        mock_storage.list_trade_outcomes.return_value = []
        mock_storage.list_engine_logs.return_value = mock_logs
        mock_storage.list_alerts.return_value = []
        report = generate_daily_report(today)

    regime_history = report["regime_history"]
    regimes = [r["regime"] for r in regime_history]
    assert "recovered_str" in regimes
    assert "unknown" in regimes


if __name__ == "__main__":
    test_daily_report_structure()
    test_daily_report_portfolio()
    test_daily_report_portfolio_with_positions()
    test_daily_report_trades()
    test_daily_report_strategies_empty()
    test_daily_report_regime_history_empty()
    test_daily_report_alerts()
    test_daily_report_date_format()
    test_daily_report_default_date()
    test_daily_report_invalid_date_fallback()
    test_build_summary()
    test_build_summary_negative_pnl()
    test_build_summary_empty_regimes()
    print("All daily report tests passed.")
