# MT5 runtime on dev

The user authorized local → PR into `dev` → merge → server cutover on 2026-11-02.
The 22 accepted assets replace dev's default provider mappings; CORN and DJI remain
disabled. Existing mappings and provider-keyed candle history are retained, not deleted.
The local verification is recorded in [the local runbook](mt5-local-integration.md).

Current dev state and the 2026-11-06 terminal-only lean/CPU rollout are recorded in
[the deployment evidence](mt5-dev-cpu-20261106.md). The current registry has 20 MT5
mappings and two Binance symbols; this rollout did not change mappings. The
first-cutover instructions below describe the earlier activation.

## Release and private state

CI builds and checks both MDG and the Wine runtime from the same revision. Both images
are published to the existing private registry repository and deployed by digest.
MT5's MQL5 Services are compiled with MetaEditor in the builder stage. The lean
runtime contains their EX5 binaries, Wine/Xvfb and the installed terminal; it does
not include MetaEditor, noVNC, x11vnc or websockify.
No login, password, token or private account state is included in Git or either image.
The packaged runtime also contains an account-free Wine prefix, installed MT5 and public
factory configuration. The existing server volume remains in use; the independent
[fresh-machine Compose bundle](mt5-compose.md) supplies credentials at runtime through `.env`.

The existing [dev pipeline](deploy-docker.md) deploys MDG alone until the operator creates
`/opt/apps/signapse/mdg/mt5/enabled`. Once enabled, it also applies
[`mt5-compose.yml`](../deploy/mt5-compose.yml) and recreates the terminal with the
matching release digest. MDG's private override keeps its existing bindings and DNS.
The terminal has 1 CPU, 2 GiB RAM, a persistent external volume
`mdg-mt5-terminal-home`. The lean runtime has no browser desktop or published terminal port.
TCP 9001 is not published. The Docker bridge provides the private connection to MDG
using the terminal's already-allowlisted hostname `mdg-tcp-smoke.test`.

The lean/CPU image was deployed on 2026-11-06 as an image-ID-pinned manual terminal
release, preserving the running gateway. Source remains unmerged; a later CI
deployment can replace this manual image. Existing private volumes can retain an older MetaEditor installation;
replacing the image does not delete files in persistent state.
MT5 LiveUpdate can also download MetaEditor back into that volume when connecting
to the broker; lean packaging does not disable the vendor's automatic updates.

## First cutover

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

## Recovery and limits

Stop the terminal and remove the activation marker to disable the additional runtime.
Restore the backed-up symbol/default mapping rows and private override/environment
before deploying the compatible previous MDG digest. Do not delete the volume or
restore/drop the shared database as a routine rollback. Retain the local runtime volume
until server verification passes; leave local MT5 stopped after successful migration.

The account is a Vantage demo account. Prices are broker quotes/CFDs and may differ
from underlying exchanges. Current tick delivery is a polling snapshot, not a lossless
tick archive. Long soak testing and a measured one-second latency SLO remain unverified.
