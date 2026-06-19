from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.quote_cache import QuoteCache
from app.core.config import Settings, get_settings
from app.db.repositories import PostgresSymbolRepository
from app.db.session import get_db_session
from app.domain.quotes import QuoteError, QuoteProvider, QuoteResult
from app.domain.symbols import SymbolRepository
from app.providers.binance_spot import build_binance_spot_quote_provider
from app.services.quotes import QuoteService, parse_symbols

router = APIRouter(prefix="/v1", tags=["quotes"])


class QuoteResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    symbol: str
    asset_class: str
    provider: str
    provider_symbol: str
    price: str
    volume: str | None
    provider_time: str | None
    received_at: str
    stale: bool

    @field_serializer("price", "volume")
    def serialize_decimal_string(self, value: str | None) -> str | None:
        return value


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
) -> QuoteProvider:
    return build_binance_spot_quote_provider(base_url, timeout_seconds)


def get_quote_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuoteProvider:
    return get_binance_quote_provider(
        settings.binance_rest_base_url,
        settings.provider_http_timeout_seconds,
    )


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
                asset_class=quote.asset_class,
                provider=quote.provider,
                provider_symbol=quote.provider_symbol,
                price=str(quote.price),
                volume=None if quote.volume is None else str(quote.volume),
                provider_time=(
                    None if quote.provider_time is None else quote.provider_time.isoformat()
                ),
                received_at=quote.received_at.isoformat().replace("+00:00", "Z"),
                stale=quote.stale,
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
