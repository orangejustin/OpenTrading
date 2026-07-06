---
title: Methodology
sidebar_position: 7
---

# Methodology

How the desk grades itself and where a couple of numbers come from that surprise
people. The full reference lives in the repo:
[**docs/METHODOLOGY.md**](https://github.com/orangejustin/OpenTrading/blob/main/docs/METHODOLOGY.md).

## Calibration — when is a call graded?

```bash
ot reflect grade --days 5
```

A call is graded once it is **≥ N sessions old** (default **N = 5**, matching the
debate's 5-day swing horizon). A verdict made Monday is first gradeable the
following Monday. Grading is **idempotent** — a call is scored once, then carries
its outcome forever.

## Is the CALL/PUT for day 0 or day +1?

It depends on the horizon the call was *made* at, carried on every row as
`time_stop_days`:

- **0DTE** (`ot decide --dte 0`) — a *same-day* call, graded on the day's move.
- **Swing** (`--dte 5`, the debate default) — entered from the *next* session and
  graded at ≥5 sessions.

The desk never mixes the two: each row is graded on its own horizon. "Time stop"
is the point at which being flat-but-right becomes wrong.

## Two honesty rules

1. **Seed rows are excluded.** The journal ships with a few bootstrap examples
   (`source: "seed"`) so the desk isn't empty on day one — they never count toward
   the track record or the lessons.
2. **It grades the desk, not your P&L.** The table is the desk's *own* call
   history (debate + engine reads), currently **global — not split by book or
   account**. An "A-share" row is a China name the desk read, not anyone's
   realized trade.

Calibration-weighted fusion — where the judge trusts a proven analyst more —
waits for **~30 real graded calls** before it kicks in. Until then, single-digit
cells are anecdotes, not statistics.

## Dealer gamma — why two "call walls"?

The same name can show two call walls because they're computed over **different
DTE windows**:

| Where | Window | Question it answers |
|---|---|---|
| Macro & Flow card | ≤ 7 DTE | this week's pin risk |
| Ticker ladder / chart | ≤ 30 DTE | the swing-horizon wall |

Both are correct — they're answering different questions. The chart labels its
walls `≤30D` so it's unambiguous.

## Retention

The decision journal is **append-only** and kept (the outcome is what changes).
The news archive under `data/news-log/` is what ages out — not the journal.
