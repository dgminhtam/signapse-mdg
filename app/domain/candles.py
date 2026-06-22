from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.domain.symbols import SupportedSymbol


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    asset_class: str
    provider: str
    provider_symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    complete: bool


@dataclass(frozen=True, slots=True)
class CandleRequest:
    symbol: str
    timeframe: str
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class CandleResult:
    symbol: str
    timeframe: str
    start: datetime
    end: datetime
    candles: list[Candle]


class CandleRepository(Protocol):
    async def get_enabled_symbol(self, symbol: str) -> SupportedSymbol | None: ...

    async def list_complete(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]: ...

    async def upsert_complete(self, candles: list[Candle]) -> None: ...


class CandleProvider(Protocol):
    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]: ...
