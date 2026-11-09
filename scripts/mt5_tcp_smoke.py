"""Local-only transport probe; see docs/adr/0003-local-mt5-tcp-spike.md."""

import argparse
import asyncio
import hmac
import json
import time
from decimal import Decimal
from pathlib import Path

FRAME_LIMIT = 8192


async def read_line(reader: asyncio.StreamReader) -> bytes:
    line = await asyncio.wait_for(reader.readline(), timeout=10)
    if not line or len(line) > FRAME_LIMIT or not line.endswith(b"\n"):
        raise ValueError("Missing, oversized, or unterminated frame")
    return line.rstrip(b"\r\n")


def positive(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("Expected decimal string")
    number = Decimal(value)
    if not number.is_finite() or number <= 0:
        raise ValueError("Expected positive finite decimal")
    return number


async def run_with_gateway(host: str, port: int, token: str, samples: int) -> dict:
    from uvicorn import Config, Server

    from app.main import create_app

    gateway = Server(Config(create_app(), host="0.0.0.0", port=8000, log_level="warning"))
    task = asyncio.create_task(gateway.serve())
    try:
        async with asyncio.timeout(30):
            while not gateway.started:
                if task.done():
                    await task
                    raise RuntimeError("MDG exited before startup")
                await asyncio.sleep(0.05)
        return await run(host, port, token, samples)
    finally:
        gateway.should_exit = True
        await task


async def run(host: str, port: int, token: str, samples: int) -> dict:
    done = asyncio.get_running_loop().create_future()
    sessions = []
    rejected = 0
    active = False
    server: asyncio.Server

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal rejected, active
        owned = False
        try:
            line = await read_line(reader)
            if not hmac.compare_digest(line, f"HELLO {token}".encode()) or active:
                rejected += 1
                return
            active = owned = True
            hello = json.loads(await read_line(reader))
            if (
                hello["type"] != "hello"
                or hello["server"] != "VantageMarkets-Demo"
                or hello["service"] is not True
                or hello["algoTrading"] is not False
            ):
                raise ValueError("Unexpected terminal, program type, or trading setting")
            started = time.monotonic()
            writer.write(b"PI")
            await writer.drain()
            await asyncio.sleep(0.05)
            writer.write(b"NG\nRATES\n")
            await writer.drain()
            ticks = []
            rates = None
            ping_ms = None
            while len(ticks) < samples or rates is None or ping_ms is None:
                message = json.loads(await read_line(reader))
                if message["type"] == "pong":
                    ping_ms = round((time.monotonic() - started) * 1000, 2)
                elif message["type"] == "tick":
                    if message["symbol"] != "XAUUSD" or not message["connected"]:
                        raise ValueError("Unexpected symbol or disconnected broker")
                    positive(message["bid"])
                    positive(message["ask"])
                    if not isinstance(message["timeMscRaw"], int) or message["timeMscRaw"] <= 0:
                        raise ValueError("Invalid raw tick timestamp")
                    ticks.append(message)
                elif message["type"] == "rates":
                    if message["error"] != 0 or len(message["bars"]) != 3:
                        raise ValueError("Rates not ready or invalid count")
                    previous = 0
                    for bar in message["bars"]:
                        o, h, low, close = (positive(bar[k]) for k in ("o", "h", "l", "c"))
                        if not low <= min(o, close) <= max(o, close) <= h:
                            raise ValueError("Invalid OHLC")
                        if bar["timeRaw"] <= previous:
                            raise ValueError("Unordered bars")
                        previous = bar["timeRaw"]
                    rates = message
                else:
                    raise ValueError("Unexpected message type")
            sessions.append(
                {
                    "hello": hello,
                    "samples": len(ticks),
                    "firstTick": ticks[0],
                    "lastTick": ticks[-1],
                    "rates": rates,
                    "pingRoundTripMsIncludingFragmentDelay": ping_ms,
                }
            )
            print(json.dumps({"sessionPassed": len(sessions), "samples": len(ticks)}), flush=True)
            writer.write(b"STOP\n" if len(sessions) == 2 else b"RECONNECT\n")
            await writer.drain()
            if len(sessions) == 2 and not done.done():
                all_times = [
                    s[k]["timeMscRaw"] for s in sessions for k in ("firstTick", "lastTick")
                ]
                if max(all_times) <= min(all_times):
                    raise ValueError("Tick timestamp did not advance")
                done.set_result({"passed": True, "rejectedClients": rejected, "sessions": sessions})
        except Exception as exc:
            if owned and not done.done():
                done.set_exception(exc)
        finally:
            if owned:
                active = False
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    server = await asyncio.start_server(handle, host, port, limit=FRAME_LIMIT)
    async with server:
        # Self-check the real listener rejects unauthenticated peers before the MT5 run.
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"HELLO wrong-token\n")
        await writer.drain()
        if await asyncio.wait_for(reader.read(1), timeout=2) != b"":
            raise ValueError("Unauthenticated client was not rejected")
        writer.close()
        await writer.wait_closed()
        print(
            json.dumps({"listening": port, "unauthenticatedClientRejected": rejected == 1}),
            flush=True,
        )
        return await asyncio.wait_for(done, timeout=240)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--samples", type=int, default=40)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    token = args.token_file.read_text().strip()
    if len(token) < 32 or args.samples < 2:
        parser.error("Use a random token of at least 32 characters and at least two samples")
    result = asyncio.run(run_with_gateway(args.host, args.port, token, args.samples))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
