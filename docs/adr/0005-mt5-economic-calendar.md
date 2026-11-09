---
status: accepted for local implementation and verification
---

# Read economic calendar through a dedicated MQL5 Service

On 2026-11-04 the user authorized replacing the failing ForexFactory-based source
with MT5, completing integration and verification locally before reporting results.
The user explicitly accepted mapping MT5 macro releases to FOREX, preserving legacy
rows without duplicating new releases into METALS/ENERGY/CRYPTO, null fields absent
from MT5, original previous vs revised previous, and a separate MT5 identity namespace.

Run CalendarService alongside MarketDataService in the existing MT5/Wine terminal.
Each has its own authenticated TCP connection and request state. Calendar waits,
disconnects and deadlines must not close the quote connection or acquire its RPC lock.
No Python helper, Go sidecar, extra terminal, or new public refresh endpoint is added.

The official Python package does not expose native calendar functions. Extend the
existing direct MQL5 exception: native CalendarValueHistory and event/country metadata
are read through the Service, with seven-day bounded RPCs and validated row totals.
The existing nine-day refresh stages all responses before one repository upsert;
timeout, bad metadata, duplicates or partial frames fail without persisting a partial window.

Public shape is retained. MT5 occurrence ID becomes external_event_id `mt5:<valueId>`;
public key is `FOREX:mt5:<valueId>`. Existing provider IDs/rows are retained and never
automatically matched or merged. `previous` is the original previous number;
`revision` is revised previous, not MT5's revision counter. Values preserve native
digits and K/M/B/T multipliers, with `%` for percentage units. Missing numbers are
null, not zero. MT5 importance maps NONE/LOW/MODERATE/HIGH to null/LOW/MEDIUM/HIGH.
Description, newsUrl and both better/worse assessments are null for new MT5 rows.
source_url is not substituted for an article URL. No scraping/enrichment fallback remains.

The local DST-crossing PoC showed calendar records using the current validated
session offset, unlike historical bar time conversion. Validate broker/UTC clocks
on connection and every response; reject offset changes during a request. This
separate conversion must not alter quote/candle clocks. Behavior at a future DST
transition still requires verification; no historical rebuild is authorized here.

Sources: [native calendar](https://www.mql5.com/en/docs/calendar),
[Python API](https://www.mql5.com/en/docs/python_metatrader5),
[Service threads](https://www.mql5.com/en/docs/runtime/running),
[calendar structures](https://www.mql5.com/en/docs/constants/structures/mqlcalendar),
[local split-Service evidence](../mt5-split-calendar-poc.md).

This decision authorizes no dev/server deployment or production data migration.
