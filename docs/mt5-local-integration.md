# MT5 → MDG: tích hợp và kiểm thử local

Ngày 2026-11-02 · nhánh `codex/mt5-tcp-smoke`, tách từ `dev` tại
`a85c2be2b43e52ff9f3bfaaacb121d2004544706`. Đây là snapshot kiểm chứng local
trước PR; việc chuyển runtime lên dev theo [runbook riêng](mt5-dev-deployment.md).

**MT5 đã nối vào quote cache, REST, WebSocket và candle PostgreSQL của MDG.**
MQL5 Service chủ động mở TCP xác thực tới process FastAPI; không có Go/Python
helper cạnh terminal. MT5 vẫn giới hạn **1 CPU / 2 GiB**.

## Đã kiểm chứng

| Phép thử | Kết quả |
| --- | --- |
| 22 asset × 9 timeframe qua REST | 198/198; mỗi truy vấn `count=3` trả 3 nến OHLC hợp lệ |
| Quote trước khi có WS subscriber | XAU/USD trả giá thật; ingestion chạy từ startup |
| WebSocket XAU/USD | Nhận quote và trạng thái SUBSCRIBED |
| Terminal pause 35 giây | REST DATA_STALE, WS STALE/RECONNECTING; nến đã lưu vẫn trả được |
| Unpause, restart MDG và MT5 | Nhận giá có receipt sau restart; nến đã lưu không đổi |
| Kiểm tra code | 679 test đạt trong Docker, gồm PostgreSQL integration; 25 test tập trung chạy lại trên bản cuối đạt; Ruff/format/mypy đạt |

Bằng chứng: [ma trận API](verification/mt5-local-integration-20261102.json),
[recovery](verification/mt5-local-recovery-20261102.json),
[TCP spike trước tích hợp](mt5-tcp-smoke.md).
Số thời gian recovery là một lần đo local, không phải SLO.

## Cấu hình đang chạy

- HTTP: `http://127.0.0.1:18081`, Swagger: `/docs`, contract sinh từ app: `/openapi.json`.
- TCP 9001 chỉ ở mạng Docker với alias `mdg-tcp-smoke.test`, không publish host.
- PostgreSQL `mdg_mt5_local` riêng; không dùng DB dev. Seed local bật 22 mã,
  tắt Corn/DJI và đặt default provider `MT5_VANTAGE_DEMO` trong DB này.
- MDG giữ canonical `WTI` theo contract hiện có, map `USOUSD`; catalog planning
  gọi `WTI/USD`. Chưa đổi public canonical hoặc seed/migration production.
- Mapping stock/ETF/index là CFD; Sugar Raw Cash và Wheat SRW Cash là mapping
  thử nghiệm. Kết quả này không tự thay production coverage sản phẩm.
- Token và broker credentials nằm ngoài Git; MT5 có quyền tài khoản demo nhưng
  Algo Trading/DLL imports tắt, Service không có lệnh giao dịch.

## Chạy lại

Trong repo MDG, dùng image đã build từ Dockerfile hoặc image local có cùng
locked dependencies. Compose bind-mount source của checkout, vì vậy image tag
không chứng minh source runtime; SOURCE_REVISION phải ghi rõ working tree.

```powershell
$env:MT5_LOCAL_MDG_IMAGE = '<local-mdg-image>'
$env:MT5_LOCAL_TOKEN_FILE = '<absolute-private-token-file>'
$env:MT5_LOCAL_SOURCE_REVISION = '<base-sha>+mt5-local-working-tree'
docker compose -f compose.mt5-local.yaml up -d database
docker compose -f compose.mt5-local.yaml run --rm --no-deps gateway alembic upgrade head
docker compose -f compose.mt5-local.yaml run --rm --no-deps gateway python -m scripts.seed_mt5_local
docker compose -f compose.mt5-local.yaml up -d gateway
uv run python -m scripts.verify_mt5_local --output docs/verification/mt5-local-integration-20261102.json
uv run python -m scripts.verify_mt5_recovery --output docs/verification/mt5-local-recovery-20261102.json
```

Recovery script chỉ pause/restart container local có tên cố định; không chạy khi
đang có người sử dụng terminal đó. Dừng bằng `docker compose -f compose.mt5-local.yaml stop`;
không xóa volume nếu muốn giữ cache nến. Integration pytest phải dùng database
khác, ví dụ `mdg_mt5_pytest`, vì fixture downgrade schema.

Runtime MT5 hiện có được provision ở workspace local riêng. Source tham chiếu
[Dockerfile](../scripts/mt5/Dockerfile), [entrypoint](../scripts/mt5/entrypoint.sh),
[Service](../scripts/mt5/MarketDataService.mq5). Compile Service bằng MetaEditor,
copy EX5 vào `MQL5/Services`; cấu hình `MQL5/Files/MarketDataToken.txt` cùng token
với MDG và `MarketDataSymbols.txt` là CSV exact symbols từ
[seed mappings](../scripts/seed_mt5_local.py). Add Service một lần qua Navigator.

**Khởi động MT5 bằng `/portable`, không dùng `/config` cho runtime đã provision.**
MetaQuotes xác nhận config truyền qua `/config` là read-only, nên sửa allowlist
trong UI bị mất sau restart. Runtime dùng `Config/common.ini` private có thể ghi;
đăng nhập và lưu password local một lần, thêm `http://mdg-tcp-smoke.test` vào
allowlist, giữ Algo Trading/DLL imports tắt. Entrypoint đóng MT5 sạch trước Wine,
Compose terminal dùng `stop_grace_period: 30s`. Đã kiểm tra restart trên volume
hiện có; fresh install hoàn toàn không UI chưa được kiểm chứng.
[MetaQuotes platform start](https://www.metatrader5.com/en/terminal/help/start_advanced/start).

## Quy tắc dữ liệu và giới hạn

- Quote dùng Bid; volume nến là real_volume (0 khi không có), không đổi thành tick_volume.
- Giờ broker chuyển UTC theo New York + 7 giờ, kiểm clock handshake; W1 bắt đầu
  Chủ nhật theo sample MT5. Scan count dùng trang nhỏ để không quét nhiều năm
  khi gặp cuối tuần. Timestamp thật trùng/khuyết tại DST bị từ chối, không đoán.
- `receivedAt` giữ receipt gốc; broker event time quyết định freshness MT5.
  REST polling/heartbeat/replay không làm giá cũ mới lại.
- History chia trang 128 bar, request ID/deadline, retry LOADING trong budget;
  timeout/partial/error trả provider failure, không trả empty success giả.
- Đây là latest quote snapshots, chưa đảm bảo giao mọi raw tick. Chưa có soak
  dài hạn, benchmark latency một giây, lịch phiên đầy đủ hoặc bằng chứng quyền
  phân phối dữ liệu. Không dùng kết quả local làm xác nhận sẵn sàng production.
