# Asset Coverage

- Trạng thái tài liệu: `Current Coverage` cho nhóm "Đang hỗ trợ"; `Planned Coverage` cho nhóm "Chưa hỗ trợ"
- Độc giả chính: Product, QA, business, operations, stakeholder

Trang này liệt kê các asset Signapse định danh trong catalog sản phẩm. "Canonical symbol" là mã chuẩn Signapse dùng để người dùng, watchlist, chart, graph và các luồng phân tích cùng nói về một tài sản theo một cách nhất quán.

## Nguyên tắc nhóm asset

Signapse đang chia asset theo các nhóm sản phẩm sau:

| Nhóm | Ý nghĩa |
| --- | --- |
| Forex | Cặp tiền tệ như EUR/USD, GBP/USD. |
| Commodity | Hàng hóa như vàng, bạc, dầu thô, khí tự nhiên và nông sản. |
| Stock Index | Chỉ số chứng khoán như S&P 500, NASDAQ-100, Dow Jones. |
| US Stock | Cổ phiếu Mỹ đơn lẻ. |
| Crypto | Cặp crypto theo USD. |
| ETF | Quỹ ETF đại diện cho rổ tài sản hoặc chỉ số. |

## Đang hỗ trợ

| Nhóm | Asset | Canonical symbol | Price display decimals |
| --- | --- | --- | ---: |
| Forex | Euro / US Dollar | `EUR/USD` | 5 |
| Forex | British Pound / US Dollar | `GBP/USD` | 5 |
| Forex | US Dollar / Japanese Yen | `USD/JPY` | 3 |
| Forex | Australian Dollar / US Dollar | `AUD/USD` | 5 |
| Commodity | Gold / US Dollar | `XAU/USD` | 2 |
| Commodity | Silver / US Dollar | `XAG/USD` | 3 |
| Commodity | WTI Crude Oil | `WTI` | 2 |
| Commodity | Brent Crude Oil | `BRENT` | 2 |
| Commodity | Natural Gas | `NATGAS` | 3 |
| Commodity | Coffee / Cà phê | `COFFEE` | 2 |
| Commodity | Sugar / Đường | `SUGAR` | 2 |
| Commodity | Wheat / Lúa mì | `WHEAT` | 2 |
| Commodity | Corn / Ngô | `CORN` | 2 |
| Stock Index | S&P 500 | `SPX` | 2 |
| Stock Index | NASDAQ-100 | `NDX` | 2 |
| Stock Index | Dow Jones Industrial Average | `DJI` | 2 |
| US Stock | Apple | `AAPL` | 2 |
| US Stock | Tesla | `TSLA` | 2 |
| US Stock | NVIDIA | `NVDA` | 2 |
| US Stock | Microsoft | `MSFT` | 2 |
| Crypto | Bitcoin / US Dollar | `BTC/USD` | 2 |
| Crypto | Ethereum / US Dollar | `ETH/USD` | 2 |
| ETF | SPDR S&P 500 ETF Trust | `SPY` | 2 |
| ETF | Invesco QQQ Trust | `QQQ` | 2 |

## Chưa hỗ trợ

Các asset dưới đây nằm trong phạm vi mong muốn nhưng chưa được coi là coverage hiện tại.

| Nhóm | Asset | Canonical symbol đề xuất |
| --- | --- | --- |
| _Chưa có asset providerless trong catalog hiện tại_ |  |  |

## Ghi chú sản phẩm

- Các asset hàng hóa nông nghiệp như coffee, sugar, wheat và corn được gom vào nhóm `Commodity` để giữ taxonomy đơn giản cho người dùng.
- `Price display decimals` là số chữ số thập phân dùng khi render giá. Đây không phải tick size,
  order precision hoặc giới hạn precision của dữ liệu provider.
- MDG dùng `priceDisplayDecimals` để round `ROUND_HALF_UP` và pad giá public tại HTTP/WebSocket
  serialization boundary. Provider, domain, cache, candle aggregation và database vẫn giữ raw
  `Decimal`; candle volume không dùng price precision.
- Default provider hiện tại: Twelve Data cho `AAPL`, `BTC/USD`, `EUR/USD`, `QQQ`, `XAU/USD`;
  Binance Spot cho `ETH/USD`; YFINANCE cho 18 asset còn lại. Cả quote, candle và WebSocket của một
  asset luôn dùng cùng default provider và không fallback.
- Năm mapping YFINANCE bổ sung nhưng không active là `AAPL`, `BTC-USD`, `ETH-USD`, `EURUSD=X` và
  `QQQ`. `XAU/USD` chỉ dùng Twelve Data; không seed `GC=F` hoặc `XAUUSD=X`.
- Các mapping hàng hóa qua `YFINANCE` là futures hoặc rolling-futures proxy; riêng `XAG/USD` dùng provider symbol `SI=F`, không phải spot silver trực tiếp.
- Quote YFINANCE dùng `regularMarketPrice`; `receivedAt` là thời điểm gateway nhận snapshot, không phải provider trade time. Candle YFINANCE dùng yfinance `download`; missing/null volume được normalize thành decimal zero vì candle contract yêu cầu volume. WebSocket dùng một `AsyncWebSocket` lazy dùng chung, dựng candle từ price tick với volume zero; symbol đã subscribe nhưng chưa có tick giữ trạng thái `CONNECTING` và không fallback. Đơn vị giá futures được giữ theo Yahoo Finance vì public contract chưa có trường unit.
- Một asset chỉ nên được coi là "đang hỗ trợ" khi Signapse có thể nhận diện asset đó trong catalog, cho phép chọn vào watchlist và dùng nhất quán trong các surface phân tích liên quan.
- Canonical symbol là định danh sản phẩm, không nhất thiết luôn trùng với mã của mọi nhà cung cấp dữ liệu thị trường.
