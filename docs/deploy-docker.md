# Deploy MDG to dev

The dev workflow is [`.github/workflows/dev.yml`](../.github/workflows/dev.yml).
PRs targeting `dev` run lint, formatting, Mypy, unit/OpenAPI tests and PostgreSQL integration
checks, then build and exercise the runtime image. Pushes to `dev` run those gates, publish
`dgminhtam/signapse-mdg:sha-<full-commit>` and deploy by immutable registry digest. The exact
image exercised by the operating checks is pushed without rebuilding it in a later job.
There is no production deploy trigger. A failed gate stops the remaining jobs.

## One-time setup before the first push

These are operator prerequisites, not actions performed by editing this repository:

1. Prepare a private Docker Hub repository `dgminhtam/signapse-mdg` and a scoped publishing
   token with push/pull access. The workflow forwards it through SSH stdin for image pulls,
   using a temporary release-local Docker config removed when deployment exits. It does not
   overwrite the deploy user's Docker login or keep registry credentials on the server.
2. Configure a Tailscale OAuth client for `tag:ci`, with access restricted to the dev server's
   SSH port. The workflow uses an ephemeral runner; it does not install a self-hosted runner.
3. Give a dedicated deploy SSH identity access to the MDG directory and Docker. Verify the
   server host key out of band and store the exact `known_hosts` entry. Do not disable SSH host
   verification or reuse an agent's workstation private key.
4. On the server, keep Docker Compose v2+, Python 3.10+ and `flock` available. The existing
   PostgreSQL 16 container and external Docker network `signapse_default` must remain available.
   The deployment root is `/opt/apps/signapse/mdg`, Compose project `mdg`, service `gateway`.
5. Preserve the existing server Compose file, image identity and database backup before cutover.
   Move its runtime values into `/opt/apps/signapse/mdg/.env`, with owner-only read/write access.
   Use [`.env.example`](../.env.example) as a key reference, replacing all placeholders. Retain
   effective pool, provider, polling and other operator settings. Keep `TEST_DATABASE_URL` out
   of the runtime file. Do not set `SOURCE_REVISION`: the image supplies its build revision.
6. Move server-only networking, Tailscale port binding, DNS and any other required Compose
   overrides into `/opt/apps/signapse/mdg/docker-compose.override.yml`. Do not copy the example
   over existing settings. Audit any remaining local image patches before replacing the image.
   Ensure the database URL points to the MDG database, not the backend database.

The root Compose file now loads runtime values from `.env`; it no longer contains credentials
or example provider keys. The server's old root `docker-compose.yml` is preserved by CI. Each
release receives its own reviewed Compose and deploy script under `releases/<full-commit>/`.
The deployment uses the server's `.env` and optional override file with those release files.
Overrides must not replace the image, command, entrypoint, source code or `SOURCE_REVISION`.

Example Tailscale binding override (use the server's actual address and retain its DNS settings):

```yaml
services:
  gateway:
    ports:
      - "100.x.y.z:8000:8000"
```

The base Compose keeps `127.0.0.1:8000:8000`. Keep access internal: MDG has no client auth.
Do not publish `0.0.0.0:8000:8000`. Secrets and the override file stay outside Git and images.
Do not log `docker compose config` or `docker inspect` environment values.

## GitHub configuration

Configure these repository secrets before enabling deployment:

| Secret | Purpose |
| --- | --- |
| `DOCKERHUB_USERNAME` | Docker Hub publishing identity |
| `DOCKERHUB_TOKEN` | Scoped push token for the MDG image repository |
| `TS_OAUTH_CLIENT_ID` | Tailscale CI OAuth client ID |
| `TS_OAUTH_SECRET` | Tailscale CI OAuth client secret |
| `DEV_SSH_PRIVATE_KEY` | Dedicated dev deploy key |
| `DEV_SSH_KNOWN_HOSTS` | Verified OpenSSH host-key entry for the exact configured host |

Repository variables: `DEV_SERVER_HOST` (Tailscale address/name), `DEV_SERVER_USER` (deploy user).
App/provider/database secrets stay on the server; CI never uploads them. PR checks receive
only synthetic PostgreSQL credentials for a disposable database. Integration fixtures can
`downgrade base`; never point them at any shared dev or production database.

## Deployment and verification

The pipeline serializes dev push runs. GitHub may replace an older pending run with a newer
one, so the latest pending dev revision is the deployment candidate. A server-side file lock
also prevents two deploy processes from changing the gateway simultaneously.

The workflow uploads the release Compose and [`deploy/dev.py`](../deploy/dev.py), then:

1. Validates the image digest, full commit SHA and Compose configuration.
2. Pulls the exact digest and checks `org.opencontainers.image.revision` equals the CI commit.
3. Runs `alembic upgrade head` once using the new image. Migration failure stops before the
   gateway is replaced; do not assume earlier successful migrations were rolled back.
4. Recreates only `gateway` with the exact image. HTTP requests and WebSockets may disconnect.
5. Compares the running container's image ID with the pulled digest's image ID.
6. Runs [`scripts/verify_deployment.py`](../scripts/verify_deployment.py) inside the gateway:
   `/health` must return `UP`, `/ready` must return `READY`, `/openapi.json` must report the exact
   expected `x-build-revision`, and `/v1/symbols` must return a readable list (an empty list is valid).
   The database's Alembic heads must equal the heads shipped inside the running image.
   Startup checks retry with a 180-second retry budget and bounded HTTP requests.

Successful evidence includes source SHA, registry digest, operating checks and the Actions run.
The commit SHA is baked into the image by `BUILD_REVISION`, exposed as `SOURCE_REVISION` and
`x-build-revision`; setting an environment value alone is not proof of delivery.
No new revision endpoint is introduced. Provider live quotes/candles/streams and product QA
acceptance are outside this deployment gate. No provider credentials are required for CI checks.

## Failures and manual recovery

Any failure leaves the Actions run failed. There is no automatic image rollback, database
`downgrade`, database reset, provider backfill or restart of the backend/database stack.
After replacement, a failed check may leave dev unavailable until the operator intervenes.

Read the failed phase in Actions. Inspect the gateway locally using:

```bash
docker logs --tail=100 mdg-gateway-1
```

Review/redact logs before sharing. Fix the cause and push the corrected revision to `dev`.
For manual image recovery, first verify schema compatibility and select a previously verified
release digest; restoring an old image does not undo a migration. Database restoration or
schema changes require their own scoped recovery procedure and backup verification.

Optional candle backfill remains a separate, explicit operator action. It is never part of deploy.
Do not run `docker compose down` against the shared Signapse stack to recover MDG.

## Local runtime-image smoke check

Build without pushing, with a full source revision:

```bash
docker build --build-arg BUILD_REVISION="$(git rev-parse HEAD)" -t mdg-local .
```

Use an isolated PostgreSQL database and `ECONOMIC_CALENDAR_POLL_SECONDS=0` for local smoke tests.
Run migration with the built image, launch it, then run inside that container:

```bash
docker exec <test-gateway> python -m scripts.verify_deployment <full-commit-sha>
```

This verifies the local runtime image only. It does not prove a registry push, GitHub Actions
run, server provisioning, deployed revision or end-to-end provider integration.
