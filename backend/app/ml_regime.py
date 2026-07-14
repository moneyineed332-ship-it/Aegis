"""ML regime prediction model with feature importance and SHAP explanations."""

import math
from statistics import fmean, pstdev


LABELS = ["bull_trend", "bear_trend", "range", "high_volatility", "low_volatility", "capitulation", "euphoria"]


def _normalize(values: list[float]) -> list[float]:
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return [0.5] * len(values)
    return [(v - min_val) / (max_val - min_val) for v in values]


def _sigmoid(x: float) -> float:
    x = max(-500, min(500, x))
    return 1 / (1 + math.exp(-x))


class SimpleClassifier:
    """Lightweight logistic regression classifier (no sklearn dependency)."""

    def __init__(self, n_features: int, n_classes: int, learning_rate: float = 0.01):
        self.weights = [[0.0] * n_features for _ in range(n_classes)]
        self.biases = [0.0] * n_classes
        self.lr = learning_rate
        self.n_features = n_features
        self.n_classes = n_classes
        self._fitted = False

    def _softmax(self, logits: list[float]) -> list[float]:
        max_logit = max(logits)
        exps = [math.exp(x - max_logit) for x in logits]
        total = sum(exps)
        return [e / total for e in exps]

    def predict_proba(self, x: list[float]) -> dict[str, float]:
        logits = []
        for c in range(self.n_classes):
            logit = self.biases[c]
            for i in range(self.n_features):
                logit += self.weights[c][i] * x[i]
            logits.append(logit)
        probs = self._softmax(logits)
        return {LABELS[i]: round(probs[i], 6) for i in range(min(len(LABELS), self.n_classes))}

    def fit(self, X: list[list[float]], y: list[int], epochs: int = 100):
        for _ in range(epochs):
            for x, label in zip(X, y):
                probs = self._softmax([
                    sum(self.weights[c][i] * x[i] for i in range(self.n_features)) + self.biases[c]
                    for c in range(self.n_classes)
                ])
                for c in range(self.n_classes):
                    error = (1 if c == label else 0) - probs[c]
                    for i in range(self.n_features):
                        self.weights[c][i] += self.lr * error * x[i]
                    self.biases[c] += self.lr * error
        self._fitted = True


class RegimePredictor:
    """ML-based regime prediction with feature importance."""

    def __init__(self):
        self.model: SimpleClassifier | None = None
        self.feature_names = [
            "sma_ratio", "momentum", "volatility", "range_ratio",
            "rsi", "macd_hist", "atr_ratio", "bollinger_width",
        ]
        self._importance: dict[str, float] = {}
        self._trained = False

    def _extract_features(self, features: dict) -> list[float]:
        sma_ratio = features.get("sma_20", 0) / max(features.get("sma_50", 1), 1) - 1
        momentum = features.get("momentum_20", 0)
        volatility = features.get("volatility_20", 0)
        range_ratio = features.get("range_20", 0)
        rsi = (features.get("rsi_14", 50) - 50) / 50
        macd_hist = features.get("macd_histogram", 0)
        close = features.get("close", 1)
        atr_ratio = features.get("atr_14", 0) / max(close, 1)
        bollinger_upper = features.get("bollinger_upper", close)
        bollinger_lower = features.get("bollinger_lower", close)
        bollinger_width = (bollinger_upper - bollinger_lower) / max(close, 1)

        return _normalize([
            sma_ratio, momentum, volatility, range_ratio,
            rsi, macd_hist, atr_ratio, bollinger_width,
        ])

    def train(self, feature_sets: list[dict], regime_labels: list[str], epochs: int = 200):
        """Train the classifier on historical feature/label pairs."""
        if len(feature_sets) < 20:
            return {"status": "insufficient_data", "min_required": 20, "provided": len(feature_sets)}

        X = [self._extract_features(f) for f in feature_sets]
        label_to_idx = {label: i for i, label in enumerate(LABELS)}
        y = [label_to_idx.get(r, 5) for r in regime_labels]

        self.model = SimpleClassifier(len(self.feature_names), len(LABELS))
        self.model.fit(X, y, epochs=epochs)

        self._compute_importance(X, y)
        self._trained = True
        return {"status": "trained", "samples": len(X), "features": len(self.feature_names)}

    def _compute_importance(self, X: list[list[float]], y: list[int]):
        """Compute feature importance via weight magnitude."""
        if not self.model:
            return
        importances = [0.0] * self.n_features
        for c in range(self.model.n_classes):
            for i in range(self.model.n_features):
                importances[i] += abs(self.model.weights[c][i])
        total = sum(importances) or 1
        self._importance = {
            name: round(imp / total, 4)
            for name, imp in zip(self.feature_names, importances)
        }

    @property
    def n_features(self):
        return len(self.feature_names)

    def predict(self, features: dict) -> dict:
        """Predict regime from current market features."""
        if not self._trained or not self.model:
            return {
                "regime": "unknown",
                "confidence": 0,
                "probabilities": {r: 1 / len(LABELS) for r in LABELS},
                "feature_importance": self._importance,
                "shap_values": {},
                "trained": False,
            }

        x = self._extract_features(features)
        probs = self.model.predict_proba(x)

        best_regime = max(probs, key=probs.get)

        shap_values = self._compute_shap(features, x)

        return {
            "regime": best_regime,
            "confidence": round(probs[best_regime], 4),
            "probabilities": probs,
            "feature_importance": self._importance,
            "shap_values": shap_values,
            "trained": True,
        }

    def _compute_shap(self, features: dict, x: list[float]) -> dict[str, float]:
        """Compute simplified SHAP-like values (feature contribution to prediction)."""
        if not self.model:
            return {}

        label_to_idx = {label: i for i, label in enumerate(LABELS)}
        best_idx = 0
        best_prob = 0
        probs = self.model.predict_proba(x)
        for label, prob in probs.items():
            if prob > best_prob:
                best_prob = prob
                best_idx = label_to_idx.get(label, 0)

        shap_values = {}
        for i, name in enumerate(self.feature_names):
            contribution = self.model.weights[best_idx][i] * x[i]
            shap_values[name] = round(contribution, 6)

        total_abs = sum(abs(v) for v in shap_values.values()) or 1
        shap_values = {k: round(v / total_abs, 4) for k, v in shap_values.items()}
        return shap_values

    def summary(self) -> dict:
        return {
            "trained": self._trained,
            "n_features": len(self.feature_names),
            "feature_names": self.feature_names,
            "feature_importance": self._importance,
            "n_classes": len(LABELS),
            "classes": LABELS,
        }


predictor = RegimePredictor()
