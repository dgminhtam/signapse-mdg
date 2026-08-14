from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import PostgresSymbolRepository
from app.db.session import get_db_session
from app.domain.symbols import SymbolRepository
from app.services.symbols import SymbolService

router = APIRouter(prefix="/v1", tags=["symbols"])


class ProviderMappingResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    provider: str
    provider_symbol: str
    is_default: bool


class SymbolResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    symbol: str
    asset_class: str
    provider: str
    provider_symbol: str
    enabled: bool
    price_display_decimals: int
    provider_mappings: list[ProviderMappingResponse] | None = None


class SymbolListResponse(BaseModel):
    symbols: list[SymbolResponse]


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
