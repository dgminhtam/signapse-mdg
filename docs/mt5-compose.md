# Chạy MT5 và MDG bằng image trên máy mới

Bundle [compose.mt5.yaml](../compose.mt5.yaml) dùng hai image đã đóng gói: MDG và
MT5/Wine. Một terminal chạy MarketDataService và CalendarService. PostgreSQL là
container riêng; không cần cài Python, Wine hoặc MT5 trên máy host.

Bản local hiện tại là `signapse-mt5:cpu-lean-local`; xem
[kết quả tối ưu CPU/RAM](mt5-runtime-performance.md). CPU sau full history vẫn
có thể gần một core. Compose mặc định 2 GiB; lượt kiểm thử mới đạt ở 1 GiB,
không swap bằng bản sao Compose riêng, chưa thay cấu hình deploy.

## Khởi động

Máy cần Docker Engine/Desktop với Linux containers AMD64, Compose v2, đủ dung lượng cho Wine/MT5, và kết
nối ra registry cùng Vantage. Hai image phải có sẵn local hoặc tài khoản Docker có
quyền pull chúng. Dùng image theo digest khi bàn giao một bản đã kiểm chứng.

1. Đặt `compose.mt5.yaml` và bản sao [.env.mt5.example](../.env.mt5.example) tên
   `.env` trong cùng thư mục.
2. Điền `MDG_IMAGE`, `MT5_IMAGE`, `POSTGRES_PASSWORD`, `MT5_LOGIN`, `MT5_PASSWORD`
   và `MT5_TOKEN`. Tài khoản hỗ trợ hiện tại là `VantageMarkets-Demo`.
3. Chạy:

```sh
docker compose --env-file .env -f compose.mt5.yaml up -d
```

Password PostgreSQL phải dùng các ký tự `A-Z`, `a-z`, `0-9`, `_`, `-` vì được ghép
vào connection URI. Dùng một giá trị ngẫu nhiên dài cho password và token; token
tối thiểu 32 ký tự. Mật khẩu Vantage được đặt trong dấu nháy đơn trong `.env` để
Compose giữ nguyên ký tự `$` hoặc `#`; dùng quy tắc escape của Compose nếu bản thân
mật khẩu chứa dấu nháy đơn. Không ghi credentials vào image, Git hoặc log, và giới
hạn quyền đọc `.env` cho người vận hành. Người có quyền Docker vẫn có thể đọc
environment của container.

Compose tạo volume trống theo project, chờ PostgreSQL sẵn sàng, rồi initializer
chạy Alembic và seed 20 mapping MT5 vào database `mdg_mt5_local`.
BTC/USDT và ETH/USDT dùng Binance Spot. Danh sách MT5 mặc định đã khớp với
registry, nên có thể để dòng `MT5_SYMBOLS` ở dạng comment trong `.env`. Gateway
khởi động hai listener private 9001/9002; terminal tự cấu hình bằng các biến runtime.
Không bind-mount source, installer, token file hoặc volume MT5 đã chuẩn bị từ máy cũ.

HTTP MDG chỉ bind loopback `http://127.0.0.1:18081`; OpenAPI: `/openapi.json`.
Image lean không có noVNC/x11vnc/websockify hoặc cổng desktop.

Không mở TCP 9001/9002 ra host. Alias receiver trong mạng Compose là
`mdg-tcp-smoke.test`. Giữ nguyên alias và port của hai service khi dùng bundle này.

## Kiểm tra dữ liệu

```sh
docker compose --env-file .env -f compose.mt5.yaml ps
curl 'http://127.0.0.1:18081/v1/quotes?symbols=XAU%2FUSD,EUR%2FUSD&provider=MT5_VANTAGE_DEMO'
```

Quote phải có hai phần tử trong `quotes`, `errors` rỗng và `receivedAt` tiếp tục
tăng khi có tick mới. Có thể theo dõi WebSocket tại
`ws://127.0.0.1:18081/v1/stream?symbols=XAU%2FUSD,EUR%2FUSD&provider=MT5_VANTAGE_DEMO`.

