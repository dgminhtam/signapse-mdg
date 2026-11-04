> Historical PoC snapshot. Current CalendarService has no fault-injection commands;
> see [active local integration](mt5-calendar-integration.md).

# PoC economic calendar trên MT5 local

Ngày 2026-11-04. **Đọc được calendar thật trên MT5/Wine + Vantage demo, nhưng gọi
calendar đồng bộ trong vòng lấy tick có thể làm ngừng gửi quote.** Chưa tích hợp
nguồn này vào calendar MDG hoặc triển khai server.

## Phạm vi và bằng chứng

PoC ở nhánh `codex/mt5-calendar-poc`, base `ef62137584124f59b1bd14aba48093e8a4952e2a`,
với source chưa commit. Dùng bản sao volume local đã provision; container MT5 gốc,
gateway local và database local giữ nguyên trạng thái tắt. Không đăng nhập tài khoản
mới, thực hiện giao dịch, ghi calendar vào database hoặc đổi nguồn đang chạy.

MQL5 Service được bổ sung lệnh đọc `CALENDAR`, dùng chung vòng lặp quote hiện có.
Collector riêng đóng vai bên nhận TCP xác thực, lưu dữ liệu public và đo XAUUSD/EURUSD.
Mỗi lượt gồm baseline 30 giây, ba truy vấn tuần, lượt đọc lại và recovery 30 giây.
Giới hạn terminal vẫn 1 CPU / 2 GiB. Token và private terminal state ở ngoài Git.

- [Kết quả cuối](verification/mt5-calendar-poc-20261104.json): sáu truy vấn hợp lệ,
  collector exit 0, không có connection error.
- [Bảy mẫu tham chiếu](verification/mt5-calendar-reference-20261104.json) và
  [đối chiếu cuối](verification/mt5-calendar-comparison-20261104.json).
- [Lần đọc đầu](verification/mt5-calendar-poc-initial-20261104.json),
  [đối chiếu lần đầu](verification/mt5-calendar-comparison-initial-20261104.json) và
  [runtime, compile, source hashes, cleanup](verification/mt5-calendar-runtime-20261104.json).

## Dữ liệu ba tuần

Tuần tính từ thứ Hai 00:00 giờ Việt Nam, đến thứ Hai kế tiếp exclusive.
Số lượng là snapshot của phiên khảo sát, không phải cam kết độ phủ toàn bộ sự kiện.

| Tuần | Sự kiện | Có actual | Có forecast | Có revised previous |
| --- | ---: | ---: | ---: | ---: |
| 26/10–01/11 | 304 | 238 | 192 | 50 |
| 02/11–08/11 | 237 | 53 | 122 | 15 |
| 09/11–15/11 | 219 | 0 | 124 | 0 |

Hai lượt đọc trả cùng số lượng. Không có occurrence ID trùng trong từng query,
lỗi native, lỗi metadata hoặc row ngoài UTC window đã chuẩn hóa.

Đối chiếu PCE, ECI, JOLTS, Productivity, NFP, CPI và PPI với HTML MetaQuotes:
**7/7 giờ UTC và forecast khớp**; ba actual đã công bố khớp, bốn actual chưa công bố
đều null. Actual của PCE/ECI/JOLTS còn được đối chiếu với BEA/BLS. Forecast chỉ
được xác nhận là số của MetaQuotes, không phải số do cơ quan thống kê xác nhận.

JOLTS cho thấy cần giữ riêng hai trường: `previous=7.079M`,
`revisedPrevious=7.190M`; website/BLS hiển thị số đã sửa 7.190M. Đây là khác biệt
ý nghĩa dữ liệu, không phải lỗi giải mã. PoC giữ raw integer strings, số Decimal
đã chia 1.000.000, unit/multiplier/digits và hai trường previous riêng biệt.

## Phát hiện về giờ calendar

Phiên hiện tại có clock broker lệch UTC **+02:00**. Native calendar trả cả sự kiện
tuần trước theo offset phiên này. Tái sử dụng profile giờ nến theo DST lịch sử
(+03:00 trước 01/11) làm PCE/ECI lệch sớm một giờ: 11:30Z thay vì 12:30Z.

