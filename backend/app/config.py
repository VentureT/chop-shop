"""Application configuration, env-driven via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings with defaults so the app runs with no .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Chop Shop API"
    environment: str = "development"
    # NoDecode: read the raw CSV string from .env and split it ourselves below.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    ebay_env: str = "production"  # production | sandbox
    default_zip: str = "75201"

    cache_ttl_days: int = 7
    cache_path: str = "cache.db"

    state: str = "TX"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def ebay_configured(self) -> bool:
        return bool(self.ebay_client_id and self.ebay_client_secret)

    @property
    def ebay_api_base(self) -> str:
        host = "api.sandbox.ebay.com" if self.ebay_env == "sandbox" else "api.ebay.com"
        return f"https://{host}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
