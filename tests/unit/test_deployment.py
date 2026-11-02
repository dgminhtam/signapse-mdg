import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from deploy import dev
from scripts import verify_deployment as verify

REVISION = "a" * 40
IMAGE = "dgminhtam/signapse-mdg@sha256:" + "b" * 64


@pytest.fixture
def docker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Mock, Mock]:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("DATABASE_URL=server-only\n")
    (tmp_path / "docker-compose.override.yml").write_text("services: {}\n")
    run = Mock()
    output = Mock(
        side_effect=[
            IMAGE,
            json.dumps(
                [
                    {
                        "Id": "image-id",
                        "Config": {
                            "Labels": {
                                "org.opencontainers.image.revision": REVISION,
                            }
                        },
                    }
                ]
            ),
            "gateway-id\n",
            "image-id\n",
        ]
    )
    monkeypatch.setattr(dev.subprocess, "run", run)
    monkeypatch.setattr(dev.subprocess, "check_output", output)
    return run, output


def test_deploy_migrates_before_switching_and_checks_the_actual_image(
    docker: tuple[Mock, Mock],
) -> None:
    run, output = docker
    dev.deploy(IMAGE, REVISION)
    commands = [call.args[0] for call in run.call_args_list]
    assert commands[2][-3:] == ["alembic", "upgrade", "head"]
    assert commands[3][-5:] == ["up", "-d", "--no-deps", "--force-recreate", "gateway"]
    assert commands[4][-4:] == ["python", "-m", "scripts.verify_deployment", REVISION]
    assert "docker-compose.override.yml" in " ".join(commands[0])
    assert run.call_args.kwargs["env"]["MDG_IMAGE"] == IMAGE
    assert output.call_args.args[0] == ["docker", "inspect", "--format", "{{.Image}}", "gateway-id"]


def test_failed_migration_never_replaces_the_gateway(docker: tuple[Mock, Mock]) -> None:
    run, _ = docker
    run.side_effect = [None, None, subprocess.CalledProcessError(1, "alembic")]
    with pytest.raises(subprocess.CalledProcessError):
        dev.deploy(IMAGE, REVISION)
    assert run.call_count == 3


def test_wrong_image_label_stops_before_migration(docker: tuple[Mock, Mock]) -> None:
    run, output = docker
    output.side_effect = [IMAGE, json.dumps([{"Id": "id", "Config": {"Labels": {}}}])]
    with pytest.raises(ValueError, match="revision"):
        dev.deploy(IMAGE, REVISION)
    assert run.call_count == 2


def test_wrong_running_digest_never_passes_verification(docker: tuple[Mock, Mock]) -> None:
    run, output = docker
    responses = list(output.side_effect)
    output.side_effect = [*responses[:-1], "different-image"]
    with pytest.raises(ValueError, match="digest"):
        dev.deploy(IMAGE, REVISION)
    assert run.call_count == 4


def test_server_override_cannot_change_the_release_image(docker: tuple[Mock, Mock]) -> None:
    run, output = docker
    output.side_effect = ["old-image:dev"]
    with pytest.raises(ValueError, match="override"):
        dev.deploy(IMAGE, REVISION)
    assert run.call_count == 1


@pytest.mark.parametrize(
    "image,revision", [("dgminhtam/signapse-mdg:dev", REVISION), (IMAGE, "dev")]
)
def test_deploy_rejects_mutable_or_unidentified_builds(image: str, revision: str) -> None:
    with pytest.raises(ValueError):
        dev.deploy(image, revision)


def test_activated_mt5_requires_private_provisioning(
    docker: tuple[Mock, Mock], tmp_path: Path
) -> None:
    (tmp_path / "mt5").mkdir()
    (tmp_path / "mt5" / "enabled").touch()
    with pytest.raises(ValueError, match="runtime digest"):
        dev.deploy(IMAGE, REVISION)
    with pytest.raises(ValueError, match="private MT5 token"):
        dev.deploy(IMAGE, REVISION, IMAGE)
    docker[0].assert_not_called()


def test_activated_mt5_deploys_both_reviewed_images(
    docker: tuple[Mock, Mock], tmp_path: Path
) -> None:
    run, output = docker
    runtime = "dgminhtam/signapse-mdg@sha256:" + "c" * 64
    (tmp_path / "mt5").mkdir()
    (tmp_path / "mt5" / "enabled").touch()
    (tmp_path / "mt5" / "token.txt").write_text("private")
    metadata = json.dumps(
        [{"Id": "image-id", "Config": {"Labels": {"org.opencontainers.image.revision": REVISION}}}]
    )
    output.side_effect = [f"{IMAGE}\n{runtime}", metadata, metadata, "gateway-id", "image-id"]
    dev.deploy(IMAGE, REVISION, runtime)
    commands = [call.args[0] for call in run.call_args_list]
    assert any(command[-2:] == ["pull", "terminal"] for command in commands)
    assert any(
        command[-5:] == ["up", "-d", "--no-deps", "--force-recreate", "terminal"]
        for command in commands
    )
    assert "mt5-compose.yml" in " ".join(commands[0])
    assert run.call_args.kwargs["env"]["MT5_IMAGE"] == runtime


@pytest.mark.parametrize(
    "path,bad",
    [
        ("/health", {"status": "DOWN"}),
        ("/ready", {"status": "NOT_READY"}),
        ("/openapi.json", {"x-build-revision": "unknown"}),
        ("/openapi.json", {"x-build-revision": "c" * 40}),
        ("/v1/symbols", {"error": "database unavailable"}),
    ],
)
def test_operating_checks_reject_unready_or_wrong_revisions(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    bad: dict[str, object],
) -> None:
    payloads = {
        "/health": {"status": "UP"},
        "/ready": {"status": "READY"},
        "/openapi.json": {"x-build-revision": REVISION},
        "/v1/symbols": {"symbols": []},
    }
    monkeypatch.setattr(verify, "read_json", lambda request: payloads[request])
    verify.check_http(REVISION)
    payloads[path] = bad
    with pytest.raises(ValueError):
        verify.check_http(REVISION)
