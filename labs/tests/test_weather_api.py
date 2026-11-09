"""Unit-тесты weather_api."""

from __future__ import annotations

import httpx
import pytest

from labs.sources.weather_api import (
    find_city,
    get_city_weather,
    request_json,
)


class _FakeResponse:
    def __init__(self, payload, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._payload


# ---------- request_json ----------


def test_request_json_ok(monkeypatch):
    monkeypatch.setattr(
        "labs.sources.weather_api.httpx.get",
        lambda *a, **kw: _FakeResponse({"ok": True}),
    )
    assert request_json("u", {}) == {"ok": True}


def test_request_json_non_dict(monkeypatch):
    monkeypatch.setattr(
        "labs.sources.weather_api.httpx.get",
        lambda *a, **kw: _FakeResponse([1, 2, 3]),
    )
    with pytest.raises(ValueError, match="неожиданном формате"):
        request_json("u", {})


def test_request_json_retries_then_success(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectTimeout("slow")
        return _FakeResponse({"ok": True})

    monkeypatch.setattr("labs.sources.weather_api.httpx.get", fake_get)
    monkeypatch.setattr("labs.sources.weather_api.time.sleep", lambda s: None)
    assert request_json("u", {}) == {"ok": True}
    assert calls["n"] == 2


def test_request_json_all_fail(monkeypatch):
    def fake_get(*a, **kw):
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr("labs.sources.weather_api.httpx.get", fake_get)
    monkeypatch.setattr("labs.sources.weather_api.time.sleep", lambda s: None)
    with pytest.raises(httpx.ConnectTimeout):
        request_json("u", {})


# ---------- find_city ----------


def test_find_city_ok(monkeypatch):
    monkeypatch.setattr(
        "labs.sources.weather_api.request_json",
        lambda url, params: {
            "results": [
                {
                    "name": "Berlin",
                    "country": "Germany",
                    "latitude": 52.5,
                    "longitude": 13.4,
                }
            ]
        },
    )
    city = find_city("Berlin")
    assert city["name"] == "Berlin"
    assert city["latitude"] == 52.5


def test_find_city_empty_name():
    with pytest.raises(ValueError, match="не может быть пустым"):
        find_city("   ")


def test_find_city_not_found(monkeypatch):
    monkeypatch.setattr(
        "labs.sources.weather_api.request_json",
        lambda url, params: {},
    )
    with pytest.raises(ValueError, match="не найден"):
        find_city("Nowhere")


def test_find_city_http_error(monkeypatch):
    def boom(url, params):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("labs.sources.weather_api.request_json", boom)
    with pytest.raises(RuntimeError):
        find_city("Berlin")


# ---------- get_city_weather ----------


def _daily() -> dict:
    return {
        "time": ["2026-11-09", "2026-11-10"],
        "temperature_2m_max": [20.0, 18.0],
        "temperature_2m_min": [10.0, 8.0],
        "precipitation_sum": [0.0, 0.5],
        "precipitation_probability_max": [5, 40],
        "wind_speed_10m_max": [5.0, 6.0],
    }


def test_get_city_weather_ok(monkeypatch):
    monkeypatch.setattr(
        "labs.sources.weather_api.request_json",
        lambda url, params: {"daily": _daily()},
    )
    data = get_city_weather(52.5, 13.4)
    assert data["today"]["temperature_2m_max"] == 20.0
    assert data["tomorrow"]["temperature_2m_max"] == 18.0


def test_get_city_weather_http_error(monkeypatch):
    def boom(url, params):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("labs.sources.weather_api.request_json", boom)
    with pytest.raises(RuntimeError):
        get_city_weather(52.5, 13.4)


def test_get_city_weather_no_daily(monkeypatch):
    monkeypatch.setattr(
        "labs.sources.weather_api.request_json",
        lambda url, params: {},
    )
    with pytest.raises(ValueError, match="ежедневного прогноза"):
        get_city_weather(52.5, 13.4)


def test_get_city_weather_short_dates(monkeypatch):
    monkeypatch.setattr(
        "labs.sources.weather_api.request_json",
        lambda url, params: {"daily": {"time": ["2026-11-09"]}},
    )
    with pytest.raises(ValueError, match="на два дня"):
        get_city_weather(52.5, 13.4)


def test_get_city_weather_missing_value(monkeypatch):
    daily = _daily()
    daily["temperature_2m_max"] = [None, 18.0]
    monkeypatch.setattr(
        "labs.sources.weather_api.request_json",
        lambda url, params: {"daily": daily},
    )
    with pytest.raises(ValueError, match="отсутствует параметр"):
        get_city_weather(52.5, 13.4)
