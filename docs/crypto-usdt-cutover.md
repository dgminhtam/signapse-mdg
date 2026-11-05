# Crypto USDT cutover — 2026-11-05

The accepted replacement is BTC/USDT → BINANCE_SPOT:BTCUSDT and
ETH/USDT → BINANCE_SPOT:ETHUSDT. Each has one default mapping, two price
display decimals and internal 24/7 UTC sessions. USD provider overrides do
not describe the same instruments and are removed from the registry.

Migration 20261105_0021 replaces the two registry entries. It does not
relabel or erase recorded candle history. Downgrade reconstructs the
previous seeded USD defaults, not an operator's former custom mappings;
restore the verified backup for exact recovery.

For the explicitly authorized test reset, stop gateway writers, take a
PostgreSQL custom-format backup and verify restoration in an isolated DB.
Run `scripts/retire_usd_crypto_test_data.sql` with psql, setting
`expected_database` to the exact `dev-` database and `apply=false` first.
It reports the candle identities, performs scoped deletes and rolls back.
After reviewing that result, run the same script with `apply=true`.
The script removes old canonical registry/candle rows only; other symbols
and their provider settings remain intact. Deploy the new image through
the existing dev pipeline, then verify live revision, registry, HTTP
quotes/candles/historical-price and quote-only WebSocket for both pairs.
Check unsupported responses for the retired canonical symbols and confirm
an unrelated symbol still works. Restart/reseed must preserve USDT routing.

MT5 seed/verification retains the two Binance crypto entries and configures
only the twenty non-crypto MT5 mappings. No automatic fallback is introduced.
Keep dated evidence and applied migrations as history; do not rewrite them
to claim that an earlier run verified USDT.
