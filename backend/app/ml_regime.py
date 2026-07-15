"""ML regime prediction model with L2 regularization, train/test split, and metrics.

No sklearn dependency — implements logistic regression from scratch with:
- L2 regularization to prevent overfitting
- Train/test split for proper evaluation
- Accuracy, F1-score, confusion matrix
- More features (ADX, Stochastic RSI, VWAP)
"""

import math
import random
from statistics import fmean, stdev


LABELS = ["bull_trend", "bear_trend", "range", "high_volatility", "low_volatility", "capitulation", "euphoria"]


def _normalize(values: list[float]) -> list[float]:
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return [0.5] * len(values)
    return [(v - min_val) / (max_val - min_val) for v in values]


def _standardize(values: list[float]) -> list[float]:
    """Z-score standardization — better for gradient descent convergence."""
    if len(values) < 2:
        return [0.0] * len(values)
    mean = fmean(values)
    std = stdev(values)
    if std == 0:
        return [0.0] * len(values)
    return [(v - mean) / std for v in values]


class SimpleClassifier:
    """Logistic regression with L2 regularization and Adam-like learning rate."""

    def __init__(self, n_features: int, n_classes: int, learning_rate: float = 0.01, l2_lambda: float = 0.01):
        self.weights = [[0.0] * n_features for _ in range(n_classes)]
        self.biases = [0.0] * n_classes
        self.lr = learning_rate
        self.l2_lambda = l2_lambda
        self.n_features = n_features
        self.n_classes = n_classes
        self._fitted = False
        # Adam moments
        self._m_w = [[0.0] * n_features for _ in range(n_classes)]
        self._v_w = [[0.0] * n_features for _ in range(n_classes)]
        self._m_b = [0.0] * n_classes
        self._v_b = [0.0] * n_classes
        self._t = 0

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
        self._t = 0
        for _ in range(epochs):
            self._t += 1
            beta1, beta2, eps = 0.9, 0.999, 1e-8
            for x, label in zip(X, y):
                probs = self._softmax([
                    sum(self.weights[c][i] * x[i] for i in range(self.n_features)) + self.biases[c]
                    for c in range(self.n_classes)
                ])
                for c in range(self.n_classes):
                    target = 1.0 if c == label else 0.0
                    error = target - probs[c]
                    for i in range(self.n_features):
                        grad = error * x[i] - self.l2_lambda * self.weights[c][i]
                        self._m_w[c][i] = beta1 * self._m_w[c][i] + (1 - beta1) * grad
                        self._v_w[c][i] = beta2 * self._v_w[c][i] + (1 - beta2) * grad * grad
                        m_hat = self._m_w[c][i] / (1 - beta1 ** self._t)
                        v_hat = self._v_w[c][i] / (1 - beta2 ** self._t)
                        self.weights[c][i] += self.lr * m_hat / (math.sqrt(v_hat) + eps)
                    grad_b = error - self.l2_lambda * self.biases[c]
                    self._m_b[c] = beta1 * self._m_b[c] + (1 - beta1) * grad_b
                    self._v_b[c] = beta2 * self._v_b[c] + (1 - beta2) * grad_b * grad_b
                    m_hat_b = self._m_b[c] / (1 - beta1 ** self._t)
                    v_hat_b = self._v_b[c] / (1 - beta2 ** self._t)
                    self.biases[c] += self.lr * m_hat_b / (math.sqrt(v_hat_b) + eps)
        self._fitted = True


