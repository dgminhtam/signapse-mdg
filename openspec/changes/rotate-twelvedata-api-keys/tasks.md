## 1. Configuration

- [x] 1.1 Add typed settings support for comma-separated `TWELVEDATA_API_KEYS`.
- [x] 1.2 Build an ordered de-duplicated effective Twelve Data key list and keep empty values out.
- [x] 1.3 Update `.env.example`, README, deploy docs, and system design configuration notes.

## 2. REST Key Rotation

- [x] 2.1 Add a small Twelve Data-only process-local key pool in `app/providers/`.
- [x] 2.2 Update the Twelve Data REST provider factory to accept the effective key list.
- [x] 2.3 Rotate quote and candle REST operations across healthy keys.
- [x] 2.4 Cool down a key on key-related provider failures and retry at most one alternate key.
- [x] 2.5 Preserve existing no-data candle behavior without cooling down a key.

## 3. Stream Key Selection

- [x] 3.1 Update the Twelve Data stream provider factory to accept the effective key list.
- [x] 3.2 Select a key only when opening or reopening a WebSocket connection.
- [x] 3.3 Preserve live subscription reuse without rotating a connected WebSocket.

## 4. Wiring and Tests

- [x] 4.1 Update quote, candle, stream, and backfill wiring to pass effective Twelve Data keys.
- [x] 4.2 Add unit tests for effective key parsing and de-duplication.
- [x] 4.3 Add REST provider tests for round-robin key use, one alternate retry, cooldown, and no-data preservation.
- [x] 4.4 Add stream provider tests for connect-time key selection and no live rotation.
- [x] 4.5 Run focused Twelve Data tests, `uv run ruff check .`, and `uv run mypy app`.
