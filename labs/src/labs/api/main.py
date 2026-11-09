"""FastAPI-сервис для прогнозирования дождя."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Annotated, Any, cast

import joblib
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sklearn.metrics import roc_auc_score
from starlette.concurrency import run_in_threadpool

from labs.sources.open_meteo import TARGET_COLUMN, WEATHER_FEATURES
from labs.sources.weather_api import find_city, get_city_weather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = PROJECT_ROOT / "data"
MODEL_PATH = DATA_DIR / "best_model.pkl"  # базовая модель на диске
METRICS_PATH = DATA_DIR / "metrics.json"
STATIC_DIR = PROJECT_ROOT / "static"

MAX_MODEL_SIZE = 500 * 1024 * 1024  # 500 МБ
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 МБ
MAX_CSV_SIZE = 50 * 1024 * 1024  # 50 МБ

DATA_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Weather ML Service",
    description=(
        "Сервис машинного обучения для прогноза дождя на основе исторических погодных данных."
    ),
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Активная модель в памяти. Базовая грузится из MODEL_PATH при старте,
# загруженная пользователем живёт только здесь и не пишется на диск.
model: Any | None = None
model_source: str = "none"  # "none" | "file" | "uploaded"


class CityRequest(BaseModel):
    """Запрос прогноза погоды по названию города."""

    city: str = Field(min_length=1, max_length=100)


def validate_model(candidate: Any) -> None:
    """Проверить совместимость загруженной модели."""

    if not callable(getattr(candidate, "predict", None)):
        raise ValueError("Модель не поддерживает predict().")

    if not callable(getattr(candidate, "predict_proba", None)):
        raise ValueError("Модель не поддерживает predict_proba().")

    actual_features = getattr(candidate, "n_features_in_", None)

    if actual_features is not None and actual_features != len(WEATHER_FEATURES):
        raise ValueError(
            f"Модель ожидает {actual_features} признаков, "
            f"а сервис передаёт {len(WEATHER_FEATURES)}."
        )

    classes = getattr(candidate, "classes_", None)

    if classes is not None and 1 not in classes:
        raise ValueError("Модель должна поддерживать класс 1 (дождь).")


def load_model_from_path(path: Path) -> Any:
    """Загрузить модель из PKL-файла."""

    if not path.exists():
        raise FileNotFoundError(f"Файл модели не найден: {path}")

    loaded_model = joblib.load(path)
    validate_model(loaded_model)

    return loaded_model


@app.on_event("startup")
def startup_event() -> None:
    """Загрузить базовую модель при запуске сервиса."""

    global model, model_source

    if not MODEL_PATH.exists():
        logger.warning("Модель не найдена. Сначала обучите её или используйте POST /upload-model.")
        return

    try:
        model = load_model_from_path(MODEL_PATH)
        model_source = "file"
        logger.info("Базовая модель загружена из %s", MODEL_PATH)
    except (OSError, ValueError, EOFError, AttributeError, TypeError):
        logger.exception("Не удалось загрузить базовую модель.")
        model = None
        model_source = "none"


def get_model() -> Any:
    """Вернуть загруженную модель."""

    if model is None:
        raise HTTPException(
            status_code=503,
            detail=("Модель не загружена. Обучите её или вызовите /upload-model."),
        )
    return model


def validate_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Проверить входные признаки и привести их к нужному порядку."""

    missing = [feature for feature in WEATHER_FEATURES if feature not in dataframe.columns]

    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Не хватает обязательных признаков: {missing}",
        )

    features = dataframe[WEATHER_FEATURES].copy()

    for column in WEATHER_FEATURES:
        features[column] = pd.to_numeric(
            features[column],
            errors="coerce",
        )

    if features.isna().any().any():
        raise HTTPException(
            status_code=422,
            detail="Все признаки должны содержать числовые значения.",
        )

    return features


def predict_features(features: pd.DataFrame) -> tuple[Any, Any]:
    """Получить предсказания и вероятность дождя."""

    current_model = get_model()

    try:
        predictions = current_model.predict(features)
        probabilities_all = current_model.predict_proba(features)

        classes = list(current_model.classes_)
        rain_class_index = classes.index(1)

        probabilities = probabilities_all[:, rain_class_index]

    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Не удалось выполнить предсказание: {exc}",
        ) from exc

    return predictions, probabilities


