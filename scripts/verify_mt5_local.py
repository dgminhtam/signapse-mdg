"""Verify the running local MT5 provider through MDG's real HTTP/WS boundaries."""

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import websockets

from app.domain.timeframes import TIMEFRAMES
from scripts.seed_mt5_local import MAPPINGS


async def main(output: Path, base_url: str = "http://127.0.0.1:18081") -> None:
    result: dict[str, object] = {"at": datetime.now(UTC).isoformat(), "matrix": []}
    matrix: list[dict[str, object]] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        async with asyncio.timeout(45):
            while True:
                try:
                    health = await client.get("/health")
                    quotes = (await client.get("/v1/quotes", params={"symbols": "XAU/USD"})).json()
                    if health.status_code == 200 and quotes.get("quotes"):
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.5)
        registry = (
            await client.get("/v1/symbols", params={"includeProviderMappings": "true"})
        ).json()
        names = {item["symbol"] for item in registry["symbols"]}
        assert names == set(MAPPINGS) | {"BTC/USDT", "ETH/USDT"}, names
        result["registryCount"] = len(names)
        quote = (
            await client.get("/v1/quotes", params={"symbols": "XAU/USD,EUR/USD,NATGAS"})
        ).json()
        assert any(q["symbol"] == "XAU/USD" and Decimal(q["price"]) > 0 for q in quote["quotes"])
        result["quotesBeforeWebSocket"] = quote
        ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        async with websockets.connect(f"{ws_url}/v1/stream?symbols=XAU/USD") as ws:
            messages = []
            async with asyncio.timeout(15):
                while sum(m["type"] == "quote" for m in messages) < 3:
                    messages.append(json.loads(await ws.recv()))
            assert any(m.get("state") == "SUBSCRIBED" for m in messages)
            result["websocket"] = messages
        for symbol in MAPPINGS:
            passed = 0
            for frame in TIMEFRAMES:
                started = time.monotonic()
                response = await client.get(
                    "/v1/candles",
                    params={
                        "symbol": symbol,
                        "timeframe": frame,
                        "count": 3,
                    },
                )
                record: dict[str, object] = {
                    "symbol": symbol,
                    "timeframe": frame,
                    "status": response.status_code,
                    "ms": round((time.monotonic() - started) * 1000, 2),
                }
                body = response.json()
                if response.is_success:
                    candles = body["candles"]
                    record["count"] = len(candles)
                    record["valid"] = len(candles) == 3
                    previous = ""
                    for c in candles:
                        o, h, low, close = (Decimal(c[k]) for k in ("open", "high", "low", "close"))
                        assert 0 < low <= min(o, close) <= max(o, close) <= h
                        assert c["openTime"] > previous
                        previous = c["openTime"]
                    if candles:
                        record["firstOpen"] = candles[0]["openTime"]
                        record["lastOpen"] = candles[-1]["openTime"]
                    passed += bool(record["valid"])
                else:
                    record["error"] = body
                matrix.append(record)
                result["matrix"] = matrix
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(result, indent=2) + "\n")
            print(
                json.dumps({"symbol": symbol, "passed": passed, "total": len(TIMEFRAMES)}),
                flush=True,
            )
        result["matrix"] = matrix
        result["passed"] = all(r.get("valid") for r in matrix)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"passed": result["passed"], "output": str(output)}), flush=True)
        if not result["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:18081")
    args = parser.parse_args()
    asyncio.run(main(args.output, args.base_url))
