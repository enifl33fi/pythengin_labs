"""Загрузка исторических погодных данных из Open-Meteo."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

API_URL = "https://archive-api.open-meteo.com/v1/archive"

# Признаки, которые будут использоваться при обучении.
WEATHER_FEATURES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "wind_speed_10m_max",
    "latitude",
    "longitude",
]

TARGET_COLUMN = "rain_tomorrow"

# Города для формирования обучающего датасета.
TRAINING_CITIES: list[dict[str, str | float]] = [
    {"name": "Helsinki", "latitude": 60.1699, "longitude": 24.9384},
    {"name": "Stockholm", "latitude": 59.3293, "longitude": 18.0686},
    {"name": "London", "latitude": 51.5072, "longitude": -0.1276},
    {"name": "Paris", "latitude": 48.8566, "longitude": 2.3522},
    {"name": "Berlin", "latitude": 52.5200, "longitude": 13.4050},
    {"name": "Madrid", "latitude": 40.4168, "longitude": -3.7038},
]


def fetch_weather_data(
    latitude: float,
    longitude: float,
    years: int = 5,
) -> pd.DataFrame:
    """Загрузить историческую погоду для одной точки."""

    if not -90 <= latitude <= 90:
        raise ValueError("Широта должна быть от -90 до 90.")

    if not -180 <= longitude <= 180:
        raise ValueError("Долгота должна быть от -180 до 180.")

    if not 1 <= years <= 10:
        raise ValueError("Количество лет должно быть от 1 до 10.")

    end_date = date.today() - timedelta(days=5)
    start_date = end_date - timedelta(days=365 * years)

    params: dict[str, str | int | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "wind_speed_10m_max",
            ]
        ),
        "timezone": "auto",
    }

    logger.info(
        "Загрузка погоды: latitude=%s, longitude=%s",
        latitude,
        longitude,
    )

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(API_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ошибка получения данных Open-Meteo: {exc}") from exc

    daily = payload.get("daily")

    if not daily or "time" not in daily:
        raise ValueError("Open-Meteo не вернул ежедневные данные.")

    dataframe = pd.DataFrame(daily)

    dataframe["date"] = pd.to_datetime(dataframe["time"])
    dataframe = dataframe.drop(columns=["time"])

    required_columns = [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "wind_speed_10m_max",
    ]

    missing = [column for column in required_columns if column not in dataframe.columns]

    if missing:
        raise ValueError(f"В ответе отсутствуют столбцы: {missing}")

    # Добавляем географические координаты к каждой записи.
    dataframe["latitude"] = latitude
    dataframe["longitude"] = longitude

    # Для дня D определяем, был ли дождь в день D+1.
    tomorrow_precipitation = dataframe["precipitation_sum"].shift(-1)

    dataframe[TARGET_COLUMN] = (tomorrow_precipitation > 0.1).astype("float64")

    # У последнего дня нет данных за следующий день.
    dataframe = dataframe.iloc[:-1].copy()

    dataframe = dataframe.dropna(subset=[*WEATHER_FEATURES, TARGET_COLUMN])

    dataframe[TARGET_COLUMN] = dataframe[TARGET_COLUMN].astype(int)

    if dataframe.empty:
        raise ValueError("После очистки не осталось данных.")

    return dataframe[["date", *WEATHER_FEATURES, TARGET_COLUMN]]


def build_multi_city_dataset(
    years: int = 5,
) -> pd.DataFrame:
    """Создать общий датасет для всех обучающих городов."""

    city_dataframes = []

    for city in TRAINING_CITIES:
        logger.info("Обрабатываем город: %s", city["name"])

        dataframe = fetch_weather_data(
            latitude=float(city["latitude"]),
            longitude=float(city["longitude"]),
            years=years,
        )

        dataframe["city"] = city["name"]

        city_dataframes.append(dataframe)

    result = pd.concat(
        city_dataframes,
        ignore_index=True,
    )

    result = result.sort_values(["date", "city"]).reset_index(drop=True)

    return result


def save_weather_data(
    output_path: Path = Path("data/weather.csv"),
    years: int = 5,
) -> Path:
    """Собрать данные для нескольких городов и сохранить CSV."""

    dataframe = build_multi_city_dataset(years=years)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(output_path, index=False)

    logger.info(
        "Сохранено строк: %s. Файл: %s",
        len(dataframe),
        output_path,
    )

    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    path = save_weather_data()

    print(f"Датасет сохранён: {path.resolve()}")
