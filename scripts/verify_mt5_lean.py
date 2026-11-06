"""Verify fresh-volume MT5, native data, restart, and sampled container resources."""

import argparse
import asyncio
import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import websockets

from scripts.verify_mt5_local import main as verify_candles


def docker(*args: str, timeout: float = 120) -> str:
    return subprocess.check_output(
        ["docker", *args], text=True, stderr=subprocess.PIPE, timeout=timeout
    ).strip()


async def verify(args: argparse.Namespace) -> None:
    compose = [
        "compose",
        "--env-file",
        str(args.env_file),
        "-p",
        args.project,
        "-f",
        "compose.mt5.yaml",
    ]
    terminal = f"{args.project}-terminal-1"
    result = {
        "startedAt": datetime.now(UTC).isoformat(),
        "project": args.project,
        "localOnly": True,
    }
    samples = []
    phase = "cold-start"

    def save() -> None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    async def sample() -> None:
        while True:
            try:
                raw = await asyncio.to_thread(
                    docker, "stats", "--no-stream", "--format", "{{json .}}", terminal
                )
                samples.append(
                    {"at": datetime.now(UTC).isoformat(), "phase": phase, **json.loads(raw)}
                )
            except subprocess.SubprocessError, json.JSONDecodeError:
                pass
            await asyncio.sleep(2)

    # No existing project volume is accepted, even if it currently looks empty.
    volumes = set(docker("volume", "ls", "--format", "{{.Name}}").splitlines())
    result["emptyVolumes"] = {}
    for suffix in ("terminal-home", "database-data"):
        name = f"{args.project}_{suffix}"
        assert name not in volumes, "Use a new project name for the fresh-volume test"
        docker(
            "volume",
            "create",
            "--label",
            f"com.docker.compose.project={args.project}",
            "--label",
            f"com.docker.compose.volume={suffix}",
            name,
        )
        check = docker(
            "run",
            "--rm",
            "--entrypoint",
            "python",
            "--mount",
            f"type=volume,src={name},dst=/check,volume-nocopy",
            args.mdg_image,
            "-c",
            "from pathlib import Path; assert not any(Path('/check').iterdir()); print(0)",
        )
        assert check == "0"
        result["emptyVolumes"][suffix] = 0
    save()
    monitor = asyncio.create_task(sample())
    try:
        await asyncio.to_thread(docker, *compose, "up", "-d", timeout=300)
        async with httpx.AsyncClient(base_url=args.base_url, timeout=120) as client:
            today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            params = {
                "from": (today - timedelta(days=2)).isoformat(),
                "to": (today + timedelta(days=7)).isoformat(),
                "types": "FOREX",
                "limit": 5000,
            }

            async def calendar() -> list[dict]:
                response = await client.get("/v1/economic-calendar", params=params)
                response.raise_for_status()
                return response.json()["events"]

            for label in ("FIRST", "RESTART"):
                phase = label.lower() + "-recovery"
                started = datetime.now(UTC)
                started_clock = time.monotonic()
                if label == "RESTART":
                    await asyncio.to_thread(docker, *compose, "restart", "terminal")
                deadline = time.monotonic() + 420
                while True:
                    try:
                        quotes = (
                            await client.get(
                                "/v1/quotes",
                                params={
                                    "symbols": "XAU/USD,EUR/USD",
                                    "provider": "MT5_VANTAGE_DEMO",
                                },
                            )
                        ).json()
                        events = await calendar()
                        if (
                            len(quotes.get("quotes", [])) == 2
                            and not quotes["errors"]
                            and events
                            and all(
                                datetime.fromisoformat(q["receivedAt"]) >= started
                                for q in quotes["quotes"]
                            )
                            and min(datetime.fromisoformat(e["lastSeenAt"]) for e in events)
                            >= started
                        ):
                            break
                    except httpx.HTTPError, KeyError:
                        pass
                    assert time.monotonic() < deadline, (
                        "Fresh native quote/calendar did not recover"
                    )
                    await asyncio.sleep(2)
                record = {
                    "startedAt": started.isoformat(),
                    "freshDataSeconds": round(time.monotonic() - started_clock, 2),
                    "quotes": quotes,
                    "calendarCount": len(events),
                    "terminalId": docker("inspect", "--format", "{{.Id}}", terminal),
                    "terminalStartedAt": docker(
                        "inspect", "--format", "{{.State.StartedAt}}", terminal
                    ),
                    "terminalRestartCount": int(
                        docker("inspect", "--format", "{{.RestartCount}}", terminal)
                    ),
                    "terminalOOMKilled": docker(
                        "inspect", "--format", "{{.State.OOMKilled}}", terminal
                    )
                    == "true",
                }
                assert record["terminalRestartCount"] == 0 and not record["terminalOOMKilled"]
                assert len({e["key"] for e in events}) == len(events)
                assert all(
                    e["key"].startswith("FOREX:mt5:") and e["type"] == "FOREX" for e in events
                )
                assert all(
                    e[k] is None
                    for e in events
                    for k in ("description", "newsUrl", "actualBetterWorse", "revisionBetterWorse")
                )
                first_seen = max(e["lastSeenAt"] for e in events)
                phase = label.lower() + "-stream"
                url = args.base_url.replace("http://", "ws://")
                record["streamTrials"] = []
                for _attempt in range(3):
                    statuses, ticks = [], {"XAU/USD": set(), "EUR/USD": set()}
                    async with websockets.connect(
                        f"{url}/v1/stream?symbols=XAU%2FUSD,EUR%2FUSD&provider=MT5_VANTAGE_DEMO"
                    ) as ws:
                        until = time.monotonic() + 30
                        while time.monotonic() < until:
                            try:
                                message = json.loads(
                                    await asyncio.wait_for(
                                        ws.recv(), timeout=until - time.monotonic()
                                    )
                                )
                            except TimeoutError:
                                break
                            if message["type"] == "status":
                                statuses.append(message["state"])
                            elif message["type"] == "quote":
                                assert Decimal(message["price"]) > 0
                                ticks[message["symbol"]].add(message["receivedAt"])
                    stable = (
                        "SUBSCRIBED" in statuses
                        and not {"STALE", "RECONNECTING", "ERROR"}.intersection(statuses)
                        and all(len(values) >= 3 for values in ticks.values())
                    )
                    record["streamTrials"].append(
                        {
                            "statuses": statuses,
                            "uniqueQuoteReceipts": {s: len(v) for s, v in ticks.items()},
                            "stable": stable,
                        }
                    )
                    result[label] = record
                    save()
                    if stable:
                        break
                assert stable, "No stable 30-second quote stream after startup; see streamTrials"
                refreshed = await calendar()
                assert max(e["lastSeenAt"] for e in refreshed) > first_seen
                record.update(
                    {
                        "streamSeconds": 30,
                        "streamStatuses": statuses,
                        "uniqueQuoteReceipts": {s: len(v) for s, v in ticks.items()},
                        "calendarRefreshedAt": max(e["lastSeenAt"] for e in refreshed),
                    }
                )
                result[label] = record
                save()
                phase = label.lower() + "-candles"
                record["candleTrials"] = []
                for attempt in range(2):
                    suffix = "-retry" if attempt else ""
                    candle_output = args.output.with_name(
                        args.output.stem + f"-{label}-candles{suffix}.json"
                    )
                    try:
                        await verify_candles(candle_output, args.base_url)
                    except SystemExit as exc:
                        matrix = json.loads(candle_output.read_text())["matrix"]
                        failures = [row for row in matrix if not row.get("valid")]
                        record["candleTrials"].append(
                            {"passed": False, "evidence": candle_output.name, "failures": failures}
                        )
                        save()
                        if (
                            exc.code != 1
                            or attempt
                            or not failures
                            or any(
                                row.get("status") != 503
                                or row.get("error", {}).get("error", {}).get("code")
                                != "PROVIDER_UNAVAILABLE"
                                for row in failures
                            )
                        ):
                            raise
                        # Keep startup 503s in evidence; require a complete passing retry.
                        await asyncio.sleep(15)
                    else:
                        record["candleTrials"].append(
                            {"passed": True, "evidence": candle_output.name}
                        )
                        break
                record["candles"] = {
                    "passed": True,
                    "requests": 198,
                    "evidence": candle_output.name,
                }
                if label == "RESTART":
                    # More bars than the first run persisted requires a new native CopyRates call.
                    response = await client.get(
                        "/v1/candles",
                        params={
                            "symbol": "XAU/USD",
                            "timeframe": "1m",
                            "count": 10,
                            "provider": "MT5_VANTAGE_DEMO",
                        },
                    )
                    response.raise_for_status()
                    assert len(response.json()["candles"]) == 10
                    record["uncachedCandleCountAfterRestart"] = 10
                save()
            phase = "steady"
            await asyncio.sleep(60)
            final_quotes = (
                await client.get("/v1/quotes", params={"symbols": "XAU/USD,EUR/USD"})
            ).json()
            assert len(final_quotes["quotes"]) == 2 and not final_quotes["errors"]
            result["finalQuotes"] = final_quotes
        result["passed"] = True
    finally:
        monitor.cancel()
        await asyncio.gather(monitor, return_exceptions=True)
        result["resourceSamples"] = samples
        result["completedAt"] = datetime.now(UTC).isoformat()
        save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:18085")
    parser.add_argument("--mdg-image", default="signapse-mdg:mt5-compose-local")
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(verify(parser.parse_args()))
