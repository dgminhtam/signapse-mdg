from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.serialization import format_datetime, format_decimal
from app.cache.quote_cache import QuoteCache
from app.core.config import Settings, get_settings
from app.db.repositories import PostgresSymbolRepository
from app.db.session import get_db_session
from app.domain.quotes import ProviderSymbolQuoteProvider, QuoteError, QuoteProvider, QuoteResult
from app.domain.symbols import SymbolRepository
from app.providers.binance_spot import build_binance_spot_quote_provider
from app.providers.twelvedata_market_data import build_twelvedata_market_data_provider
from app.services.quote_provider_router import QuoteProviderRouter
from app.services.quotes import QuoteService, parse_symbols

router = APIRouter(prefix="/v1", tags=["quotes"])


class QuoteResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    symbol: str
    price: str
    received_at: str


class QuoteErrorResponse(BaseModel):
    symbol: str
    code: str
    message: str


class QuoteListResponse(BaseModel):
    quotes: list[QuoteResponse]
    errors: list[QuoteErrorResponse]


@lru_cache
def get_quote_cache() -> QuoteCache:
    return QuoteCache()


@lru_cache
def get_binance_quote_provider(
    base_url: str,
    timeout_seconds: float,
) -> ProviderSymbolQuoteProvider:
    return build_binance_spot_quote_provider(base_url, timeout_seconds)


@lru_cache
def get_twelvedata_quote_provider(
    api_key: str,
    base_url: str,
    timeout_seconds: float,
) -> ProviderSymbolQuoteProvider:
    return build_twelvedata_market_data_provider(api_key, base_url, timeout_seconds)


def get_quote_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuoteProvider:
    providers = {
        "BINANCE_SPOT": get_binance_quote_provider(
            settings.binance_rest_base_url,
            settings.provider_http_timeout_seconds,
        )
    }
    if settings.twelvedata_api_key is not None and settings.twelvedata_api_key.strip():
        providers["TWELVE_DATA"] = get_twelvedata_quote_provider(
            settings.twelvedata_api_key,
            settings.twelvedata_rest_base_url,
            settings.provider_http_timeout_seconds,
        )
    return QuoteProviderRouter(providers)


def get_quote_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SymbolRepository:
    return PostgresSymbolRepository(session)


def get_quote_service(
    repository: Annotated[SymbolRepository, Depends(get_quote_repository)],
    provider: Annotated[QuoteProvider, Depends(get_quote_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
    cache: Annotated[QuoteCache, Depends(get_quote_cache)],
) -> QuoteService:
    return QuoteService(
        repository=repository,
        provider=provider,
        cache=cache,
        cache_ttl_seconds=settings.quote_cache_ttl_seconds,
        stale_after_seconds=settings.quote_stale_after_seconds,
    )


@router.get("/quotes", response_model=QuoteListResponse)
async def get_latest_quotes(
    request: Request,
    service: Annotated[QuoteService, Depends(get_quote_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuoteListResponse:
    symbols = parse_symbols(request.query_params.get("symbols"), settings.max_quote_symbols)
    result = await service.get_latest_quotes(symbols)
    return _to_response(result)


def _to_response(result: QuoteResult) -> QuoteListResponse:
    return QuoteListResponse(
        quotes=[
            QuoteResponse(
                symbol=quote.symbol,
                price=format_decimal(quote.price),
                received_at=format_datetime(quote.received_at),
            )
            for quote in result.quotes
        ],
        errors=[_to_error_response(error) for error in result.errors],
    )


def _to_error_response(error: QuoteError) -> QuoteErrorResponse:
    return QuoteErrorResponse(
        symbol=error.symbol,
        code=error.code,
        message=error.message,
    )
