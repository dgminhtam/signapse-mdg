from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str | None = None
    database_pool_size: int = Field(default=5, ge=1)
    database_pool_max_overflow: int = Field(default=5, ge=0)
    database_pool_timeout_seconds: float = Field(default=5, gt=0)
    binance_rest_base_url: str = "https://api.binance.com"
    provider_http_timeout_seconds: float = Field(default=5, gt=0)
    quote_cache_ttl_seconds: float = Field(default=10, ge=0)
    quote_stale_after_seconds: float = Field(default=30, gt=0)
    max_quote_symbols: int = Field(default=10, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
