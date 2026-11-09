"""/predict."""

from __future__ import annotations

_VALID = {
    "temperature_2m_max": 10.0,
    "temperature_2m_min": 5.0,
    "precipitation_sum": 0.0,
    "wind_speed_10m_max": 5.0,
    "latitude": 52.5,
    "longitude": 13.4,
}


def test_empty_records(client):
    assert client.post("/predict", json=[]).status_code == 422


def test_missing_features(client):
    r = client.post("/predict", json=[{"temperature_2m_max": 10}])
    assert r.status_code == 422


def test_no_model(client):
    assert client.post("/predict", json=[_VALID]).status_code == 503


def test_invalid_numeric(client_with_model):
    r = client_with_model.post("/predict", json=[{**_VALID, "temperature_2m_max": "abc"}])
    assert r.status_code == 422


def test_success(client_with_model):
    r = client_with_model.post("/predict", json=[_VALID, _VALID])
    assert r.status_code == 200
    preds = r.json()["predictions"]
    assert len(preds) == 2
    assert preds[0]["rain_tomorrow"] == 1
    assert preds[0]["rain_probability"] == 0.7
