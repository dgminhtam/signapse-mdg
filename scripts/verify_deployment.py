"""Read-only operating checks, executed inside the running gateway image."""

import asyncio
import http.client
import json
import re
import sys
import time
from typing import Any

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


def read_json(path: str) -> dict[str, Any]:
    connection = http.client.HTTPConnection("127.0.0.1", 8000, timeout=5)
    try:
        connection.request("GET", path, headers={"Cache-Control": "no-cache"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"{path} did not return HTTP 200.")
        if "application/json" not in (response.getheader("Content-Type") or ""):
            raise ValueError(f"{path} did not return JSON.")
        value = json.load(response)
        if not isinstance(value, dict):
            raise ValueError(f"{path} did not return a JSON object.")
        return value
    finally:
        connection.close()


def check_http(revision: str) -> None:
    if read_json("/health").get("status") != "UP":
        raise ValueError("Liveness failed.")
    if read_json("/ready").get("status") != "READY":
        raise ValueError("Readiness failed.")
    if read_json("/openapi.json").get("x-build-revision") != revision:
        raise ValueError("Live OpenAPI revision does not match the expected build.")
    if not isinstance(read_json("/v1/symbols").get("symbols"), list):
        raise ValueError("Symbol registry cannot be read.")


async def check_migrations() -> None:
    url = get_settings().database_url
    if not url:
        raise ValueError("DATABASE_URL is required.")
    expected = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            current = await connection.run_sync(
                lambda sync: set(MigrationContext.configure(sync).get_current_heads())
            )
        if not expected or current != expected:
            raise ValueError("Database migration revision does not match the image head.")
    finally:
        await engine.dispose()


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-f0-9]{40}", sys.argv[1]):
        print("Usage: python -m scripts.verify_deployment <full-commit-sha>", file=sys.stderr)
        return 1
    deadline = time.monotonic() + 180
    while True:
        try:
            check_http(sys.argv[1])
            asyncio.run(check_migrations())
            print("PASS: health, readiness, live revision, symbols and migration head.")
            return 0
        except Exception as exc:
            # Never emit DB connection strings or exception messages containing credentials.
            print(f"Operating checks pending ({type(exc).__name__}).", flush=True)
            if time.monotonic() >= deadline:
                print(
                    "FAIL: operating checks timed out; manual recovery required.", file=sys.stderr
                )
                return 1
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
