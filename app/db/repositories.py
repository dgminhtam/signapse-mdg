from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SupportedSymbolModel
from app.domain.errors import DatabaseUnavailableError
from app.domain.symbols import SupportedSymbol


class PostgresSymbolRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_enabled(self) -> list[SupportedSymbol]:
        statement = (
            select(SupportedSymbolModel)
            .where(SupportedSymbolModel.enabled.is_(True))
            .order_by(SupportedSymbolModel.symbol.asc())
        )
        try:
            rows = (await self._session.scalars(statement)).all()
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError from exc

        return [
            SupportedSymbol(
                symbol=row.symbol,
                asset_class=row.asset_class,
                provider=row.provider,
                provider_symbol=row.provider_symbol,
                enabled=row.enabled,
            )
            for row in rows
        ]
