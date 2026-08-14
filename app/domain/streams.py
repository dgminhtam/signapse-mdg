import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from app.domain.candles import Candle
from app.domain.quotes import Quote
from app.domain.symbols import SupportedSymbol

StreamChannel = Literal["quote", "candle"]
StreamState = Literal[
    "CONNECTING",
    "SUBSCRIBED",
    "STALE",
    "RECONNECTING",
    "MARKET_CLOSED",
    "ERROR",
]


@dataclass(frozen=True, slots=True, eq=False)
class QuoteInterest:
    symbol: str
    provider: str | None = None
    provider_symbol: str | None = None
    channel: Literal["quote"] = "quote"

    def __hash__(self) -> int:
        return hash((self.symbol, self.channel))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, QuoteInterest):
            return NotImplemented
        return (
            self.symbol == other.symbol
            and self.channel == other.channel
            and _optional_equal(self.provider, other.provider)
            and _optional_equal(self.provider_symbol, other.provider_symbol)
        )


@dataclass(frozen=True, slots=True, eq=False)
class CandleInterest:
    symbol: str
    timeframe: str
    provider: str | None = None
    provider_symbol: str | None = None
    channel: Literal["candle"] = "candle"

    def __hash__(self) -> int:
        return hash((self.symbol, self.timeframe, self.channel))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CandleInterest):
            return NotImplemented
        return (
            self.symbol == other.symbol
            and self.timeframe == other.timeframe
            and self.channel == other.channel
            and _optional_equal(self.provider, other.provider)
            and _optional_equal(self.provider_symbol, other.provider_symbol)
        )


type StreamInterest = QuoteInterest | CandleInterest


@dataclass(frozen=True, slots=True)
class StreamQuote:
    quote: Quote

    @property
    def interest(self) -> QuoteInterest:
        return QuoteInterest(
            self.quote.symbol,
            self.quote.provider,
            self.quote.provider_symbol,
        )


@dataclass(frozen=True, slots=True)
class StreamCandle:
    candle: Candle
    received_at: datetime

    @property
    def interest(self) -> CandleInterest:
        return CandleInterest(
            self.candle.symbol,
            self.candle.timeframe,
            self.candle.provider,
            self.candle.provider_symbol,
        )


@dataclass(frozen=True, slots=True)
class ProviderSignal:
    state: Literal["RECONNECTING", "MARKET_CLOSED", "CONNECTING", "ERROR"]
    interests: tuple[StreamInterest, ...]
    observed_at: datetime
    code: str = "PROVIDER_UNAVAILABLE"
    message: str = "The market data provider is temporarily unavailable."


type ProviderStreamEvent = StreamQuote | StreamCandle | ProviderSignal


@dataclass(frozen=True, slots=True)
class StatusEvent:
    state: StreamState
    symbols: tuple[str, ...]
    channels: tuple[StreamChannel, ...]
    observed_at: datetime
    code: str | None = None
    message: str | None = None


type DownstreamEvent = StreamQuote | StreamCandle | StatusEvent


@dataclass(frozen=True, slots=True)
class StreamRequest:
    symbols: tuple[str, ...]
    timeframe: str
    provider: str | None = None


class MarketStreamProvider(Protocol):
    events: asyncio.Queue[ProviderStreamEvent]

    async def subscribe_quote(self, symbol: SupportedSymbol) -> None: ...

    async def subscribe_candle(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
    ) -> None: ...

    async def unsubscribe(self, interest: StreamInterest) -> None: ...

    async def close(self) -> None: ...


def _optional_equal(left: str | None, right: str | None) -> bool:
    return left is None or right is None or left == right