@app.get("/")
def index() -> FileResponse:
    """Открыть главную страницу приложения."""

    index_path = STATIC_DIR / "index.html"

    if not index_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Файл static/index.html не найден.",
        )

    return FileResponse(index_path)


@app.get("/health")
def health() -> dict[str, str | bool]:
    """Проверить доступность сервиса и наличие модели."""

    return {
        "status": "ok",
        "model_loaded": model is not None,
        "model_source": model_source,
    }


@app.get("/api/metrics")
def get_metrics() -> dict[str, Any]:
    """Получить метрики базовой модели."""

    if not METRICS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Файл metrics.json не найден.",
        )

    try:
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        return cast(dict[str, Any], metrics)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Не удалось прочитать метрики модели.",
        ) from exc


@app.post("/api/predict")
def predict_by_city(request: CityRequest) -> dict[str, Any]:
    """Получить прогноз погоды и предсказать дождь по названию города."""

    current_model = get_model()

    city_name = request.city.strip()

    if not city_name:
        raise HTTPException(
            status_code=422,
            detail="Введите название города.",
        )

    # 1. Поиск города. find_city() бросает ValueError, когда города нет
    #    в геокодинге — это клиентская ошибка, поэтому 404, а не 502.
    try:
        city = cast(dict[str, Any], find_city(city_name))
    except ValueError as exc:
        logger.info("Город не найден: %s", exc)
        raise HTTPException(
            status_code=404,
            detail=f"Город '{city_name}' не найден.",
        ) from exc
    except Exception as exc:
        logger.exception("Ошибка при обращении к API геокодинга.")
        raise HTTPException(
            status_code=502,
            detail="Не удалось найти город.",
        ) from exc

    # 2. Прогноз погоды. Любая ошибка здесь — проблема upstream-сервиса.
    try:
        latitude = float(city["latitude"])
        longitude = float(city["longitude"])

        weather = cast(
            dict[str, Any],
            get_city_weather(latitude, longitude),
        )

    except (KeyError, TypeError, ValueError) as exc:
        logger.exception("Некорректные данные от погодного API.")
        raise HTTPException(
            status_code=502,
            detail="Не удалось обработать ответ погодного сервиса.",
        ) from exc
    except Exception as exc:
        logger.exception("Ошибка при обращении к погодному API.")
        raise HTTPException(
            status_code=502,
            detail="Не удалось получить прогноз погоды.",
        ) from exc

    # 3. Формирование прогноза.
    try:
        today = cast(dict[str, Any], weather["today"])
        tomorrow = cast(dict[str, Any], weather["tomorrow"])

        model_input = {
            "temperature_2m_max": today["temperature_2m_max"],
            "temperature_2m_min": today["temperature_2m_min"],
            "precipitation_sum": today["precipitation_sum"],
            "wind_speed_10m_max": today["wind_speed_10m_max"],
            "latitude": latitude,
            "longitude": longitude,
        }

        features = validate_features(pd.DataFrame([model_input]))

        prediction = current_model.predict(features)[0]
        probabilities = current_model.predict_proba(features)[0]

        classes = list(current_model.classes_)
        rain_probability = float(probabilities[classes.index(1)])

    except HTTPException:
        raise
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        logger.exception("Ошибка при формировании прогноза.")
        raise HTTPException(
            status_code=422,
            detail=f"Не удалось выполнить предсказание: {exc}",
        ) from exc

    return {
        "city": {
            "name": city.get("name", city_name),
            "country": city.get("country", ""),
        },
        "coordinates": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "tomorrow_weather": tomorrow,
        "prediction": {
            "rain_tomorrow": int(prediction),
            "rain_probability": round(rain_probability, 4),
            "message": ("Ожидается дождь" if int(prediction) == 1 else "Дождь не ожидается"),
        },
    }


