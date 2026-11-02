---
status: accepted for local and dev verification
---

# Integrate MT5 directly into MDG

The user accepted the direct architecture on 2026-11-02 and authorized local
implementation and tests before any dev deployment. Extend the successful TCP
spike; keep the SDK exception in ADR 0003. No Go, message broker, or Python
helper in the terminal container. The existing FastAPI process owns the TCP
listener, quote ingestion and candle RPC. It runs as one worker, disabled by
default. The listener is private to the local Docker network.

Local feed identity is `MT5_VANTAGE_DEMO`, bound to `VantageMarkets-Demo`.
Read the symbol registry at startup; mappings are installed only in a dedicated
local database by an explicit seed command, not a production migration. Keep
MDG's existing canonical `WTI`; its MT5 mapping is `USOUSD`. The other 21
canonical symbols follow the approved catalog; Corn/DJI are disabled locally.
CFD/cash candidates remain test mappings, not production asset acceptance.

Quote price uses Bid, matching the observed terminal chart mode. Candle volume
is native real_volume (zero when unavailable), not tick_volume. Retain broker
timestamps internally and expose UTC. Vantage documents GMT+2 / GMT+3 following
US DST and server midnight at New York 17:00; the clock conversion is therefore
New York wall time plus seven hours. Validate the current terminal clock against
this profile on handshake; reject a mismatched feed rather than guess an offset.
Test both DST boundaries and broker-native H4/D1/W1/MN1 opens. Session gaps come
from native bars; do not filter broker CFD candles by another provider's calendar.

The bridge delivers latest quote state, not a durable raw-tick log. MQL5 polls
CopyTicks for the latest observation; sequence/time checks suppress stale or
duplicate updates. Reconnect resynchronizes latest state. Preserve the original
market time and gateway receipt time when REST reads an existing snapshot, so
polling, replay, or heartbeat cannot make an old price fresh. Ingestion starts
with the application, even with zero WebSocket subscribers. Existing quote/status
WebSocket and HTTP response shapes remain unchanged.

Wire v1 uses UTF-8 newline-delimited frames, capped at 64 KiB. An initial
`HELLO <shared-token>` line authenticates before JSON metadata or market data is
accepted. JSON frames carry hello, tick, rates result or broker status. MDG sends
bounded tab-separated `RATES` commands with request ID, allowlisted symbol,
timeframe, native start/end and maximum 128 bars. One RPC at a time with deadlines;
late results cannot satisfy another request. Partial/loading/native errors are
failures, not empty history. No shell, file path or arbitrary execution commands.

Sources: [accepted architecture](https://github.com/signapse-group/signapse-planing/blob/main/docs/design/mdg-mt5-direct-integration.md),
[Vantage server clock](https://www.vantagemarkets.com/en/academy/metatrader-5-tutorial/).
On 2026-11-02 the user additionally authorized PR into dev, merge and migration of
the complete runtime to the dev server. The [dev runbook](../mt5-dev-deployment.md)
owns activation of these 22 mappings and private state migration. Production
deployment and production asset acceptance remain outside this authorization.
