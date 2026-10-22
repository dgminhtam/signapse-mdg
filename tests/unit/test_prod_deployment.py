import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from deploy import prod

REVISION = "a" * 40
IMAGE = "dgminhtam/signapse-mdg@sha256:" + "b" * 64


@pytest.mark.parametrize("failure", [None, "backup", "migration"])
def test_prod_backup_precedes_migration_and_failures_stop_replacement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str | None
) -> None:
    monkeypatch.setattr(prod, "ROOT", tmp_path)
    monkeypatch.setattr(prod.shutil, "copyfile", Mock())
    responses = iter(
        [
            "signapse-prod",
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

    monkeypatch.setattr(prod, "backup", backup)
    monkeypatch.setattr(prod, "run", run)
    if failure:
        with pytest.raises((ValueError, subprocess.CalledProcessError)):
            prod.deploy(IMAGE, REVISION)
        assert "replace" not in events
    else:
        prod.deploy(IMAGE, REVISION)
        assert events == ["backup", "migration", "replace"]


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
                "signapse_mdg",
                json.dumps([{"Image": "old", "Config": {"Image": "old-ref", "Labels": {}}}]),
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
