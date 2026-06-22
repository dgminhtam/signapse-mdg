from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import MarketDataCandleModel, SupportedSymbolModel
from app.domain.candles import Candle
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


class PostgresCandleRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_enabled_symbol(self, symbol: str) -> SupportedSymbol | None:
        statement = select(SupportedSymbolModel).where(
            SupportedSymbolModel.symbol == symbol,
            SupportedSymbolModel.enabled.is_(True),
        )
        try:
            async with self._session_factory() as session:
                row = await session.scalar(statement)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError from exc
        if row is None:
            return None
        return SupportedSymbol(
            symbol=row.symbol,
            asset_class=row.asset_class,
            provider=row.provider,
            provider_symbol=row.provider_symbol,
            enabled=row.enabled,
        )

    async def list_complete(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        statement = (
            select(MarketDataCandleModel)
            .where(
                MarketDataCandleModel.provider == symbol.provider,
                MarketDataCandleModel.provider_symbol == symbol.provider_symbol,
                MarketDataCandleModel.timeframe == timeframe,
                MarketDataCandleModel.open_time >= start,
                MarketDataCandleModel.open_time < end,
                MarketDataCandleModel.complete.is_(True),
            )
            .order_by(MarketDataCandleModel.open_time.asc())
        )
        try:
            async with self._session_factory() as session:
                rows = (await session.scalars(statement)).all()
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError from exc
        return [_to_candle(row) for row in rows]

    async def upsert_complete(self, candles: list[Candle]) -> None:
        complete = [candle for candle in candles if candle.complete]
        if not complete:
            return
        try:
            async with self._session_factory.begin() as session:
                for candle in complete:
                    statement = insert(MarketDataCandleModel).values(
                        symbol=candle.symbol,
                        asset_class=candle.asset_class,
                        provider=candle.provider,
                        provider_symbol=candle.provider_symbol,
                        timeframe=candle.timeframe,
                        open_time=candle.open_time,
                        close_time=candle.close_time,
                        open=candle.open,
                        high=candle.high,
                        low=candle.low,
                        close=candle.close,
                        volume=candle.volume,
                        complete=True,
                    )
                    await session.execute(
                        statement.on_conflict_do_update(
                            constraint="uq_market_data_candles_identity",
                            set_={
                                "symbol": statement.excluded.symbol,
                                "asset_class": statement.excluded.asset_class,
                                "close_time": statement.excluded.close_time,
                                "open": statement.excluded.open,
                                "high": statement.excluded.high,
                                "low": statement.excluded.low,
                                "close": statement.excluded.close,
                                "volume": statement.excluded.volume,
                                "complete": True,
                                "updated_at": func.now(),
                            },
                        )
                    )
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError from exc


def _to_candle(row: MarketDataCandleModel) -> Candle:
    return Candle(
        symbol=row.symbol,
        asset_class=row.asset_class,
        provider=row.provider,
        provider_symbol=row.provider_symbol,
        timeframe=row.timeframe,
        open_time=row.open_time,
        close_time=row.close_time,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        volume=row.volume,
        complete=row.complete,
    )
