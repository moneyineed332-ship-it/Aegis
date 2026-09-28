"""One source of truth for "is there an open position".

The order book is the record of what is held. The ICT risk manager kept its own
list of trades it had opened, and counted positions from that list. Measured on a
local run:

  /api/v1/oms/status  positions_count=1  total_exposure=16.81
  /api/ict/dashboard/risk  open_positions=0

so a position consumed the exposure cap while no drawdown or daily-loss limit
could see it. The cause was a leftover crypto position from an earlier Donchian
run, but the flaw is general: any position the ICT manager did not open was
invisible to every limit that counts positions.
"""

import inspect

import pytest

from app import storage
from app.ict_risk_manager import IctRiskManager


def _put_position(symbol, quantity, price):
    with storage.connection() as db:
        db.execute(
            "INSERT INTO positions (symbol, quantity, average_price) VALUES (?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET quantity=excluded.quantity, "
            "average_price=excluded.average_price",
            (symbol, quantity, price),
        )


@pytest.fixture
def rm():
    return IctRiskManager(initial_capital=50.0)


class TestBookIsTheSourceOfTruth:
    def test_reports_the_book_not_the_private_list(self, rm):
        assert rm.book_open_positions() == []
        _put_position("BTCUSDT", 0.0002, 84072.35517)
        assert [p["symbol"] for p in rm.book_open_positions()] == ["BTCUSDT"]

    def test_exposure_matches_the_oms(self, rm):
        _put_position("BTCUSDT", 0.0002, 84072.35517)
        book = sum(abs(p["quantity"] * p["average_price"]) for p in rm.book_open_positions())
        assert book == pytest.approx(16.81, abs=0.01)
        assert book == pytest.approx(storage.list_positions()[0]["quantity"] * storage.list_positions()[0]["average_price"])

    def test_zero_quantity_is_not_open(self, rm):
        _put_position("EURUSD", 0.0, 1.08)
        assert rm.book_open_positions() == []

    def test_filtered_by_instrument(self, rm):
        _put_position("EURUSD", 0.01, 1.08)
        _put_position("XAUUSD", 0.01, 2650.0)
        assert [p["symbol"] for p in rm.book_open_positions("XAUUSD")] == ["XAUUSD"]
        assert len(rm.book_open_positions()) == 2


class TestLimitsCountTheBook:
    def test_simultaneous_positions_uses_the_book(self, rm):
        """A position the manager did not open still occupies the account."""
        _put_position("EURUSD", 0.01, 1.08)
        status = rm.check_all_limits("EURUSD", 1.0800, 1.0780, 1.0860, direction="buy")
        reasons = " ".join(status.blocking_reasons)
        assert "simultaneous" in reasons.lower() or "non rapprochees" in reasons.lower(), reasons

    def test_no_book_means_no_blocker_from_position_count(self, rm):
        status = rm.check_all_limits("EURUSD", 1.0800, 1.0780, 1.0860, direction="buy")
        assert not any("simultaneous" in r.lower() for r in status.blocking_reasons)


class TestUnreconciledPositionsFailClosed:
    """A position with no stop loss and no accounting must stop new entries."""

    def test_flags_positions_it_does_not_manage(self, rm):
        _put_position("BTCUSDT", 0.0002, 84072.35517)
        assert [p["symbol"] for p in rm.unreconciled_positions()] == ["BTCUSDT"]

    def test_blocks_trading_while_unreconciled(self, rm):
        _put_position("BTCUSDT", 0.0002, 84072.35517)
        status = rm.check_all_limits("EURUSD", 1.0800, 1.0780, 1.0860, direction="buy")
        assert status.can_trade is False
        assert any("non rapprochees" in r for r in status.blocking_reasons)
        assert any("BTCUSDT" in r for r in status.blocking_reasons)

    def test_block_names_the_symbol_so_it_can_be_acted_on(self, rm):
        _put_position("BTCUSDT", 0.0002, 84072.35517)
        status = rm.check_all_limits("EURUSD", 1.0800, 1.0780, 1.0860, direction="buy")
        named = [r for r in status.blocking_reasons if "non rapprochees" in r]
        assert named and "BTCUSDT" in named[0]


class TestReportedNumbersAreHonest:
    def test_status_separates_held_from_managed(self, rm):
        _put_position("BTCUSDT", 0.0002, 84072.35517)
        status = rm.get_status()
        assert status["open_positions"] == 1
        assert status["managed_positions"] == 0
        assert status["unreconciled_positions"] == ["BTCUSDT"]

    def test_per_instrument_also_reports_both(self, rm):
        _put_position("XAUUSD", 0.01, 2650.0)
        status = rm.get_status()
        assert status["instruments"]["XAUUSD"]["open_positions"] == 1
        assert status["instruments"]["XAUUSD"]["managed_positions"] == 0

    def test_dashboard_does_not_use_the_private_list(self):
        from app.routers import ict_dashboard

        # Comments are stripped: the fix documents the old expression by name,
        # so a naive substring search matches its own explanation.
        code = "\n".join(
            ln for ln in inspect.getsource(ict_dashboard.get_risk_metrics).splitlines()
            if not ln.lstrip().startswith("#")
        )
        assert "len(rm._open_trades)" not in code
        assert "rm.book_open_positions()" in code

    def test_no_remaining_use_of_the_private_list_as_a_count(self):
        from app import ict_risk_manager as mod

        src = inspect.getsource(mod)
        for pattern in (
            "len([t for t in self._open_trades.values() if t.instrument == instrument])",
        ):
            assert pattern not in src, f"still counting from the private list: {pattern}"
