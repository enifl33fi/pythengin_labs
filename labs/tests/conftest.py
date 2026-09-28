from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

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
