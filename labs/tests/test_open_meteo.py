"""Unit-тесты open_meteo с мок-httpx."""

from __future__ import annotations

import httpx
import pandas as pd
import pytest

from labs.sources.open_meteo import (
    TARGET_COLUMN,
    build_multi_city_dataset,
    fetch_weather_data,
    save_weather_data,
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


class _FakeClient:
    def __init__(self, payload, *, raise_http: bool = False) -> None:
        self._payload = payload
        self._raise = raise_http

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, url, params=None):
        if self._raise:
            raise httpx.ConnectError("boom")
        return _FakeResponse(self._payload)


def _payload() -> dict:
    return {
        "daily": {
            "time": ["2026-11-01", "2026-11-02", "2026-11-03"],
            "temperature_2m_max": [10.0, 12.0, 11.0],
            "temperature_2m_min": [5.0, 6.0, 5.5],
            "precipitation_sum": [0.0, 2.5, 0.0],
            "wind_speed_10m_max": [5.0, 8.0, 6.0],
        }
    }


def test_fetch_weather_data_ok(monkeypatch):
    monkeypatch.setattr(
        "labs.sources.open_meteo.httpx.Client",
        lambda *a, **kw: _FakeClient(_payload()),
    )
    df = fetch_weather_data(52.5, 13.4, years=1)
    assert len(df) == 2
    assert TARGET_COLUMN in df.columns


def test_fetch_weather_data_bad_lat():
    with pytest.raises(ValueError, match="Широта"):
        fetch_weather_data(100.0, 13.4)


def test_fetch_weather_data_bad_lon():
    with pytest.raises(ValueError, match="Долгота"):
        fetch_weather_data(52.5, 200.0)


def test_fetch_weather_data_bad_years():
    with pytest.raises(ValueError, match="Количество лет"):
        fetch_weather_data(52.5, 13.4, years=0)


def test_fetch_weather_data_http_error(monkeypatch):
    monkeypatch.setattr(
        "labs.sources.open_meteo.httpx.Client",
        lambda *a, **kw: _FakeClient({}, raise_http=True),
    )
    with pytest.raises(RuntimeError):
        fetch_weather_data(52.5, 13.4)


def test_fetch_weather_data_no_daily(monkeypatch):
    monkeypatch.setattr(
        "labs.sources.open_meteo.httpx.Client",
        lambda *a, **kw: _FakeClient({}),
    )
    with pytest.raises(ValueError, match="ежедневные данные"):
        fetch_weather_data(52.5, 13.4)


def test_build_multi_city_dataset(monkeypatch):
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-11-01"]),
            "temperature_2m_max": [10.0],
            "temperature_2m_min": [5.0],
            "precipitation_sum": [0.0],
            "wind_speed_10m_max": [5.0],
            "latitude": [52.5],
            "longitude": [13.4],
            TARGET_COLUMN: [0],
        }
    )
    monkeypatch.setattr(
        "labs.sources.open_meteo.fetch_weather_data",
        lambda **kw: df.copy(),
    )
    result = build_multi_city_dataset(years=1)
    assert "city" in result.columns
    assert len(result) == 6


def test_save_weather_data(monkeypatch, tmp_path):
    df = pd.DataFrame({"x": [1, 2]})
    monkeypatch.setattr(
        "labs.sources.open_meteo.build_multi_city_dataset",
        lambda years=5: df.copy(),
    )
    out = save_weather_data(output_path=tmp_path / "w.csv", years=1)
    assert out.exists()
