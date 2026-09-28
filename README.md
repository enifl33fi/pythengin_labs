# Labs
**Labs** — каркас проекта для семестрового курса. Репозиторий развивается от
лабораторной к лабораторной и превращается в инструмент для сбора, нормализации
и анализа данных из внешних источников.

На текущем этапе (ЛР1) реализован только фундамент: конфигурация на
`pydantic-settings`, настройка логирования в `stderr`, CLI на Typer с командами
`version` и `check-config`, тесты с покрытием ≥ 70 %, pre-commit и CI в GitHub
Actions.

## Требования

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — установка:

  ```bash
  # Linux / macOS
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Windows PowerShell
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

- **git**

## Установка

```bash
git clone https://github.com/<user>/<repo>.git
cd <repo>/labs
uv sync
```

Команда `uv sync` создаст виртуальное окружение `.venv/`, установит все
зависимости (включая dev-группу) и установит сам пакет в editable-режиме вместе
с точкой входа `rg`.

Проверка, что всё встало:

```bash
uv run rg version
```

## Конфигурация

Все переменные окружения имеют префикс `RG_`. Их можно задать в файле `.env`
в корне проекта (см. `.env.example`) или напрямую в переменных окружения.

| Переменная             | Тип     | По умолчанию | Описание                                                                  |
|------------------------|---------|--------------|---------------------------------------------------------------------------|
| `RG_GITHUB_TOKEN`      | `str?`  | `None`       | Токен GitHub. Опционально. В CLI выводится только в замаскированном виде. |
| `RG_DATA_DIR`          | `Path`  | `data`       | Директория для данных. Создаётся лениво методом `ensure_data_dir()`.      |
| `RG_LOG_LEVEL`         | `str`   | `INFO`       | Уровень логирования: `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`. |
| `RG_REQUEST_TIMEOUT`   | `float` | `30.0`       | Таймаут HTTP-запросов в секундах. Границы: `0 < t <= 300`.                |
| `RG_MAX_CONCURRENCY`   | `int`   | `8`          | Максимум параллельных задач. Границы: `1 <= n <= 64`.                     |

Скопируйте пример и отредактируйте:

```bash
cp .env.example .env
```

## Использование

### `rg --help`

```text
Usage: rg [OPTIONS] COMMAND [ARGS]...

  CLI для управления проектом.

Options:
  --help  Show this message and exit.

Commands:
  check-config  Загрузить настройки, инициализировать логирование и вывести сводку.
  version       Показать версию пакета.
```

### `rg version`

```text
$ uv run rg version
labs 0.1.0
```

### `rg check-config`

```text
$ uv run rg check-config
Configuration summary:
  data_dir        = data
  log_level       = INFO
  request_timeout = 30.0
  max_concurrency = 8
  github_token    = <not set>
2026-09-28 17:38:36 | INFO     | labs.cli | check-config completed successfully
```

Секреты никогда не выводятся в открытом виде. Если токен задан — печатается
маскированный вид:

```text
$ RG_GITHUB_TOKEN=ghp_supersecretvalue1234 uv run rg check-config
Configuration summary:
  ...
  github_token    = ghp_****1234
```

## Разработка

```bash
# Тесты с покрытием (порог 70 % зашит в pyproject.toml)
uv run pytest

# Линтер и проверка форматирования
uv run ruff check .
uv run ruff format --check .

# Типизация в strict-режиме
uv run mypy

# Установить git-хуки (один раз после клонирования)
uv run pre-commit install

# Прогнать хуки вручную по всем файлам
uv run pre-commit run --all-files
```

Проверить, что локально всё соответствует CI:

```bash
uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

## Структура проекта

```
labs/
├── .github/workflows/ci.yml    # GitHub Actions: lint, format, mypy, tests
├── .env.example                # пример конфигурации (сам .env не коммитится)
├── .pre-commit-config.yaml     # хуки: ruff, ruff-format, mypy, базовые проверки
├── pyproject.toml              # метаданные, зависимости, конфиги инструментов
├── uv.lock                     # зафиксированные версии зависимостей
├── README.md
├── docs/
│   └── lab1_report.md          # отчёт по лабораторной
├── src/
│   └── labs/                   # исходный код пакета (src-layout)
│       ├── __init__.py         # версия пакета
│       ├── __main__.py         # python -m labs
│       ├── cli.py              # CLI на Typer (команды version, check-config)
│       ├── config.py           # Settings на pydantic-settings
│       ├── logging_setup.py    # настройка логирования в stderr
│       ├── api/                # заготовка: HTTP-клиенты (следующие ЛР)
│       ├── models/             # заготовка: доменные модели
│       ├── pipelines/          # заготовка: пайплайны обработки данных
│       ├── sources/            # заготовка: источники данных
│       └── storage/            # заготовка: слои хранения
└── tests/
    ├── conftest.py             # изоляция тестов от .env и окружения
    ├── test_cli.py             # CLI через typer.testing.CliRunner
    ├── test_config.py          # Settings: значения, env, валидация
    └── test_logging.py         # setup_logging: level, stderr, шумные логгеры
```

> **Примечание.** Репозиторий устроен так, что `labs/` — это подпапка. Если
> вы клонируете репозиторий целиком, сначала перейдите в неё: `cd <repo>/labs`.
