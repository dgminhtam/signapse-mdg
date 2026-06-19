from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_up_with_utc_time() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert set(response.json()) == {"status", "time"}
    assert response.json()["status"] == "UP"

    health_time = datetime.fromisoformat(response.json()["time"])
    assert health_time.tzinfo is not None
    assert health_time.utcoffset() == UTC.utcoffset(health_time)
