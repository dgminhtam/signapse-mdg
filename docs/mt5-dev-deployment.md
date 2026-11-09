# MT5 runtime on dev

Crypto cutover 2026-11-05 supersedes the two USD crypto mappings in the
original rollout below. MT5 now serves twenty non-crypto symbols; BTC/USDT
and ETH/USDT use Binance Spot. Update the persistent terminal symbol file
as well as the registry, following [the cutover runbook](crypto-usdt-cutover.md).

The user authorized local → PR into `dev` → merge → server cutover on 2026-11-02.
The 22 accepted assets replace dev's default provider mappings; CORN and DJI remain
disabled. Existing mappings and provider-keyed candle history are retained, not deleted.
The local verification is recorded in [the local runbook](mt5-local-integration.md).

Current dev state and the 2026-11-06 terminal-only lean/CPU rollout are recorded in
[the deployment evidence](mt5-dev-cpu-20261106.md). The current registry has 20 MT5
mappings and two Binance symbols; this rollout did not change mappings. The
first-cutover instructions below describe the earlier activation.

## Release and private state

MDG CI builds and publishes only the gateway. When the server marker
`/opt/apps/signapse/mdg/mt5/enabled` is present, the gateway joins the private
`mdg_mt5` network with alias `mdg-tcp-smoke.test` and reads its existing token.
The release updates only the gateway and leaves the running terminal attached.

[mt5-services](https://github.com/signapse-group/mt5-services) owns the runtime
image, manual release and terminal Compose. The operator pins the terminal
image digest and retains the existing volume `mdg-mt5-terminal-home`.
Quote/candle and calendar use private TCP 9001/9002. Keep these ports private.

When adopting the independent terminal Compose project, follow the handoff
and rollback steps in the runtime repo. Verify quote, candle and calendar
afterwards. For fresh local volumes, use the [MDG Compose bundle](mt5-compose.md).

## First cutover (historical, paired pipeline)

1. Inspect architecture, space, running gateway, database and bindings. Back up the MDG
   database and private environment/override before changing mappings.
2. Merge the reviewed PR and let CI deploy the new MDG with MT5 still disabled.
3. Stop the local terminal cleanly. Archive its entire `/home/mt5` volume (Wine prefix,
   broker login, symbols, history and registered Service), verify archive checksum, and
   transfer it over verified SSH. Keep archive/state outside Git with owner-only access.
   Import into the external volume with UID/GID 10001, preserving file ownership.
   A new server instance may require broker reauthentication; verify rather than assume.
4. Copy the private shared token to `mt5/token.txt` (mode 600). Confirm it matches the
   terminal's `MQL5/Files/MarketDataToken.txt`; do not display its contents.
5. Use the newly deployed image to run `python -m scripts.seed_mt5_local --database
   dev-signapse-mdg`. This explicitly guarded operator step enables the agreed 22
   symbols and switches their default mappings in one transaction. No schema downgrade
   or candle deletion is performed. Do not point test fixtures at this database.
6. Create the activation marker, then rerun only the successful dev Actions run's
   `deploy` job. This reuses the checked images/digests and supplies the temporary registry
   login through the existing pipeline. The release `dev.py` validates both revision labels
   and runs the existing migration/HTTP/build checks under the deployment lock.
7. Verify the running terminal image ID, resource limits, broker login/Service connection,
   fresh REST and WebSocket XAU/USD prices, all 22 × 9 candle requests, and persistent
   state after a terminal restart. Read the live `/openapi.json` build revision.
   Save sanitized evidence under `docs/verification/`.

## First-cutover recovery and limits

Stop the terminal and remove the activation marker to disable the additional runtime.
Restore the backed-up symbol/default mapping rows and private override/environment
before deploying the compatible previous MDG digest. Do not delete the volume or
restore/drop the shared database as a routine rollback. Retain the local runtime volume
until server verification passes; leave local MT5 stopped after successful migration.

The account is a Vantage demo account. Prices are broker quotes/CFDs and may differ
from underlying exchanges. Current tick delivery is a polling snapshot, not a lossless
tick archive. Long soak testing and a measured one-second latency SLO remain unverified.