Calendar chạy lúc gateway khởi động và mỗi 300 giây mặc định. Đợi lượt refresh
thành công rồi gọi `/v1/economic-calendar?from=<UTC>&to=<UTC>&types=FOREX` với range
trong cửa sổ UTC today−2 ngày đến today+7 ngày exclusive. Kiểm tra key
`FOREX:mt5:<valueId>` và `lastSeenAt` mới. `/health`, `/ready` và terminal healthcheck
chỉ chứng minh process/database; chúng không chứng minh Vantage đã đăng nhập hoặc
calendar đã fetch. GET calendar chỉ đọc DB, không tự trigger fetch.

## Lưu state và chạy lại

```sh
docker compose --env-file .env -f compose.mt5.yaml stop
docker compose --env-file .env -f compose.mt5.yaml up -d
```

Named volumes `database-data` và `terminal-home` giữ dữ liệu DB và state terminal
qua restart/recreate. Compose mặc định có project name `mdg-mt5`; dùng `-p <name>`
trên mọi lệnh nếu muốn nhiều instance tách biệt. Để kiểm chứng từ volume trống,
dùng project name mới và xác nhận chưa có volume của project đó trước khi chạy.
Không dùng `down -v` trên instance cần giữ dữ liệu.

Initializer áp dụng lại 20 mapping/default provider MT5 khi được chạy;
bundle dành cho DB riêng và không kết nối DB dev/server. Không thay password DB
trong `.env` rồi kỳ vọng PostgreSQL trên volume cũ tự đổi password; rotation cần
đổi credential trong database trước. Thay image không tự reset volume.

## Build dành cho người phát triển