@app.post("/upload-model")
async def upload_model(
    file: Annotated[UploadFile, File()],
) -> dict[str, str]:
    """Загрузить модель в память — без записи в data/.

    Базовая best_model.pkl остаётся нетронутой, загруженная модель
    действует до перезапуска сервера (или до POST /reset-model).
    Никаких temp-файлов мы не создаём — Starlette уже спулил
    содержимое UploadFile в %TEMP% (память до 1 МБ, дальше — файл ОС).
    """

    global model, model_source

    if Path(file.filename or "").suffix.lower() != ".pkl":
        raise HTTPException(
            status_code=400,
            detail="Разрешена загрузка только файлов .pkl.",
        )

    limit_mb = MAX_MODEL_SIZE // (1024 * 1024)

    try:
        # 1. Проходим по чанкам и считаем размер — но никуда не пишем.
        await file.seek(0)
        total = 0
        while True:
            chunk = await file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_MODEL_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Размер файла превышает {limit_mb} МБ.",
                )

        logger.info(
            "Получен файл %r (%d байт), десериализуем в память.",
            file.filename,
            total,
        )

        # 2. Возвращаемся в начало и читаем модель из спула.
        #    run_in_threadpool — чтобы не блокировать event loop
        #    синхронным joblib.load() на время десериализации.
        await file.seek(0)
        candidate = await run_in_threadpool(joblib.load, file.file)
        validate_model(candidate)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Не удалось загрузить модель.")
        raise HTTPException(
            status_code=400,
            detail=f"Несовместимая модель: {exc}",
        ) from exc

    # 3. Атомарная подмена в памяти (присваивание под GIL — безопасно).
    model = candidate
    model_source = "uploaded"

    logger.info("Модель подменена в памяти (best_model.pkl не тронут).")

    return {
        "status": "success",
        "message": ("Модель загружена в память. Действует до перезапуска сервера."),
    }


@app.post("/reset-model")
def reset_model() -> dict[str, str]:
    """Вернуть базовую модель из data/best_model.pkl"""
    global model, model_source

    if not MODEL_PATH.exists():
        model = None
        model_source = "none"
        logger.info("Базовый файл отсутствует — сервис переведён в режим без модели.")
        return {
            "status": "success",
            "message": "Базовой модели нет — сервис работает без модели.",
        }

    try:
        model = load_model_from_path(MODEL_PATH)
        model_source = "file"
    except (OSError, ValueError, EOFError, AttributeError, TypeError) as exc:
        # Файл есть, но битый — это уже настоящая ошибка, 500.
        logger.exception("Не удалось загрузить базовую модель.")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось загрузить базовую модель: {exc}",
        ) from exc

    logger.info("Базовая модель восстановлена из %s", MODEL_PATH)

    return {
        "status": "success",
        "message": "Базовая модель восстановлена.",
    }


@app.post("/predict")
def predict(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Предсказать дождь для переданных записей."""

    if not records:
        raise HTTPException(
            status_code=422,
            detail="Передайте хотя бы одну запись.",
        )

    features = validate_features(pd.DataFrame(records))
    predictions, probabilities = predict_features(features)

    output: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        output.append(
            {
                **record,
                TARGET_COLUMN: int(predictions[index]),
                "rain_probability": round(
                    float(probabilities[index]),
                    4,
                ),
            }
        )

    return {"predictions": output}


@app.post("/predict-from-csv")
async def predict_from_csv(
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """Обработать CSV-файл и вернуть предсказания модели."""

    if Path(file.filename or "").suffix.lower() != ".csv":
        raise HTTPException(
            status_code=400,
            detail="Загрузите файл с расширением .csv.",
        )

    content = await file.read(MAX_CSV_SIZE + 1)

    if len(content) > MAX_CSV_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(f"Размер файла превышает {MAX_CSV_SIZE // (1024 * 1024)} МБ."),
        )

    try:
        dataframe = pd.read_csv(io.BytesIO(content))
    except (
        ValueError,
        UnicodeDecodeError,
        pd.errors.ParserError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось прочитать CSV: {exc}",
        ) from exc

    if dataframe.empty:
        raise HTTPException(
            status_code=400,
            detail="CSV не содержит строк с данными.",
        )

    features = validate_features(dataframe)
    predictions, probabilities = predict_features(features)

    dataframe["predicted_rain_tomorrow"] = predictions.astype(int)
    dataframe["rain_probability"] = probabilities

    auc: float | None = None
    if TARGET_COLUMN in dataframe.columns:
        try:
            actual = pd.to_numeric(
                dataframe[TARGET_COLUMN],
                errors="raise",
            )
            if actual.isin([0, 1]).all() and actual.nunique() == 2:
                auc = float(roc_auc_score(actual, probabilities))
        except (ValueError, TypeError):
            auc = None

    rows = json.loads(dataframe.to_json(orient="records", date_format="iso"))

    return {
        "roc_auc": auc,
        "rows_count": len(dataframe),
        "data": rows,
    }
