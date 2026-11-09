# Tối ưu CPU/RAM MT5 trên local — 2026-11-05

Bản `signapse-mt5:cpu-lean-local` giảm phần CPU vẽ UI và số lần đánh thức hai
service. Kiểm thử từ volume trống ở **1 CPU, 1 GiB RAM, không swap** đạt quote,
calendar, candle và restart. Tuy nhiên **chưa giải quyết được CPU gần một core
sau khi tải history đầy đủ**: các cửa sổ đo sau candle vẫn 78.6–90.71% CPU.
RAM đỉnh quan sát giảm, RAM trung bình sau candle không giảm.

Đây là kết quả local trên Docker Desktop/WSL2, working tree nhánh
`codex/mt5-runtime-cpu`, base `5986885f70e7c3c1cda2dc72b60c6ded1e5aa0b9`.
Chưa commit, push hoặc deploy. Thay đổi packaging/lean của các lượt trước vẫn
nằm trong cùng working tree; không coi toàn bộ diff là thay đổi riêng lượt CPU.

## Vì sao vẫn gần một core

Profiler stdlib đọc delta CPU của process/thread từ `/proc` và tổng cgroup trong
30 giây; CPU 100% tương đương khoảng một core. Memory là working set Docker,
không phải tổng bộ nhớ Docker Desktop hoặc RAM toàn bộ stack MDG/PostgreSQL.
Xem [profiler](https://github.com/signapse-group/mt5-services/blob/main/profile_runtime.py) và định nghĩa trường
[`/proc/stat`](https://docs.kernel.org/filesystems/proc.html).

Đối chiếu UI trên cùng baseline trước tải candle đầy đủ:

| Trạng thái | CPU tổng | Main thread | Xvfb | Working set cuối |
| --- | ---: | ---: | ---: | ---: |
| Cửa sổ hiển thị | 60.21% | 13.39% | 2.23% | 571.98 MiB |
| Minimize | 38.42% | 1.97% | 0% | 578.07 MiB |
| Restore cửa sổ | 50.46% | 11.06% | — | 588.64 MiB |

[Baseline](verification/mt5-cpu-profile-baseline-20261105.json),
[minimize](verification/mt5-cpu-profile-minimized-20261105.json),
[restore](verification/mt5-cpu-profile-restored-20261105.json) cho thấy giảm render
là tác động có thể đảo ngược. Đóng bốn chart mặc định chỉ đạt 47.99% ở lượt riêng,
không có lợi ích rõ; đã khôi phục profile chart và không đưa thao tác này vào image.

Sau toàn bộ candle matrix, cửa sổ vẫn minimize nhưng CPU tăng trở lại. Trong
[profile có nhóm thread](verification/mt5-cpu-profile-history-groups-20261105.json):

| Nhóm | CPU trên một core |
| --- | ---: |
| Tổng cgroup | 90.71% |
| `wineserver` | 40.92% |
| 23 thread `history symbol` của terminal | 35.82% |
| MarketDataService | 2.73% |
| CalendarService | 1.13% |
| Main UI | 2.47% |

Đây là attribution đã quan sát được của tải cao: native history và Wine chiếm
phần lớn, service loop và UI chỉ chiếm phần nhỏ sau minimize.

Phép [đối chiếu restart đã ổn định](verification/mt5-cpu-history-activation-valid-20261105.json)
đọc quote mới trước khi đo, dùng provider đúng `MT5_VANTAGE_DEMO`: trước candle
CPU 37.77%, 4 thread history dùng 8.17%; sau 22 request 1m × 20 bars đều thành
công, CPU 89.25%, 23 thread history dùng 34.73%. Quote tiếp tục cập nhật qua hai
cửa sổ đo 30s. Như vậy workload candle kích hoạt thêm native history worker và
tải còn lưu lại sau request. Chưa chứng minh nguyên nhân sâu bên trong MT5/Wine
hoặc rằng chỉ một API tạo ra toàn bộ tải nền.
Một phép đo restart bổ sung đã dùng nhầm provider `MT5` và bắt trúng startup;
[artifact lỗi](verification/mt5-cpu-history-activation-20261105.json) được đánh dấu
không hợp lệ cho so sánh nhân quả, không dùng làm bằng chứng candle thành công.

Host dùng kernel `6.6.87.1-microsoft-standard-WSL2`, không có `/dev/ntsync`.
[Kernel mô tả NTSync](https://docs.kernel.org/userspace-api/ntsync.html) là cơ chế
hỗ trợ emulation synchronization của Windows. Chưa thử kernel/NTSync khác nên
không kết luận thiếu NTSync là root cause hoặc bật nó sẽ giải quyết CPU MT5.

## Thay đổi giữ lại

- MarketDataService dùng `SymbolInfoTick` để đọc snapshot mới nhất thay vì
  `CopyTicks(..., 1)`. Đây là đúng primitive cho contract latest quote;
  [SymbolInfoTick](https://www.mql5.com/en/docs/marketinformation/symbolinfotick)
  trả tick hiện tại, còn [CopyTicks](https://www.mql5.com/en/docs/series/copyticks)
  có cơ chế đồng bộ tick database. Lượt riêng chưa chứng minh CPU giảm nhờ thay
  primitive; RAM thấp hơn sau restart cũng có yếu tố cache/khởi động.
- Idle loop của cả hai MQL5 service nghỉ 50 ms thay vì 20 ms. Quote polling vẫn
  250 ms. Snapshot + loop 50 ms + minimize đạt 35.29% CPU, 305.28 MiB trong
  [cửa sổ yên trước full history](verification/mt5-cpu-profile-combined-20261105.json).
  Đây không phải mức CPU duy trì sau mọi workload; lượt này cũng trùng một phần
  với build riêng trên host nên không dùng làm benchmark duy nhất.
- Helper stdlib minimize đúng main window một lần khi khởi động, bỏ qua helper
  window 1px của Wine. Khi dừng, map/activate rồi Alt+F4 để MT5 lưu state trước
  khi Wine kết thúc. Kiểm thử stop cho exit 0, không OOM; baseline trước đó có
  lượt stop exit 137. Helper không chạy watcher liên tục.

Giữ đủ 22 symbol, 9 timeframe, MaxBars 100000, native `CopyRates`, Bid quote,
broker clock/authentication và cấm trading. Không giảm phạm vi candle, không
bỏ Wine/Xvfb, không thêm dependency. Kiểm thử có cả request tối đa 1000 bars.

## Kết quả đầy đủ và tài nguyên

| Chỉ số terminal | Lean trước | Bản CPU mới |
| --- | ---: | ---: |
| CPU trung bình 60s sau matrix | 93.04% | 85.91% |
| RAM trung bình cùng pha | 503.04 MiB | 514.29 MiB |
| RAM đỉnh lấy mẫu toàn lượt | 873 MiB | 691.8 MiB |
| Image bytes | 6,874,561,032 | 6,874,581,232 |
| Giới hạn test | 1 CPU / 2 GiB | 1 CPU / 1 GiB, swap 0 |

[Baseline](verification/mt5-lean-runtime-20261105.json) và
[bản mới](verification/mt5-cpu-runtime-20261105.json) là hai lượt nối tiếp,
không phải benchmark cố định thị trường/cache. Vì thế không quy mọi chênh lệch
cho code. RAM đỉnh lấy mẫu giảm khoảng 20.8%, còn RAM steady tăng khoảng 11 MiB.
Profile sau đó tiếp tục ghi 78.6% và 90.71% CPU: chưa có bằng chứng tiết kiệm CPU
ổn định lớn sau full history. cgroup memory.peak đọc sau restart là 701.8 MiB,
chỉ thuộc generation đó; không thay thế peak lấy mẫu xuyên cả lượt.

Compose nguồn vẫn mặc định 2 GiB. Test dùng bản sao Compose chỉ đổi terminal
`mem_limit: 1g`, `memswap_limit: 1g`; không đổi giới hạn service khác. Không tự
hạ cấu hình deploy từ một lượt local. [Memory/UI](verification/mt5-cpu-memory-ui-20261105.json)
ghi nhận minimize, swap 0, memory event max/OOM/oom_kill đều 0.

[Native verifier](verification/mt5-cpu-local-20261105.json) giữ cả trial startup
chưa đạt, không chỉ trial cuối:

- Hai volume DB/terminal mới đều xác nhận 0 entry; tự login Vantage demo, hai
  service kết nối. Fresh quote và 334 calendar FOREX xuất hiện sau 45.83 giây;
  sau restart 16.19 giây. `lastSeenAt`/`receivedAt` mới được kiểm tra, không chỉ
  đọc lại dữ liệu cũ. Trading tắt; không lỗi socket/calendar guard.
- Candle **198/198 lần đầu và 198/198 sau restart**, đều first attempt. Kiểm tra
  OHLC, thứ tự UTC, scope registry, native timeframe và một request uncached
  khác count sau restart. WS cần trial thứ hai ở cả hai pha: pha đầu có
  RECONNECTING; pha restart trial đầu chỉ CONNECTING. Không tuyên bố startup
  stream liền mạch hoặc mọi trial đều đạt.
- [Capacity/concurrency](verification/mt5-cpu-capacity-20261105.json): EUR/USD 1m,
  XAU/USD 1h, BTC/USD 1m mỗi request 1000 bars đều HTTP 200, 1.33–2.13 giây.
  Đồng thời 45s WS nhận XAU 149 / EUR 41 / BTC 56 quote, chỉ CONNECTING/SUBSCRIBED;
  calendar 334 events tiếp tục refresh. Không STALE/RECONNECTING/ERROR trong
  cửa sổ capacity này.

Hai pha không auto restart/OOM. Test calendar poll 15s, mặc định vẫn 300s.
[Health cuối](verification/mt5-cpu-final-health-20261105.json) sau phép restart
chẩn đoán tiếp tục xác nhận quote/calendar có timestamp mới, cửa sổ minimize,
swap 0 và không có memory max/OOM event. Kết thúc đã stop cả ba container với
exit 0, giữ image và hai volume cuối để chạy lại; chỉ xóa project/volume setup
lỗi do lượt này tạo, đã kiểm tra ownership label. Không có container test còn chạy.
MQL5 compile 0 errors / 0 warnings; native FileSharingCheck đạt; audit image
không credentials, MetaEditor, noVNC/x11vnc/websockify hoặc test fixture.
Runtime LiveUpdate vẫn có thể tải MetaEditor vào volume như đã ghi ở runbook.
679 unit tests, Ruff check/format 166 file và Mypy 65 app file đạt.

Image đã kiểm chứng:
`sha256:7e2322b850aeada9495633b490dc70233f00f0bdef986d224c7c9f681fa8c6cf`.
[Image audit](verification/mt5-cpu-image-20261105.json) và runtime evidence giữ
EX5/source hashes. Không xuất image từ terminal đã đăng nhập.

## Phạm vi còn lại

Chưa soak dài, chưa thử máy vật lý thứ hai, chưa benchmark Windows native hoặc
Wine/kernel khác. Không sửa kernel/WSL, không dùng flag sync không kiểm chứng,
không tắt update, không giảm symbol/history để tạo số CPU đẹp hơn. Muốn giảm
CPU mạnh tiếp cần A/B native Windows hoặc môi trường Wine có NTSync với cùng
workload và kiểm thử contract tương tự; lợi ích chưa được xác nhận.

Một lượt setup Compose timeout 120s được giữ trong
[evidence riêng](verification/mt5-cpu-compose-timeout-20261105.json); harness tăng
thời hạn setup lên 300s rồi test lại bằng project/volume mới. Không tăng API
timeout để che candle lỗi. Postman CLI chưa cài; dùng native HTTP/WS harness sẵn
có, không đổi API contract. Không chạy lại bộ integration PostgreSQL độc lập;
native test đã chạy migration/seed và persistence trên DB mới.
