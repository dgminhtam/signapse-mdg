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

| Nhóm | Asset | Canonical symbol |
| --- | --- | --- |
| Forex | Euro / US Dollar | `EUR/USD` |
| Forex | British Pound / US Dollar | `GBP/USD` |
| Forex | US Dollar / Japanese Yen | `USD/JPY` |
| Forex | Australian Dollar / US Dollar | `AUD/USD` |
| Commodity | Gold / US Dollar | `XAU/USD` |
| Commodity | Silver / US Dollar | `XAG/USD` |
| Commodity | WTI Crude Oil | `WTI` |
| Commodity | Brent Crude Oil | `BRENT` |
| Stock Index | S&P 500 | `SPX` |
| Stock Index | NASDAQ-100 | `NDX` |
| Stock Index | Dow Jones Industrial Average | `DJI` |
| US Stock | Apple | `AAPL` |
| US Stock | Tesla | `TSLA` |
| US Stock | NVIDIA | `NVDA` |
| US Stock | Microsoft | `MSFT` |
| Crypto | Bitcoin / US Dollar | `BTC/USD` |
| Crypto | Ethereum / US Dollar | `ETH/USD` |
| ETF | SPDR S&P 500 ETF Trust | `SPY` |
| ETF | Invesco QQQ Trust | `QQQ` |

## Chưa hỗ trợ

Các asset dưới đây nằm trong phạm vi mong muốn nhưng chưa được coi là coverage hiện tại.

| Nhóm | Asset | Canonical symbol đề xuất |
| --- | --- | --- |
| Commodity | Natural Gas | `NATGAS` |
| Commodity | Coffee / Cà phê | `COFFEE` |
| Commodity | Sugar / Đường | `SUGAR` |
| Commodity | Wheat / Lúa mì | `WHEAT` |
| Commodity | Corn / Ngô | `CORN` |

## Ghi chú sản phẩm

- Các asset hàng hóa nông nghiệp như coffee, sugar, wheat và corn được gom vào nhóm `Commodity` để giữ taxonomy đơn giản cho người dùng.
- Một asset chỉ nên được coi là "đang hỗ trợ" khi Signapse có thể nhận diện asset đó trong catalog, cho phép chọn vào watchlist và dùng nhất quán trong các surface phân tích liên quan.
- Canonical symbol là định danh sản phẩm, không nhất thiết luôn trùng với mã của mọi nhà cung cấp dữ liệu thị trường.
