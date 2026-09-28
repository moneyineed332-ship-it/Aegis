"""Engine state must not cross the mode boundary.

Both pipelines write the same in-memory variables -- the ICT path sets
_last_signal with strategy "ict_smc", the legacy path with the Donchian
strategy -- and both persist to the same engine_state keys. Without a mode tag a
crypto run hands its state to a Forex run.

Reproduced before the fix: an ICT run reporting
  last_signal      = {"symbol": "ETHUSDT", "strategy": "donchian_breakout_long_flat"}
  last_smc_analysis keyed by PAXGUSDT / BTCUSDT / ETHUSDT
  symbols          = ["EURUSD", "GBPUSD", "XAUUSD"]
so a Forex bot quoted a crypto trade it never made.

Status, started_at, circuit_breaker and the ICT risk/position state are NOT
scoped: a risk lock must survive a restart and a mode change.
"""

import inspect
import json

import pytest

from app import engine


@pytest.fixture
def clean_globals(monkeypatch):
    monkeypatch.setattr(engine, "_last_prices", {}, raising=False)
    monkeypatch.setattr(engine, "_last_signal", None, raising=False)
    monkeypatch.setattr(engine, "_last_analyses", {}, raising=False)
    monkeypatch.setattr(engine, "_last_smc_analysis", {}, raising=False)
    monkeypatch.setattr(engine, "_last_mtf_analysis", {}, raising=False)
    monkeypatch.setattr(engine, "_last_ict_signals", {}, raising=False)
    return True


class TestStateKeysAreScopedByMode:
    def test_key_carries_the_mode(self, monkeypatch):
        monkeypatch.setattr(engine.config, "ICT_MODE", True)
        assert engine._scoped_state_key("last_signal") == "last_signal::ict"
        monkeypatch.setattr(engine.config, "ICT_MODE", False)
        assert engine._scoped_state_key("last_signal") == "last_signal::legacy"

    def test_globals_are_never_persisted_unscoped(self):
        """A regression here re-opens the contamination.

        The key is checked as the *direct* first argument of set_engine_state,
        because the literal also appears inside _scoped_state_key(...) calls.
        """
        src = inspect.getsource(engine._save_state)
        for key in engine._MODE_SCOPED_STATE_KEYS:
            direct = f'set_engine_state("{key}"'
            assert direct not in src, f"{key} is still written unscoped"
            scoped = f'set_engine_state(_scoped_state_key("{key}")'
            assert scoped in src, f"{key} is not written under the mode-scoped key"
        assert 'storage.set_engine_state("cycle_count"' in src, (
            "cycle_count is a diagnostic and stays unscoped on purpose"
        )

    def test_restore_only_reads_scoped_keys(self):
        src = inspect.getsource(engine._restore_state)
        for key in engine._MODE_SCOPED_STATE_KEYS:
            assert f'get_engine_state("{key}")' not in src, f"{key} is still read unscoped"


class TestLegacyStateIsDiscardedNotInherited:
    def test_unscoped_state_is_deleted_on_restore(self, monkeypatch, clean_globals):
        seen: dict = {}

        def fake_get(name):
            if name == "last_signal":
                return json.dumps({"symbol": "ETHUSDT", "strategy": "donchian_breakout_long_flat"})
            if name in ("last_analyses", "last_smc_analysis", "last_mtf_analysis", "last_ict_signals"):
                return json.dumps({"PAXGUSDT": {}})
            return None

        def fake_delete(name):
            seen.setdefault("deleted", []).append(name)

        monkeypatch.setattr(engine.storage, "get_engine_state", fake_get)
        monkeypatch.setattr(engine.storage, "delete_engine_state", fake_delete)
        monkeypatch.setattr(engine.storage, "list_active_trailing_stops", lambda: [])
        monkeypatch.setattr(engine, "_restore_trailing_stops_from_db", lambda: None, raising=False)
        monkeypatch.setattr(engine.config, "ICT_MODE", True)

        engine._restore_state()

        assert "last_signal" in seen.get("deleted", []), "stale unscoped state was not retired"
        # And none of it reached the in-memory variables.
        assert engine._last_signal is None
        assert engine._last_smc_analysis == {}
        assert engine._last_analyses == {}
        assert engine._last_prices == {}

    def test_mode_change_wipes_partial_state_even_with_nothing_in_db(self, monkeypatch):
        """A leftover in-process value must not survive a restore either."""
        monkeypatch.setattr(engine, "_last_signal", {"symbol": "ETHUSDT"}, raising=False)
        monkeypatch.setattr(engine, "_last_smc_analysis", {"BTCUSDT": {}}, raising=False)
        monkeypatch.setattr(engine.storage, "get_engine_state", lambda name: None)
        monkeypatch.setattr(engine.storage, "delete_engine_state", lambda name: None)
        monkeypatch.setattr(engine, "_restore_trailing_stops_from_db", lambda: None, raising=False)
        monkeypatch.setattr(engine.config, "ICT_MODE", True)

        engine._restore_state()
        assert engine._last_signal is None
        assert engine._last_smc_analysis == {}


