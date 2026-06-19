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


class SymbolResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    symbol: str
    asset_class: str
    provider: str
    provider_symbol: str
    enabled: bool


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


@router.get("/symbols", response_model=SymbolListResponse)
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
            )
            for symbol in symbols
        ]
    )
