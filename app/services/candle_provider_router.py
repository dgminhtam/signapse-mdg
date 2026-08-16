import logging
from datetime import datetime

from app.core.observability import log_failure
from app.domain.candles import Candle, CandleProvider
from app.domain.errors import ProviderUnavailableError
from app.domain.symbols import SupportedSymbol

logger = logging.getLogger(__name__)


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
            error = ProviderUnavailableError(
                failure_reason="PROVIDER_NOT_CONFIGURED",
                operation="candles.fetch_candles",
                provider=symbol.provider,
                provider_symbol=symbol.provider_symbol,
                symbol=symbol.symbol,
                timeframe=timeframe,
                request_from=start,
                request_to=end,
            )
            log_failure(logger, "provider_not_configured", error)
            raise error
        return await provider.fetch_candles(
            symbol=symbol,
            timeframe=timeframe,
            provider_interval=provider_interval,
            start=start,
            end=end,
            limit=limit,
        )
