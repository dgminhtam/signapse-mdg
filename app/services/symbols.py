from app.domain.symbols import SupportedSymbol, SymbolRepository


class SymbolService:
    def __init__(self, repository: SymbolRepository) -> None:
        self._repository = repository

    async def list_supported_symbols(self) -> list[SupportedSymbol]:
        return await self._repository.list_enabled()
