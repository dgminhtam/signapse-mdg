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
    binance_ws_base_url: str = "wss://stream.binance.com:9443"
    twelvedata_api_key: str | None = None
    twelvedata_rest_base_url: str = "https://api.twelvedata.com"
    provider_http_timeout_seconds: float = Field(default=5, gt=0)
    provider_ws_reconnect_delay_seconds: float = Field(default=5, ge=0)
    quote_cache_ttl_seconds: float = Field(default=10, ge=0)
    quote_stale_after_seconds: float = Field(default=30, gt=0)
    max_quote_symbols: int = Field(default=10, ge=1)
    max_candle_range_days: int = Field(default=30, ge=1)
    max_candles_per_request: int = Field(default=1000, ge=1, le=1000)
    stream_client_queue_capacity: int = Field(default=256, ge=1)
    stream_provider_queue_capacity: int = Field(default=1024, ge=1)
    stream_persistence_queue_capacity: int = Field(default=256, ge=1)
    stream_idle_grace_seconds: float = Field(default=5, ge=0)
    stream_freshness_check_seconds: float = Field(default=1, gt=0)
    twelvedata_ws_heartbeat_seconds: float = Field(default=15, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
