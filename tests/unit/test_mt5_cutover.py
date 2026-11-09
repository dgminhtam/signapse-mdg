from unittest.mock import Mock

import pytest

from scripts import seed_mt5_local


async def test_mt5_cutover_rejects_wrong_database_before_connecting(monkeypatch):
    monkeypatch.setattr(
        seed_mt5_local,
        "get_settings",
        lambda: Mock(database_url="postgresql+asyncpg://private@host/backend"),
    )
    connect = Mock()
    monkeypatch.setattr(seed_mt5_local, "build_session_factory", connect)
    with pytest.raises(ValueError, match="unexpected database"):
        await seed_mt5_local.main("dev-signapse-mdg")
    connect.assert_not_called()
