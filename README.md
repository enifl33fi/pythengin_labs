# Weather ML Service

## Предметная область
Сервис машинного обучения для прогноза дождя на завтра на основе
исторических погодных данных и текущего прогноза Open-Meteo.

## Стек
- Python 3.12, FastAPI, Pydantic
- scikit-learn (LogReg, RandomForest), pandas, numpy, joblib
- httpx (Open-Meteo API)
- Тесты: pytest, pytest-cov
- Линт: ruff, mypy (strict)
- Пакетный менеджер: uv

## Запуск
```bash
uv sync --all-groups
uv run python -m labs.sources.open_meteo    # скачать датасет
uv run python -m labs.pipelines.train       # обучить модель
uv run uvicorn labs.api.main:app --reload
