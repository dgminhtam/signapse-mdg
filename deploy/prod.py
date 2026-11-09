"""Run under the production deployment lock."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path("/opt/signapse-prod/mdg")
BACKUPS = Path("/var/backups/signapse-mdg")
GATEWAY = "signapse-prod-mdg-gateway-1"
DATABASE = "signapse-prod-database-1"


def output(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def database_user() -> str:
    info = json.loads(output("docker", "inspect", DATABASE))[0]
    env = dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)
    return str(env["POSTGRES_USER"])


def backup(revision: str) -> Path:
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    BACKUPS.chmod(0o700)
    folder = BACKUPS / (datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ-") + revision)
    folder.mkdir(mode=0o700)
    user = database_user()
    previous = json.loads(output("docker", "inspect", GATEWAY))[0]
    runtime = dict(item.split("=", 1) for item in previous["Config"]["Env"] if "=" in item)
    db = runtime.get("DATABASE_URL", "").rsplit("/", 1)[-1]
    if db != "signapse_mdg":
        raise ValueError("Unexpected production database.")
    schema = output(
        "docker",
        "exec",
        DATABASE,
        "psql",
        "-U",
        user,
        "-d",
        db,
        "-Atc",
        "SELECT version_num FROM alembic_version ORDER BY version_num",
    )
    (folder / "manifest.json").write_text(
        json.dumps(
            {
                "release": revision,
                "database": db,
                "migration_heads": schema.splitlines(),
                "previous_image_id": previous["Image"],
                "previous_image_ref": previous["Config"]["Image"],
                "previous_compose_files": previous["Config"]["Labels"].get(
                    "com.docker.compose.project.config_files"
                ),
            },
            indent=2,
        )
        + "\n"
    )
    for name in ("docker-compose.yml", ".env"):
        if (ROOT / name).is_file():
            shutil.copyfile(ROOT / name, folder / name)
    partial = folder / "database.dump.partial"
    with partial.open("wb") as target:
        subprocess.run(
            ["docker", "exec", DATABASE, "pg_dump", "-U", user, "-d", db, "-Fc"],
            stdout=target,
            check=True,
        )
    if partial.stat().st_size == 0:
        raise ValueError("Empty backup.")
    with partial.open("rb") as source:
        subprocess.run(
            ["docker", "exec", "-i", DATABASE, "pg_restore", "--list"],
            stdin=source,
            stdout=subprocess.DEVNULL,
            check=True,
        )
    partial.rename(folder / "database.dump")
    (folder / "COMPLETE").touch()
    print(f"Backup verified: {folder}", flush=True)
    # Only delete our complete, timestamped backups after a new one succeeds.
    cutoff = datetime.now(UTC) - timedelta(days=7)
    for old in BACKUPS.iterdir():
        if (
            old != folder
            and not old.is_symlink()
            and old.is_dir()
            and re.fullmatch(r"\d{8}T\d{12}Z-[a-f0-9]{40}", old.name)
            and (old / "COMPLETE").is_file()
            and datetime.fromtimestamp(old.stat().st_mtime, UTC) < cutoff
        ):
            shutil.rmtree(old)
    return folder


def deploy(image: str, revision: str) -> None:
    if not re.fullmatch(r"dgminhtam/signapse-mdg@sha256:[a-f0-9]{64}", image):
        raise ValueError("Expected immutable MDG image.")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Expected full source SHA.")
    if output("tailscale", "ip", "-4") != "100.74.15.80":
        raise ValueError("Wrong deployment host.")
    os.environ["MDG_IMAGE"] = image
    release = Path(__file__).resolve().parent
    compose = [
        "docker",
        "compose",
        "--project-name",
        "signapse-prod-mdg",
        "--project-directory",
        str(ROOT),
        "-f",
        str(release / "docker-compose.prod.yml"),
    ]
    run(*compose, "config", "--quiet")
    if output(*compose, "config", "--images") != image:
        raise ValueError("Wrong release image.")
    run(*compose, "pull", "gateway")
    metadata = json.loads(output("docker", "image", "inspect", image))[0]
    if (metadata["Config"].get("Labels") or {}).get(
        "org.opencontainers.image.revision"
    ) != revision:
        raise ValueError("Image revision mismatch.")
    first_release = not (ROOT / ".env").exists()
    previous = subprocess.run(
        ["docker", "container", "inspect", GATEWAY],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    folder = backup(revision) if previous.returncode == 0 else None
    run(*compose, "run", "--rm", "--no-deps", "-T", "gateway", "alembic", "upgrade", "head")
    if first_release:
        run(
            *compose,
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "gateway",
            "python",
            "-c",
            "import asyncio; from scripts.seed_mt5_local import main; "
            "asyncio.run(main('signapse_mdg'))",
        )
    run(*compose, "up", "-d", "--no-deps", "--wait", "--wait-timeout", "120", "gateway")
    container = output(*compose, "ps", "-q", "gateway")
    if (
        not container
        or output("docker", "inspect", "--format", "{{.Image}}", container) != metadata["Id"]
    ):
        raise ValueError("Running image mismatch.")
    run(*compose, "exec", "-T", "gateway", "python", "-m", "scripts.verify_deployment", revision)
    # Keep normal operator compose commands pointed at the successfully deployed image.
    shutil.copyfile(release / "docker-compose.prod.yml", ROOT / "docker-compose.yml")
    (ROOT / ".env").write_text(f"MDG_IMAGE={image}\n")
    print(
        json.dumps({"status": "PASS", "revision": revision, "image": image, "backup": str(folder)})
    )


if __name__ == "__main__":
    os.umask(0o077)
    try:
        if len(sys.argv) != 4 or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", sys.argv[3]):
            raise ValueError("Usage: prod.py <image@digest> <sha> <registry-user>")
        token = sys.stdin.read().strip()
        if not token:
            raise ValueError("Missing registry credential.")
        with tempfile.TemporaryDirectory(prefix="mdg-registry-") as auth:
            os.environ["DOCKER_CONFIG"] = auth
            subprocess.run(
                ["docker", "login", "--username", sys.argv[3], "--password-stdin"],
                input=token,
                text=True,
                check=True,
            )
            deploy(sys.argv[1], sys.argv[2])
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(
            f"Prod deploy failed ({type(exc).__name__}); inspect the failed phase and backup; "
            "manual recovery required.",
            file=sys.stderr,
        )
        sys.exit(1)
