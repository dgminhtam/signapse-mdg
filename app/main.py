from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import (
    candle_request_error_handler,
    database_unavailable_handler,
    provider_unavailable_handler,
    quote_request_error_handler,
)
from app.api.routes_candles import get_candle_cache
from app.api.routes_candles import router as candles_router
from app.api.routes_health import router as health_router
from app.api.routes_quotes import get_quote_cache
from app.api.routes_quotes import router as quotes_router
from app.api.routes_stream import router as stream_router
from app.api.routes_symbols import router as symbols_router
from app.core.config import get_settings
from app.db.repositories import PostgresCandleRepository
from app.db.session import build_session_factory
from app.domain.errors import (
    CandleRequestError,
    DatabaseUnavailableError,
    ProviderUnavailableError,
    QuoteRequestError,
)
from app.providers.binance_spot_stream import build_binance_spot_stream_provider
from app.providers.twelvedata_market_data_stream import (
    build_twelvedata_market_data_stream_provider,
)
from app.providers.yfinance_market_data_stream import (
    build_yfinance_market_data_stream_provider,
)
from app.services.stream_manager import StreamManager
from app.services.stream_provider_router import MultiProviderStreamProvider


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    database = build_session_factory(settings)
    repository = PostgresCandleRepository(database[1]) if database is not None else None
    binance_provider = build_binance_spot_stream_provider(
        settings.binance_ws_base_url,
        settings.provider_ws_reconnect_delay_seconds,
        settings.stream_provider_queue_capacity,
    )
    twelvedata_provider = build_twelvedata_market_data_stream_provider(
        settings.twelvedata_effective_api_keys(),
        queue_capacity=settings.stream_provider_queue_capacity,
        heartbeat_seconds=settings.twelvedata_ws_heartbeat_seconds,
    )
    yfinance_provider = build_yfinance_market_data_stream_provider(
        queue_capacity=settings.stream_provider_queue_capacity,
        reconnect_delay_seconds=settings.provider_ws_reconnect_delay_seconds,
    )
    provider = MultiProviderStreamProvider(
        {
            "BINANCE_SPOT": binance_provider,
            "TWELVE_DATA": twelvedata_provider,
            "YFINANCE": yfinance_provider,
        },
        queue_capacity=settings.stream_provider_queue_capacity,
    )
    manager = StreamManager(
        provider=provider,
        quote_cache=get_quote_cache(),
        candle_cache=get_candle_cache(),
        candle_repository=repository,
        client_queue_capacity=settings.stream_client_queue_capacity,
        persistence_queue_capacity=settings.stream_persistence_queue_capacity,
        idle_grace_seconds=settings.stream_idle_grace_seconds,
        stale_after_seconds=settings.quote_stale_after_seconds,
        freshness_check_seconds=settings.stream_freshness_check_seconds,
    )
    application.state.stream_manager = manager
    application.state.stream_provider = provider
    application.state.binance_stream_provider = binance_provider
    application.state.twelvedata_market_data_stream_provider = twelvedata_provider
    application.state.yfinance_market_data_stream_provider = yfinance_provider
    yield
    await manager.stop()
    if database is not None:
        await database[0].dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title="Signapse Market Data Gateway",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_exception_handler(
        DatabaseUnavailableError,
        database_unavailable_handler,
    )
    application.add_exception_handler(QuoteRequestError, quote_request_error_handler)
    application.add_exception_handler(CandleRequestError, candle_request_error_handler)
    application.add_exception_handler(ProviderUnavailableError, provider_unavailable_handler)
    application.include_router(health_router)
    application.include_router(symbols_router)
    application.include_router(quotes_router)
    application.include_router(candles_router)
    application.include_router(stream_router)
    return application


app = create_app()
