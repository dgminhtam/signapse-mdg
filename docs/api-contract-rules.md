# Quy tắc sinh và bàn giao API contract bằng OpenAPI

## Phạm vi và nguồn chuẩn

Áp dụng khi thêm, sửa, review hoặc bàn giao HTTP API của MDG, kể cả thay đổi chỉ liên quan
đến schema/documentation. Đây là nguồn quy tắc kỹ thuật OpenAPI của repo; AGENTS và README
chỉ dẫn tới tài liệu này. Quy tắc dựa trên
[policy API xuyên repo của planning](https://github.com/signapse-group/signapse-planing/blob/main/workflow/project-execution-workflow.md#contract-api-và-handoff),
được cụ thể hóa cho FastAPI/Pydantic của MDG.

| Nguồn | Trách nhiệm |
| --- | --- |
| Requirement/issue được giao và [spec](spec.md) | Behavior được chấp nhận, domain semantics và thiết kế mục tiêu; không chứng minh đã deploy. Tracker theo [policy của repo](agents/issue-tracker.md). |
| `/openapi.json` của đúng producer environment | Contract kỹ thuật HTTP đã publish: operations, inputs, outputs và semantics cho consumer. `/docs` chỉ là giao diện đọc contract này. |
| Routes, API DTOs, parsers, serializers, handlers và tests | Sinh và kiểm chứng contract cùng implementation, ở cùng revision. |
| [WebSocket Stream Contract](spec.md#websocket-stream-contract) | Reference canonical cho `/v1/stream`, payloads, trạng thái và close codes; không giả lập thành HTTP operation trong OpenAPI. |

Thiết kế API trước khi implement, nhưng API đề xuất chưa publish không phải contract đã giao.
Khi requirement, runtime và generated schema mâu thuẫn, ghi rõ discrepancy và owner xử lý;
không sửa mô tả để hợp thức hóa behavior sai. Thiếu contract cần thiết chặn phần integration
phụ thuộc. Không dùng spec, mapping ledger hoặc comment để âm thầm bù thành một schema HTTP
cuối cùng song song. Giữ spec đồng bộ về behavior/rationale; không chép toàn bộ generated schema
vào Markdown. Các khoảng trống hiện có được ghi cuối tài liệu, không được xem là ngoại lệ lâu dài.

## 1. Sinh từ application và giữ nguyên behavior

- Dùng `create_app()` trong [app/main.py](../app/main.py), routes và Pydantic API DTOs hiện có
  làm nguồn sinh. Không viết tay một file OpenAPI độc lập làm nguồn chuẩn thứ hai.
- Dùng `response_model`, metadata của route, `Field`, `Query`, `Path`, `Header` và `responses`
  ở nơi phù hợp. DTO công khai thuộc `app/api/`; không expose DB entity hoặc SDK model.
- Routes hiện đọc query qua `Request.query_params` để dùng parser nghiệp vụ. Các tham số này
  không tự xuất hiện trong OpenAPI: khai báo metadata tại operation, dùng `openapi_extra`
  khi cần giữ nguyên parser. Chuyển sang binding tự động chỉ khi bảo toàn behavior đã chấp nhận.
  Không đổi lỗi `400` thành `422`, cách trim, xử lý empty/repeated query hoặc thứ tự validation
  chỉ để Swagger hiển thị được tham số.
- Ưu tiên metadata tại route/model; chỉ custom generation dùng chung khi cơ chế có sẵn không
  biểu diễn đúng output. Customization phải xác định rõ operations/schemas bị ảnh hưởng,
  giữ `$ref` hợp lệ và không rewrite mọi nullable field theo một quy tắc toàn cục.
- Không sửa artifact đã export. Nếu cần snapshot cho review/tooling, sinh lại từ application
  cùng revision, ghi nguồn/config, và coi snapshot là evidence có thể tái tạo.
- Giữ `operationId` duy nhất và ổn định cho operation không đổi. Không đổi dialect/version
  chỉ để qua validator; xác minh output và consumer khi nâng FastAPI/Pydantic.

[FastAPI hỗ trợ mở rộng operation bằng `openapi_extra`](https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/).
Metadata chỉ mô tả contract; parser/validator/serializer vẫn phải thực thi đúng behavior.

## 2. Inputs và validation

Mỗi operation phải khai báo đúng method/path, summary, description, tags và mọi input công khai:
tên trên wire, vị trí, requiredness, type/format, enum/limits/default khi áp dụng và ví dụ hợp lệ.

- Dùng tên API thực tế: `from`, `receivedAt`, `priceDisplayDecimals`, không lấy tên Python như
  `from_` hay `received_at` làm tên wire. Kiểm tra alias trong generated output.
- Phân biệt missing, empty, whitespace, repeated parameter và invalid value. CSV như `symbols`
  phải mô tả delimiter, normalization, duplicate handling và ordering theo parser; không khai
  báo thành repeated array nếu runtime không nhận encoding đó.
- `required: true` chỉ dùng khi tham số luôn bắt buộc. Điều kiện giữa các query parameters
  độc lập phải mô tả tại operation và kiểm chứng parser; không biến điều kiện theo mode thành
  bắt buộc vô điều kiện. Với object request mà JSON Schema biểu diễn được quan hệ, dùng schema
  có cấu trúc thay vì chỉ prose.
- Schema phải có các constraints biểu diễn được như enum, min/max, pattern, length và item limits.
  Không suy mọi giá trị provider hỗ trợ thành public support của MDG.
- Default cố định và default động phải phân biệt. Ví dụ `to` bị bỏ được resolve bằng request-time
  UTC, không ghi một timestamp mẫu thành `default`. Limit theo Settings phải khớp cấu hình hiệu lực;
  nếu schema không thể hiện được giá trị theo deployment, mô tả rõ và ghi gap thay vì hứa sai.

## 3. Required, nullable, omission và JSON response

`required` nói key có phải xuất hiện; nullable nói giá trị có thể là JSON `null`. Hai trục độc lập,
áp dụng cho cả request và response. OpenAPI 3.1 phải dùng schema chấp nhận `null` như `anyOf`
hoặc type union; không chỉ thêm keyword `nullable` của OpenAPI 3.0.

| Wire contract | Schema | Ghi chú Pydantic v2 |
| --- | --- | --- |
| Required, non-nullable | Có trong `required`, không chấp nhận `null` | `value: str` không default. |
| Required, nullable | Có trong `required`, chấp nhận giá trị hoặc `null` | `value: str \| None` không default. |
| Optional, nullable | Không trong `required`, chấp nhận giá trị hoặc `null` | `value: str \| None = None` cho input; response còn phụ thuộc serializer. |
| Optional, non-nullable | Không trong `required`, không chấp nhận `null` | Input có thể dùng default hợp lệ nếu đúng semantics; output bỏ key có điều kiện cần kiểm chứng serializer và schema riêng. Không gán default `None` cho `str` để lách validation. |

Đọc [Pydantic fields](https://docs.pydantic.dev/latest/concepts/fields/) và
[JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/) khi chọn khai báo.
Input schema không tự chứng minh output schema: defaults, serialization mode và alias có thể khác.

- Kiểm tra `response_model_exclude_none`, `exclude_unset`, `exclude_defaults`, serializers và
  `JSONResponse` trực tiếp. Các cờ loại key không tự bảo đảm schema mô tả đúng omission/nullability.
- Ví dụ hiện có: economic calendar có `currency: str | None` và luôn serialize key; đây là required,
  nullable. `/v1/symbols` bỏ `providerMappings` khi không có mappings; response schema cần mô tả
  việc bỏ key và kiểu giá trị thực sự phát ra, không suy từ annotation nội bộ.
- Price/OHLC/volume trên wire là string, không phải JSON number; tái sử dụng
  [serialization](../app/api/serialization.py). Mô tả precision/rounding của price theo symbol;
  không áp dụng price rounding sang volume. Không chuyển qua `float` để tạo examples.
- Timestamp UTC phải mô tả `string`/`date-time` khi đúng runtime, cùng timezone và ý nghĩa mốc thời gian.
  DTO dùng `str` sẽ không tự có `format: date-time`; bổ sung metadata và kiểm chứng serializer.
- Chỉ khai báo `additionalProperties: false`, enum và bounds khi runtime thực sự bảo đảm điều đó.
  Mỗi example phải đúng schema, required keys, nullability và semantics của operation.

## 4. Status, errors, headers và security

- Khai báo success và các error responses thực tế qua `responses`, gồm body model, media type,
  description, headers và examples cần thiết. Exception handler hoặc nhánh trả `JSONResponse`
  không tự làm OpenAPI biết status/body tương ứng.
- Tái sử dụng [ErrorResponse](../app/api/errors.py) cho các lỗi dùng envelope `error`;
  giữ `code`, `message`, `details` đúng serialization. Không ép mọi lỗi vào một schema:
  `/ready` trả `ReadyResponse` với `503`, khác lỗi database của endpoint dữ liệu.
- Phân biệt request failure với partial success. `/v1/quotes` có `quotes` và `errors` theo symbol
  trong HTTP `200`; không biến toàn bộ per-symbol errors thành HTTP `503` trong tài liệu.
- Ghi đúng HTTP status và machine code theo route/parser/handler, gồm `400`, `404`, `503`, `500`
  khi áp dụng. Không thêm `422` mặc định cho custom parser, cũng không xóa `422` khỏi schema nếu
  operation thực tế vẫn phát validation response đó. Không hứa retry/idempotency ngoài behavior đã chốt.
- Mô tả `X-Request-ID` theo [middleware](../app/core/observability.py), gồm input tùy chọn,
  cách nhận/thay giá trị và response header. Không dùng `requestId` trong body nếu runtime không có.
- Security metadata phải phản ánh cơ chế được thực thi. MDG hiện không có client authentication;
  private-network deployment không phải bearer scheme. Không sao chép JWT/permissions của BE.
  Không đưa upstream API key, provider exception hoặc dữ liệu thật nhạy cảm vào schema/examples.

Khai báo additional responses theo
[FastAPI responses](https://fastapi.tiangolo.com/advanced/additional-responses/); khai báo không thay
việc kiểm chứng JSON thực tế, nhất là các nhánh đi qua handler hoặc trả response trực tiếp.

## 5. Business semantics và WebSocket

Description giải thích điều consumer cần để dùng API đúng, không sao chép toàn bộ implementation.
Với phần API bị thay đổi, đối chiếu các semantics liên quan trong [spec](spec.md):

| Operation | Những semantics phải rõ khi áp dụng |
| --- | --- |
| `/v1/symbols` | Canonical symbol, Default Provider/Provider Mappings, enabled scope, display precision và conditional fields. |
| `/v1/quotes` | Symbol parsing/order, freshness, partial errors, Provider Override và không tự fallback. |
| `/v1/candles` | Các mode range/`limit`/`count`; slots khác actual rows; `[from,to)`; default request time; mutual exclusions; ordering; forming/complete; gaps và partial result; giá trị volume placeholder. |
| `/v1/historical-price` | Ý nghĩa `at`, cách chọn giá/resolution, `pricedAt`, giới hạn tìm kiếm và `PRICE_NOT_FOUND`. |
| `/v1/economic-calendar` | Range, filters, limit/order, timezone, nullable fields và empty result. |
| `/health`, `/ready` | Liveness khác readiness, status/body khi dependency không sẵn sàng; không suy health Pass thành provider/API readiness. |

Các bảng này là checklist nội dung, không tạo thêm field, constraint hoặc behavior mới.
Không đưa cấu hình scan budget/internal provider metadata thành public field khi chưa được chấp nhận.

`/v1/stream` không nằm trong HTTP OpenAPI generated hiện tại. Cập nhật reference WebSocket trong
spec cùng implementation/tests khi thay stream; handoff dẫn đúng revision của reference đó.
Mô tả subscription query, quote/status payloads, ordering/lifecycle, stale/reconnect và close codes
thực tế. Không thêm HTTP GET giả hoặc mặc định có candle events. Nếu sau này có SSE, mô tả media
type, event/payload và semantics tại HTTP operation tương ứng.

## 6. Verification trước review

1. Inventory routes, inputs, DTOs, serializers, handlers, Settings và consumers bị ảnh hưởng.
   Đối chiếu requirement đã chấp nhận; giữ thay đổi ngoài scope thành finding riêng.
2. Sinh schema từ application mới cùng revision; đọc `/openapi.json` qua ASGI HTTP boundary.
   Kiểm tra dialect, operation IDs duy nhất, references resolve được, schema/examples hợp lệ,
   parameters, media types, status/headers/security và descriptions của phần thay đổi.
3. Đối chiếu HTTP JSON/status/headers thực tế với schema. Khi sửa nullable/required/omission,
   kiểm tra key thiếu, `null`, giá trị hợp lệ/không hợp lệ và output có/bỏ key như contract.
   Với raw query parser, giữ regression cho missing/empty/repeated/invalid và `400` so với `422`.
4. Tái sử dụng route tests trong `tests/unit/test_*_api.py` và HTTPX ASGITransport. Chỉ test schema
   có thể tạo app không chạy lifespan; không cần kết nối provider hoặc DB. Behavior test phải đi
   qua parser/serializer/handler đang sửa; mock service không chứng minh logic bên trong service.
   Nếu behavior phụ thuộc persistence, dùng integration tests với test database riêng.
5. Chạy focused tests phù hợp, rồi các [Development Checks](../README.md#development-checks)
   khi sửa code/config/runtime. Ghi rõ integration tests bị skip do thiếu `TEST_DATABASE_URL`.
   Khi sửa generation dùng chung, kiểm tra cả schemas/operations khác chịu ảnh hưởng.

Chỉ sửa văn bản rule/docs: kiểm tra nội dung, links và formatting; không mặc định thêm test suite,
dependency, Postman collection, CI job hoặc QA task mới. Sửa metadata sinh contract trong Python
vẫn cần kiểm tra generated output và checks phù hợp; không gọi đó là Markdown-only để bỏ verification.
Thay runtime/bug cần regression behavior tương ứng, không chỉ snapshot schema.

## 7. Review local, publication và consumer handoff

- **Local review:** generated OpenAPI cùng revision + checks đủ cho review producer. Không yêu cầu
  revision đó đã deploy trước review; ghi rõ publication còn pending.
- **Live delivery:** sau deploy trong scope được giao, fetch mới `/openapi.json` đúng environment,
  đối chiếu phần contract thay đổi và chứng minh build đang chạy chứa contribution đã review.
  Ghi URL, thời điểm/kết quả fetch, producer revision và deployment/build evidence.
- `info.version` hiện là version ứng dụng, không chứng minh commit đang deploy. Nếu chưa có
  `x-build-revision`, dùng deployment/image evidence truy được tới source revision; không tự
  ghi HEAD local thành deployed revision. Không có bằng chứng thì publication chưa xác minh.
- **Consumer:** đọc contract live đúng environment trước khi chốt integration API đã có. Đánh dấu
  breaking change, operations/schemas đổi, consumer bị ảnh hưởng, dependency và integration còn chờ.
  Breaking change MDG phải có kế hoạch rollout được chấp nhận; không tự áp dụng ngoại lệ chấp nhận
  FE lỗi tạm trên dev của BE sang MDG hoặc production. Không giữ compatibility path trừ khi scope yêu cầu.
- Handoff giữ references và kết quả, không sao chép schema. Evidence local, deploy success hoặc
  health Pass không thay consumer integration/QA acceptance. Thiếu evidence chỉ chặn kết luận tương ứng.

Thông tin tối thiểu để bàn giao API:

```text
Output: MDG · revision · local review hoặc live delivery.
Contract: generated artifact hoặc URL môi trường · thời điểm/kết quả kiểm tra.
Verification: checks đã chạy · evidence nối source với build nếu bàn giao live.
Impact: breaking changes · consumers/dependencies · integration hoặc publication còn chờ.
```

## Hiện trạng khảo sát ngày 2026-10-15

Đã đọc working tree trên base `7b6d1fd` và gọi `/openapi.json` qua HTTPX ASGITransport, không chạy
lifespan, DB, provider hoặc live deployment. Repo có thay đổi local từ trước ở tài liệu và việc
loại OpenSpec; khảo sát dùng nội dung working tree, không xem base SHA là toàn bộ state đó.

- Output là OpenAPI `3.1.0`, 7 HTTP GET operations. Cả 7 chỉ khai báo response `200`, chưa có
  operation description hoặc parameters; các route dữ liệu đọc query trực tiếp từ `Request`.
- Custom errors trong `app/api/errors.py` và `503` của `/ready` chưa được khai báo trong output.
  `CandleResponse.openTime` đang là string chưa có `date-time`.
- `SymbolResponse.providerMappings` đang cho phép `null` trong schema, trong khi route loại key
  có giá trị `None`. Đây là gap cần kiểm tra/chỉnh ở contribution triển khai contract.
- Chưa có `x-build-revision`; không thấy test đọc OpenAPI trong cây tests hiện tại.
  `/v1/stream` không xuất hiện trong HTTP paths, phù hợp việc dùng reference WebSocket riêng.

Các findings này là baseline để triển khai tiếp, không phải xác nhận API đã tuân thủ bộ rule.
Đợt viết rule không sửa runtime, generator hoặc quy trình tracker/deployment.

## Hoàn thiện local sau khảo sát

Đã bổ sung metadata cho cả 7 HTTP operations, query parameters, status/error bodies, examples,
X-Request-ID, timestamp formats, decimal strings và omission/nullability. Giới hạn theo Settings
được áp dụng khi sinh contract; SOURCE_REVISION cung cấp x-build-revision, mặc định unknown.
Các findings ở mục khảo sát là baseline trước thay đổi, không còn mô tả output local hiện tại.
Tests đọc /openapi.json qua ASGI và kiểm tra metadata cùng các route regression hiện có.
Publication, deployed revision và consumer integration vẫn cần evidence riêng sau deploy.
