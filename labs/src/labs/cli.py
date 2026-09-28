from __future__ import annotations

import logging

import typer

from labs import __version__
from labs.config import get_settings
from labs.logging_setup import setup_logging

app = typer.Typer(
    name="rg",
    help="CLI для управления проектом.",
    no_args_is_help=True,
    add_completion=False,
)

logger = logging.getLogger(__name__)


def _mask_token(token: str | None) -> str:
    if not token:
        return "<not set>"
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}****{token[-4:]}"


@app.command()
def version() -> None:
    typer.echo(f"labs {__version__}")


@app.command(name="check-config")
def check_config() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    typer.echo("Configuration summary:")
    typer.echo(f"  data_dir        = {settings.data_dir}")
    typer.echo(f"  log_level       = {settings.log_level}")
    typer.echo(f"  request_timeout = {settings.request_timeout}")
    typer.echo(f"  max_concurrency = {settings.max_concurrency}")
    typer.echo(f"  github_token    = {_mask_token(settings.github_token)}")

    logger.info("check-config completed successfully")


if __name__ == "__main__":
    app()
