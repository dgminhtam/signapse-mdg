## Context

MDG currently preserves normalized provider `Decimal` scale through every public HTTP and
WebSocket price field. Signapse is the service's internal consumer, and its streaming use case is
primarily presentation. Requiring each consumer to load `/v1/symbols` and reproduce formatting
policy makes the client contract harder to use and risks inconsistent prices between initial HTTP
snapshots and subsequent WebSocket updates.

The symbol registry already supplies a required `price_display_decimals` value. The current
serializer uses `format(value, "f")`, while the quote, candle, and stream domain objects and caches
must retain raw normalized values.

## Goals / Non-Goals

**Goals:**

- Return price strings already rounded and padded for direct Signapse display.
- Apply one deterministic policy across latest quotes, historical prices, historical candle OHLC,
  and WebSocket quote/candle OHLC.
- Preserve raw provider-normalized `Decimal` values until the final API serialization boundary.
- Keep existing JSON field sets and candle volume behavior unchanged.

**Non-Goals:**

- Quantizing provider results, cached quotes, candle aggregation, persisted candles, or domain
  models.
- Defining provider tick size, order precision, volume precision, locale, separators, or currency
  symbols.
- Adding display metadata events or repeating `priceDisplayDecimals` in market-data payloads.
- Supporting separate raw and formatted variants of the same endpoint.

## Decisions

### Format only at the public serialization boundary

Add a small price formatter beside the existing decimal serializer. It accepts a raw `Decimal` and
the persisted display-decimal count, rounds with `ROUND_HALF_UP`, and returns fixed-point text with
exactly that many fractional digits.

Provider adapters, services, caches, candle calculation, and persistence continue to use the
unchanged raw value. Formatting earlier was rejected because rounded ticks could corrupt candle
highs/lows, cache reuse, and persisted history.

### Apply one policy to HTTP and WebSocket prices

Latest quote `price`, historical `price`, historical candle OHLC, WebSocket quote `price`, and
WebSocket candle OHLC use the same formatter. Candle `volume` continues through the raw fixed-point
serializer because price precision has no meaning for volume.

Formatting only WebSocket values was rejected because Signapse can load an HTTP snapshot before
receiving stream updates; different precision across those transports would create visible value
changes unrelated to the market.

### Carry precision as result and registration context

Services that already resolve the supported-symbol registry carry the selected
`price_display_decimals` alongside their result context. Individual `Quote` and `Candle` domain
values remain unchanged. WebSocket client registration retains the precision map already available
from its resolved symbol list, and the sender supplies it to event serialization.

Adding display precision to every provider event or cached market-data object was rejected because
it couples raw data to presentation policy and duplicates static metadata.

### Preserve response shapes

Existing price fields change value semantics but no new fields or event types are added. Consumers
can render the returned strings directly and do not need a `/symbols` lookup solely for price text.
`/symbols` remains the registry discovery API and continues exposing `priceDisplayDecimals`.

## Risks / Trade-offs

- [Existing consumers expect raw precision] → Treat this as a breaking internal contract change
  and deploy compatible Signapse consumers with the MDG release.
- [Rounded public values cannot support higher-precision calculations] → Keep raw values inside
  MDG; introduce a separately specified raw-data contract only if a real downstream need appears.
- [Frontend converts strings to numbers and loses trailing zeros] → Direct text displays keep the
  string; numeric chart axes may still use `/symbols` metadata when explicit axis precision is
  required.
- [HTTP and WebSocket implementations drift] → Use one formatter and shared exact-value regression
  cases for both transports.

## Migration Plan

1. Deploy the existing symbol precision schema and ensure every retained registry row has an
   explicit value.
2. Deploy MDG with the shared formatter and all HTTP/WebSocket serializers updated together.
3. Deploy Signapse consumers that accept display-formatted price strings.
4. Roll back the MDG application if a consumer requires the previous raw transport values; no
   database rollback is needed.

## Open Questions

None.
