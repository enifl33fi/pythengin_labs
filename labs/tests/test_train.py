"""Unit-тесты train.py (без тяжёлого обучения)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from labs.pipelines.train import create_models, load_dataset
from labs.sources.open_meteo import TARGET_COLUMN, WEATHER_FEATURES


def test_create_models_returns_two_pipelines():
    models = create_models()
    assert set(models) == {"logistic_regression", "random_forest"}
    assert all(isinstance(m, Pipeline) for m in models.values())


def test_load_dataset_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_dataset(tmp_path / "nope.csv")


def _make_csv(tmp_path: Path, *, n: int = 200) -> Path:
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    rows = [
        {
            "date": dates[i].strftime("%Y-%m-%d"),
            "temperature_2m_max": 10 + (i % 15),
            "temperature_2m_min": 0 + (i % 10),
            "precipitation_sum": (i % 2) * 3.0,
            "wind_speed_10m_max": 5 + (i % 10),
            "latitude": 52.5,
            "longitude": 13.4,
            TARGET_COLUMN: i % 2,
        }
        for i in range(n)
    ]
    p = tmp_path / "w.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def test_load_dataset_ok(tmp_path):
    p = _make_csv(tmp_path, n=200)
    df = load_dataset(p)
    assert len(df) == 200
    assert set(df[TARGET_COLUMN].unique()) == {0, 1}


def test_load_dataset_bad_target(tmp_path):
    df = pd.DataFrame(
        {
            **{c: [1.0, 2.0] * 100 for c in WEATHER_FEATURES},
            TARGET_COLUMN: [0] * 200,
        }
    )
    p = tmp_path / "w.csv"
    df.to_csv(p, index=False)
    with pytest.raises(ValueError, match="оба класса"):
        load_dataset(p)


def test_load_dataset_too_small(tmp_path):
    p = _make_csv(tmp_path, n=50)
    with pytest.raises(ValueError, match="мало"):
        load_dataset(p)


def test_train_and_evaluate(tmp_path, monkeypatch):
    """Полный цикл на синтетическом датасете — закрывает оставшиеся строки."""
    from labs.pipelines import train as train_module

    data = _make_csv(tmp_path, n=200)
    real_load = train_module.load_dataset

    def fake_load(*args, **kwargs):
        return real_load(data)

    # load_dataset() вызывается без аргумента — дефолт зашит в def-time,
    # поэтому patc'им саму функцию, а не DATA_PATH.
    monkeypatch.setattr(train_module, "load_dataset", fake_load)
    monkeypatch.setattr(train_module, "MODEL_PATH", tmp_path / "m.pkl")
    monkeypatch.setattr(train_module, "METRICS_PATH", tmp_path / "m.json")

    metrics = train_module.train_and_evaluate()
    assert metrics["best_model"] in ("logistic_regression", "random_forest")
    assert (tmp_path / "m.pkl").exists()
    assert (tmp_path / "m.json").exists()
