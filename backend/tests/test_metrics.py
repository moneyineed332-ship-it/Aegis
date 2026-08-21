"""Tests for the metrics module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.metrics import Counter, Gauge, Histogram


def test_counter_increment():
    c = Counter("test_counter", "Test counter")
    c.labels().inc()
    assert c._values[()] == 1.0
    c.labels().inc()
    c.labels().inc(5)
    assert c._values[()] == 7.0


def test_counter_reset():
    c = Counter("test_counter2", "Test counter")
    c.labels().inc(10)
    c._values.clear()
    assert c._values.get((), 0) == 0


def test_gauge_set():
    g = Gauge("test_gauge", "Test gauge")
    g.labels().set(42)
    assert g._values[()] == 42.0
    g.labels().set(0)
    assert g._values[()] == 0.0


def test_histogram_observe():
    h = Histogram("test_histogram", "Test histogram")
    h.labels().observe(0.5)
    h.labels().observe(3)
    h.labels().observe(7)
    h.labels().observe(15)
    data = h._counts[()]
    bc = data["buckets"]
    assert bc["_count"] == 4
    assert bc["_sum"] == 25.5


def test_histogram_percentiles():
    h = Histogram("test_hist2", "Test histogram")
    for i in range(1, 101):
        h.labels().observe(float(i))
    data = h._counts[()]
    bc = data["buckets"]
    assert bc["_count"] == 100
    assert bc["_sum"] == 5050.0


def test_counter_with_labels():
    c = Counter("test_labeled", "Test", label_names=("method",))
    c.labels(method="GET").inc()
    c.labels(method="POST").inc(3)
    assert c._values[("GET",)] == 1.0
    assert c._values[("POST",)] == 3.0


def test_gauge_with_labels():
    g = Gauge("test_gauge_labels", "Test", label_names=("endpoint",))
    g.labels(endpoint="/api").set(100)
    g.labels(endpoint="/ws").set(50)
    assert g._values[("/api",)] == 100.0
    assert g._values[("/ws",)] == 50.0


def test_histogram_with_labels():
    h = Histogram("test_hist_labels", "Test", label_names=("method",))
    h.labels(method="GET").observe(0.1)
    h.labels(method="POST").observe(0.5)
    assert h._counts[("GET",)]["buckets"]["_count"] == 1
    assert h._counts[("POST",)]["buckets"]["_count"] == 1


def test_serialize_counter():
    c = Counter("test_ser_counter", "Test", label_names=("x",))
    c.labels(x="a").inc(5)
    text = c._serialize()
    assert "test_ser_counter" in text
    assert "counter" in text


def test_serialize_gauge():
    g = Gauge("test_ser_gauge", "Test")
    g.labels().set(42)
    text = g._serialize()
    assert "test_ser_gauge" in text
    assert "gauge" in text
    assert "42" in text


def test_serialize_histogram():
    h = Histogram("test_ser_hist", "Test")
    h.labels().observe(1.0)
    text = h._serialize()
    assert "test_ser_hist" in text
    assert "histogram" in text
