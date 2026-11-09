"""Обучение и сравнение моделей прогнозирования дождя."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from labs.sources.open_meteo import TARGET_COLUMN, WEATHER_FEATURES

logger = logging.getLogger(__name__)

DATA_PATH = Path("data/weather.csv")
MODEL_PATH = Path("data/best_model.pkl")
METRICS_PATH = Path("data/metrics.json")


def create_models() -> dict[str, Pipeline]:
    """Создать модели с одинаковой предобработкой признаков."""
    return {
        "logistic_regression": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("feature_selection", SelectKBest(score_func=f_classif, k="all")),
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("feature_selection", SelectKBest(score_func=f_classif, k="all")),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=300,
                        min_samples_leaf=3,
                        class_weight="balanced",
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
    }


def load_dataset(path: Path = DATA_PATH) -> pd.DataFrame:
    """Загрузить и проверить подготовленный датасет."""
    if not path.exists():
        raise FileNotFoundError(
            f"Датасет не найден: {path}. Сначала загрузите данные из Open-Meteo."
        )

    dataframe = pd.read_csv(path)

    required_columns = [*WEATHER_FEATURES, TARGET_COLUMN]
    missing_columns = [column for column in required_columns if column not in dataframe.columns]

    if missing_columns:
        raise ValueError(f"В датасете отсутствуют обязательные столбцы: {missing_columns}")

    dataframe = dataframe.dropna(subset=[TARGET_COLUMN]).copy()
    dataframe[TARGET_COLUMN] = dataframe[TARGET_COLUMN].astype(int)

    if not set(dataframe[TARGET_COLUMN].unique()).issubset({0, 1}):
        raise ValueError("Целевая переменная должна содержать только 0 и 1.")

    if dataframe[TARGET_COLUMN].nunique() != 2:
        raise ValueError("Для обучения и оценки ROC-AUC нужны оба класса: 0 и 1.")

    if len(dataframe) < 100:
        raise ValueError(
            "Слишком мало наблюдений. Для этой лабораторной нужно "
            "получить более длинный период исторических данных."
        )

    return dataframe


def train_and_evaluate() -> dict[str, object]:
    """Обучить модели, сравнить метрики и сохранить лучшую."""
    logging.basicConfig(level=logging.INFO)

    dataframe = load_dataset()

    if "date" in dataframe.columns:
        dataframe["date"] = pd.to_datetime(dataframe["date"])
        dataframe = dataframe.sort_values("date").reset_index(drop=True)

    unique_dates = sorted(dataframe["date"].unique())

    split_index = int(len(unique_dates) * 0.8)
    split_date = unique_dates[split_index]

    train_data = dataframe[dataframe["date"] < split_date].copy()

    test_data = dataframe[dataframe["date"] >= split_date].copy()

    X_train = train_data[WEATHER_FEATURES]
    y_train = train_data[TARGET_COLUMN]

    X_test = test_data[WEATHER_FEATURES]
    y_test = test_data[TARGET_COLUMN]

    if y_train.nunique() != 2 or y_test.nunique() != 2:
        raise ValueError(
            "В обучающей и тестовой выборках должны присутствовать "
            "оба класса. Проверьте период и распределение целевой переменной."
        )

    results: dict[str, dict[str, float]] = {}
    trained_models: dict[str, Pipeline] = {}

    for name, model in create_models().items():
        logger.info("Обучаем модель %s", name)
        model.fit(X_train, y_train)

        probabilities = model.predict_proba(X_test)[:, 1]
        predictions = model.predict(X_test)

        auc = float(roc_auc_score(y_test, probabilities))
        accuracy = float(accuracy_score(y_test, predictions))

        results[name] = {
            "roc_auc": auc,
            "accuracy": accuracy,
        }
        trained_models[name] = model

        print(f"\n=== {name} ===")
        print(f"ROC-AUC: {auc:.4f}")
        print(f"Accuracy: {accuracy:.4f}")
        print(classification_report(y_test, predictions, zero_division=0))

    best_name = max(
        results,
        key=lambda model_name: results[model_name]["roc_auc"],
    )
    best_model = trained_models[best_name]

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, MODEL_PATH)

    metrics = {
        "best_model": best_name,
        "features": WEATHER_FEATURES,
        "target": TARGET_COLUMN,
        "train_rows": len(train_data),
        "test_rows": len(test_data),
        "results": results,
    }

    METRICS_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Лучшая модель: %s", best_name)
    logger.info("Модель сохранена: %s", MODEL_PATH)
    logger.info("Метрики сохранены: %s", METRICS_PATH)

    print("\n=== Результат сравнения ===")
    print(f"Лучшая модель: {best_name}")
    print(f"Файл модели: {MODEL_PATH}")
    print(f"Файл метрик: {METRICS_PATH}")

    return metrics


if __name__ == "__main__":
    train_and_evaluate()
