from collections import Counter

_provider_selection_counts: Counter[tuple[str, str]] = Counter()


def record_provider_selection(provider: str, mode: str) -> None:
    """Record low-cardinality provider/mode telemetry for internal diagnostics."""
    _provider_selection_counts[(provider, mode)] += 1


def provider_selection_counts() -> dict[tuple[str, str], int]:
    return dict(_provider_selection_counts)
