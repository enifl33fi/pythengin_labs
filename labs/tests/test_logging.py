from __future__ import annotations

import logging

import pytest

from labs.logging_setup import NOISY_LOGGERS, setup_logging


def test_setup_logging_sets_level() -> None:
    setup_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_replaces_handlers() -> None:
    setup_logging("INFO")
    setup_logging("INFO")
    setup_logging("INFO")
    assert len(logging.getLogger().handlers) == 1


def test_noisy_loggers_are_quiet() -> None:
    setup_logging("DEBUG")
    for name in NOISY_LOGGERS:
        assert logging.getLogger(name).level == logging.WARNING


def test_logs_go_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging("INFO")
    logging.getLogger("test").info("hello-stderr")

    captured = capsys.readouterr()
    assert "hello-stderr" in captured.err
    assert "hello-stderr" not in captured.out
