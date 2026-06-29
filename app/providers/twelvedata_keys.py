from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from app.domain.errors import ProviderUnavailableError


class TwelveDataKeyUnavailableError(Exception):
    pass


class TwelveDataApiKeyPool:
    def __init__(
        self,
        api_keys: Sequence[str],
        *,
        cooldown_seconds: float = 60,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._keys = tuple(dict.fromkeys(key.strip() for key in api_keys if key.strip()))
        if not self._keys:
            raise ProviderUnavailableError
        self._cooldown = timedelta(seconds=max(cooldown_seconds, 0))
        self._cooldowns: dict[str, datetime] = {}
        self._index = 0
        self._clock = clock or (lambda: datetime.now(UTC))

    def next_key(self, *, exclude: str | None = None) -> str:
        now = self._clock()
        for _ in self._keys:
            key = self._keys[self._index % len(self._keys)]
            self._index += 1
            if key == exclude:
                continue
            cooled_until = self._cooldowns.get(key)
            if cooled_until is None or cooled_until <= now:
                return key
        raise ProviderUnavailableError

    def cool_down(self, key: str) -> None:
        self._cooldowns[key] = self._clock() + self._cooldown
