# Kiểm chứng TCP trực tiếp MT5–MDG tại local

**Kết quả ngày 2026-11-02: đạt.** Nhánh `codex/mt5-tcp-smoke` tách từ `dev`
tại `a85c2be2b43e52ff9f3bfaaacb121d2004544706`; chưa commit/push/deploy.

MQL5 Service trên Wine 11 / MT5 build 6286 kết nối trực tiếp tới Python trong
container thử MDG. Receiver và FastAPI hiện có chạy cùng process, sử dụng source
`app/` của nhánh. Container MT5 vẫn giới hạn **1 CPU / 2 GiB**, không mở chart/EA,
Algo Trading và DLL imports tắt. Không có Go hoặc Python helper cạnh terminal.

| Kiểm tra thực tế | Kết quả |
| --- | --- |
| Biên dịch Service | 0 lỗi, 0 cảnh báo |
| TCP hai chiều | Hai phiên xác thực thành công; tự kết nối lại sau phiên đầu |
| MQL5 → MDG | 40 mẫu XAUUSD/phiên, tổng 80; timestamp tick tiến lên, Bid/Ask hợp lệ |
| MDG → MQL5 → MDG | PING và yêu cầu ba nến M1 đã đóng đều thành công ở cả hai phiên |
| Dữ liệu TCP | Gửi lệnh theo hai phần, rồi gộp hai lệnh; Service xử lý đúng |
| Xác thực | Client sai token bị đóng kết nối |
| MDG HTTP đồng thời | `/health` trả 200/UP; `/openapi.json` trả 200, revision khớp source |
| Kiểm tra code | 614 test có sẵn đạt, 48 integration test skip vì thiếu DB thử; 7 test mới đạt; Ruff/format/mypy đạt |

Bằng chứng đã loại thông tin đăng nhập: [kết quả JSON](verification/mt5-tcp-smoke-20261102.json).
PING mất khoảng 65 ms trong lần chạy có FastAPI, **bao gồm 50 ms cố ý chờ giữa
hai phần lệnh**; không dùng số này làm độ trễ broker → MDG.

## Chạy lại

Source: [receiver Python](../scripts/mt5_tcp_smoke.py),
[Service MQL5](../scripts/mt5/TcpSmoke.mq5),
[giới hạn và protocol thử](adr/0003-local-mt5-tcp-spike.md).

1. Tạo token ngẫu nhiên ít nhất 32 ký tự trong file private ngoài Git. Đưa cùng
   token vào `MQL5/Files/TcpSmokeToken.txt` của terminal và file cho receiver.
2. Compile `TcpSmoke.mq5` bằng MetaEditor, đặt EX5 vào `MQL5/Services`. Đây vẫn
   là runtime được provision sẵn; lần đầu cần Add Service qua Navigator.
3. Chạy receiver trong image có dependencies MDG, cùng Docker network với MT5.
   Bind-mount `app/` của nhánh vào `/app/app`, `scripts/` vào `/probe`, đặt
   `PYTHONPATH=/app`; dùng Docker network alias **`mdg-tcp-smoke.test`**.
   Chạy `python /probe/mt5_tcp_smoke.py --token-file <file> --output <file>`.
   Không publish cổng TCP 9001; nếu kiểm tra HTTP, chỉ bind `127.0.0.1:18081:8000`.
4. Trong MT5, thêm `http://mdg-tcp-smoke.test` vào allowlist và bật quyền
   WebRequest cho danh sách đó. Hostname không có dấu chấm không lưu được trong
   lần thử này. Giữ Algo Trading/DLL imports tắt, khởi chạy Service.
5. Receiver tự kết thúc sau hai phiên đạt; lỗi/timeout không trả thành công.
   Service giới hạn 180 giây, receiver 240 giây. Dọn token và container thử sau chạy.

**Chưa kiểm chứng:** cursor/lossless tick, history lớn, timezone/DST, độ trễ một
giây hoặc tải liên tục. Chưa đăng ký MT5 provider hay đưa dữ liệu vào cache,
database, REST/WS market-data của MDG. Token và container receiver đã dọn; runtime
MT5 hiện có được giữ lại. Không thay đổi server.
