"""Run from the server's MDG directory; release files live beside this script."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def deploy(image: str, revision: str) -> None:
    if not re.fullmatch(r"dgminhtam/signapse-mdg@sha256:[a-f0-9]{64}", image):
        raise ValueError("Expected an immutable MDG Docker Hub digest.")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Expected a full source commit SHA.")
    root = Path.cwd()
    release = Path(__file__).resolve().parent
    env_file = root / ".env"
    if not env_file.is_file():
        raise ValueError("Server .env must be provisioned before deployment.")
    env = {**os.environ, "MDG_IMAGE": image, "MDG_ENV_FILE": str(env_file)}
    compose = [
        "docker",
        "compose",
        "--project-name",
        "mdg",
        "--project-directory",
        str(root),
        "--env-file",
        str(env_file),
        "-f",
        str(release / "docker-compose.yml"),
    ]
    override = root / "docker-compose.override.yml"
    if override.is_file():
        compose += ["-f", str(override)]

    def run(*args: str) -> None:
        subprocess.run(list(args), env=env, check=True)

    def output(*args: str) -> str:
        return subprocess.check_output(list(args), env=env, text=True).strip()

    run(*compose, "config", "--quiet")
    if output(*compose, "config", "--images") != image:
        raise ValueError("Server override must not replace the release image.")
    run(*compose, "pull", "gateway")
    metadata = json.loads(output("docker", "image", "inspect", image))[0]
    if (metadata["Config"].get("Labels") or {}).get(
        "org.opencontainers.image.revision"
    ) != revision:
        raise ValueError("Published image revision does not match this deployment.")
    # Migrate once before switching the running gateway; never downgrade on failure.
    run(*compose, "run", "--rm", "--no-deps", "-T", "gateway", "alembic", "upgrade", "head")
    run(*compose, "up", "-d", "--no-deps", "--force-recreate", "gateway")
    container = output(*compose, "ps", "-q", "gateway")
    if not container:
        raise ValueError("Gateway container is missing.")
    running = output("docker", "inspect", "--format", "{{.Image}}", container)
    if running != metadata["Id"]:
        raise ValueError("Running gateway does not use the published image digest.")
    run(*compose, "exec", "-T", "gateway", "python", "-m", "scripts.verify_deployment", revision)
    print(json.dumps({"status": "PASS", "revision": revision, "image": image}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("Usage: python3 dev.py <image@sha256:digest> <full-commit-sha>")
        deploy(sys.argv[1], sys.argv[2])
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        # Do not include environment, credentials or database exceptions in deployment output.
        print(
            f"Deployment failed ({type(exc).__name__}); manual recovery required.", file=sys.stderr
        )
        sys.exit(1)
