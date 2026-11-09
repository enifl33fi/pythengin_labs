"""Unit-тесты inspect_data."""

from __future__ import annotations

import pandas as pd
import pytest

from labs.pipelines.inspect_data import main
from labs.sources.open_meteo import TARGET_COLUMN, WEATHER_FEATURES


def test_inspect_data_missing():
    # CWD уже tmp_path (autouse фикстура) — data/weather.csv нет
    with pytest.raises(FileNotFoundError):
        main()


def test_inspect_data_success(tmp_path, capsys):
    (tmp_path / "data").mkdir(exist_ok=True)

    df = pd.DataFrame(
        {
            **{c: [1.0, 2.0, 3.0, 4.0] for c in WEATHER_FEATURES},
            TARGET_COLUMN: [0, 1, 0, 1],
        }
    )
    df.to_csv(tmp_path / "data" / "weather.csv", index=False)

    main()

    out = capsys.readouterr().out
    assert "Размер датасета" in out
    assert "Распределение" in out
