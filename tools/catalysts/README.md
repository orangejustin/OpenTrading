# catalysts — keyless market-catalyst calendar + event gate

The **event gate is Step 0** of the OpenTrading workflow: before any setup or size,
know what's on the calendar. A great name into a known high-impact print = smaller
size, or wait. This tool aggregates the catalysts that actually move the tape — with
**no API key** — and prints an explicit gate verdict.

```bash
ot catalysts                 # next 14 days + event-gate verdict
ot catalysts --days 45       # look further out (catch the next FOMC / quad-witching)
ot catalysts --gate-days 2   # gate fires only for high-impact events <= 2 days out
ot catalysts --format json   # machine-readable (for the skill / email pipeline)
ot catalysts --from 2026-09-10   # anchor to a date other than today
```

## What it tracks

| Catalyst | Source | Accuracy |
|---|---|---|
| **FOMC decisions** (+ SEP / dot plot on Mar/Jun/Sep/Dec) | curated `calendar.json` from [federalreserve.gov](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) | **confirmed** |
| **Quad-witching** (3rd Fri Mar/Jun/Sep/Dec) & **monthly OPEX** (3rd Fri) | computed | **exact** |
| **Quarter-end rebalance** (last business day Mar/Jun/Sep/Dec) | computed | **exact** |
| **CPI / PCE / Jobs (NFP)** | rule-estimated, flagged `·est` | **approximate — verify** |

Confirmed dates always win over estimates: a confirmed print in `calendar.json` suppresses
the same-kind estimate for that month. To upgrade an `·est` print to confirmed, paste the
official date into `calendar.json`'s `fixed` list (CPI/NFP → [bls.gov/schedule](https://www.bls.gov/schedule/news_release/cpi.htm),
PCE → [bea.gov/news/schedule](https://www.bea.gov/news/schedule)).

## The gate verdict

If a **high-tier** event falls within `--gate-days` (default 3), the tool prints:

```
  ⚠️  EVENT GATE: FOMC decision in 2 days (Wed Jul 29)
      → trim size / no fresh risk into the print; this is Step 0.
```

Otherwise it confirms the gate is clear. Born from the **6/17 FOMC miss** — the whole point
is to never get caught sizing into a known print again.

> **Why estimates at all?** FOMC and OPEX are the biggest gate events and are exact here.
> CPI/PCE/NFP vary by a day or two (holidays, BLS/BEA scheduling), so the rule-based dates are
> flagged `·est` — the **warning** ("a CPI is due ~mid-July") is the value; verify the exact day
> before sizing. Honest scope: this is a calendar, not a data feed.

Stdlib only. Educational, not financial advice.
