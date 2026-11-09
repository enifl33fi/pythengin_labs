"""Проверка качества подготовленного погодного датасета."""

from pathlib import Path

import pandas as pd

from labs.sources.open_meteo import TARGET_COLUMN, WEATHER_FEATURES


def main() -> None:
    """Вывести основные характеристики датасета."""
    path = Path("data/weather.csv")

    if not path.exists():
        raise FileNotFoundError(
            "Файл data/weather.csv не найден. Сначала запустите модуль labs.sources.open_meteo."
        )

    dataframe = pd.read_csv(path)

    print("\n=== Размер датасета ===")
    print(f"Строк: {dataframe.shape[0]}")
    print(f"Столбцов: {dataframe.shape[1]}")

    print("\n=== Первые пять строк ===")
    print(dataframe.head().to_string(index=False))

    print("\n=== Типы данных ===")
    print(dataframe.dtypes.to_string())

    print("\n=== Пропущенные значения ===")
    print(dataframe.isna().sum().to_string())

    print("\n=== Распределение целевой переменной ===")
    print(dataframe[TARGET_COLUMN].value_counts(dropna=False).to_string())

    print("\n=== Доля дождливых дней ===")
    print(f"{dataframe[TARGET_COLUMN].mean():.2%}")

    print("\n=== Описательная статистика признаков ===")
    print(dataframe[WEATHER_FEATURES].describe().to_string())


if __name__ == "__main__":
    main()
