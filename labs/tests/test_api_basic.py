"""/, /health, /api/metrics."""

from __future__ import annotations

import json

import labs.api.main as main_module


def test_health_no_model(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["model_loaded"] is False
    assert body["model_source"] == "none"


def test_health_with_model(client_with_model):
    body = client_with_model.get("/health").json()
    assert body["model_loaded"] is True
    assert body["model_source"] == "uploaded"


def test_index_missing(monkeypatch, tmp_path, client):
    monkeypatch.setattr(main_module, "STATIC_DIR", tmp_path / "empty")
    r = client.get("/")
    assert r.status_code == 404


def test_index_ok(monkeypatch, tmp_path, client):
    (tmp_path / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    monkeypatch.setattr(main_module, "STATIC_DIR", tmp_path)
    r = client.get("/")
    assert r.status_code == 200


def test_metrics_missing(client):
    r = client.get("/api/metrics")
    assert r.status_code == 404


def test_metrics_invalid_json(monkeypatch, tmp_path, client):
    p = tmp_path / "metrics.json"
    p.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(main_module, "METRICS_PATH", p)
    r = client.get("/api/metrics")
    assert r.status_code == 500


def test_metrics_ok(monkeypatch, tmp_path, client):
    p = tmp_path / "metrics.json"
    p.write_text(json.dumps({"roc_auc": 0.85}), encoding="utf-8")
    monkeypatch.setattr(main_module, "METRICS_PATH", p)
    r = client.get("/api/metrics")
    assert r.status_code == 200
    assert r.json()["roc_auc"] == 0.85