PoC cuối đổi cả query bounds và event time bằng offset từ handshake đã xác thực,
giữ thêm `barProfileScheduledAt` để thấy cách diễn giải cũ. Không sửa helper giờ
nến của ứng dụng. Bảy mẫu đều khớp sau thay đổi, bao gồm hai phía mốc DST 01/11.
Quy tắc offset phiên mới chỉ có bằng chứng cho ba tuần này; chưa suy rộng sang
phiên đổi DST trong tương lai hoặc toàn bộ lịch sử.

## Tác động lên quote

| Lần đo | Native fetch / toàn handler | Khoảng giữa hai snapshot quanh query |
| --- | --- | --- |
| Initial, đọc tuần trước lần đầu | 3.303 / 3.565 giây | XAUUSD 3.663 giây; EURUSD 3.665 giây |
| Chạy lại, tuần trước lần đầu của phiên | 457 / 621 ms | XAUUSD 895 ms; EURUSD 896 ms |
| Chạy lại, tuần này / tuần sau | 55 / 151 ms; 57 / 118 ms | Khoảng 360 / 301 ms |
| Chạy lại, ba truy vấn warm | Handler 69–90 ms | Khoảng 273–277 ms |

Trong query dài, không có quote snapshot được gửi; code cũng xác nhận cùng thread
chưa quay về `CopyTicks` khi native calendar/metadata/send còn chạy. Vì vậy cách
gộp đồng bộ này có tác động lên luồng quote. Warm query ngắn hơn chu kỳ polling
không tạo khoảng dừng bổ sung rõ rệt trong lần đo này; thiếu tick bên trong một
query dưới 250 ms tự nó không chứng minh bất thường.

Baseline không hoàn toàn phẳng: initial có outlier snapshot nội bộ 4.495 giây;
run cuối XAUUSD có outlier 3.188 giây, dù p95 snapshot khoảng 276 ms. Metrics tách
gap nằm hoàn toàn trong baseline khỏi gap băng qua query. Không diễn giải mọi
khoảng ngừng là do calendar, cũng không dùng kết quả này làm SLO.

Kết luận kỹ thuật: có thể tiếp tục thử MT5 làm nguồn calendar, nhưng cần kiểm chứng
đường thực thi calendar tách khỏi vòng lấy tick trước khi coi là không ảnh hưởng giá.
PoC này chưa kiểm tra phương án tách đó.

## Kiểm tra và chạy lại

MetaEditor thực tế: **0 errors / 0 warnings**. Tám focused tests đạt; Ruff check,
format và `git diff --check` đạt. Tests gồm Decimal/missing/zero, query gap băng qua
biên phase, tách baseline, DST và shutdown với TCP client giữ kết nối mở.

Collector dùng image MDG có locked dependencies, mount source PoC, output directory
và token private read-only. Trên mạng Docker local riêng, đặt alias bên nhận là
`mdg-tcp-smoke.test`; terminal dùng bản sao volume và compile Service PoC cùng tên
đã đăng ký. Không chạy collector này song song với MDG trên cùng endpoint.

```text
python -m scripts.verify_mt5_calendar_poc --token-file /run/poc-token \
  --output /output/mt5-calendar-poc-20261104.json --anchor-date 2026-11-04
```

`passed=true` xác nhận sáu query có dữ liệu hợp lệ và source tick tiến ở baseline/
recovery; không có nghĩa quote không bị ảnh hưởng hoặc nguồn đã sẵn sàng production.

Đã dừng terminal PoC, collector đã thoát; clone volume private được giữ để thử lại.
Docker local từng restart trong lần copy đầu chưa giới hạn bộ nhớ; copy lại với
128 MiB hoàn tất, Keycloak đang chạy trước tác vụ được khởi động lại sau cleanup.
Lần collector đầu bị chờ peer khi shutdown; đã sửa và thêm TCP regression, giữ
nguyên bằng chứng initial, rồi chạy lại hoàn tất sạch.

Chưa soak dài hạn, chưa quan sát actual mới xuất hiện đúng lúc công bố, chưa đối
chiếu toàn bộ 760 sự kiện hoặc chứng minh thay thế đủ bốn nhóm calendar hiện tại.
