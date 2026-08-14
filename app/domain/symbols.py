from dataclasses import dataclass, replace
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ProviderMapping:
    provider: str
    provider_symbol: str
    is_default: bool


SelectionMode = Literal["DEFAULT", "OVERRIDE"]


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    symbol: str
    provider: str
    provider_symbol: str
    mode: SelectionMode

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.symbol, self.provider, self.provider_symbol


@dataclass(frozen=True, slots=True)
class SupportedSymbol:
    symbol: str
    asset_class: str
    provider: str
    provider_symbol: str
    enabled: bool
    price_display_decimals: int
    calendar_source: str | None = None
    calendar_name: str | None = None
    calendar_timezone: str | None = None
    provider_mappings: tuple[ProviderMapping, ...] = ()

    @property
    def mappings(self) -> tuple[ProviderMapping, ...]:
        """Return mappings while preserving compatibility with hand-built symbols."""
        if self.provider_mappings:
            return self.provider_mappings
        return (ProviderMapping(self.provider, self.provider_symbol, True),)

    def with_mapping(self, mapping: ProviderMapping) -> SupportedSymbol:
        return replace(
            self,
            provider=mapping.provider,
            provider_symbol=mapping.provider_symbol,
        )


class SymbolRepository(Protocol):
    async def list_enabled(self) -> list[SupportedSymbol]: ...
