# Native MT5 calendar tích hợp MDG — local

Ngày 2026-11-04. Branch `codex/mt5-calendar-poc`, base `ef62137` + working tree chưa commit.
**CalendarService đã nối vào refresh, PostgreSQL và API MDG; nguồn scraper cũ đã được gỡ.**
Phạm vi bàn giao là implementation và kiểm thử local, chưa deploy dev/server.

## Quy tắc đã chốt

Theo quyết định trực tiếp của người dùng trong chat ngày 04/11:

- Macro MT5 được map vào FOREX, không nhân bản sang METALS/ENERGY/CRYPTO.
- Giữ nguyên dữ liệu nguồn cũ. Occurrence MT5 dùng `FOREX:mt5:<valueId>` để không
  ghi đè raw ID cũ; không tự merge hai provider hoặc tự backfill lịch sử production.
- Previous giữ giá trị gốc; revision là revised previous. Description/newsUrl và hai
  assessment better/worse thiếu từ MT5 được trả null. Không thay source_url vào newsUrl.

Chi tiết mapping và giới hạn timezone: [ADR 0005](adr/0005-mt5-economic-calendar.md).

## Thành phần và cấu hình

Một MT5/Wine terminal chạy hai MQL5 Service:

| Thành phần | Trách nhiệm |
| --- | --- |
| MarketDataService / TCP 9001 | Quote và candle, source gốc không thêm xử lý calendar |
| CalendarService / TCP 9002 | Native calendar, kết nối xác thực và thread riêng |
| MT5CalendarProvider | Listener riêng trong FastAPI, deadlines, validation, UTC và numeric mapping |
| EconomicCalendarRefreshService | Lấy toàn bộ window hợp lệ rồi upsert PostgreSQL |
| GET /v1/economic-calendar | Chỉ đọc persisted rows, không gọi terminal khi GET |

Default polling 300 giây và window UTC today−2 ngày → today+7 ngày exclusive được giữ.
Window 9 ngày được chia thành RPC tối đa 7 ngày. Sai clock, metadata, row count,
duplicate ID, disconnect, timeout hoặc partial page làm fail cả lượt trước khi upsert.
Calendar không dùng socket/lock RPC của quote. Khi calendar down, GET vẫn đọc DB.

```text
MT5_ENABLED=true
MT5_TOKEN_FILE=/run/mt5-token
MT5_TCP_PORT=9001
MT5_CALENDAR_TCP_PORT=9002
MT5_CALENDAR_TIMEOUT_SECONDS=60
ECONOMIC_CALENDAR_POLL_SECONDS=300
```

Token giữ ngoài Git; hai TCP port chỉ ở private Docker network. Nếu chạy MDG chỉ
với database và chưa provision MT5/token, đặt poll seconds về 0. Khi dùng port tùy
chỉnh, sửa input tương ứng trong MQL5 Service; registration mặc định dùng 9002.
Entrypoint compile cả hai source và idempotently đăng ký CalendarService trên volume
đã provision. Không bật Algo Trading hoặc DLL imports.

market-calendar-tool, adapter scraper và tests riêng của adapter đã được bỏ khỏi
source/dependency lock; không có fallback về ForexFactory. Các cột enrichment cũ
và repository semantics được giữ để đọc lịch sử, không chạy detail scraping nữa.

## Bằng chứng kiểm thử

- [Kết quả integration](verification/mt5-calendar-integration-20261104.json): native
  terminal → provider → PostgreSQL → HTTP và WebSocket thật trên loopback.
- [Đối chiếu bảy mẫu](verification/mt5-calendar-integration-comparison-20261104.json)
  với [reference](verification/mt5-calendar-reference-20261104.json).
- [Runtime/build/checks](verification/mt5-calendar-integration-runtime-20261104.json).

| Khoảng tuần Việt Nam | MT5 rows đọc qua API sau persistence |
| --- | ---: |
| 26/10–01/11 | 304 |
| 02/11–08/11 | 237 |
| 09/11–15/11 | 219 |

Sáu mốc kiểm tra quan trọng đều đạt: cron startup có success thật; sync lặp không
tạo duplicate; fixture legacy cùng raw ID vẫn giữ nội dung; calendar outage báo
provider failure; persisted GET còn đọc được trong outage; listener mở lại và
calendar reconnect thành công. Bảy mẫu UTC/actual/forecast khớp reference, bao gồm
ba actual đã phát hành và bốn actual null đúng trạng thái tại thời điểm khảo sát.
JOLTS qua HTTP giữ `previous=7.079M`, `revision=7.190M` đúng ý nghĩa đã chốt.

Kiểm thử TCP dùng connection thật cho partial response, timeout và sai role.
PostgreSQL regression xác nhận RPC trang hai bị partial không ghi trang đầu.
Shutdown giữ client TCP đang mở được kiểm tra để tránh chờ vô hạn; đã sửa thứ tự
đóng quote listener/client trước wait_closed trong MT5Provider khi tích hợp lifecycle.

**651 unit tests + 52 PostgreSQL integration tests đạt**. Ruff check/format,
Mypy toàn app, dependency-lock check và build image MDG với locked dependencies đạt.
Cả hai MQL5 Service compile bằng MetaEditor thực tế với 0 errors / 0 warnings.

Trong chạy integration đầu, WebSocket quote tiếp tục có event trong 5 giây calendar
listener down: XAU/USD 16 event, EUR/USD 5 event. Khoảng event lớn nhất lần lượt
~0,82 / 1,37 giây; baseline ~0,82 / 2,72 giây. Đây là event quote mới sau dedup,
khác snapshot polling của PoC cũ; không suy ra SLO hoặc độ tươi cố định cho broker.
Raw evidence của lượt cuối giữ số đo cụ thể để đối chiếu.

## Chạy lại local

Dùng database disposable riêng (script bảo vệ tên `mdg_mt5_local`), chạy Alembic
và seed MT5 mapping theo runbook local hiện có. Database cho pytest phải tách riêng:
fixture integration downgrade schema. Không dùng database dev/server cho tests.

Build image từ root checkout này bằng Dockerfile hiện có. Trong mạng Docker riêng,
đặt alias gateway `mdg-tcp-smoke.test`, mount token private và output directory,
khởi động terminal từ clone volume đã provision với entrypoint/source mới.

```text
python -m scripts.verify_mt5_calendar_integration \
  --output /output/mt5-calendar-integration-20261104.json
```

Script chạy application FastAPI thật và HTTP/WebSocket ở port 8000, đợi cron có
success rồi dừng cron để kiểm manual refresh có kiểm soát. Nó chèn một fixture legacy
vào DB local, đóng/mở riêng listener calendar và kiểm phục hồi. Nó không tạo admin
endpoint hoặc API refresh mới. Lượt test dùng poll 10 giây, timeout 5 giây để quan sát
retry/outage nhanh; production defaults vẫn là 300 / 60 giây. Terminal cần thời gian
khởi động nên lần cron đầu có thể timeout với test budget 5 giây; lần sau thành công.

Chưa commit/push/deploy. Chưa kiểm consumer BE/FE end-to-end, soak dài hạn, actual
mới xuất hiện đúng giờ công bố hoặc lần DST tương lai. Không tự động rebuild/migrate
lịch sử từ scraper sang MT5; retained old rows và missing-field contract phải được
giữ khi lập rollout riêng sau này.
