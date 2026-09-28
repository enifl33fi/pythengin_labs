from __future__ import annotations

import logging
import sys

NOISY_LOGGERS: tuple[str, ...] = (
    "urllib3",
    "httpx",
    "httpcore",
    "asyncio",
)

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(handler)

    root.setLevel(level.upper())

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
