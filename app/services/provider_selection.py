import logging
from collections.abc import Sequence

from app.core.observability import record_provider_selection
from app.domain.errors import ProviderSelectionError
from app.domain.symbols import ProviderSelection, SelectionMode, SupportedSymbol

logger = logging.getLogger(__name__)

INVALID_PROVIDER_MESSAGE = "The provider query parameter is invalid."
UNSUPPORTED_PROVIDER_MESSAGE = "The requested provider is not supported for this symbol."
DATABASE_UNAVAILABLE_MESSAGE = (
    "The requested database-backed capability is temporarily unavailable."
)


def parse_provider_values(
    values: Sequence[str],
    *,
    error_type: type[Exception] = ProviderSelectionError,
) -> str | None:
    if not values:
        return None
    if len(values) != 1 or not values[0].strip():
        raise error_type("INVALID_PROVIDER", INVALID_PROVIDER_MESSAGE)
    return values[0]


def resolve_provider_selection(
    symbol: SupportedSymbol,
    provider: str | None,
) -> tuple[SupportedSymbol, ProviderSelection]:
    mappings = symbol.mappings
    defaults = [mapping for mapping in mappings if mapping.is_default]
    if len(defaults) != 1:
        raise ProviderSelectionError(
            "DATABASE_UNAVAILABLE",
            DATABASE_UNAVAILABLE_MESSAGE,
            {"symbol": symbol.symbol},
        )
    default = defaults[0]

    selected = default if provider is None else next(
        (mapping for mapping in mappings if mapping.provider == provider),
        None,
    )
    if selected is None:
        raise ProviderSelectionError(
            "UNSUPPORTED_PROVIDER",
            UNSUPPORTED_PROVIDER_MESSAGE,
            {"symbol": symbol.symbol, "provider": provider or ""},
        )

    mode: SelectionMode = "DEFAULT" if provider is None else "OVERRIDE"
    selected_symbol = symbol.with_mapping(selected)
    logger.info(
        "provider_selected",
        extra={
            "symbol": symbol.symbol,
            "provider": selected.provider,
            "provider_symbol": selected.provider_symbol,
            "selection_mode": mode,
        },
    )
    record_provider_selection(selected.provider, mode)
    return selected_symbol, ProviderSelection(
        symbol=symbol.symbol,
        provider=selected.provider,
        provider_symbol=selected.provider_symbol,
        mode=mode,
    )
