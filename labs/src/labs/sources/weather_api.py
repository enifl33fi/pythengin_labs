"""Получение координат города и прогноза погоды из Open-Meteo."""

from __future__ import annotations

import time
from typing import Any

import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=15.0)
MAX_RETRIES = 3


def request_json(
    url: str,
    params: dict[str, str | int | float],
) -> dict[str, Any]:
    """Выполнить GET-запрос с повторными попытками при сетевых ошибках."""

    for attempt in range(MAX_RETRIES):
        try:
            response = httpx.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            payload = response.json()

            if not isinstance(payload, dict):
                raise ValueError("API вернул ответ в неожиданном формате.")

            return payload

        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt == MAX_RETRIES - 1:
                raise

            # Пауза перед следующей попыткой: 2, затем 4 секунды.
            time.sleep(2 * (attempt + 1))

    raise RuntimeError("Не удалось получить ответ от Open-Meteo.")


def find_city(city_name: str) -> dict[str, str | float]:
    """Найти город и получить его координаты."""

    city_name = city_name.strip()

    if not city_name:
        raise ValueError("Название города не может быть пустым.")

    params: dict[str, str | int | float] = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json",
    }

    try:
        payload = request_json(GEOCODING_URL, params)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ошибка поиска города: {exc}") from exc

    results = payload.get("results")

    if not results:
        raise ValueError(f"Город '{city_name}' не найден.")

    city = results[0]

    return {
        "name": str(city["name"]),
        "country": str(city.get("country", "")),
        "latitude": float(city["latitude"]),
        "longitude": float(city["longitude"]),
    }


def get_city_weather(
    latitude: float,
    longitude: float,
) -> dict[str, object]:
    """Получить погодные параметры на сегодня и завтра."""

    params: dict[str, str | int | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": (
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_sum,"
            "precipitation_probability_max,"
            "wind_speed_10m_max"
        ),
        "timezone": "auto",
        "forecast_days": 2,
    }

    try:
        payload = request_json(FORECAST_URL, params)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ошибка получения прогноза погоды: {exc}") from exc

    daily = payload.get("daily")

    if not isinstance(daily, dict):
        raise ValueError("Open-Meteo не вернул данные ежедневного прогноза.")

    dates = daily.get("time")

    if not isinstance(dates, list) or len(dates) < 2:
        raise ValueError("Open-Meteo не вернул прогноз на два дня.")

    def get_value(name: str, index: int) -> float:
        """Получить числовое значение погодного параметра."""

        values = daily.get(name)

        if not isinstance(values, list) or len(values) <= index or values[index] is None:
            raise ValueError(f"В прогнозе отсутствует параметр {name}.")

        return float(values[index])

    # Первый день — сегодня, второй — завтра.
    today: dict[str, object] = {
        "date": dates[0],
        "temperature_2m_max": get_value("temperature_2m_max", 0),
        "temperature_2m_min": get_value("temperature_2m_min", 0),
        "precipitation_sum": get_value("precipitation_sum", 0),
        "wind_speed_10m_max": get_value("wind_speed_10m_max", 0),
    }

    tomorrow: dict[str, object] = {
        "date": dates[1],
        "temperature_2m_max": get_value("temperature_2m_max", 1),
        "temperature_2m_min": get_value("temperature_2m_min", 1),
        "precipitation_sum": get_value("precipitation_sum", 1),
        "precipitation_probability_max": get_value("precipitation_probability_max", 1),
        "wind_speed_10m_max": get_value("wind_speed_10m_max", 1),
    }

    return {
        "today": today,
        "tomorrow": tomorrow,
    }
