---
status: experimental
---

# Verify direct MQL5 TCP before implementing an MT5 provider

The user authorized a local TCP feasibility test on a branch from `dev`. Run a
bounded listener from this repository and a chart-independent MQL5 Service in the
existing Wine/MT5 container. Do not register a provider, change public HTTP/WS
behavior, persist market data, or deploy to the server in this spike.

The official MetaTrader Python package uses terminal IPC and does not establish a
supported cross-container Linux connection to a Wine terminal. Adding another
Python process beside the terminal would defeat the requested removal of the
sidecar. This is the scoped exception to preferring an official SDK: test native
MQL5 `Socket*` calls against Python's standard-library `asyncio` TCP listener.
No new dependency is needed.

Spike-only wire contract: UTF-8 lines, at most 8192 bytes including newline.
The first line is `HELLO <ephemeral-token>`. The receiver then sends fixed
`PING`, `RATES`, `RECONNECT`, or `STOP` lines. The Service returns JSON lines:
`hello`, `pong`, `tick` (latest XAUUSD sample), and `rates` (three closed M1
bars, with native timestamps). There is no arbitrary command execution or
broker credential on the wire. The token file stays outside Git and the TCP
port is not published to the host. The listener has frame/time limits and checks
decimal values before accepting a result.

Pass requires two authenticated sessions from one Service run, an advancing
XAUUSD tick timestamp, positive Bid/Ask, valid OHLC for three closed M1 bars,
and a PING response on both sessions. The receiver deliberately fragments a
command and coalesces commands to exercise stream parsing, then closes the first
connection to require reconnect. A separate denied client verifies authentication.

This proves only transport and small read-only requests on the tested build.
It does not prove lossless streaming, timezone normalization, one-second broker
latency, load capacity, unattended provisioning, or integration with MDG's
cache/database/public APIs. Tick messages are repeated snapshots, not a cursor.
The fixed commands are not a proposed production protocol.

Sources: [MQL5 network functions](https://www.mql5.com/en/docs/network),
[SocketConnect](https://www.mql5.com/en/docs/network/socketconnect),
[MetaTrader Python integration](https://www.mql5.com/en/docs/python_metatrader5).

Local execution passed on 2026-11-02; see [results and rerun notes](../mt5-tcp-smoke.md).
This result does not promote the experimental wire format to a production contract.
