from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from labs.config import Settings, get_settings


def test_defaults() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.github_token is None
    assert s.log_level == "INFO"
    assert s.request_timeout == 30.0
    assert s.max_concurrency == 8
    assert s.data_dir == Path("data")


def test_settings_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RG_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("RG_MAX_CONCURRENCY", "16")
    monkeypatch.setenv("RG_DATA_DIR", "custom_data")

    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert s.log_level == "DEBUG"
    assert s.max_concurrency == 16
    assert s.data_dir == Path("custom_data")


def test_rejects_invalid_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RG_MAX_CONCURRENCY", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_rejects_too_high_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RG_MAX_CONCURRENCY", "999")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_rejects_negative_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RG_REQUEST_TIMEOUT", "-1.0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_ensure_data_dir(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "data"
    s = Settings(data_dir=target, _env_file=None)  # type: ignore[call-arg]
    result = s.ensure_data_dir()
    assert result.is_dir()
    # Повторный вызов не должен падать.
    assert s.ensure_data_dir() == target
