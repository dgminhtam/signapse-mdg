from datetime import UTC, datetime

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import (
    EconomicCalendarEventModel,
    MarketDataCandleModel,
    SupportedSymbolModel,
    SymbolProviderMappingModel,
)
from app.domain.candles import Candle
from app.domain.economic_calendar import (
    EconomicCalendarEnrichment,
    EconomicCalendarEnrichmentCandidate,
    EconomicCalendarEvent,
    EconomicCalendarFetchedEvent,
    EconomicCalendarRequest,
)
from app.domain.errors import DatabaseUnavailableError
from app.domain.symbols import ProviderMapping, SupportedSymbol


class PostgresSymbolRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_enabled(self) -> list[SupportedSymbol]:
        statement = (
            select(SupportedSymbolModel, SymbolProviderMappingModel)
            .outerjoin(
                SymbolProviderMappingModel,
                and_(
                    SymbolProviderMappingModel.supported_symbol_id == SupportedSymbolModel.id,
                ),
            )
            .where(SupportedSymbolModel.enabled.is_(True))
            .order_by(
                SupportedSymbolModel.symbol.asc(),
                SymbolProviderMappingModel.is_active.desc().nullslast(),
                SymbolProviderMappingModel.provider.asc().nullslast(),
            )
        )
        try:
            rows = (await self._session.execute(statement)).all()
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError from exc

        grouped: dict[int, tuple[SupportedSymbolModel, list[SymbolProviderMappingModel]]] = {}
        for symbol, mapping in rows:
            entry = grouped.setdefault(symbol.id, (symbol, []))
            if mapping is not None:
                entry[1].append(mapping)
        return [_to_supported_symbol(symbol, mappings) for symbol, mappings in grouped.values()]


class PostgresCandleRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_enabled_symbol(
        self,
        symbol: str,
        provider: str | None = None,
    ) -> SupportedSymbol | None:
        statement = (
            select(SupportedSymbolModel, SymbolProviderMappingModel)
            .outerjoin(
                SymbolProviderMappingModel,
                and_(
                    SymbolProviderMappingModel.supported_symbol_id == SupportedSymbolModel.id,
                ),
            )
            .where(
                SupportedSymbolModel.symbol == symbol,
                SupportedSymbolModel.enabled.is_(True),
            )
        )
        try:
            async with self._session_factory() as session:
                rows = (await session.execute(statement)).all()
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError from exc
        if not rows:
            return None
        symbol_model = rows[0][0]
        mappings = [mapping for _, mapping in rows if mapping is not None]
        resolved = _to_supported_symbol(symbol_model, mappings)
        if provider is None:
            return resolved
        selected = next(
            (mapping for mapping in resolved.mappings if mapping.provider == provider),
            None,
        )
        return None if selected is None else resolved.with_mapping(selected)

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


class PostgresEconomicCalendarRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_events(
        self,
        request: EconomicCalendarRequest,
    ) -> list[EconomicCalendarEvent]:
        statement = (
            select(EconomicCalendarEventModel)
            .where(
                EconomicCalendarEventModel.scheduled_at >= request.start,
                EconomicCalendarEventModel.scheduled_at < request.end,
            )
            .order_by(
                EconomicCalendarEventModel.scheduled_at.asc(),
                EconomicCalendarEventModel.calendar_type.asc(),
                EconomicCalendarEventModel.external_event_id.asc(),
            )
            .limit(request.limit)
        )
        if request.types:
            statement = statement.where(EconomicCalendarEventModel.calendar_type.in_(request.types))
        if request.currencies:
            statement = statement.where(EconomicCalendarEventModel.currency.in_(request.currencies))
        if request.impact:
            statement = statement.where(EconomicCalendarEventModel.impact.in_(request.impact))
        try:
            async with self._session_factory() as session:
                rows = (await session.scalars(statement)).all()
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError from exc
        return [_to_economic_calendar_event(row) for row in rows]

    async def upsert_events(self, events: list[EconomicCalendarFetchedEvent]) -> None:
        if not events:
            return
        try:
            async with self._session_factory.begin() as session:
                for event in events:
                    statement = insert(EconomicCalendarEventModel).values(
                        calendar_type=event.calendar_type,
                        external_event_id=event.external_event_id,
                        name=event.name,
                        currency=event.currency,
                        impact=event.impact,
                        scheduled_at=event.scheduled_at,
                        actual=event.actual,
                        forecast=event.forecast,
                        previous=event.previous,
                        revision=event.revision,
                        actual_better_worse=event.actual_better_worse,
                        revision_better_worse=event.revision_better_worse,
                        description=event.description,
                        news_url=event.news_url,
                    )
                    excluded = statement.excluded
                    description = func.coalesce(
                        excluded.description,
                        EconomicCalendarEventModel.description,
                    )
                    news_url = func.coalesce(
                        excluded.news_url,
                        EconomicCalendarEventModel.news_url,
                    )
                    changed = or_(
                        EconomicCalendarEventModel.name.is_distinct_from(excluded.name),
                        EconomicCalendarEventModel.currency.is_distinct_from(excluded.currency),
                        EconomicCalendarEventModel.impact.is_distinct_from(excluded.impact),
                        EconomicCalendarEventModel.scheduled_at.is_distinct_from(
                            excluded.scheduled_at
                        ),
                        EconomicCalendarEventModel.actual.is_distinct_from(excluded.actual),
                        EconomicCalendarEventModel.forecast.is_distinct_from(excluded.forecast),
                        EconomicCalendarEventModel.previous.is_distinct_from(excluded.previous),
                        EconomicCalendarEventModel.revision.is_distinct_from(excluded.revision),
                        EconomicCalendarEventModel.actual_better_worse.is_distinct_from(
                            excluded.actual_better_worse
                        ),
                        EconomicCalendarEventModel.revision_better_worse.is_distinct_from(
                            excluded.revision_better_worse
                        ),
                        EconomicCalendarEventModel.description.is_distinct_from(description),
                        EconomicCalendarEventModel.news_url.is_distinct_from(news_url),
                    )
                    await session.execute(
                        statement.on_conflict_do_update(
                            constraint="uq_economic_calendar_events_identity",
                            set_={
                                "name": excluded.name,
                                "currency": excluded.currency,
                                "impact": excluded.impact,
                                "scheduled_at": excluded.scheduled_at,
                                "actual": excluded.actual,
                                "forecast": excluded.forecast,
                                "previous": excluded.previous,
                                "revision": excluded.revision,
                                "actual_better_worse": excluded.actual_better_worse,
                                "revision_better_worse": excluded.revision_better_worse,
                                "description": description,
                                "news_url": news_url,
                                "last_seen_at": func.now(),
                                "last_changed_at": case(
                                    (changed, func.now()),
                                    else_=EconomicCalendarEventModel.last_changed_at,
                                ),
                                "updated_at": func.now(),
                            },
                        )
                    )
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError from exc

    async def claim_enrichment_candidates(
        self,
        start: datetime,
        end: datetime,
        attempted_at: datetime,
    ) -> list[EconomicCalendarEnrichmentCandidate]:
        day_start = attempted_at.astimezone(UTC).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        statement = (
            select(EconomicCalendarEventModel)
            .where(
                EconomicCalendarEventModel.scheduled_at >= start,
                EconomicCalendarEventModel.scheduled_at < end,
                or_(
                    EconomicCalendarEventModel.description.is_(None),
                    EconomicCalendarEventModel.news_url.is_(None),
                ),
                or_(
                    EconomicCalendarEventModel.enrichment_attempted_at.is_(None),
                    EconomicCalendarEventModel.enrichment_attempted_at < day_start,
                ),
            )
            .order_by(
                EconomicCalendarEventModel.scheduled_at.asc(),
                EconomicCalendarEventModel.calendar_type.asc(),
                EconomicCalendarEventModel.external_event_id.asc(),
            )
            .with_for_update(skip_locked=True)
        )
        try:
            async with self._session_factory.begin() as session:
                rows = (await session.scalars(statement)).all()
                candidates = [
                    EconomicCalendarEnrichmentCandidate(
                        calendar_type=row.calendar_type,
                        external_event_id=row.external_event_id,
                    )
                    for row in rows
                ]
                for row in rows:
                    row.enrichment_attempted_at = attempted_at
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError from exc
        return candidates

    async def update_enrichments(
        self,
        enrichments: list[EconomicCalendarEnrichment],
    ) -> None:
        usable = [
            enrichment
            for enrichment in enrichments
            if enrichment.description is not None or enrichment.news_url is not None
        ]
        if not usable:
            return
        try:
            async with self._session_factory.begin() as session:
                for enrichment in usable:
                    values: dict[str, object] = {
                        "last_seen_at": func.now(),
                        "updated_at": func.now(),
                    }
                    changed = []
                    if enrichment.description is not None:
                        values["description"] = enrichment.description
                        changed.append(
                            EconomicCalendarEventModel.description.is_distinct_from(
                                enrichment.description
                            )
                        )
                    if enrichment.news_url is not None:
                        values["news_url"] = enrichment.news_url
                        changed.append(
                            EconomicCalendarEventModel.news_url.is_distinct_from(
                                enrichment.news_url
                            )
                        )
                    values["last_changed_at"] = case(
                        (or_(*changed), func.now()),
                        else_=EconomicCalendarEventModel.last_changed_at,
                    )
                    await session.execute(
                        update(EconomicCalendarEventModel)
                        .where(
                            EconomicCalendarEventModel.calendar_type == enrichment.calendar_type,
                            EconomicCalendarEventModel.external_event_id
                            == enrichment.external_event_id,
                        )
                        .values(**values)
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


def _to_economic_calendar_event(row: EconomicCalendarEventModel) -> EconomicCalendarEvent:
    return EconomicCalendarEvent(
        calendar_type=row.calendar_type,
        external_event_id=row.external_event_id,
        name=row.name,
        currency=row.currency,
        impact=row.impact,
        scheduled_at=row.scheduled_at,
        actual=row.actual,
        forecast=row.forecast,
        previous=row.previous,
        revision=row.revision,
        actual_better_worse=row.actual_better_worse,
        revision_better_worse=row.revision_better_worse,
        description=row.description,
        news_url=row.news_url,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        last_changed_at=row.last_changed_at,
    )


def _to_supported_symbol(
    row: SupportedSymbolModel,
    mappings: list[SymbolProviderMappingModel],
) -> SupportedSymbol:
    ordered_mappings = sorted(
        mappings,
        key=lambda mapping: (not mapping.is_active, mapping.provider),
    )
    defaults = [mapping for mapping in ordered_mappings if mapping.is_active]
    if len(defaults) != 1:
        raise DatabaseUnavailableError
    default = defaults[0]
    provider_mappings = tuple(
        ProviderMapping(
            provider=mapping.provider,
            provider_symbol=mapping.provider_symbol,
            is_default=mapping.is_active,
        )
        for mapping in ordered_mappings
    )
    return SupportedSymbol(
        symbol=row.symbol,
        asset_class=row.asset_class,
        provider=default.provider,
        provider_symbol=default.provider_symbol,
        enabled=row.enabled,
        price_display_decimals=row.price_display_decimals,
        calendar_source=row.calendar_source,
        calendar_name=row.calendar_name,
        calendar_timezone=row.calendar_timezone,
        provider_mappings=provider_mappings,
    )
