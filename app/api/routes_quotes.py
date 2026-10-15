from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.openapi import (
    DATABASE_UNAVAILABLE_RESPONSE,
    PRICE_DESCRIPTION,
    PROVIDER_PARAMETER,
    RAW_QUERY_DESCRIPTION,
    DecimalString,
    UtcTimestamp,
    error_response,
    query_parameter,
)
from app.api.serialization import format_datetime, format_price
from app.cache.quote_cache import QuoteCache
from app.core.config import Settings, get_settings
from app.db.repositories import PostgresSymbolRepository
from app.db.session import get_db_session
from app.domain.errors import ProviderSelectionError, QuoteRequestError
from app.domain.quotes import ProviderSymbolQuoteProvider, QuoteError, QuoteProvider, QuoteResult
from app.domain.symbols import SymbolRepository
from app.providers.binance_spot import build_binance_spot_quote_provider
from app.providers.twelvedata_market_data import build_twelvedata_market_data_provider
from app.providers.yfinance_market_data import build_yfinance_quote_provider
from app.services.provider_selection import parse_provider_values
from app.services.quote_provider_router import QuoteProviderRouter
from app.services.quotes import QuoteService, parse_symbols

router = APIRouter(prefix="/v1", tags=["quotes"])


class QuoteResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    symbol: str = Field(description="Canonical symbol from the request.")
    price: DecimalString = Field(description=PRICE_DESCRIPTION)
    received_at: UtcTimestamp = Field(
        description="UTC gateway receipt time used for freshness checks."
    )


class QuoteErrorResponse(BaseModel):
    symbol: str = Field(description="Canonical/requested symbol that could not be resolved.")
    code: str = Field(
        description="Per-symbol failure; this item does not change the HTTP 200 status.",
        json_schema_extra={
            "enum": [
                "UNSUPPORTED_SYMBOL",
                "UNSUPPORTED_PROVIDER",
                "PROVIDER_UNAVAILABLE",
                "DATA_STALE",
            ]
        },
    )
    message: str = Field(description="Human-readable explanation; branch on code, not message.")


class QuoteListResponse(BaseModel):
    quotes: list[QuoteResponse] = Field(
        description="Successful items in deduplicated request order."
    )
    errors: list[QuoteErrorResponse] = Field(
        description="Failed items in deduplicated request order."
    )


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
    api_keys: tuple[str, ...],
    base_url: str,
    timeout_seconds: float,
) -> ProviderSymbolQuoteProvider:
    return build_twelvedata_market_data_provider(api_keys, base_url, timeout_seconds)


@lru_cache
def get_yfinance_quote_provider(
    timeout_seconds: float,
) -> ProviderSymbolQuoteProvider:
    return build_yfinance_quote_provider(timeout_seconds)


def get_quote_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuoteProvider:
    providers: dict[str, ProviderSymbolQuoteProvider] = {
        "BINANCE_SPOT": get_binance_quote_provider(
            settings.binance_rest_base_url,
            settings.provider_http_timeout_seconds,
        ),
        "YFINANCE": get_yfinance_quote_provider(
            settings.provider_http_timeout_seconds,
        ),
    }
    twelvedata_api_keys = settings.twelvedata_effective_api_keys()
    if twelvedata_api_keys:
        providers["TWELVE_DATA"] = get_twelvedata_quote_provider(
            twelvedata_api_keys,
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


@router.get(
    "/quotes",
    response_model=QuoteListResponse,
    summary="Get latest quotes with per-symbol failures",
    description="Returns ordered quotes and errors. Unsupported symbols/mappings, unavailable "
    "providers and stale cached data are per-symbol errors under HTTP 200, even when every symbol "
    "fails. Database/registry failure affects the whole request and returns 503. Refresh failure "
    "may reuse a sufficiently recent quote from the same mapping, never another provider. "
    + RAW_QUERY_DESCRIPTION,
    openapi_extra={
        "parameters": [
            query_parameter(
                "symbols",
                "Comma-separated canonical symbols, case-sensitive. Trim each item, discard empty "
                "items, deduplicate while preserving first occurrence. At least one nonempty item "
                "is required; the configured maximum counts distinct symbols after normalization.",
                {"type": "string", "minLength": 1},
                required=True,
                example="BTC/USD,ETH/USD",
            ),
            PROVIDER_PARAMETER,
        ]
    },
    responses={
        200: {
            "description": "Successful, partial or all-failed quote batch.",
            "content": {
                "application/json": {
                    "example": {
                        "quotes": [
                            {
                                "symbol": "BTC/USD",
                                "price": "104250.12",
                                "receivedAt": "2026-06-19T10:30:12Z",
                            }
                        ],
                        "errors": [
                            {
                                "symbol": "UNKNOWN",
                                "code": "UNSUPPORTED_SYMBOL",
                                "message": "Symbol is not supported by this gateway.",
                            }
                        ],
                    }
                }
            },
        },
        400: error_response(
            "INVALID_SYMBOLS for missing/empty symbols; TOO_MANY_SYMBOLS for the distinct-symbol "
            "limit; INVALID_PROVIDER for an empty or repeated provider.",
            "INVALID_SYMBOLS",
            "The symbols query parameter is required.",
        ),
        503: DATABASE_UNAVAILABLE_RESPONSE,
    },
)
async def get_latest_quotes(
    request: Request,
    service: Annotated[QuoteService, Depends(get_quote_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuoteListResponse:
    symbols = parse_symbols(request.query_params.get("symbols"), settings.max_quote_symbols)
    try:
        provider = parse_provider_values(request.query_params.getlist("provider"))
    except ProviderSelectionError as exc:
        raise QuoteRequestError(exc.code, exc.message) from exc
    result = (
        await service.get_latest_quotes(symbols)
        if provider is None
        else await service.get_latest_quotes(symbols, provider)
    )
    return _to_response(result)


def _to_response(result: QuoteResult) -> QuoteListResponse:
    return QuoteListResponse(
        quotes=[
            QuoteResponse(
                symbol=quote.symbol,
                price=format_price(
                    quote.price,
                    result.price_display_decimals[quote.symbol],
                ),
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
