import asyncio
import logging

from app.domain.errors import ProviderUnavailableError
from app.domain.streams import (
    CandleInterest,
    MarketStreamProvider,
    ProviderStreamEvent,
    QuoteInterest,
    StreamInterest,
)
from app.domain.symbols import SupportedSymbol

logger = logging.getLogger(__name__)


class MultiProviderStreamProvider:
    def __init__(
        self,
        providers: dict[str, MarketStreamProvider],
        *,
        queue_capacity: int,
    ) -> None:
        self._providers = providers
        self.events: asyncio.Queue[ProviderStreamEvent] = asyncio.Queue(queue_capacity)
        self._forward_tasks: dict[str, asyncio.Task[None]] = {}
        self._interest_providers: dict[StreamInterest, str] = {}
        self._lock = asyncio.Lock()

    async def subscribe_quote(self, symbol: SupportedSymbol) -> None:
        provider = self._provider_for(symbol)
        async with self._lock:
            self._ensure_forwarding(symbol.provider, provider)
            await provider.subscribe_quote(symbol)
            self._interest_providers[QuoteInterest(symbol.symbol)] = symbol.provider

    async def subscribe_candle(
        self,
        symbol: SupportedSymbol,
        timeframe: str,
        provider_interval: str,
    ) -> None:
        provider = self._provider_for(symbol)
        interest = CandleInterest(symbol.symbol, timeframe)
        async with self._lock:
            self._ensure_forwarding(symbol.provider, provider)
            await provider.subscribe_candle(symbol, timeframe, provider_interval)
            self._interest_providers[interest] = symbol.provider

    async def unsubscribe(self, interest: StreamInterest) -> None:
        async with self._lock:
            provider_name = self._interest_providers.pop(interest, None)
            if provider_name is None:
                return
            provider = self._providers.get(provider_name)
            if provider is None:
                return
            await provider.unsubscribe(interest)

    async def close(self) -> None:
        async with self._lock:
            providers = list(self._providers.values())
            tasks = list(self._forward_tasks.values())
            self._interest_providers.clear()
            self._forward_tasks.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(*(provider.close() for provider in providers), return_exceptions=True)

    def _provider_for(self, symbol: SupportedSymbol) -> MarketStreamProvider:
        provider = self._providers.get(symbol.provider)
        if provider is None:
            raise ProviderUnavailableError
        return provider

    def _ensure_forwarding(self, name: str, provider: MarketStreamProvider) -> None:
        task = self._forward_tasks.get(name)
        if task is not None and not task.done():
            return
        self._forward_tasks[name] = asyncio.create_task(
            self._forward_events(name, provider),
            name=f"stream-router-forward-{name}",
        )

    async def _forward_events(self, name: str, provider: MarketStreamProvider) -> None:
        while True:
            event = await provider.events.get()
            try:
                try:
                    self.events.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("stream_router_event_dropped", extra={"provider": name})
            finally:
                provider.events.task_done()
