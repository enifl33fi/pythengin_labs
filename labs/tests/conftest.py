from __future__ import annotations

import io
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LogisticRegression

import labs.api.main as main_module
from labs.api.main import app
from labs.config import get_settings


@pytest.fixture(autouse=True)
def _isolated_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("RG_"):
            monkeypatch.delenv(key, raising=False)

    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


class FakeModel:
    n_features_in_: int = 6
    classes_: np.ndarray = np.array([0, 1])

    def predict(self, X: Any) -> np.ndarray:
        return np.ones(len(X), dtype=int)

    def predict_proba(self, X: Any) -> np.ndarray:
        n = len(X)
        return np.column_stack([np.full(n, 0.3), np.full(n, 0.7)])


@pytest.fixture
def fake_model() -> FakeModel:
    return FakeModel()


@pytest.fixture
def valid_pkl_bytes() -> bytes:
    """Настоящая sklearn-модель с 6 признаками и 2 классами."""
    X = np.array([[i] * 6 for i in range(1, 21)], dtype=float)
    y = np.array([0] * 10 + [1] * 10)
    model = LogisticRegression().fit(X, y)
    buf = io.BytesIO()
    joblib.dump(model, buf)
    return buf.getvalue()


@pytest.fixture
def app_no_disk_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """app с несуществующими MODEL_PATH и METRICS_PATH (модель не грузится)."""
    monkeypatch.setattr(main_module, "MODEL_PATH", tmp_path / "absent.pkl")
    monkeypatch.setattr(main_module, "METRICS_PATH", tmp_path / "absent.json")
    main_module.model = None
    main_module.model_source = "none"
    return app


@pytest.fixture
def client(app_no_disk_model: Any) -> Iterator[TestClient]:
    with TestClient(app_no_disk_model) as c:
        main_module.model = None
        main_module.model_source = "none"
        yield c


@pytest.fixture
def client_with_model(
    app_no_disk_model: Any,
    fake_model: FakeModel,
) -> Iterator[TestClient]:
    with TestClient(app_no_disk_model) as c:
        main_module.model = fake_model
        main_module.model_source = "uploaded"
        yield c
        main_module.model = None
        main_module.model_source = "none"