class TestStatusExposesOnlyCurrentMode:
    def test_status_symbols_match_the_engine_universe(self, monkeypatch):
        """Status and the analysis loop must resolve the universe the same way."""
        monkeypatch.setattr(engine.config, "ICT_MODE", True)
        monkeypatch.setattr(engine.config, "ICT_SYMBOLS", ["EURUSD", "GBPUSD", "XAUUSD"])
        monkeypatch.setattr(engine, "_last_signal", None, raising=False)
        status = engine.get_engine_status()
        assert status["symbols"] == list(engine.config.resolve_symbols())
        assert status["symbols"] == ["EURUSD", "GBPUSD", "XAUUSD"]

    def test_legacy_status_reports_crypto(self, monkeypatch):
        monkeypatch.setattr(engine.config, "ICT_MODE", False)
        monkeypatch.setattr(engine.config, "FOCUSED_MODE", True)
        monkeypatch.setattr(engine.config, "FOCUSED_SYMBOLS", ["PAXGUSDT", "BTCUSDT", "ETHUSDT"])
        status = engine.get_engine_status()
        assert status["symbols"] == ["PAXGUSDT", "BTCUSDT", "ETHUSDT"]

    def test_ict_run_never_reports_a_crypto_signal(self, monkeypatch):
        monkeypatch.setattr(engine.config, "ICT_MODE", True)
        monkeypatch.setattr(engine, "_last_signal", None, raising=False)
        status = engine.get_engine_status()
        signal = status.get("last_signal") or {}
        if signal:
            assert signal.get("symbol") in ("EURUSD", "GBPUSD", "XAUUSD"), (
                f"ICT status reports {signal.get('symbol')}"
            )
            assert signal.get("recommendation", {}).get("strategy") == "ict_smc"


class TestAnalysisDictionariesAreRebuilt:
    """A symbol leaving the universe must not keep its last analysis."""

    def test_cycle_clears_the_keyed_dicts(self):
        src = inspect.getsource(engine.task_fetch_analysis)
        body = src.split("for symbol in symbols:")[0]
        assert "_last_smc_analysis.clear()" in body
        assert "_last_mtf_analysis.clear()" in body
        assert "_last_analyses.clear()" in body

    def test_clear_happens_before_the_symbol_loop(self):
        src = inspect.getsource(engine.task_fetch_analysis)
        clears = [ln for ln in src.splitlines() if ln.strip().endswith(".clear()")]
        loop_at = src.index("for symbol in symbols:")
        for ln in clears:
            assert src.index(ln) < loop_at, f"clear after the loop: {ln.strip()}"


class TestFailSafeStateIsNotScoped:
    """These must keep working across restarts and mode changes."""

    @pytest.mark.parametrize("key", ["status", "started_at", "stopped_at", "circuit_breaker"])
    def test_not_in_the_scoped_set(self, key):
        assert key not in engine._MODE_SCOPED_STATE_KEYS

    def test_ict_risk_state_keeps_its_own_key(self):
        src = inspect.getsource(engine._save_state)
        assert "_ict_risk_manager.save_state()" in src
        assert "_ict_position_manager.save_state()" in src


class TestRegimeHysteresisIsPerInstrument:
    """Global state leaking between symbols, the same family as mode leaking.

    regime.classify kept its hysteresis in one module global, so one symbol's
    regime was decided partly by whatever the previous symbol was classified as.
    Calling it in sequence for the three correlated pairs EURUSD/GBPUSD/XAUUSD
    let the first call's high-confidence regime override the others.
    """

    @pytest.fixture(autouse=True)
    def _clear_hysteresis(self, monkeypatch):
        from app import regime

        monkeypatch.setattr(regime, "_HYSTERESIS", {}, raising=False)
        monkeypatch.setattr(regime, "_prev_regime", None, raising=False)
        monkeypatch.setattr(regime, "_prev_confidence", 0.0, raising=False)

    BULLISH = {"adx": 35, "rsi_14": 60, "sma_ratio": 0.05, "momentum_20": 0.05, "volatility_20": 0.01}
    WEAK = {"rsi_14": 50, "adx": 12, "momentum_20": 0.0, "volatility_20": 0.004, "atr_14": 0.5, "close": 100}

    def test_one_symbol_cannot_override_another(self):
        from app import regime

        first = regime.classify(self.BULLISH, symbol="EURUSD")
        second = regime.classify(self.WEAK, symbol="GBPUSD")
        assert first["regime"] == "bull_trend"
        assert second["regime"] != "bull_trend", "GBPUSD inherited EURUSD's regime"
        assert second["is_choppy"] is True

    def test_hysteresis_still_works_within_one_instrument(self):
        from app import regime

        regime.classify(self.WEAK, symbol="XAUUSD")
        assert "XAUUSD" in regime._HYSTERESIS, "per-instrument state was not recorded"

    def test_confidence_stays_within_bounds(self):
        """The range fallback produced confidence -1.7 with no moving average."""
        from app import regime

        no_ma = {"rsi_14": 50, "adx": 12, "close": 100, "atr_14": 0.5}
        result = regime.classify(no_ma, symbol="EURUSD")
        assert 0.0 <= result["confidence"] <= 1.0
        assert all(0.0 <= p <= 1.0 for p in result["probabilities"].values())

    def test_answer_does_not_depend_on_another_instrument(self):
        from app import regime

        clean = regime.classify(self.WEAK, symbol="EURUSD")
        regime.classify(self.BULLISH, symbol="GBPUSD")
        after = regime.classify(self.WEAK, symbol="EURUSD")
        assert after["regime"] == clean["regime"]

    def test_conftest_resets_hysteresis_between_tests(self):
        """Otherwise the suite stays order-dependent, which is how this surfaced."""
        import inspect as _inspect

        src = _inspect.getsource(
            __import__("tests.conftest", fromlist=["_isolated_db"])._isolated_db
        )
        assert "_HYSTERESIS.clear()" in src
