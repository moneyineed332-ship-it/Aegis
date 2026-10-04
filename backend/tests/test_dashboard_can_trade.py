"""The dashboard's can_trade was a verdict on nothing.

/api/ict/dashboard/risk and /api/ict/dashboard/risk/status both called
check_all_limits(instrument, 0.0, 0.0, 0.0) to fill the field. Zero levels make
the R:R zero, so every instrument reported:

    can_trade=False  ['R:R insuffisant: 0.00 < 1.50']

permanently. The field could never be true, and the reason named a defect in the
account when the real cause was that no signal had been supplied. An operator
reading that has no way to tell a blocked account from a missing input.
"""

from datetime import datetime, timezone

import pytest

from app.ict_risk_manager import IctRiskManager

# The session gate reads a clock, and trading hours are 08:00-22:00 UTC. Tests
# that assert can_trade is True used to depend on when the suite happened to run,
# so the suite could not go green for ten hours a day: at 22:50 UTC new_york had
# closed and london had not opened, and three tests failed with
# "Hors session (prochaine dans 579min)" while nothing had broken.
#
# check_all_limits and check_account_limits now take `now`, which is passed
# through to session_filter. Pinning it here means the real session logic still
# decides the answer; only the time is fixed. INSIDE_LONDON is a Thursday at
# 10:00 UTC, and OUTSIDE_ALL is Sunday at 03:00 UTC, which is outside every
# window including asian.
INSIDE_LONDON = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
OUTSIDE_ALL = datetime(2026, 1, 18, 3, 0, tzinfo=timezone.utc)


@pytest.fixture
def rm():
    from app import storage

    storage.initialize()
    return IctRiskManager(initial_capital=50.0)


class TestZeroLevelsAreNotUsedForTheDashboard:
    def test_zero_levels_still_produce_the_broken_verdict(self, rm):
        """Pins the defect so the fix cannot be undone by using zero levels again."""
        for instrument in ("EURUSD", "GBPUSD", "XAUUSD"):
            status = rm.check_all_limits(instrument, 0.0, 0.0, 0.0)
            assert status.can_trade is False
            assert any("R:R" in r for r in status.blocking_reasons)

    def test_dashboard_no_longer_calls_check_all_limits_with_zeros(self):
        from app.routers import ict_dashboard

        for handler in (ict_dashboard.get_risk_metrics, ict_dashboard.get_risk_status):
            source = __import__("inspect").getsource(handler)
            assert "check_all_limits(" not in source, (
                f"{handler.__name__} still evaluates a signal it does not have"
            )
            assert "check_account_limits(" in source


class TestAccountGatesAreHonest:
    def test_can_trade_can_now_be_true(self, rm):
        for instrument in ("EURUSD", "GBPUSD", "XAUUSD"):
            status = rm.check_account_limits(instrument, now=INSIDE_LONDON)
            assert status.can_trade is True, status.blocking_reasons

    def test_scope_is_declared_as_account(self, rm):
        assert rm.check_account_limits("EURUSD", now=INSIDE_LONDON).scope == "account"

    def test_signal_scope_is_still_declared_on_a_real_signal(self, rm):
        status = rm.check_all_limits("EURUSD", 1.1370, 1.1330, 1.1450, direction="buy", now=INSIDE_LONDON)
        assert status.scope == "signal"

    def test_unevaluated_gates_are_named(self, rm):
        status = rm.check_account_limits("EURUSD", now=INSIDE_LONDON)
        assert status.not_evaluated
        assert "R:R" in status.not_evaluated
        assert "ATR" in status.not_evaluated

    def test_volatility_is_unknown_not_passed(self, rm):
        """No ATR to judge means unknown, not a silent pass."""
        status = rm.check_account_limits("EURUSD", now=INSIDE_LONDON)
        assert status.volatility_ok is False
        assert status.volatility_reason


class TestAccountGatesStillBlock:
    def test_trade_limit(self, rm):
        rm._trades_today = 2
        status = rm.check_account_limits("EURUSD", now=INSIDE_LONDON)
        assert status.can_trade is False
        assert any("trades/session" in r for r in status.blocking_reasons)

    def test_consecutive_losses(self, rm):
        rm._consecutive_losses = 3
        status = rm.check_account_limits("EURUSD", now=INSIDE_LONDON)
        assert status.can_trade is False
        assert any("consecutive" in r for r in status.blocking_reasons)

    def test_daily_drawdown(self, rm):
        rm._daily_pnl = -2.0
        status = rm.check_account_limits("EURUSD", now=INSIDE_LONDON)
        assert status.can_trade is False
        assert any("drawdown" in r.lower() for r in status.blocking_reasons)

    def test_unreconciled_position(self, rm, monkeypatch):
        from app import storage

        with storage.connection() as db:
            db.execute(
                "INSERT INTO positions (symbol, quantity, average_price) VALUES (?,?,?) "
                "ON CONFLICT(symbol) DO UPDATE SET quantity=excluded.quantity",
                ("BTCUSDT", 0.0002, 84072.0),
            )
        status = rm.check_account_limits("EURUSD", now=INSIDE_LONDON)
        assert status.can_trade is False
        assert any("rapprochees" in r for r in status.blocking_reasons)

    def test_out_of_session(self, rm):
        """Previously guarded by `if not status.session_allowed`.

        That made it a no-op for most of the day: it only asserted when the wall
        clock happened to be outside a session, and said nothing otherwise. With
        `now` pinned to a Sunday 03:00 UTC, outside every window including
        asian, it always runs.
        """
        status = rm.check_account_limits("EURUSD", now=OUTSIDE_ALL)
        assert status.session_allowed is False
        assert status.can_trade is False
        assert any("session" in r.lower() for r in status.blocking_reasons)

    def test_inside_session_is_not_blocked_for_that_reason(self, rm):
        """The counterpart, so the gate cannot pass by always saying no."""
        status = rm.check_account_limits("EURUSD", now=INSIDE_LONDON)
        assert status.session_allowed is True
        assert not any("session" in r.lower() for r in status.blocking_reasons)


class TestSignalGatesAreUntouched:
    """The account-only path must not have weakened the real gate."""

    @pytest.mark.parametrize("entry,sl,tp,expected", [
        (1.1370, 1.1360, 1.1375, "R:R"),
        (1.1370, 1.1000, 1.1500, "R:R"),
    ])
    def test_bad_rr_still_blocked(self, rm, entry, sl, tp, expected):
        status = rm.check_all_limits("EURUSD", entry, sl, tp, direction="buy", current_atr_pips=30, now=INSIDE_LONDON)
        assert status.can_trade is False
        assert any(expected in r for r in status.blocking_reasons)

    def test_low_atr_still_blocked(self, rm):
        status = rm.check_all_limits("EURUSD", 1.1370, 1.1330, 1.1450,
                                     direction="buy", current_atr_pips=5, now=INSIDE_LONDON)
        assert status.can_trade is False
        assert any("Volatilit" in r for r in status.blocking_reasons)

    def test_a_good_signal_still_trades(self, rm):
        status = rm.check_all_limits("EURUSD", 1.1370, 1.1330, 1.1450,
                                     direction="buy", current_atr_pips=30, now=INSIDE_LONDON)
        assert status.can_trade is True, status.blocking_reasons

