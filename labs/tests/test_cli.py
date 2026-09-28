from __future__ import annotations

import pytest
from typer.testing import CliRunner

from labs import __version__
from labs.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_both_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.stdout
    assert "check-config" in result.stdout


def test_check_config_hides_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RG_GITHUB_TOKEN", "ghp_supersecretvalue1234")
    result = runner.invoke(app, ["check-config"])
    assert result.exit_code == 0
    assert "ghp_supersecretvalue1234" not in result.stdout
    assert "ghp_****1234" in result.stdout


def test_check_config_without_token() -> None:
    result = runner.invoke(app, ["check-config"])
    assert result.exit_code == 0
    assert "<not set>" in result.stdout


def test_mask_token_short_secret() -> None:
    from labs.cli import _mask_token

    assert _mask_token(None) == "<not set>"
    assert _mask_token("") == "<not set>"
    assert _mask_token("abc") == "****"
    assert _mask_token("abcdefghijkl") == "abcd****ijkl"
