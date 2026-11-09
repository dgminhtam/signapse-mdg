import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from deploy import prod

REVISION = "a" * 40
IMAGE = "dgminhtam/signapse-mdg@sha256:" + "b" * 64


@pytest.mark.parametrize(
    ("first_release", "failure"),
    [(False, None), (False, "backup"), (False, "migration"), (True, None)],
)
def test_prod_backup_precedes_migration_and_failures_stop_replacement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, first_release: bool, failure: str | None
) -> None:
    monkeypatch.setattr(prod, "ROOT", tmp_path)
    monkeypatch.setattr(prod.shutil, "copyfile", Mock())
    if not first_release:
        (tmp_path / ".env").touch()
    monkeypatch.setattr(
        prod.subprocess, "run", Mock(return_value=Mock(returncode=int(first_release)))
    )
    responses = iter(
        [
            "100.74.15.80",
            IMAGE,
            json.dumps(
                [
                    {
                        "Id": "image-id",
                        "Config": {"Labels": {"org.opencontainers.image.revision": REVISION}},
                    }
                ]
            ),
            "container-id",
            "image-id",
        ]
    )
    monkeypatch.setattr(prod, "output", lambda *args: next(responses))
    events: list[str] = []

    def backup(revision: str) -> Path:
        events.append("backup")
        if failure == "backup":
            raise ValueError("backup failed")
        return tmp_path

    def run(*args: str) -> None:
        if "alembic" in args:
            events.append("migration")
            if failure == "migration":
                raise subprocess.CalledProcessError(1, args)
        if "up" in args:
            events.append("replace")
        if any("seed_mt5_local" in arg for arg in args):
            events.append("seed")

    monkeypatch.setattr(prod, "backup", backup)
    monkeypatch.setattr(prod, "run", run)
    if failure:
        with pytest.raises((ValueError, subprocess.CalledProcessError)):
            prod.deploy(IMAGE, REVISION)
        assert "replace" not in events
    else:
        prod.deploy(IMAGE, REVISION)
        expected = (
            ["migration", "seed", "replace"]
            if first_release
            else ["backup", "migration", "replace"]
        )
        assert events == expected


def test_failed_dump_is_never_marked_complete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(prod, "BACKUPS", tmp_path / "backups")
    monkeypatch.setattr(prod, "ROOT", tmp_path)
    monkeypatch.setattr(prod, "database_user", lambda: "postgres")
    monkeypatch.setattr(
        prod,
        "output",
        Mock(
            side_effect=[
                json.dumps(
                    [
                        {
                            "Image": "old",
                            "Config": {
                                "Image": "old-ref",
                                "Labels": {},
                                "Env": ["DATABASE_URL=postgresql+asyncpg://database/signapse_mdg"],
                            },
                        }
                    ]
                ),
                "head",
            ]
        ),
    )
    monkeypatch.setattr(prod.shutil, "copyfile", Mock())
    monkeypatch.setattr(
        prod.subprocess, "run", Mock(side_effect=subprocess.CalledProcessError(1, "pg_dump"))
    )
    with pytest.raises(subprocess.CalledProcessError):
        prod.backup(REVISION)
    assert not list((tmp_path / "backups").glob("*/COMPLETE"))
