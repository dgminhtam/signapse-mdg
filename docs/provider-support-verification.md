# Provider Support Verification

Ngày verify: `2026-07-27`

Phạm vi: 24 asset trong catalog, chỉ kiểm tra provider đang được đặt làm mặc định. Không kiểm tra
provider thay thế và không fallback.

Quy ước WebSocket:

- ✅: đã xác nhận có hỗ trợ. `AAPL` và `QQQ` được xác nhận bổ sung sau smoke test.
- ⚠️: subscribe thành công nhưng chưa quan sát được tick trong cửa sổ smoke test 25 giây; cần
  verify lại, chưa kết luận là không hỗ trợ.

| Asset | Provider mặc định | Candle | WebSocket | Đủ `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1week`, `1month` |
| --- | --- | :---: | :---: | :---: |
| `AAPL` | `TWELVE_DATA` | ✅ | ✅ | ✅ |
| `AUD/USD` | `YFINANCE` (`AUDUSD=X`) | ✅ | ✅ | ✅ |
| `BRENT` | `YFINANCE` (`BZ=F`) | ✅ | ⚠️ | ✅ |
| `BTC/USD` | `TWELVE_DATA` | ✅ | ✅ | ✅ |
| `COFFEE` | `YFINANCE` (`KC=F`) | ✅ | ⚠️ | ✅ |
| `CORN` | `YFINANCE` (`ZC=F`) | ✅ | ⚠️ | ✅ |
| `DJI` | `YFINANCE` (`^DJI`) | ✅ | ⚠️ | ✅ |
| `ETH/USD` | `BINANCE_SPOT` (`ETHUSD`) | ✅ | ✅ | ✅ |
| `EUR/USD` | `TWELVE_DATA` | ✅ | ✅ | ✅ |
| `GBP/USD` | `YFINANCE` (`GBPUSD=X`) | ✅ | ✅ | ✅ |
| `MSFT` | `YFINANCE` | ✅ | ✅ | ✅ |
| `NATGAS` | `YFINANCE` (`NG=F`) | ✅ | ⚠️ | ✅ |
| `NDX` | `YFINANCE` (`^NDX`) | ✅ | ⚠️ | ✅ |
| `NVDA` | `YFINANCE` | ✅ | ✅ | ✅ |
| `QQQ` | `TWELVE_DATA` | ✅ | ✅ | ✅ |
| `SPX` | `YFINANCE` (`^GSPC`) | ✅ | ⚠️ | ✅ |
| `SPY` | `YFINANCE` | ✅ | ✅ | ✅ |
| `SUGAR` | `YFINANCE` (`SB=F`) | ✅ | ⚠️ | ✅ |
| `TSLA` | `YFINANCE` | ✅ | ✅ | ✅ |
| `USD/JPY` | `YFINANCE` (`JPY=X`) | ✅ | ✅ | ✅ |
| `WHEAT` | `YFINANCE` (`ZW=F`) | ✅ | ⚠️ | ✅ |
| `WTI` | `YFINANCE` (`CL=F`) | ✅ | ⚠️ | ✅ |
| `XAG/USD` | `YFINANCE` (`SI=F`) | ✅ | ⚠️ | ✅ |
| `XAU/USD` | `TWELVE_DATA` | ✅ | ✅ | ✅ |

## Kết quả tổng hợp

- Candle: `24/24` asset có hỗ trợ.
- Đủ chín timeframe: `24/24` asset có hỗ trợ.
- WebSocket đã xác nhận: `13/24` asset.
- WebSocket cần verify lại do chưa thấy tick: `BRENT`, `COFFEE`, `CORN`, `DJI`, `NATGAS`, `NDX`,
  `SPX`, `SUGAR`, `WHEAT`, `WTI`, `XAG/USD`.

## Việc cần xử lý sau

- `.env` local đang dùng `TWELVEDATA_API_KEY`, nhưng runtime chỉ đọc `TWELVEDATA_API_KEYS`; năm
  asset mặc định dùng Twelve Data sẽ không được đăng ký khi chạy với cấu hình hiện tại.
- Public WebSocket API hiện chỉ nhận candle timeframe `1m`, `5m`, `15m`, `1h`, `4h`, `1d`;
  `30m`, `1week`, `1month` mới chỉ có ở candle REST.
- Chạy lại WebSocket smoke test cho 11 asset ⚠️ trong giờ giao dịch phù hợp và với cửa sổ quan sát
  dài hơn trước khi đổi trạng thái.
