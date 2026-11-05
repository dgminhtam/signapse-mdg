from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.openapi import DATABASE_UNAVAILABLE_RESPONSE
from app.db.repositories import PostgresSymbolRepository
from app.db.session import get_db_session
from app.domain.symbols import SymbolRepository
from app.services.symbols import SymbolService

router = APIRouter(prefix="/v1", tags=["symbols"])


class ProviderMappingResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    provider: str = Field(
        description="Case-sensitive Provider Identifier accepted for this symbol."
    )
    provider_symbol: str = Field(description="Provider-specific instrument identifier.")
    is_default: bool = Field(description="Whether this mapping supplies the Default Provider.")


class SymbolResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    symbol: str = Field(description="Stable, case-sensitive canonical gateway symbol.")
    asset_class: str = Field(
        description="Asset classification from the registry, e.g. CRYPTO or FOREX."
    )
    provider: str = Field(
        description="Default Provider Identifier, not a consolidated data source."
    )
    provider_symbol: str = Field(description="Instrument identifier used by the Default Provider.")
    enabled: bool = Field(
        description="Whether the registry symbol is enabled; this endpoint lists enabled symbols."
    )
    price_display_decimals: int = Field(
        description="Number of decimal places for public prices, including trailing zeroes.",
        json_schema_extra={"minimum": 0, "maximum": 18},
    )
    # The route omits None; it never sends a nullable providerMappings property.
    provider_mappings: list[ProviderMappingResponse] | SkipJsonSchema[None] = Field(
        default=None,
        description="Supported mappings, default first then provider; omitted when unavailable.",
    )


class SymbolListResponse(BaseModel):
    symbols: list[SymbolResponse] = Field(
        description="Enabled symbols ordered by canonical symbol."
    )


def get_symbol_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SymbolRepository:
    return PostgresSymbolRepository(session)


def get_symbol_service(
    repository: Annotated[SymbolRepository, Depends(get_symbol_repository)],
) -> SymbolService:
    return SymbolService(repository)


@router.get(
    "/symbols",
    response_model=SymbolListResponse,
    response_model_exclude_none=True,
    summary="List supported symbols and provider mappings",
    description="Reads the enabled registry, ordered by canonical symbol. Symbols without a usable "
    "default mapping make the request fail with 503 DATABASE_UNAVAILABLE. "
    "provider/providerSymbol identify that default; providerMappings "
    "lists supported overrides when available. Mapping availability is not a live provider health "
    "guarantee. An empty registry returns an empty symbols array. No client authentication.",
    responses={
        200: {
            "description": "Enabled symbol registry.",
            "content": {
                "application/json": {
                    "example": {
                        "symbols": [
                            {
                                "symbol": "BTC/USDT",
                                "assetClass": "CRYPTO",
                                "provider": "BINANCE_SPOT",
                                "providerSymbol": "BTCUSDT",
                                "enabled": True,
                                "priceDisplayDecimals": 2,
                                "providerMappings": [
                                    {
                                        "provider": "BINANCE_SPOT",
                                        "providerSymbol": "BTCUSDT",
                                        "isDefault": True,
                                    },
                                ],
                            }
                        ]
                    }
                }
            },
        },
        503: DATABASE_UNAVAILABLE_RESPONSE,
    },
)
async def list_supported_symbols(
    service: Annotated[SymbolService, Depends(get_symbol_service)],
) -> SymbolListResponse:
    symbols = await service.list_supported_symbols()
    return SymbolListResponse(
        symbols=[
            SymbolResponse(
                symbol=symbol.symbol,
                asset_class=symbol.asset_class,
                provider=symbol.provider,
                provider_symbol=symbol.provider_symbol,
                enabled=symbol.enabled,
                price_display_decimals=symbol.price_display_decimals,
                provider_mappings=(
                    [
                        ProviderMappingResponse(
                            provider=mapping.provider,
                            provider_symbol=mapping.provider_symbol,
                            is_default=mapping.is_default,
                        )
                        for mapping in symbol.provider_mappings
                    ]
                    if symbol.provider_mappings
                    else None
                ),
            )
            for symbol in symbols
        ]
    )
