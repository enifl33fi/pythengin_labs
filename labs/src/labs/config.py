from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    github_token: str | None = None
    data_dir: Path = Path("data")
    log_level: str = "INFO"
    request_timeout: float = Field(default=30.0, gt=0, le=300)
    max_concurrency: int = Field(default=8, ge=1, le=64)

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
