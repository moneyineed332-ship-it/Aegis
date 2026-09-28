"""Two gaps in the ICT position handling, both found by the local audit.

1. The take-profit was the FARTHEST liquidity pool, not the nearest.

   The generator took levels[0]. liquidity_zones() returns zones in the order
   swing_highs_lows() produced them, which is chronological, so [0] was the
   oldest qualifying level: the farthest one whenever price had risen into the
   structure. Measured over 327 rolling windows on EURUSD/GBPUSD/XAUUSD 15m it
   was the nearest level 30 times (9 %), the farthest 231 (71 %), and in 91 of
   125 rising windows it was the farthest.

   That is backwards: price is drawn to the first pool it reaches.

2. Modes B, C and D were implemented but unreachable.

   PositionManager implements all four handlers, but the engine constructed it
   with the default mode and nothing ever called set_mode, so a running bot
   could only ever manage positions in mode A.
"""

import pytest

from app.ict_signal_generator import _nearest_liquidity_target


class TestNearestLiquidityTarget:
    def test_long_takes_the_closest_level_above(self):
        assert _nearest_liquidity_target([1.1410, 1.1450, 1.1500], 1.1370, "buy") == 1.1410

    def test_short_takes_the_closest_level_below(self):
        assert _nearest_liquidity_target([1.1350, 1.1300, 1.1250], 1.1370, "sell") == 1.1350

    def test_chronological_order_does_not_decide(self):
        """The old code returned the first element; order must not matter."""
        ascending = _nearest_liquidity_target([1.1400, 1.1420, 1.1500], 1.1370, "buy")
        descending = _nearest_liquidity_target([1.1500, 1.1420, 1.1400], 1.1370, "buy")
        assert ascending == descending == 1.1400

    def test_levels_behind_entry_are_ignored(self):
        assert _nearest_liquidity_target([1.1300, 1.1350], 1.1370, "buy") is None
        assert _nearest_liquidity_target([1.1400, 1.1450], 1.1370, "sell") is None

    def test_no_levels_returns_none_so_the_rr_fallback_engages(self):
        assert _nearest_liquidity_target([], 1.1370, "buy") is None

    def test_handles_dicts_and_plain_numbers(self):
        assert _nearest_liquidity_target([{"price": 1.1400}, {"price": 1.1420}], 1.1370, "buy") == 1.1400
        assert _nearest_liquidity_target([1.1400, 1.1420], 1.1370, "buy") == 1.1400

    def test_skips_missing_prices(self):
        assert _nearest_liquidity_target([None, {"price": 1.1400}], 1.1370, "buy") == 1.1400

    def test_exactly_at_entry_is_not_a_target(self):
        assert _nearest_liquidity_target([1.1370, 1.1400], 1.1370, "buy") == 1.1400

    def test_generator_no_longer_indexes_the_list(self):
        from app.ict_signal_generator import ICTSignalGenerator

        source = __import__("inspect").getsource(ICTSignalGenerator)
        assert '_nearest_liquidity_target(' in source
        for pattern in ('buy_liq[0]', 'sell_liq[0]',
                        'buy_side_liquidity", [])[0].get("price"',
                        'sell_side_liquidity", [])[0].get("price"'):
            assert pattern not in source, f"the generator still uses {pattern}"


class TestPositionModeIsSelectable:
    def test_config_exposes_the_mode(self):
        from app import config

        assert config.ICT_POSITION_MODE in (
            "fixed_tp", "partial", "breakeven", "trailing_structural"
        )

    def test_engine_builds_the_manager_with_the_configured_mode(self, monkeypatch):
        import inspect as _inspect

        from app import engine

        source = _inspect.getsource(engine._init_ict_pipeline)
        assert "mode=config.ICT_POSITION_MODE" in source

    def test_every_mode_has_a_handler(self):
        from app.position_manager import PositionManager

        for handler in ("_handle_fixed_tp_mode", "_handle_partial_mode",
                        "_handle_breakeven_mode", "_handle_trailing_mode"):
            assert hasattr(PositionManager, handler), f"{handler} is missing"

    def test_set_mode_accepts_each_mode(self):
        from app.position_manager import PositionManager

        pm = PositionManager()
        for mode in ("fixed_tp", "partial", "breakeven", "trailing_structural"):
            pm.set_mode(mode)
            assert pm.mode == mode

    def test_mode_endpoints_exist_and_require_a_token(self):
        from fastapi.routing import APIRoute
        from fastapi.testclient import TestClient
        from app.main import app

        routes = {r.path for r in app.routes if isinstance(r, APIRoute)}
        assert "/api/ict/dashboard/position-mode" in routes
        client = TestClient(app)
        assert client.get("/api/ict/dashboard/position-mode").status_code == 401
        assert client.post("/api/ict/dashboard/position-mode", json={}).status_code == 401
