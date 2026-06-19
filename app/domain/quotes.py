from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    asset_class: str
    provider: str
    provider_symbol: str
    price: Decimal
    volume: Decimal | None
    provider_time: datetime | None
    received_at: datetime
    stale: bool = False


@dataclass(frozen=True, slots=True)
class QuoteError:
    symbol: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class QuoteResult:
    quotes: list[Quote]
    errors: list[QuoteError]


@dataclass(frozen=True, slots=True)
class ProviderQuoteBatch:
    prices: dict[str, Decimal]
    unavailable_symbols: frozenset[str]


class QuoteProvider(Protocol):
    async def fetch_latest_prices(
        self,
        provider_symbols: list[str],
    ) -> ProviderQuoteBatch: ...
