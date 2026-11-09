import asyncio

import pytest

from scripts.mt5_tcp_smoke import FRAME_LIMIT, positive, read_line


@pytest.mark.parametrize("frame", [b"truncated", b"x" * FRAME_LIMIT + b"\n"])
async def test_probe_rejects_incomplete_or_oversized_frames(frame: bytes) -> None:
    reader = asyncio.StreamReader(limit=FRAME_LIMIT)
    reader.feed_data(frame)
    reader.feed_eof()
    with pytest.raises(ValueError):
        await read_line(reader)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "0", "-1", 3.5])
def test_probe_rejects_invalid_market_prices(value: object) -> None:
    with pytest.raises(ValueError):
        positive(value)
