"""Tests for the ICT structure-detection sensitivity.

A swing is a fractal: ``candles[i]`` must dominate ``lookback`` neighbours on
BOTH sides, so the swing order is ``2 * lookback + 1`` bars. ``market_structure``
returns neutral unless it finds at least two swing highs AND two swing lows.

The ICT signal generator overrode that lookback to 10, i.e. a 21-bar fractal,
while the library default is 5 (an 11-bar fractal). Measured on real EURUSD
M15 data over 26 rolling windows of 120 bars:

    lookback   windows with >=2 highs and >=2 lows   non-neutral trend   BOS
         3                    88%                            58%        19%
         5                    81%                            58%        12%
        10                    38%                            31%         8%
        20                     0%                             0%         0%

On 4h, lookback=10 found structure in 0% of windows, so the H4 trend context
was permanently neutral. These tests pin the sensitivity contract so the
generator cannot silently drift back to an unusable value.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.indicators import _classify_trend, market_structure, swing_highs_lows
from app.ict_signal_generator import ICTSignalGenerator, STRUCTURE_LOOKBACK


import math
import random


def _zigzag(n=240, period=24, base=1.10, amp=0.004):
    """Deterministic irregular series: a seeded random walk with a slow drift.

    A pure sine is not a valid fixture here: its peaks are exactly equal, so
    every swing is classified ``equal_highs`` and the trend stays neutral no
    matter the order. A seeded walk gives irregular swings, like real data.
    """
    rng = random.Random(20260101)
    candles = []
    price = base
    for i in range(n):
        price *= 1 + rng.gauss(0.0006, 0.0018) + 0.0002 * math.sin(2 * math.pi * i / period)
        price = max(price, 0.5)
        candles.append({
            "symbol": "EURUSD", "interval": "15m",
            "open_time": 1_700_000_000_000 + i * 900_000,
            "close_time": 1_700_000_000_000 + (i + 1) * 900_000 - 1,
            "open": price, "high": price * 1.0012, "low": price * 0.9988,
            "close": price, "volume": 1000,
        })
    return candles


def _detection_rate(order, window=120, step=20, n=300, seed=7):
    """Fraction of rolling windows where market_structure is not neutral."""
    candles = _zigzag(n=n)
    usable = trend = total = 0
    for start in range(0, len(candles) - window + 1, step):
        total += 1
        pivots = swing_highs_lows(candles[start:start + window], order)
        if len(pivots["highs"]) >= 2 and len(pivots["lows"]) >= 2:
            usable += 1
        if market_structure(candles[start:start + window], order)["trend"] != "neutral":
            trend += 1
    return usable / total, trend / total


class TestSwingOrder:
    def test_lower_order_finds_more_structure_than_a_higher_one(self):
        """The whole point: a coarser fractal sees strictly less structure."""
        usable_5, trend_5 = _detection_rate(5)
        usable_10, trend_10 = _detection_rate(10)
        assert trend_5 > trend_10, "structure order 5 should beat order 10"
        assert usable_5 > usable_10

    def test_configured_order_is_usable_on_most_bars(self):
        usable, trend = _detection_rate(STRUCTURE_LOOKBACK)
        assert usable > 0.5, f"only {usable:.0%} of windows yield 2 highs + 2 lows"
        assert trend > 0.2, f"only {trend:.0%} of windows yield a trend"

    def test_structure_points_are_chronological(self):
        """The trend window must be the most recent points IN TIME.

        The points are built by two loops (all highs, then all lows), so the
        unsorted tail skipped the most recent highs entirely.
        """
        ms = market_structure(_zigzag(), STRUCTURE_LOOKBACK)
        indices = [p["index"] for p in ms["structure_points"]]
        assert indices == sorted(indices), "structure_points are not in chronological order"

    def test_recent_sequence_is_chronological(self):
        ms = market_structure(_zigzag(), STRUCTURE_LOOKBACK)
        seq = [p["index"] for p in ms["recent_sequence"]]
        assert seq == sorted(seq)

    def test_trend_window_is_the_latest_points_in_time(self):
        """Whatever the trend verdict, it must be read off the latest points."""
        ms = market_structure(_zigzag(), STRUCTURE_LOOKBACK)
        pts = ms["structure_points"]
        window = pts[-6:]
        assert all(p["index"] >= pts[-6]["index"] for p in window)
        # the last point is the most recent swing detected
        assert pts[-1]["index"] == max(p["index"] for p in pts)

    def test_too_few_bars_yield_neutral(self):
        ms = market_structure(_zigzag(n=6), STRUCTURE_LOOKBACK)
        assert ms["trend"] == "neutral"
        assert ms["last_bos"] is None



class TestGeneratorSensitivity:
    def test_configured_lookback_is_the_library_default(self):
        """The generator must not drift below the order that yields structure."""
        from app.indicators import market_structure as ms_default

        default = ms_default.__defaults__[0]
        assert STRUCTURE_LOOKBACK == default, (
            f"structure lookback {STRUCTURE_LOOKBACK} != indicators default {default}"
        )

    def test_lookback_does_not_exceed_the_usable_range(self):
        assert STRUCTURE_LOOKBACK <= 5, (
            "a structure order above 5 found structure in under 40% of real M15 windows"
        )

    def test_every_structure_call_uses_the_constant(self):
        """No hard-coded lookback may reappear at a call site."""
        import inspect

        from app import ict_signal_generator as mod

        source = inspect.getsource(mod)
        assert "lookback=10)" not in source
        assert "lookback=20)" not in source
        assert source.count("STRUCTURE_LOOKBACK") >= 5
        assert source.count("ZONE_LOOKBACK") >= 4

    def test_analyze_structure_returns_points_in_time(self):
        gen = ICTSignalGenerator("EURUSD")
        st = gen._analyze_structure(_zigzag())
        assert st["trend"] in ("bullish", "bearish", "neutral")
        indices = [p["index"] for p in st["structure_points"]]
        assert indices == sorted(indices)
        # swing_highs_lows is a helper payload, not a market verdict
        assert "swing_highs_lows" in st


class TestTrendClassification:
    """The trend is the polarity of the most recent structural event."""

    def _points(self, types):
        return [{"index": i, "type": t} for i, t in enumerate(types)]

    def test_trailing_higher_low_is_bullish(self):
        assert _classify_trend(self._points(["hh", "hl", "hl"])) == "bullish"

    def test_trailing_lower_high_is_bearish(self):
        assert _classify_trend(self._points(["ll", "lh", "lh"])) == "bearish"

    def test_single_higher_high_is_bullish(self):
        assert _classify_trend(self._points(["hh"])) == "bullish"

    def test_dominant_higher_low_run_is_bullish(self):
        """The count rule could not express this; it read neutral."""
        assert _classify_trend(self._points(["hl", "hl", "hl", "hl"])) == "bullish"

    def test_dominant_lower_low_run_is_bearish(self):
        assert _classify_trend(self._points(["ll", "ll", "ll", "ll"])) == "bearish"

    def test_equal_highs_carry_no_direction(self):
        # An equal-high pivot is liquidity, not structure: the previous
        # structural event still governs.
        assert _classify_trend(self._points(["hl", "eh"])) == "bullish"
        assert _classify_trend(self._points(["lh", "eh"])) == "bearish"

    def test_empty_is_neutral(self):
        assert _classify_trend([]) == "neutral"

    def test_mixed_window_follows_the_last_event(self):
        assert _classify_trend(self._points(["hh", "hl", "ll", "hl"])) == "bullish"
        assert _classify_trend(self._points(["ll", "lh", "hl", "lh"])) == "bearish"

    def test_never_locked_to_one_direction_on_a_real_series(self):
        """A count rule produced 0 bullish labels on EURUSD 15m."""
        from collections import Counter

        counts = Counter()
        candles = _zigzag(n=400)
        for t in range(30, len(candles)):
            ms = market_structure(candles[:t + 1], STRUCTURE_LOOKBACK)
            counts[ms["trend"]] += 1
        assert counts["bullish"] > 0, "never labels a market bullish"
        assert counts["bearish"] > 0, "never labels a market bearish"

    def test_symmetry_is_better_than_the_count_rule(self):
        """Measured on real data: 32 vs 45 asymmetry, 99% vs 81% coverage."""
        from collections import Counter

        def count_rule(points):
            w = points[-6:] if len(points) >= 6 else points
            hh = sum(1 for p in w if p["type"] == "hh")
            hl = sum(1 for p in w if p["type"] == "hl")
            lh = sum(1 for p in w if p["type"] == "lh")
            ll = sum(1 for p in w if p["type"] == "ll")
            if hh >= 2 and hl >= 1:
                return "bullish"
            if lh >= 2 and ll >= 1:
                return "bearish"
            if hh == 1 and hl == 1 and lh == 0 and ll == 0:
                return "bullish"
            if lh == 1 and ll == 1 and hh == 0 and hl == 0:
                return "bearish"
            return "neutral"

        candles = _zigzag(n=400)
        new, old = Counter(), Counter()
        for t in range(30, len(candles)):
            w = candles[:t + 1]
            piv = swing_highs_lows(w, STRUCTURE_LOOKBACK)
            if len(piv["highs"]) < 2 or len(piv["lows"]) < 2:
                continue
            pts = []
            hs, ls = piv["highs"], piv["lows"]
            for i in range(1, len(hs)):
                a, b = hs[i - 1], hs[i]
                pts.append({"index": b["index"], "type": "hh" if b["price"] > a["price"] else ("lh" if b["price"] < a["price"] else "eh")})
            for i in range(1, len(ls)):
                a, b = ls[i - 1], ls[i]
                pts.append({"index": b["index"], "type": "hl" if b["price"] > a["price"] else ("ll" if b["price"] < a["price"] else "el")})
            pts.sort(key=lambda p: p["index"])
            new[_classify_trend(pts)] += 1
            old[count_rule(pts)] += 1

        def asym(c):
            tot = c["bullish"] + c["bearish"]
            return abs(c["bullish"] / tot - c["bearish"] / tot) * 100 if tot else 100.0

        assert new["neutral"] < old["neutral"], "coverage should improve"
        assert asym(new) < asym(old), "directional bias should shrink"


class TestTrendHasNoPredictiveEdge:
    """Document the finding so nobody promotes the label to a signal.

    Measured on real data: 2.7 bps spread over 20 bars, t = 0.98, permutation
    p = 1.000. The label is a regime descriptor, not a conviction signal.
    """

    def test_label_is_a_descriptor_not_a_direction_call(self):
        """_determine_direction must still require a BOS or a liquidity sweep."""
        import inspect

        from app.ict_signal_generator import ICTSignalGenerator

        source = inspect.getsource(ICTSignalGenerator._determine_direction)
        assert "last_bos" in source or "bull_sweep" in source or "bear_sweep" in source, (
            "direction must be confirmed by a break or a sweep, not by the bias alone"
        )

    def test_short_series_returns_empty_rather_than_fake_structure(self):
        """Too few bars must yield neutral, never a fabricated swing."""
        gen = ICTSignalGenerator("EURUSD")
        st = gen._analyze_structure(_zigzag(n=6))
        assert st["trend"] == "neutral"
        assert st["last_bos"] is None

