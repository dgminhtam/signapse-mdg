from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.symbols import SupportedSymbol


@dataclass(frozen=True, slots=True)
class PriceTick:
    symbol: SupportedSymbol
    price: Decimal
    provider_time: datetime | None
    received_at: datetime
