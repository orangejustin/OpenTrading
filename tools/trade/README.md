# `ot propose` / `ot risk` / `ot approve` — staged trades with a risk gate

The execution half of the desk, shaped so an **agent can drive it end to end
without being able to move money**.

Three verbs, three states, one human step that no automation may perform:

```
ot propose TICKER --side CALL|PUT|LONG|SHORT --entry P --stop P [...]   -> staged
ot risk    ID                                                          -> passed | blocked
ot approve ID --yes                            HUMAN ONLY              -> approved
```

`approved` is a **terminal state**, not an order. OpenTrading has no execution
adapter wired, and the approve verb refuses to run without an explicit `--yes`
carrying the exact proposal id. If a future broker adapter is added, it may
consume only `approved` proposals — never `staged` or `passed` ones.

## Why this shape

Borrowed from the field study (`REPO_STUDY.md`): QuantDinger's paper-only
default and scoped agent tokens, MMR's `propose → risk → approve` object flow,
OpenAlice's "stage, review, then commit" account operations. The common lesson
across all three is that the LLM belongs on the *proposal* side of the gate,
never on the execution side.

## The gates

| Gate | Blocks? | What it checks |
|---|---|---|
| **G1 invalidation** | yes | A stop exists and sits on the *losing* side of entry. A proposal without an invalidation cannot be sized, so it cannot be a proposal. |
| **G2 risk budget** | yes | `size × |entry−stop| / entry` as a share of the account, against `--max-loss-pct` (default 2%). Budget comes from `--budget` or `cash` in the watchlist. |
| **G3 reward** | warn | R:R ≥ 1 when a target is given. Non-blocking — a scalp can be sub-1R on purpose. |
| **G4 leverage** | yes | Daily-reset multiple + *complex* membership. Stacking a levered vehicle on an existing position in the same complex is **blocked**: 2× on top of a concentrated single-name book is one risk at higher leverage, not two positions. |
| **G5 event clock** | yes | A Tier-1 print (`ot catalysts`) inside the horizon blocks initiation. |
| **G6 0DTE liquidity** | yes | Only for `--dte 0`. After an expiry the chain returns all-nulls, which reads like a clean quote rather than "there is no chain" — this catches it. |
| **G7 calibration** | warn | Surfaces `ot reflect`'s hit-rate for this direction. Arguing against your own base rate beats arguing against nothing. |

### The complex map

`LEVERAGED` in `propose.py` is hand-curated, because no vendor dataset carries
it — FinanceDatabase has no holdings column at all and does not even list
LOFF / DRAM / RAM. Each entry is `(daily-reset multiple, complex)`; instruments
sharing a complex are **one bet**:

```python
"LOFF": (2.0, "spacex"),   "SPCX": (1.0, "spacex"),
"RAM":  (2.0, "memory"),   "DRAM": (1.0, "memory"),  "MU": (1.0, "memory"),
"TQQQ": (3.0, "nasdaq"),   "SQQQ": (-3.0, "nasdaq"), "QQQ": (1.0, "nasdaq"),
```

Add to it as the book grows — this table is the gate's whole intelligence.

## Files

Both git-ignored, under `data/`:

- `data/proposals/<id>.json` — the proposal plus its gate results
- `data/audit/proposals.jsonl` — append-only; every state change, never rewritten

## Example

```
$ ot propose LOFF --side LONG --entry 13.01 --stop 11.50 --size 8000 --budget 100000 --dte 5
staged LOFF-2026-07-18-1  (LONG LOFF @ 13.01, stop 11.5)

$ ot risk LOFF-2026-07-18-1
  ✓ G1 invalidation    stop 11.5 is 11.6% from entry 13.01
  ✓ G2 risk budget     max loss $929 = 0.93% of $100,000 (limit 2.0%)
  ✗ G4 leverage        LOFF is 2x daily-reset on the 'spacex' complex and the book
                       already holds SPCX in that SAME complex — that is one bet at
                       higher leverage, not diversification
  ✓ G5 event clock     no Tier-1 print inside 5d
  ! G7 calibration     this desk is 46% on LONG over 155 graded calls — below a coin
                       flip; demand a second independent block of evidence

  BLOCKED by 1 gate(s).
```

Educational only — not financial advice. **This tool does not place orders.**
