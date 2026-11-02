"""Disrupt only the dedicated local containers, verifying stale state and recovery."""

import argparse
import asyncio
import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import websockets

TERMINAL = "mt5-provider-local-terminal-1"
GATEWAY = "mdg-mt5-local-gateway-1"


async def docker(*args: str) -> None:
    completed = await asyncio.to_thread(subprocess.run, ["docker", *args], capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors="replace"))


async def fresh(client: httpx.AsyncClient, after: str = "") -> dict:
    async with asyncio.timeout(120):
        while True:
            try:
                body = (await client.get("/v1/quotes", params={"symbols": "XAU/USD"})).json()
                if body.get("quotes") and body["quotes"][0]["receivedAt"] > after:
                    return body["quotes"][0]
            except httpx.TransportError, ValueError:
                pass
            await asyncio.sleep(0.5)


async def main(output: Path) -> None:
    result: dict = {"at": datetime.now(UTC).isoformat()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"passed": False, "state": "running"}) + "\n")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:18081", timeout=20) as client:
        before = await fresh(client)
        cutoff = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(minutes=3)
        params = {
            "symbol": "XAU/USD",
            "timeframe": "1m",
            "from": (cutoff - timedelta(minutes=3)).isoformat(),
            "to": cutoff.isoformat(),
        }
        original = await client.get("/v1/candles", params=params)
        original.raise_for_status()
        assert len(original.json()["candles"]) == 3
        assert all(c["complete"] for c in original.json()["candles"])
        async with websockets.connect("ws://127.0.0.1:18081/v1/stream?symbols=XAU/USD") as ws:
            async with asyncio.timeout(15):
                while json.loads(await ws.recv())["type"] != "quote":
                    pass
            paused = False
            try:
                await docker("pause", TERMINAL)
                paused = True
                await asyncio.sleep(35)
                stale = (await client.get("/v1/quotes", params={"symbols": "XAU/USD"})).json()
                assert not stale["quotes"] and stale["errors"][0]["code"] == "DATA_STALE"
                cached = await client.get("/v1/candles", params=params)
                assert cached.status_code == 200 and cached.json() == original.json()
                states = []
                async with asyncio.timeout(5):
                    while not any(s in {"STALE", "RECONNECTING"} for s in states):
                        event = json.loads(await ws.recv())
                        if event["type"] == "status":
                            states.append(event["state"])
                result["whileTerminalPaused"] = {
                    "quote": stale,
                    "websocketStates": states,
                    "persistedCandlesServed": True,
                }
            finally:
                if paused:
                    await docker("unpause", TERMINAL)
            started = time.monotonic()
            result["afterUnpause"] = await fresh(client, before["receivedAt"])
            result["unpauseRecoverySeconds"] = round(time.monotonic() - started, 2)
            print("Pause/stale/cache/reconnect passed", flush=True)
        for container in (GATEWAY, TERMINAL):
            before = await fresh(client)
            started = time.monotonic()
            await docker("restart", container)
            restarted_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            current = await fresh(client, restarted_at)
            cached = await client.get("/v1/candles", params=params)
            assert cached.status_code == 200 and cached.json() == original.json()
            result[container] = {
                "recoverySeconds": round(time.monotonic() - started, 2),
                "quote": current,
                "persistedCandlesUnchanged": True,
            }
            print(json.dumps({"restarted": container, "passed": True}), flush=True)
        result["passed"] = True
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"passed": True, "output": str(output)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(main(parser.parse_args().output))
