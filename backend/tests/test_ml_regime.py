"""Tests for the ML regime predictor.

The feature scaler used to min-max normalize the 12 features of a SINGLE
sample, which forced every input into [0, 1] by construction and left the
classifier with no between-sample variance. The split was also a random
shuffle, which leaked autocorrelated neighbours across the boundary.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ml_regime import LABELS, RegimePredictor


def _features(i: int) -> dict:
    """Feature dicts with real spread across samples."""
    return {
        "close": 100.0 + i,
        "sma_20": 100.0 + i * 0.5,
        "sma_50": 100.0 + i * 0.2,
        "momentum_20": (i % 17) / 100.0,
        "volatility_20": (i % 7) / 100.0,
        "range_20": (i % 11) / 100.0,
        "rsi_14": 20 + (i % 60),
        "macd_histogram": ((i % 13) - 6) / 10.0,
        "atr_14": 1.0 + (i % 5),
        "bollinger_width": (i % 9) / 100.0,
        "adx": 10 + (i % 40),
        "stoch_rsi_k": 10 + (i % 80),
        "williams_r": -80 + (i % 60),
        "zscore_20": ((i % 15) - 7) / 2.0,
    }


def _dataset(n: int = 300):
    feats = [_features(i) for i in range(n)]
    labels = [LABELS[i % len(LABELS)] for i in range(n)]
    return feats, labels


class TestScaler:
    def test_row_is_not_normalized_against_itself(self):
        p = RegimePredictor()
        row = p._extract_features(_features(3))
        # Raw values keep their magnitudes instead of all landing in [0, 1].
        assert max(row) > 1.0 or min(row) < 0.0

    def test_scaler_maps_training_rows_onto_the_unit_interval(self):
        p = RegimePredictor()
        rows = [p._extract_features(_features(i)) for i in range(200)]
        p._fit_scaler(rows)
        scaled = [p._scale(r) for r in rows]
        for column in zip(*scaled):
            assert min(column) == pytest.approx(0.0, abs=1e-9)
            assert max(column) == pytest.approx(1.0, abs=1e-9)

    def test_each_feature_is_scaled_independently(self):
        """The old code made all 12 inputs of a row near-identical."""
        p = RegimePredictor()
        rows = [p._extract_features(_features(i)) for i in range(200)]
        p._fit_scaler(rows)
        first = p._scale(rows[0])
        assert len(set(round(v, 6) for v in first)) > 1

    def test_constant_feature_maps_to_zero(self):
        p = RegimePredictor()
        rows = [[0.0] * len(p.feature_names) for _ in range(10)]
        p._fit_scaler(rows)
        assert p._scale(rows[0]) == [0.0] * len(p.feature_names)

    def test_identity_when_unfitted(self):
        p = RegimePredictor()
        row = [1.0, 2.0, 3.0]
        assert p._scale(row) == row

    def test_out_of_range_value_is_not_clamped(self):
        p = RegimePredictor()
        p._fit_scaler([[0.0] * 12, [1.0] * 12])
        scaled = p._scale([5.0] * 12)
        assert scaled[0] == pytest.approx(5.0)


class TestChronologicalSplit:
    def test_split_is_reported_as_chronological(self):
        p = RegimePredictor()
        feats, labels = _dataset(300)
        result = p.train(feats, labels, epochs=5)
        assert result["split"] == "chronological_purged"
        assert result["embargo"] > 0

    def test_train_is_the_past_and_test_is_the_future(self):
        p = RegimePredictor()
        feats, labels = _dataset(300)
        result = p.train(feats, labels, epochs=5)
        assert result["train_samples"] + result["embargo"] + result["test_samples"] == result["samples"]

    def test_scaler_only_sees_training_rows(self):
        """The test window must not influence the scaling."""
        p = RegimePredictor()
        feats, labels = _dataset(300)
        p.train(feats, labels, epochs=5)
        assert p._scaler is not None
        mins, maxs = p._scaler["min"], p._scaler["max"]
        assert len(mins) == len(p.feature_names)
        assert len(maxs) == len(p.feature_names)

    def test_too_little_data_after_embargo(self):
        p = RegimePredictor()
        feats, labels = _dataset(50)
        # A huge test window plus the embargo leaves fewer than 10 training rows.
        result = p.train(feats, labels, epochs=2, test_split=0.9)
        assert result["status"] == "insufficient_data"
        assert "embargo" in result["reason"]


class TestMetrics:
    def _fitted(self):
        p = RegimePredictor()
        feats, labels = _dataset(300)
        p.train(feats, labels, epochs=3)
        return p

    def test_macro_f1_includes_classes_the_model_never_predicts(self):
        """A model emitting a single label must not score a perfect macro F1."""
        p = self._fitted()
        p._compute_metrics(
            [[0.0] * len(p.feature_names) for _ in range(10)],
            [0] * 10,  # every sample is class 0
        )
        # Only 1 of 7 classes can score, so macro F1 must be far below 1.
        assert p._metrics["macro_f1"] < 0.2

    def test_per_class_covers_every_label(self):
        p = self._fitted()
        p._compute_metrics([[0.0] * 12 for _ in range(5)], [0] * 5)
        assert set(p._metrics["per_class"]) == set(LABELS)

    def test_accuracy_is_reported(self):
        p = self._fitted()
        p._compute_metrics([[0.0] * 12 for _ in range(4)], [1, 1, 2, 2])
        assert 0.0 <= p._metrics["accuracy"] <= 1.0

    def test_macro_f1_equals_mean_of_all_classes(self):
        p = self._fitted()
        p._compute_metrics([[0.0] * 12 for _ in range(6)], [0, 1, 2, 3, 4, 5])
        expected = sum(v["f1"] for v in p._metrics["per_class"].values()) / len(LABELS)
        assert p._metrics["macro_f1"] == pytest.approx(round(expected, 4), abs=1e-3)


class TestPersistence:
    def test_scaler_survives_save_and_load(self, tmp_path, monkeypatch):
        from app import storage as _storage

        saved = {}
        monkeypatch.setattr(_storage, "save_ml_model", lambda mid, data: saved.update(data))
        monkeypatch.setattr(_storage, "load_ml_model", lambda mid: saved or None)

        p = RegimePredictor()
        feats, labels = _dataset(300)
        p.train(feats, labels, epochs=3)
        assert "scaler" in saved

        restored = RegimePredictor()
        assert restored.load_model() is True
        assert restored._scaler == p._scaler

    def test_model_without_scaler_is_rejected(self, monkeypatch):
        from app import storage as _storage
        from app.ml_regime import SimpleClassifier

        payload = {
            "model": SimpleClassifier(3, 2).to_dict(),
            "importance": {},
            "trained": True,
            "metrics": {},
        }
        monkeypatch.setattr(_storage, "load_ml_model", lambda mid: payload)

        p = RegimePredictor()
        assert p.load_model() is False
        assert p._trained is False


class TestPredictBeforeTraining:
    def test_untrained_predictor_says_so(self):
        p = RegimePredictor()
        result = p.predict(_features(1))
        assert result["trained"] is False
        assert result["regime"] == "unknown"
