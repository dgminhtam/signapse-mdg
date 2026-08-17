from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import (
    candle_request_error_handler,
    database_unavailable_handler,
    economic_calendar_request_error_handler,
    historical_price_not_found_handler,
    provider_unavailable_handler,
    quote_request_error_handler,
    unexpected_error_handler,
)
from app.api.routes_candles import router as candles_router
from app.api.routes_crawl import router as crawl_router
from app.api.routes_economic_calendar import router as economic_calendar_router
from app.api.routes_health import router as health_router
from app.api.routes_historical_price import router as historical_price_router
from app.api.routes_quotes import get_quote_cache
from app.api.routes_quotes import router as quotes_router
from app.api.routes_stream import router as stream_router
from app.api.routes_symbols import router as symbols_router
from app.core.config import get_settings
from app.core.cronjob import CronjobManager
from app.core.observability import DiagnosticContextMiddleware, configure_logging
from app.db.repositories import PostgresEconomicCalendarRepository
from app.db.session import build_session_factory
from app.domain.errors import (
    CandleRequestError,
    DatabaseUnavailableError,
    EconomicCalendarRequestError,
    HistoricalPriceNotFoundError,
    ProviderUnavailableError,
    QuoteRequestError,
)
from app.providers.binance_spot_stream import build_binance_spot_stream_provider
from app.providers.market_calendar_tool import MarketCalendarToolProvider
from app.providers.twelvedata_market_data_stream import (
    build_twelvedata_market_data_stream_provider,
)
from app.providers.yfinance_market_data_stream import (
    build_yfinance_market_data_stream_provider,
)
from app.services.economic_calendar_refresh import (
    EconomicCalendarFetchCronjob,
    EconomicCalendarRefreshService,
)
from app.services.stream_manager import StreamManager
from app.services.stream_provider_router import MultiProviderStreamProvider


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    cronjob_manager = CronjobManager()
    database = build_session_factory(settings)
    if database is not None and settings.economic_calendar_poll_seconds > 0:
        cronjob_manager.register(
            EconomicCalendarFetchCronjob(
                EconomicCalendarRefreshService(
                    provider=MarketCalendarToolProvider(),
                    repository=PostgresEconomicCalendarRepository(database[1]),
                ),
                interval_seconds=settings.economic_calendar_poll_seconds,
            )
        )
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
        client_queue_capacity=settings.stream_client_queue_capacity,
        idle_grace_seconds=settings.stream_idle_grace_seconds,
        stale_after_seconds=settings.quote_stale_after_seconds,
        freshness_check_seconds=settings.stream_freshness_check_seconds,
    )
    application.state.stream_manager = manager
    application.state.stream_provider = provider
    application.state.binance_stream_provider = binance_provider
    application.state.twelvedata_market_data_stream_provider = twelvedata_provider
    application.state.yfinance_market_data_stream_provider = yfinance_provider
    application.state.cronjob_manager = cronjob_manager
    await cronjob_manager.start()
    yield
    await cronjob_manager.stop()
    await manager.stop()
    if database is not None:
        await database[0].dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title="Signapse Market Data Gateway",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(DiagnosticContextMiddleware)
    application.add_exception_handler(Exception, unexpected_error_handler)
    application.add_exception_handler(
        DatabaseUnavailableError,
        database_unavailable_handler,
    )
    application.add_exception_handler(QuoteRequestError, quote_request_error_handler)
    application.add_exception_handler(CandleRequestError, candle_request_error_handler)
    application.add_exception_handler(
        EconomicCalendarRequestError,
        economic_calendar_request_error_handler,
    )
    application.add_exception_handler(
        HistoricalPriceNotFoundError,
        historical_price_not_found_handler,
    )
    application.add_exception_handler(ProviderUnavailableError, provider_unavailable_handler)
    application.include_router(health_router)
    application.include_router(symbols_router)
    application.include_router(quotes_router)
    application.include_router(candles_router)
    application.include_router(historical_price_router)
    application.include_router(economic_calendar_router)
    application.include_router(stream_router)
    application.include_router(crawl_router)
    return application


app = create_app()
