> Historical PoC snapshot. Current CalendarService has no fault-injection commands;
> see [active local integration](mt5-calendar-integration.md).

# Hai MQL5 Service trong cùng MT5/Wine — kết quả local

Ngày 2026-11-04, trên branch `codex/mt5-calendar-poc`, base `ef62137` + source chưa commit.
**Đọc calendar và gửi quote chạy đồng thời được trong cùng một terminal.**
Phép thử này ủng hộ tách `CalendarService` khỏi vòng quote/nến trước khi tích hợp MDG.

## Thay đổi và phạm vi

- `MarketDataService.mq5` trở về đúng source ở base: quote/nến, TCP 9001.
- `CalendarService.mq5` chạy thread MQL5 riêng, đọc native calendar, TCP 9002.
  Giữ kiểm tra Vantage demo, Algo Trading tắt, token authentication và request bounds.
- Collector PoC mở hai listener trong cùng process Python; dùng lại normalization,
  calendar validation và quote metrics của PoC trước. Chưa thay HTTP API/provider production.
- Cùng một container MT5/Wine, một login demo, clone volume local đã có; giới hạn
  1 CPU / 2 GiB. Không tạo terminal thứ hai, không truy cập server hoặc ghi DB.

Source: [CalendarService](../scripts/mt5/CalendarService.mq5),
[collector](../scripts/verify_mt5_split_calendar.py),
[entrypoint local](../scripts/mt5/calendar-poc-entrypoint.sh).
Clone volume có hai Service được đăng ký trong `Config/services.ini`, cùng host
`mdg-tcp-smoke.test`, khác port. Private state/token vẫn ở ngoài Git.

## Kết quả

[Raw evidence](verification/mt5-split-calendar-20261104.json) có `passed=true`,
8 query hợp lệ, collector exit 0 và không có lỗi quote/calendar ngoài lần ngắt TCP
calendar được chủ động gây ra. [Đối chiếu](verification/mt5-split-calendar-comparison-20261104.json)
xác nhận bảy mẫu trước đó vẫn khớp giờ UTC, actual/null và forecast.

| Calendar | Sự kiện | Native fetch / toàn handler lần đầu | Handler warm |
| --- | ---: | --- | ---: |
| Tuần 26/10–01/11 | 304 | 470 / 568 ms | 83 ms |
| Tuần 02/11–08/11 | 237 | 59 / 131 ms | 62 ms |
| Tuần 09/11–15/11 | 219 | 64 / 139 ms | 59 ms |

Đây là lần đầu trong phiên terminal mới, nhưng volume đã có cache từ PoC trước;
không gọi đây là phép đo cold cache sạch hoàn toàn.

| Giai đoạn | XAUUSD / EURUSD khoảng snapshot lớn nhất | Quan sát |
| --- | --- | --- |
| Baseline 30 giây, sau warmup | 276 / 277 ms | Mỗi mã 110 snapshot |
| Calendar đọc tuần trước ~580 ms ở collector | 274 / 274 ms | Mỗi mã nhận 2 source tick mới ngay trong query |
| Chặn riêng thread calendar 5 giây, quan sát 6 giây | 276 / 276 ms | Mỗi mã nhận 22 snapshot; XAUUSD 19, EURUSD 4 source tick mới |
| Ngắt/kết nối lại TCP calendar ~1,03 giây | 278 / 278 ms | Quote socket giữ kết nối; XAUUSD tiếp tục tiến |
| Recovery 30 giây | 278 / 279 ms | Mỗi mã 110 snapshot; query calendar sau lỗi vẫn hợp lệ |

Phép chặn 5 giây dùng `Sleep(5000)` qua lệnh PoC `POC_DELAY`: đó là lỗi chậm được
chủ động mô phỏng trong Service calendar, không phải timeout upstream thật.
`POC_RECONNECT` chỉ đóng rồi mở lại kết nối TCP calendar; chưa stop/start lại
chính MQL5 Service. Hai lệnh fault-injection chỉ phục vụ PoC, không phải contract production.

Số snapshot và độ tươi dữ liệu là hai đại lượng khác nhau. Cuối giai đoạn chặn,
EURUSD có source age ~5,9 giây dù snapshot vẫn tới đều; XAUUSD ~1,1 giây. Vì vậy
không kết luận mọi symbol luôn tươi dưới 300 ms. Source timestamps và quote age
được giữ trong evidence; snapshot lặp không được tính thành source tick mới.
Warmup cũng có outlier ~4,4 giây, nên bảng baseline lấy sau warmup 10 giây.

So với PoC chung loop trước có khoảng ngừng snapshot ~3,7 giây khi đọc calendar,
lần tách này không quan sát ngừng gửi quote tương ứng trong query hoặc fault delay.
Đây là bằng chứng local cho việc loại bỏ chặn chung vòng lặp, chưa phải SLO dài hạn.

## Verification và trạng thái bàn giao

Cả hai Service compile bằng MetaEditor thực tế: **0 errors / 0 warnings**.
Tám tests normalization/metrics/TCP cleanup hiện có đạt; Ruff check/format collector
mới và `git diff --check` đạt. Live collector có assertions về dữ liệu, clock,
nguồn tick tiến trong baseline/fault/recovery và phục hồi calendar sau reconnect.

Đã dừng container terminal PoC; collector thoát 0. Keycloak vẫn chạy. Container
MT5/gateway/database local gốc vẫn tắt; clone volume giữ cấu hình hai Service để thử lại.
Source và evidence chưa commit/push/deploy.

Chưa đo soak dài hạn, timeout native thật, restart toàn Service calendar hay tác động
khi terminal thiếu CPU/RAM. Chưa nối hai listener này vào provider MDG production;
đường clock calendar vẫn chỉ được kiểm chứng trong ba tuần đã khảo sát.
