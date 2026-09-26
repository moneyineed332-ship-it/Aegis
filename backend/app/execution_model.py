"""Execution timing rules shared by every backtester.

Look-ahead bias
---------------
A backtester loop that reads ``candles[i]`` to form a signal and then fills at
``candles[i]["close"]`` is assuming it knew the close of bar ``i`` and traded
at that same close. That is impossible, and it inflates every result.

The rule enforced here is deliberately strict:

* A decision taken from data up to and including bar ``i`` can only be filled
  at bar ``i + 1``'s OPEN, with slippage. The open of ``i+1`` is the first
  price actually reachable after the close of ``i`` is known.
* Stops and take-profits are intrabar triggers, so they are evaluated on bars
  strictly AFTER the bar the position was filled on. A position cannot be
  stopped out on the very bar it was opened, which is the classic
  "open at the close, then profit from that same bar's range" artefact.
* The last bar of the series cannot open a new position, because there is no
  next bar to fill on.

The helpers return ``None`` when no fill is possible, so callers cannot
silently fall back to the current bar.

Legitimate exception
--------------------
``backtesting.py`` (SMA crossover and Donchian) slices its inputs
exclusively — ``candles[index - period:index]`` — so it only ever sees bars up
to ``index - 1`` and fills on bar ``index``. There is no look-ahead there, and
it deliberately stays on that cheaper model. It is not a counter-example to
the rule; it is the same rule applied with an exclusive window instead of an
explicit one-bar deferral.
"""

from typing import Any


def next_bar_open(candles: list[dict], signal_index: int) -> dict | None:
    """Return the bar after ``signal_index``, or None if it does not exist."""
    nxt = signal_index + 1
    if nxt >= len(candles):
        return None
    return candles[nxt]


def fill_price(
    candles: list[dict],
    signal_index: int,
    side: str,
    slippage_rate: float = 0.0,
) -> float | None:
    """Price for an order decided on bar ``signal_index``.

    Returns the next bar's open moved by slippage in the trade direction, or
    ``None`` when ``signal_index`` is the last bar.
    """
    bar = next_bar_open(candles, signal_index)
    if bar is None:
        return None
    base = bar.get("open")
    if not base:
        return None
    return base * (1 + slippage_rate) if side == "buy" else base * (1 - slippage_rate)


def intrabar_exit_price(
    bar: dict,
    side: str,
    stop_loss: float,
    take_profit: float,
    slippage_rate: float = 0.0,
) -> tuple[float, str] | None:
    """Resolve a stop or take-profit hit inside ``bar``.

    Returns ``(price, reason)`` or ``None`` when neither level is touched.
    A long is assumed when ``side == "buy"``. When a single bar spans both
    levels the pessimistic one wins, because the intrabar path is unknown.
    """
    high = bar.get("high")
    low = bar.get("low")
    if high is None or low is None or not stop_loss or not take_profit:
        return None
    if side == "buy":
        hit_stop = low <= stop_loss
        hit_target = high >= take_profit
        if hit_stop:
            return stop_loss * (1 - slippage_rate), "stop_loss"
        if hit_target:
            return take_profit * (1 - slippage_rate), "take_profit"
    else:
        hit_stop = high >= stop_loss
        hit_target = low <= take_profit
        if hit_stop:
            return stop_loss * (1 + slippage_rate), "stop_loss"
        if hit_target:
            return take_profit * (1 + slippage_rate), "take_profit"
    return None


def is_last_index(index: int, total: int) -> bool:
    """True when no fill is possible after ``index``."""
    return index + 1 >= total


def assert_no_lookahead(
    trades: list[dict[str, Any]],
    candles: list[dict],
) -> None:
    """Audit helper: every trade must be stamped after the bar that caused it.

    Raises ``AssertionError`` when a trade carries a ``signal_index`` that is
    not strictly before the bar its price was taken from. Used by the tests to
    keep the execution model honest.
    """
    for trade in trades:
        if "signal_index" not in trade or "fill_index" not in trade:
            continue
        if trade["fill_index"] <= trade["signal_index"]:
            raise AssertionError(
                f"look-ahead: signal on bar {trade['signal_index']} filled on bar {trade['fill_index']}"
            )
