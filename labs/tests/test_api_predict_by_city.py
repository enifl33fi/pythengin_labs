"""/api/predict."""

from __future__ import annotations

import labs.api.main as main_module


def _fake_find_city(name: str) -> dict:
    return {"name": "Berlin", "country": "Germany", "latitude": 52.5, "longitude": 13.4}


def _fake_weather(lat: float, lon: float) -> dict:
    return {
        "today": {
            "temperature_2m_max": 20.0,
            "temperature_2m_min": 10.0,
            "precipitation_sum": 0.0,
            "wind_speed_10m_max": 5.0,
        },
        "tomorrow": {
            "date": "2026-11-10",
            "temperature_2m_max": 18.0,
            "temperature_2m_min": 8.0,
            "precipitation_sum": 0.5,
            "precipitation_probability_max": 40.0,
            "wind_speed_10m_max": 6.0,
        },
    }


def test_no_model(client):
    r = client.post("/api/predict", json={"city": "Berlin"})
    assert r.status_code == 503


def test_empty_city(client_with_model):
    assert client_with_model.post("/api/predict", json={"city": ""}).status_code == 422


def test_whitespace_city(client_with_model):
    assert client_with_model.post("/api/predict", json={"city": "   "}).status_code == 422


def test_city_not_found(monkeypatch, client_with_model):
    def boom(name):
        raise ValueError("not found")

    monkeypatch.setattr(main_module, "find_city", boom)
    r = client_with_model.post("/api/predict", json={"city": "Nowhere"})
    assert r.status_code == 404


def test_geocoding_error(monkeypatch, client_with_model):
    def boom(name):
        raise RuntimeError("network down")

    monkeypatch.setattr(main_module, "find_city", boom)
    r = client_with_model.post("/api/predict", json={"city": "Berlin"})
    assert r.status_code == 502


def test_weather_error(monkeypatch, client_with_model):
    monkeypatch.setattr(main_module, "find_city", _fake_find_city)

    def boom(lat, lon):
        raise RuntimeError("weather down")

    monkeypatch.setattr(main_module, "get_city_weather", boom)
    r = client_with_model.post("/api/predict", json={"city": "Berlin"})
    assert r.status_code == 502


def test_success(monkeypatch, client_with_model):
    monkeypatch.setattr(main_module, "find_city", _fake_find_city)
    monkeypatch.setattr(main_module, "get_city_weather", _fake_weather)
    r = client_with_model.post("/api/predict", json={"city": "Berlin"})
    assert r.status_code == 200
    data = r.json()
    assert data["city"]["name"] == "Berlin"
    assert data["prediction"]["rain_tomorrow"] == 1
    assert data["prediction"]["rain_probability"] == 0.7
