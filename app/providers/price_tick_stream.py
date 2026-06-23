from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.candles import Candle
from app.domain.market_sessions import get_market_session_policy
from app.domain.streams import StreamCandle
from app.domain.symbols import SupportedSymbol
from app.domain.timeframes import EPOCH, get_timeframe


@dataclass(frozen=True, slots=True)
class PriceTick:
    symbol: SupportedSymbol
    price: Decimal
    provider_time: datetime | None
    received_at: datetime


class PriceTickCandleBuilder:
    def __init__(self, *, volume: Decimal = Decimal("0")) -> None:
        self._volume = volume
        self._current: dict[tuple[str, str], Candle] = {}

    def apply_tick(
        self,
        tick: PriceTick,
        timeframe: str,
    ) -> list[StreamCandle]:
        model = get_timeframe(timeframe)
        if model is None:
            return []
        source_time = (tick.provider_time or tick.received_at).astimezone(UTC)
        bucket_start = bucket_open(source_time, model.duration)
        policy = get_market_session_policy(tick.symbol)
        if not policy.is_eligible(bucket_start, timeframe):
            self._current.pop((tick.symbol.symbol, timeframe), None)
            return []

        close_time = bucket_start + model.duration - timedelta(milliseconds=1)
        key = (tick.symbol.symbol, timeframe)
        current = self._current.get(key)
        emitted: list[StreamCandle] = []
        if current is not None and bucket_start > current.open_time:
            emitted.append(
                StreamCandle(
                    Candle(
                        current.symbol,
                        current.asset_class,
                        current.provider,
                        current.provider_symbol,
                        current.timeframe,
                        current.open_time,
                        current.close_time,
                        current.open,
                        current.high,
                        current.low,
                        current.close,
                        current.volume,
                        True,
                    ),
                    tick.received_at,
                )
            )
            current = None

        if current is None:
            current = Candle(
                tick.symbol.symbol,
                tick.symbol.asset_class,
                tick.symbol.provider,
                tick.symbol.provider_symbol,
                timeframe,
                bucket_start,
                close_time,
                tick.price,
                tick.price,
                tick.price,
                tick.price,
                self._volume,
                False,
            )
        elif bucket_start == current.open_time:
            current = Candle(
                current.symbol,
                current.asset_class,
                current.provider,
                current.provider_symbol,
                current.timeframe,
                current.open_time,
                current.close_time,
                current.open,
                max(current.high, tick.price),
                min(current.low, tick.price),
                tick.price,
                current.volume,
                False,
            )
        else:
            return emitted

        self._current[key] = current
        emitted.append(StreamCandle(current, tick.received_at))
        return emitted


def bucket_open(value: datetime, duration: timedelta) -> datetime:
    utc_value = value.astimezone(UTC)
    elapsed = utc_value - EPOCH
    return EPOCH + (elapsed // duration) * duration
