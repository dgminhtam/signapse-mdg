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

Historical Price Resolution uses the same provider mapping and a common canonical ladder for every
row: `1m`, `5m`, `1h`, then `1d`. A valid empty result (including provider retention, natural gap,
or closed-session no-data) may advance to the next resolution. Timeout, transport, credentials,
quota/rate-limit, and malformed-payload failures remain `PROVIDER_UNAVAILABLE`; the resolver never
switches provider or synthesizes a candle. The response reports the selected canonical
`resolution` and keeps `pricedAt` at the selected candle open time.

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
## Provider Override release gate

Every configured mapping must pass latest quote, every public candle timeframe, historical-price
resolution, and WebSocket quote/candle delivery before it is exposed by `providerMappings`. A
mapping that fails verification must be fixed or removed, not hidden behind a route-specific
allowlist. Transient upstream failure is `PROVIDER_UNAVAILABLE`, not `UNSUPPORTED_PROVIDER`.

The automated release-gate matrix is
`tests/integration/test_provider_mapping_surface.py`. It loads the PostgreSQL registry, covers
all 24 enabled assets and 29 configured mappings, exercises all 9 REST candle timeframes,
historical-price resolution, and both stream channels with fake upstream adapters. The matrix
passed in the local validation run; it verifies routing, identity isolation, and response seams
without requiring live credentials. Live upstream smoke remains an operational release step for
the five inactive YFINANCE alternatives below.

Current inactive alternatives requiring full-surface verification:

| Asset | Provider mapping | Default mapping |
| --- | --- | --- |
| `AAPL` | `YFINANCE:AAPL` | `TWELVE_DATA:AAPL` |
| `BTC/USD` | `YFINANCE:BTC-USD` | `TWELVE_DATA:BTC/USD` |
| `ETH/USD` | `YFINANCE:ETH-USD` | `TWELVE_DATA:ETH/USD` |
| `EUR/USD` | `YFINANCE:EURUSD=X` | `TWELVE_DATA:EUR/USD` |
| `QQQ` | `YFINANCE:QQQ` | `TWELVE_DATA:QQQ` |

## Automated validation evidence

- `uv run pytest`: 597 passed.
- `uv run ruff check app tests`: passed.
- `uv run mypy app`: passed with no issues in 61 source files.
- Historical Price Resolution keeps one immutable Provider Selection while trying the fixed
  `1m` → `5m` → `1h` → `1d` ladder; the focused integration seam rejects look-ahead candles and
  preserves `close_time <= at`.
- The adaptive-resolution change owns the exact ladder and response `resolution`; provider support
  verification only confirms that each mapping can serve the canonical intervals or return a valid
  no-data result.
