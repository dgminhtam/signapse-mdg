from datetime import datetime

from app.domain.candles import Candle, CandleProvider
from app.domain.errors import ProviderUnavailableError
from app.domain.symbols import SupportedSymbol


class CandleProviderRouter:
    def __init__(self, providers: dict[str, CandleProvider]) -> None:
        self._providers = providers

    async def fetch_candles(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Candle]:
        provider = self._providers.get(symbol.provider)
        if provider is None:
            raise ProviderUnavailableError
        return await provider.fetch_candles(
            symbol=symbol,
            timeframe=timeframe,
            provider_interval=provider_interval,
            start=start,
            end=end,
            limit=limit,
        )