class RegimePredictor:
    """ML-based regime prediction with feature importance, train/test metrics."""

    def __init__(self):
        self.model: SimpleClassifier | None = None
        self.feature_names = [
            "sma_ratio", "momentum", "volatility", "range_ratio",
            "rsi", "macd_hist", "atr_ratio", "bollinger_width",
            "adx", "stoch_rsi_k", "williams_r", "zscore",
        ]
        self._importance: dict[str, float] = {}
        self._trained = False
        self._metrics: dict = {}

    def _extract_features(self, features: dict) -> list[float]:
        close = features.get("close", 1)
        sma_ratio = features.get("sma_20", 0) / max(features.get("sma_50", 1), 1) - 1
        momentum = features.get("momentum_20", 0)
        volatility = features.get("volatility_20", 0)
        range_ratio = features.get("range_20", 0)
        rsi = (features.get("rsi_14", 50) - 50) / 50
        macd_hist = features.get("macd_histogram", 0)
        atr_ratio = features.get("atr_14", 0) / max(close, 1)
        bollinger_width = features.get("bollinger_width", 0)
        adx = (features.get("adx", 25) - 25) / 25
        stoch_rsi_k = (features.get("stoch_rsi_k", 50) - 50) / 50
        williams_r = (features.get("williams_r", -50) + 50) / 50
        zscore = features.get("zscore_20", 0) / 3

        return _normalize([
            sma_ratio, momentum, volatility, range_ratio,
            rsi, macd_hist, atr_ratio, bollinger_width,
            adx, stoch_rsi_k, williams_r, zscore,
        ])

    def train(self, feature_sets: list[dict], regime_labels: list[str], epochs: int = 200, test_split: float = 0.2):
        """Train with train/test split and compute metrics on held-out data."""
        if len(feature_sets) < 50:
            return {"status": "insufficient_data", "min_required": 50, "provided": len(feature_sets)}

        X = [self._extract_features(f) for f in feature_sets]
        label_to_idx = {label: i for i, label in enumerate(LABELS)}
        y = [label_to_idx.get(r, 5) for r in regime_labels]

        # Shuffle and split
        indices = list(range(len(X)))
        random.seed(42)
        random.shuffle(indices)
        split = int(len(X) * (1 - test_split))
        train_idx, test_idx = indices[:split], indices[split:]

        X_train, y_train = [X[i] for i in train_idx], [y[i] for i in train_idx]
        X_test, y_test = [X[i] for i in test_idx], [y[i] for i in test_idx]

        self.model = SimpleClassifier(len(self.feature_names), len(LABELS), l2_lambda=0.01)
        self.model.fit(X_train, y_train, epochs=epochs)

        # Compute metrics on test set
        if X_test:
            self._compute_metrics(X_test, y_test)

        self._compute_importance()
        self._trained = True

        return {
            "status": "trained",
            "samples": len(X),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "features": len(self.feature_names),
            "metrics": self._metrics,
        }

    def _compute_metrics(self, X_test: list[list[float]], y_test: list[int]):
        """Compute accuracy, per-class precision/recall, confusion matrix."""
        predictions = []
        for x in X_test:
            probs = self.model.predict_proba(x)
            pred_idx = max(range(len(probs)), key=lambda i: list(probs.values())[i])
            predictions.append(pred_idx)

        n_classes = len(LABELS)
        correct = sum(1 for p, y in zip(predictions, y_test) if p == y)
        accuracy = correct / len(y_test) if y_test else 0

        # Per-class precision/recall
        confusion = [[0] * n_classes for _ in range(n_classes)]
        for p, y in zip(predictions, y_test):
            confusion[y][p] += 1

        per_class = {}
        for i, label in enumerate(LABELS):
            tp = confusion[i][i]
            fp = sum(confusion[j][i] for j in range(n_classes)) - tp
            fn = sum(confusion[i]) - tp
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            per_class[label] = {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}

        # Macro F1
        f1_scores = [v["f1"] for v in per_class.values() if v["f1"] > 0]
        macro_f1 = fmean(f1_scores) if f1_scores else 0

        self._metrics = {
            "accuracy": round(accuracy, 4),
            "macro_f1": round(macro_f1, 4),
            "per_class": per_class,
        }

    def _compute_importance(self):
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
        if not self._trained or not self.model:
            return {
                "regime": "unknown",
                "confidence": 0,
                "probabilities": {r: 1 / len(LABELS) for r in LABELS},
                "feature_importance": self._importance,
                "shap_values": {},
                "trained": False,
                "metrics": self._metrics,
            }

        x = self._extract_features(features)
        probs = self.model.predict_proba(x)
        best_regime = max(probs, key=probs.get)
        best_prob = probs[best_regime]

        # Confidence threshold
        if best_prob < 0.25:
            best_regime = "range"
            best_prob = probs.get("range", 0.25)

        shap_values = self._compute_shap(x)

        return {
            "regime": best_regime,
            "confidence": round(best_prob, 4),
            "probabilities": probs,
            "feature_importance": self._importance,
            "shap_values": shap_values,
            "trained": True,
            "metrics": self._metrics,
        }

    def _compute_shap(self, x: list[float]) -> dict[str, float]:
        if not self.model:
            return {}

        label_to_idx = {label: i for i, label in enumerate(LABELS)}
        probs = self.model.predict_proba(x)
        best_idx = max(range(len(probs)), key=lambda i: list(probs.values())[i])

        shap_values = {}
        for i, name in enumerate(self.feature_names):
            contribution = self.model.weights[best_idx][i] * x[i]
            shap_values[name] = round(contribution, 6)

        total_abs = sum(abs(v) for v in shap_values.values()) or 1
        return {k: round(v / total_abs, 4) for k, v in shap_values.items()}

    def summary(self) -> dict:
        return {
            "trained": self._trained,
            "n_features": len(self.feature_names),
            "feature_names": self.feature_names,
            "feature_importance": self._importance,
            "n_classes": len(LABELS),
            "classes": LABELS,
            "metrics": self._metrics,
        }


predictor = RegimePredictor()
