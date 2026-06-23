---
name: catalyst-calendar
description: >
  The event gate — Step 0 of every trading decision. Use this skill whenever the user asks about
  upcoming market catalysts, the economic calendar, "what's on the calendar", FOMC / Fed meeting
  dates, CPI / PCE / inflation prints, jobs / NFP, OPEX / quad-witching / triple-witching, quarter-end
  rebalancing, or "is it safe to size up before X", or whenever you are about to recommend a NEW
  position or add size and need to check whether a known high-impact print is imminent. Powered by the
  keyless `ot catalysts` command — confirmed FOMC/OPEX dates plus rule-estimated CPI/PCE/NFP, with an
  explicit gate verdict. Educational only — not financial advice.
---

# Catalyst calendar — the event gate (Step 0)

**The rule:** before any setup or size, check the calendar. A great name into a known high-impact
print = **smaller size, or wait.** This gate exists because of the 6/17 FOMC miss — never size
blind into a known print again.

## How to run it

```bash
ot catalysts                 # next 14 days + an explicit gate verdict (default)
ot catalysts --days 45       # look out far enough to see the next FOMC / quad-witching
ot catalysts --gate-days 2   # only warn for high-impact events within 2 days
ot catalysts --format json   # structured — fold into the pre-market email / decision pipeline
```

## How to use the verdict

1. **Run `ot catalysts` first** — before quoting buy zones, recommending an add, or sizing up.
2. **If the gate is ⚠️ (a high-tier event within the window):** explicitly down-shift — "trim size /
   wait until after the print / no fresh risk into it." Name the event and its date in your answer.
3. **If the gate is ✅ clear:** proceed with normal sizing, but still mention the next catalyst on
   the horizon so the user is never surprised.
4. **Respect the `·est` flag:** FOMC and OPEX/quad-witching are exact. CPI/PCE/NFP are
   rule-estimated (they drift a day or two for holidays/scheduling) — treat them as a *window*
   ("CPI due ~mid-July"), and say "verify the exact day" before sizing into one.

## Tiers

- **HIGH** — FOMC, CPI, PCE, Jobs/NFP, quad-witching. These move the whole tape → the gate fires on these.
- **MED** — monthly OPEX, quarter-end rebalance. Flow/technical; size-aware, not a hard stop.

## Where the dates live

- **Confirmed** dates: `tools/catalysts/calendar.json` (`fixed` list) — curated FOMC from
  federalreserve.gov, plus any data prints you've pinned. A confirmed entry suppresses the
  same-kind estimate for that month.
- **Computed** dates: OPEX/quad-witching (3rd Friday), quarter-end (last business day of the quarter).
- **To upgrade an estimate to confirmed:** paste the official date into `calendar.json` from
  bls.gov/schedule (CPI/NFP) or bea.gov/news/schedule (PCE).

## Fold it into the workflow

- **Pre-market email / strategy:** lead the risk section with the event gate — "PCE + quarter-end
  this week (6/30); next FOMC 7/29." It frames whether to lean in or hold back.
- **`ot decide` / `stock-picker` Stage 6:** the final macro/event gate before a buy-now call should
  cite `ot catalysts` — if the entry sits right before a HIGH print, it's a "wait", not a "buy now".

This skill complements [the short-term-trader skill](../short-term-trader/SKILL.md) (which owns the
macro-first / risk-first workflow) and the stock-picker funnel (whose final gate this hardens).
Educational only — not financial advice.
