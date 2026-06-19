from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SupportedSymbol:
    symbol: str
    asset_class: str
    provider: str
    provider_symbol: str
    enabled: bool


class SymbolRepository(Protocol):
    async def list_enabled(self) -> list[SupportedSymbol]: ...