Người triển khai bằng registry không cần bước build. Để thử source local, clone
[mt5-services](https://github.com/signapse-group/mt5-services) vào thư mục cùng cấp
với checkout MDG, rồi chạy từ checkout MDG:

```sh
docker build -t signapse-mdg:mt5-compose-local .
docker build -t signapse-mt5:cpu-lean-local ../mt5-services
```

Không đưa `.env` vào build context hoặc truyền credential bằng build argument.
Build tải MT5 từ [nguồn chính thức](https://www.metatrader5.com/en/download), tạo
Wine prefix mới không có tài khoản, rồi dùng giao diện native để tìm broker
Vantage và thêm receiver cố định vào allowlist. Đây là bước tạo image; máy chạy
Compose không cần thao tác GUI. Không sao chép account database hoặc registry từ
terminal đã đăng nhập. Image giữ cả prefix sạch và cấu hình công khai vừa tạo.
Builder compile hai service bằng MetaEditor, yêu cầu 0 errors / 0 warnings rồi
chỉ copy prefix sạch và EX5 sang runtime stage độc lập. MetaEditor và các layer
cài đặt/compile không nằm trong runtime; runtime giữ Wine, Xvfb, Openbox và Python
stdlib để cấu hình từ `.env`. Startup copy EX5 vào volume, không compile lại.

[LiveUpdate của MT5](https://www.metatrader5.com/en/terminal/help/start_advanced/autoupdate)
kiểm tra component khi kết nối broker. Trong lượt local, nó đã tải lại MetaEditor
khoảng 116 MB vào **volume**, dù image không chứa compiler. Vì vậy image lean không
đảm bảo volume luôn vắng MetaEditor sau update; không dùng flag tắt update không
được vendor hỗ trợ. Việc compile hai service của MDG vẫn chỉ diễn ra trong builder.

Runtime đọc `.env`, ghi cấu hình private mode 600 và khởi động với file
`C:\mdg-start.ini`. Các thay đổi GUI trong runtime không thay thế cấu hình `.env`;
[config khởi động của MT5](https://www.metatrader5.com/en/terminal/help/start_advanced/start)
được đọc ở chế độ read-only. Giữ Algo Trading và DLL imports tắt.

Build cần Internet và phụ thuộc giao diện MT5 tiếng Anh hiện hành. Khi nâng MT5,
phải kiểm lại build và lượt chạy từ volume trống; image cũ theo digest giữ bản đã
kiểm chứng, không yêu cầu tải/cài MT5 lại trên mỗi máy chạy.

Source runtime và việc tạo MT5 sạch thuộc [repo mt5-services](https://github.com/signapse-group/mt5-services); bằng chứng local về
đăng nhập, quote, calendar và restart phải được ghi riêng sau khi chạy thật.
Build kiểm tra prefix không có tài khoản và các artifact công khai, nhưng không
nhận credentials để xác minh đăng nhập broker. Native quote/calendar sau startup
mới là bằng chứng runtime sẵn sàng; catalog tồn tại không thay thế kiểm tra này.

Để chạy verifier từ volume trống, dùng một bản `.env` riêng có
`MDG_HTTP_PORT=18085`, `ECONOMIC_CALENDAR_POLL_SECONDS=15`, rồi chạy:

```sh
uv run python -m scripts.verify_mt5_lean --env-file .env --project mdg-mt5-lean-check-1 --output docs/verification/mt5-lean-check.json
```

Project name phải chưa có volume. Verifier lưu mọi trial stream, đòi hỏi một cửa
sổ 30 giây ổn định và ma trận 198 request candle đạt cả trước/sau restart terminal.
Nếu lượt candle đầu có lỗi 503 `PROVIDER_UNAVAILABLE`, nó giữ nguyên evidence lỗi
và thử lại toàn ma trận một lần; lỗi khác hoặc retry còn lỗi làm verifier thất bại.
Đây là quy trình đo startup, không thay retry/timeout của API ứng dụng.

Hai service cùng đọc token nên phải dùng
[`FILE_SHARE_READ`](https://www.mql5.com/en/book/common/files/files_open_close).
Builder chạy `FileSharingCheck.mq5` trên fixture công khai để tái hiện việc reader
thứ hai bị chặn ở chế độ cũ và xác minh hai reader cùng mở được ở chế độ mới.
Fixture/test service không đi vào image runtime. Lượt kiểm thử đã từng gặp
CalendarService dừng lúc startup; nhánh thoát nay có log an toàn để đối chiếu,
không ghi token hoặc mật khẩu.

## Kết quả kiểm thử local — 04/11/2026

Working tree nhánh `codex/mt5-compose-bootstrap`, base `5986885`; chưa commit,
push hoặc deploy. Hai image local là `signapse-mdg:mt5-compose-local` và
`signapse-mt5:compose-local`. [Runtime/build evidence](verification/mt5-compose-runtime-20261104.json)
ghi image IDs, source hashes, kiểm tra image không có credential và metadata container.

Đã tạo project mới `mdg-mt5-empty-20261104b` và xác nhận cả volume database lẫn
terminal có **0 file trước khi chạy Compose**. Docker đưa prefix sạch đã đóng gói
trong image vào volume mới. Không mount source, installer, secret file, account
database hoặc volume từ instance cũ; chỉ Compose và file `.env` private ngoài Git.
Không thao tác GUI sau khi instance kiểm thử này được khởi động.

| Kiểm tra | Kết quả |
| --- | --- |
| Tự đăng nhập từ volume trống | Native log xác nhận `VantageMarkets-Demo`; quote TCP kết nối; không có lỗi permission 4014 |
| Database mới | Compose tự chạy migrations và seed 22 mapping trước khi gateway khởi động |
| Calendar | 341 sự kiện, key MT5 duy nhất, `lastSeenAt` tiếp tục tăng qua refresh |
| REST quote | XAU/USD và EUR/USD có giá dương, `errors=[]`, có dữ liệu trước WebSocket subscriber |
| WebSocket lần đầu, 30 giây | 83 quote XAU/USD, 28 quote EUR/USD; SUBSCRIBED, không STALE/RECONNECTING |
| Restart terminal | Cùng image/volume tự đăng nhập, quote và calendar cập nhật lại; không cần GUI |
| WebSocket sau restart, 30 giây | 109 quote XAU/USD, 51 quote EUR/USD; không STALE/RECONNECTING |
| Compile native | Cả hai service 0 errors / 0 warnings ở lần đầu và sau restart |
| Checks | 675 unit tests, Ruff check/format 161 files và Mypy app 65 files đạt; build hai image và Compose config đạt |

Bằng chứng HTTP/WS: [lần đầu](verification/mt5-compose-FIRST-20261104.json),
[sau restart](verification/mt5-compose-RESTART-20261104.json).
Lượt test dùng poll 15 giây để quan sát retry/refresh nhanh; default phát hành vẫn
là 300 giây, timeout calendar 60 giây. Lần đầu MT5 còn đăng nhập nên cron có thể
timeout rồi tự retry; không suy healthcheck đạt thành calendar đã sẵn sàng.
Thời gian chờ trong JSON tính từ lúc verifier bắt đầu, không phải SLO startup.

Instance của lượt thử cũ dùng HTTP `http://127.0.0.1:18084`, desktop localhost
6086; đây là bằng chứng lịch sử của image đầy đủ. Chưa thử trên máy vật lý thứ hai hoặc soak dài hạn; chưa chạy lại toàn bộ
pytest PostgreSQL integration suite vì app/schema không đổi. Persistence thực
được kiểm qua database mới của Compose và API native ở trên.

## Kết quả image lean local — 05/11/2026

Nhánh `codex/mt5-lean`, base `5986885`, working tree chưa commit/push/deploy.
Image cuối `signapse-mt5:lean-local` có ID
`sha256:3d3b90d756c88e7e38e41970fefa810bbd69cc58dc0950ec9f8a3210491ffcd7`.
[Metadata và số đo](verification/mt5-lean-runtime-20261105.json) ghi image IDs,
source hashes, giới hạn container, cấu hình đo và kiểm tra native.

Image không có noVNC/x11vnc/websockify, MetaEditor hoặc cổng desktop. Hai EX5 được
compile và kiểm tra trong builder; runtime giữ Wine/Xvfb, Openbox/xdotool cho
shutdown và Python stdlib cho `.env`. `/tmp` của factory/compiler là tmpfs riêng,
tránh lock display Xvfb từ bước trước. [Audit image](verification/mt5-lean-image-20261105.json)
xác nhận không có tài khoản, password/token hoặc fixture FileSharingCheck.

| Dung lượng image sau unpack | Kết quả |
| --- | --- |
| Image đầy đủ, số đo lịch sử 04/11 | 7.716.306.251 byte, khoảng 7,72 GB |
| Image lean cuối | 6.874.561.032 byte, khoảng 6,87 GB / 6,40 GiB |
| Chênh lệch | Giảm 841.745.219 byte, 10,91% |

Đây là dung lượng image chưa nén, không cộng build cache, image MDG/PostgreSQL
hoặc named volumes. Số đo image đầy đủ là bằng chứng lịch sử; không có baseline
RAM/CPU tương ứng còn chạy để kết luận mức giảm RAM/CPU.

Project `mdg-mt5-lean-20261105d` dùng hai volume mới được kiểm tra **0 file** trước
Compose. Không mount source, installer hay state terminal cũ. Tài khoản Vantage
được truyền từ `.env` private; không có thao tác GUI sau khi instance khởi động.
[Kết quả tổng hợp](verification/mt5-lean-local-20261105.json) giữ cả các trial lỗi
và trial đạt, cùng toàn bộ mẫu Docker stats.

| Kiểm tra native | Kết quả |
| --- | --- |
| Đăng nhập | VantageMarkets-Demo tự đăng nhập, Algo Trading/DLL imports tắt; token mode 600 |
| REST quote | XAU/USD, EUR/USD có giá dương, `errors=[]`, có trước WebSocket subscriber |
| Stream lần đầu, 30 giây | 73 XAU/USD, 34 EUR/USD; SUBSCRIBED, không STALE/RECONNECTING |
| Calendar | 334 sự kiện FOREX, key MT5 duy nhất, các trường thiếu giữ null; `lastSeenAt` tăng |
| Candle cold, lượt đầu | 195/198; EUR/USD 1m, 5m, 15m trả 503 sau khoảng 15 giây |
| Candle sau retry | 198/198, đủ 3 bars và OHLC hợp lệ cho 22 tài sản × 9 timeframe |
| Restart terminal | Cùng container/image/volume; quote và calendar có timestamp mới sau restart |
| Stream sau restart, 30 giây | 93 XAU/USD, 23 EUR/USD; không STALE/RECONNECTING |
| Candle sau restart | 198/198 ngay lượt đầu; request XAU/USD 1m count 10 cần thêm dữ liệu native cũng đạt |
| Native integrity | EX5 trên volume khớp builder; không có lỗi socket 4014 hoặc log lỗi guard CalendarService |

Evidence candle: [cold](verification/mt5-lean-local-20261105-FIRST-candles.json),
[retry](verification/mt5-lean-local-20261105-FIRST-candles-retry.json),
[sau restart](verification/mt5-lean-local-20261105-RESTART-candles.json).
Chờ quote/calendar mới mất 55,94 giây tính từ native verifier lần đầu và 71,32
giây tính từ lệnh restart. Các khoảng này không bao gồm toàn bộ thời gian tạo
volume/khởi động Compose và không phải SLO. API timeout candle 15 giây được giữ
nguyên; các lỗi 503 lúc cold start chưa được sửa trong adapter ở đợt đóng gói này.

Đo trên Docker Desktop Linux AMD64, terminal giới hạn **1 CPU / 2 GiB**, 22 symbol,
quote poll 250 ms và calendar poll 15 giây để kiểm refresh; default calendar phát
hành vẫn 300 giây. Không có stack thử khác chạy trong cửa sổ đo cuối.

| Tài nguyên terminal | Số đo |
| --- | --- |
| RAM working set, cửa sổ 60 giây không gọi candle sau restart | Trung bình 503,04 MiB; đỉnh 505,5 MiB, 18 mẫu |
| RAM working set cao nhất lấy mẫu trong toàn lượt | 873 MiB khi chạy candle cold |
| CPU ở cửa sổ 60 giây trên | Trung bình 93,04%; đỉnh 101,29%, xấp xỉ một core |
| CPU cao nhất lấy mẫu toàn lượt | 112,19% trong khoảng lấy mẫu ngắn |

Docker CPU 100% tương ứng khoảng một core; đỉnh ngắn có thể vượt 100% do cách lấy
mẫu/quota. Memory working set của Docker stats khác `memory.peak` có charged cache;
`memory.peak` được đọc sau restart chỉ thuộc cgroup hiện tại, không phải peak của
toàn lượt cold. Chưa chứng minh cấu hình CPU/RAM tối thiểu, giảm CPU, hoặc soak
dài hạn. Cửa sổ 60 giây là phạm vi quan sát, không khẳng định trạng thái cân bằng
lâu dài. Không còn process MetaEditor lúc kiểm tra sau benchmark.

### Những vấn đề phát hiện và giới hạn

Hai service trước đây mở cùng `MarketDataToken.txt` không có cờ chia sẻ. Native
[FileSharingCheck](verification/mt5-lean-file-sharing-20261105.json) tái hiện reader
thứ hai bị từ chối ở cách cũ, còn hai reader với `FILE_SHARE_READ` đều thành công.
Đã sửa cả MarketDataService và CalendarService, giữ nguyên kiểm tra token/broker
và quyền trading. Builder account-free cũng chạy lại phép kiểm này trước khi xuất
EX5; fixture không được ship. Các nhánh CalendarService thoát nay có log an toàn.

[Một lượt trước bản sửa](verification/mt5-lean-calendar-startup-failure-20261105.json)
đã thấy CalendarService tự dừng sau khoảng một giây và calendar trống dù quote
hoạt động. Bản cũ không log lý do thoát nên không khẳng định FileOpen là nguyên
nhân duy nhất của lượt đó. Native test xác nhận lỗi chia sẻ file là có thật;
lượt cuối đã qua cold start và restart sau sửa.
[Lượt stream đầu](verification/mt5-lean-cold-transient-20261105.json) từng thất bại
ở assertion trạng thái nhưng chưa lưu trạng thái chi tiết; probe ngay sau đó đạt.
[Lượt candle trước](verification/mt5-lean-cold-candles-20261105.json) cũng giữ lại
một 503 lúc startup. Không dùng các lượt này làm bằng chứng đạt.

LiveUpdate đã tải lại `MetaEditor64.exe` 109.414.288 byte và tạo `metaeditor.log`
trong volume của lượt cuối. Image vẫn không chứa MetaEditor; hai EX5 MDG vẫn khớp
builder và startup script không compile. Vì vậy mục tiêu loại compiler khỏi
**image** đạt, còn việc volume luôn không có compiler không được bảo đảm bởi MT5.

Checks: 675 unit tests, Ruff check/format 163 files, Mypy 65 app files, shell syntax,
Compose config, image build/audit và native file-sharing self-check đều đạt.
Chưa chạy lại toàn bộ pytest PostgreSQL integration suite; app/schema không đổi,
nhưng migrations, seed, persistence và API đã chạy thật trên database riêng mới.
Chưa thử máy vật lý thứ hai hoặc deploy server.

Đã dừng stack cuối sau khi đo để trả CPU/RAM, giữ image và hai volume cuối để
chạy lại. Chỉ các scratch project lỗi do lượt thử này tạo được dọn sau khi xác
nhận ownership labels; không prune volume/image khác hoặc thay state server.
