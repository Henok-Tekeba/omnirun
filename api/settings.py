from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def _default_cache_dir() -> Path:
    return Path.home() / ".cache" / "omnirun"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OMNIRUN_",
        env_file=".env",
        extra="ignore",
    )

    hf_endpoint: str = "https://huggingface.co"
    data_dir: Path = Field(default_factory=_project_data_dir)
    cache_dir: Path = Field(default_factory=_default_cache_dir)
    check_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    hf_max_attempts: int = Field(default=3, ge=1, le=6)
    hf_max_concurrent: int = Field(default=4, ge=1, le=32)
    max_concurrent_checks: int = Field(default=8, ge=1, le=128)
    rate_limit_per_minute: int = Field(default=30, ge=1, le=10_000)
    rate_limit_burst: int = Field(default=10, ge=1, le=10_000)
    result_cache_ttl_seconds: int = Field(default=600, ge=0, le=86_400)
    enable_result_cache: bool = True
    cors_origins: str = ""

    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]
