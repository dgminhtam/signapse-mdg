from app.domain.symbols import SupportedSymbol
from app.services.symbols import SymbolService


class FakeSymbolRepository:
    def __init__(self, symbols: list[SupportedSymbol]) -> None:
        self.symbols = symbols
        self.calls = 0

    async def list_enabled(self) -> list[SupportedSymbol]:
        self.calls += 1
        return self.symbols


async def test_service_delegates_to_repository() -> None:
    expected = [
        SupportedSymbol(
            symbol="BTC/USD",
            asset_class="CRYPTO",
            provider="TWELVE_DATA",
            provider_symbol="BTC/USD",
            enabled=True,
        )
    ]
    repository = FakeSymbolRepository(expected)

    result = await SymbolService(repository).list_supported_symbols()

    assert result == expected
    assert repository.calls == 1
