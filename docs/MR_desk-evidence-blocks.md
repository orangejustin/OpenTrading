# MR — `desk/evidence-blocks-and-calibration`

**Status: ready for review. Not pushed.** `main` advances only when you say so.

Twelve commits. The through-line: the desk had the data it needed and was
misreading it, and it had no idea how it was doing.

---

## The two defects that motivated everything else

**1. The debate counted one signal four times.** `ot decide`, `ot quant`,
`ot forecast`, trend and 5-day momentum are all transforms of the same daily
close series, and the pack rendered them as five peer bullets. Four restatements
of one signal read as four confirmations. Meanwhile dealer gamma, Fear&Greed
with breadth, the event calendar and tape-wide news — all tools the desk already
owned — were never shown to the LLMs at all.

The pack is now grouped `[0]` and `[A]`–`[G]` **by information source**, with the
rule stated in the pack itself: agreement inside a block is not corroboration.
The judge must declare `blocks_supporting`, and a single-block verdict is capped
at 50 confidence.

**2. The calibration panel had been frozen at n=1 for a month.** Root cause was
not subtle: `grade()` had no caller anywhere — not in the launchd job, not in
CI, not in the web handler. It ran once on 2026-06-18 and never again while 843
journaled calls piled up ungraded.

Wiring it into the daily mailer exposed three scoring bugs, all of which
flattered the desk:

| bug | effect |
|---|---|
| `return_pct` recorded the **underlying's** move | a profitable PUT logged as −10% and averaged against longs of the same sign |
| graded against the **latest** close | a June call got a 6-week window, a Monday call got 5 days, averaged together — which manufactures skill in a trending tape |
| benchmark cache keyed by symbol alone | every entry after the first reused the **first** entry's benchmark window |

**Before the fix the desk reported PUT at 77% and looked skilled. After: 654
calls, 50.0% hit, −0.5% alpha. A coin flip with negative alpha.** That number is
the most important output on this branch — it is why nothing here goes near live
money.

---

## What shipped

| command | what it does |
|---|---|
| `ot reflect` | fixed scoring; auto-grades in the 08:30 mailer; staleness now visible |
| `ot debate` | source-blocked evidence, playbook output, per-role effort, level grounding, measured divergences |
| `ot propose` / `risk` / `approve` | staged proposals, 8 gates, audit ledger, human-only approval |
| `ot decay` | prices daily-reset drag instead of warning about leverage |
| `ot auto` | chains the desk end to end and **stops** at the human step |
| `ot paper` | forward broker + the gate a live adapter must pass |
| `ot conc` | the book by complex; leads the morning note |
| `ot tv` | live TradingView chart over CDP, stdlib only |

### Three findings worth more than the code

**RAM decays ~10× faster than TQQQ despite carrying less leverage.** Drag goes
as the underlying's *variance*, and DRAM runs 103% annualised against QQQ's 19%:

    TQQQ  3x on QQQ  (1.19%/day)  ->  -0.042%/day
    RAM   2x on DRAM (6.51%/day)  ->  -0.424%/day

The multiple is the weak term. "2× is safer than 3×" is wrong.

**The book is 5 bets, not 8.** Grouped by complex: spacex 37.1% (SPCX + LOFF,
stacked), nasdaq 11.2% of capital but **33.6% of market risk** through TQQQ(3×),
memory 10.8% (DRAM + RAM, stacked). Total effective exposure **114.2% of book** —
leverage carries more market risk than there is capital.

**The TradingView OM crossover signals have no edge.** Measured on QQQ/SPY,
5m×60d and 1m×7d, entering at the next bar's open: ~50% win, negative average
return, and **below the base rate at every horizon**. A trend filter and a
news-coincidence filter both fail to rescue it. It is a price transform — the
same information source as block `[A]`, which is already the most over-counted
block.

---

## Safety posture

Automated execution is wired to **paper only**. `ot approve` requires a human
`--yes` carrying the exact proposal id, and nothing in `ot auto` passes it.
`ot paper fill` refuses anything not `approved`, so the paper record measures the
real process including its human step.

`ot paper gate` is the single promotion authority: **n ≥ 30 closed, mean trade
alpha > 0, win rate ≥ 50%.** It refuses on an empty book and exits non-zero, so a
caller fails closed. Given the 654-call record above, the desk has not earned
live money and the gate says so in code rather than in a comment.

---

## Verification

- `tests/test_golden.py` — 8 existing tests pass, nothing regressed
- `tests/test_desk.py` — **18 new tests**, one per bug that actually shipped here
- the new tests were **mutation-tested**: reintroducing the loose grounding
  tolerance, the silent knife rule, and an unpaired RAM each made the
  corresponding test fail, so they detect rather than decorate
- `ot privacy-audit` clean; working tree clean; no `data/`, `.env` or watchlist
  content touched

## Known caveats

- **DRAM/RAM/TQQQ/LOFF share counts in `watchlist.json` are 300-share
  placeholders.** Concentration percentages are shape-correct, not
  dollar-correct, until you set real numbers. The *shape* holds regardless —
  LOFF is 2× on top of your largest position at any size.
- No IBKR adapter. TWS/Gateway was never reachable on 7497/4002 while this was
  built; the adapter is short work once it is.
- Block `[G]` needs TradingView Desktop running with `--remote-debugging-port`.
  It degrades to absent, never to an error.
