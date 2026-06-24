# Deploy With Docker

Hướng dẫn này chạy Market Data Gateway bằng Docker Compose với một service FastAPI. PostgreSQL dùng
container database có sẵn trong Docker network `signapse_default`.

## Prerequisites

- Docker và Docker Compose.
- PostgreSQL container `signapse-database-1` đang chạy trong network `signapse_default`.
- Server có outbound network tới Binance, Twelve Data, và Yahoo Finance.

## Configure

Docker Compose dùng biến trực tiếp trong `docker-compose.yml`, không đọc `.env`.
Server-specific overrides như Tailscale bind address nên đặt trong `docker-compose.override.yml`
trên server; file đó không commit.

Trước khi deploy dev, sửa các giá trị này trong `docker-compose.yml` nếu cần:

- `image`
- `DATABASE_URL`
- `TWELVEDATA_API_KEY`
- published port ở `ports`

Default `DATABASE_URL` dùng service name `database` trong Docker network `signapse_default`:

```text
postgresql+asyncpg://postgres:REPLACE_WITH_EXISTING_POSTGRES_PASSWORD@database:5432/dev-signapse-mdg
```

Nếu Docker DNS không resolve được `database`, đổi host thành container name
`signapse-database-1`. Cả hai chỉ hoạt động khi `gateway` join network `signapse_default`.
`TWELVEDATA_API_KEY` chỉ cần cho live Twelve Data quotes/candles/streams; crypto Binance public
market data không cần API key.

Lấy password đúng từ compose/env của stack database hiện tại. Lỗi này nghĩa là password đang sai:

```text
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "postgres"
```

## Create Database

Tạo database mới bên trong PostgreSQL container đang có:

```bash
docker exec signapse-database-1 createdb -U postgres dev-signapse-mdg
```

Nếu database đã tồn tại, lệnh trên sẽ báo lỗi; bỏ qua và chạy migration.

```bash
docker exec signapse-database-1 psql -U postgres -l
```

Test connection từ image gateway trước khi migrate:

```bash
docker compose run --rm gateway python -c "import asyncio, os, asyncpg; asyncio.run(asyncpg.connect(os.environ['DATABASE_URL']))"
```

## Tailscale Dev Access

Để máy local gọi service trên dev server qua Tailscale, lấy Tailscale IPv4 trên dev server:

```bash
tailscale ip -4
```

Tạo `docker-compose.override.yml` trên dev server:

```yaml
services:
  gateway:
    ports:
      - "100.x.y.z:8000:8000"
```

Sau khi deploy, gọi từ máy local bằng Tailscale IP:

```bash
curl http://100.x.y.z:8000/health
```

Docker Compose tự merge file override khi chạy `docker compose ...`. Nếu chỉ muốn test trực tiếp
trên dev server, không tạo override và giữ `127.0.0.1:8000:8000`. Không đặt `0.0.0.0:8000:8000`
trừ khi service đã nằm sau auth/rate limit.

## Build And Push Locally

Trên máy local, build image bằng `Dockerfile` rồi push lên Docker Hub:

```bash
docker login
docker buildx build --platform linux/amd64 -t your-dockerhub-user/signapse-mdg:dev --push .
```

Giá trị tag này phải khớp với `image` trong `docker-compose.yml`:

```yaml
image: your-dockerhub-user/signapse-mdg:dev
```

## Deploy On Dev Server

Trên dev server, pull image:

```bash
docker compose pull gateway
```

Run migrations:

```bash
docker compose run --rm gateway uv run alembic upgrade head
```

Start the gateway:

```bash
docker compose up -d gateway
```

## Verify

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Supported symbols:

```bash
curl http://127.0.0.1:8000/v1/symbols
```

Binance quote smoke test:

```bash
curl "http://127.0.0.1:8000/v1/quotes?symbols=BTC%2FUSD"
```

## Operate

View logs:

```bash
docker compose logs -f gateway
```

Restart the app:

```bash
docker compose restart gateway
```

Apply migrations after a new deploy:

```bash
docker compose pull gateway
docker compose run --rm gateway uv run alembic upgrade head
docker compose up -d gateway
```

Stop services:

```bash
docker compose down
```

Keep the service internal-only unless a reverse proxy with auth and rate limiting is added.
