from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupportedSymbolModel(Base):
    __tablename__ = "supported_symbols"
    __table_args__ = (
        CheckConstraint(
            "price_display_decimals BETWEEN 0 AND 18",
            name="ck_supported_symbols_price_display_decimals",
        ),
        UniqueConstraint(
            "provider", "provider_symbol", name="uq_supported_symbols_provider_symbol"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    asset_class: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_symbol: Mapped[str] = mapped_column(Text, nullable=False)
    price_display_decimals: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    calendar_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    calendar_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    calendar_timezone: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MarketDataCandleModel(Base):
    __tablename__ = "market_data_candles"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_symbol",
            "timeframe",
            "open_time",
            name="uq_market_data_candles_identity",
        ),
        Index(
            "ix_market_data_candles_symbol_timeframe_open_time",
            "symbol",
            "timeframe",
            "open_time",
        ),
        Index(
            "ix_market_data_candles_provider_symbol_timeframe_open_time",
            "provider",
            "provider_symbol",
            "timeframe",
            "open_time",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    asset_class: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_symbol: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(Text, nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EconomicCalendarEventModel(Base):
    __tablename__ = "economic_calendar_events"
    __table_args__ = (
        CheckConstraint(
            "calendar_type IN ('FOREX', 'METALS', 'ENERGY', 'CRYPTO')",
            name="ck_economic_calendar_events_calendar_type",
        ),
        UniqueConstraint(
            "calendar_type",
            "external_event_id",
            name="uq_economic_calendar_events_identity",
        ),
        Index("ix_economic_calendar_events_scheduled_at", "scheduled_at"),
        Index(
            "ix_economic_calendar_events_type_scheduled_at",
            "calendar_type",
            "scheduled_at",
        ),
        Index(
            "ix_economic_calendar_events_currency_scheduled_at",
            "currency",
            "scheduled_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    calendar_type: Mapped[str] = mapped_column(Text, nullable=False)
    external_event_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual: Mapped[str | None] = mapped_column(Text, nullable=True)
    forecast: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_better_worse: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision_better_worse: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    news_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
