# Methodology

How every number on the desk is computed — the reference behind the `?` chips and the
Learn tab. Educational only, not financial advice. All inputs are keyless public data
unless a section says otherwise.

- [The pipeline](#the-pipeline)
- [Forecasters](#forecasters) — quant · TimesFM · dealer gamma · macro · crowd · funding
- [Fusion](#fusion) — confluence ladder · consensus · `ot rank` · debate
- [Learning loop](#learning-loop) — grading timing, horizon, provenance, retention
- [Data sources & freshness](#data-sources--freshness)
- [Running & reproducing](#running--reproducing)
- [Publishing these docs](#publishing-these-docs)

---

## The pipeline

Deterministic SOP, always: scripts fetch and compute a **frozen evidence pack**, then (only
for the debate/analysis) an LLM reads it. No agent wanders mid-analysis; identical inputs
give an identical pack. Independence is the whole point — five analysts that share one brain
are one analyst — so each forecaster uses different math and different data.

```
FORECASTERS → FUSION (ladder · consensus · rank · debate) → LEARNING (reflect grades it)
```

---

## Forecasters

### Quant — logistic regression + empirical cone (`ot quant`, keyless)
- **Data:** ~2 years of daily closes (Yahoo v8 chart).
- **Features (6), z-scored:** 5-day & 20-day momentum, RSI-14 centered at 50, MA10−MA20
  spread, 20-day realized volatility, position-in-20d-range.
- **Model:** L2-regularized logistic regression (λ=0.01), batch gradient descent
  (300 epochs, lr 0.1) → **P(up in `horizon` sessions)**, default horizon 5.
- **Cone:** *empirical*, not Gaussian — the historical distribution of forward `horizon`-day
  returns, applied to the last price (real return tails are fat, so quantiles beat σ-bands).
- **OOS hit-rate (the honesty gauge):** train on the first 70%, test on the held-out last
  30%. Read it as **<55% ≈ coin-flip → discount P(up)**; 55–62% decent; ≥62% strong. It is
  printed next to every P(up) and *gates* the quant's weight in `ot rank`.

### TimesFM — foundation-model cone (`ot forecast`, opt-in)
Google Research's 200M-param decoder-only time-series model, forecasting **zero-shot** from
the last ~500 closes; the quantile head gives P10–P90 directly. Never trained per-ticker, and
blind to news/fundamentals — a genuinely independent witness. Opt-in
(`install.sh --with-forecast`, ~2 GB, isolated venv); the keyless core never depends on it.

### Dealer gamma / GEX & walls (`ot options`, CBOE)
- **Mechanism:** dealers hedge continuously. Net **long** gamma (positive GEX) → hedging
  *opposes* moves (vol-suppressing, pins to walls); net **short** gamma → hedging *amplifies*
  moves. `$GEX per 1% = Σ(signed gamma × OI) × 100 × spot² × 0.01`, calls +, puts −.
- **Walls:** call wall = strike with the largest positive dealer gamma (resistance); put
  wall = most negative (support/floor).
- **⚠ The DTE window matters — this is why the same name shows two walls.** Walls are computed
  over options expiring within a **max-DTE window**, and different windows pick different
  strikes:

  | Where it appears | DTE window | Example (SPY, Jul 6) |
  |---|---|---|
  | Macro & Flow card (dashboard) | **≤ 7 DTE** (this week's pin risk) | call wall **750** |
  | Ticker-page chart overlay + confluence ladder | **≤ 30 DTE** (swing horizon) | call wall **760** |

  Both are correct — near-term hedging concentrates at 750, the monthly-OPEX window adds
  760. The UI labels each window (`≤7 DTE` / `≤30D`) so the difference is self-explaining,
  not a bug. Change a window with `ot options SYM --dte N`.
- **Caveat:** GEX assumes dealers are short customer options — an approximation; walls move
  as OI rolls, strongest into OPEX.

### Macro score (`ot macro`) & crowd odds (`ot poly`)
- **Macro:** SOFR, 2Y/10Y, TGA, RRP → one put/call bias (the regime tide).
- **Crowd:** Polymarket prices for the Step-0 questions (Fed holds / 25bp cut / hike / zero
  cuts / recession). Rule: a print *inside* the priced odds is a non-event; the trade lives
  *outside* them.

### Crypto funding (`ot hl`, Hyperliquid) & whales (`ot whales`)
Perp funding = the leverage bill of the crypto crowd (extreme positive = crowded longs →
size IBIT/MSTR beta down). Whales = labeled-wallet ETH balances + Δ over public RPC.

---

## Fusion

### Confluence ladder (`/api/fusion`)
Every level the desk emits — decide zones/stop, quant & TimesFM P10/P50/P90, dealer walls
(≤30 DTE), AI sniper levels, judge entry/invalidation, MA20, true 52w marks — projected onto
one axis. Levels within **0.7%** cluster into one rung; the **×N badge counts independent
sources**. ×1 = an opinion, ×2+ = structure several kinds of participants react to.

### Consensus & stand-aside
One chip per analyst (engine · quant · TimesFM · AI · debate), colored by tilt. Verdict:
**CONSENSUS LONG/SHORT** when ≥2 agree and none oppose; **STAND ASIDE** the moment any two
oppose (disagreement between methods that see *different* information is itself the signal —
the right size for ambiguity is zero).

### `ot rank` — the composite score
One transparent number per name (see [`tools/rank/README.md`](../tools/rank/README.md)):
grade (0–30) + quant edge signed toward the plan side and **gated by OOS hit-rate** (−15…15)
+ cone tilt (−9…9) + entry-zone proximity (0–15) + today's journaled debate × confidence
(−10…10) − event penalty (−8). Components are always emitted; the score is an *ordering*,
not an oracle. The web Top-3 and the morning email consume the same function.

### Debate (`ot debate`)
The evidence pack goes to a **bull** and a **bear on different model vendors** (the bear must
attack the bull's strongest point), then a separate **judge** commits: a 5-tier verdict,
confidence, entry, numeric invalidation, and a **time stop**. Forcing structured disagreement
surfaces the strongest counter-evidence before commitment; different vendors decorrelate
blind spots. Every verdict auto-journals.

---

## Learning loop

`ot reflect` closes the loop: journal → grade → lessons → back into the judge prompt.

### Journal
Append-only `data/journal/decisions.jsonl`, one row per call: ticker, market, action,
grade, confidence, entry price, **invalidation**, **time_stop_days**, thesis, per-analyst
tilts, and a **`source`** stamp (`debate` / `decide` / `manual` / `seed`).

### Grading — "days later" is *exactly* this
`ot reflect grade --days N` scores a call once it is **≥ N sessions old** (default **N=5**,
matching the swing horizon). Younger calls wait until they ripen. Grading is **idempotent** —
scored once, the `outcome` (was_right, return %, alpha vs SPY, MAE, invalidation_breached) is
attached and never recomputed. Run it nightly or by hand.

### Horizon — is a CALL/PUT for day 0 or day +1?
Whatever horizon the call was *made* at, carried on the row as `time_stop_days`:
- **0DTE** (`ot decide --dte 0`) = a **same-day** call, graded on that day's move.
- **Swing** (`--dte 5`, the debate default) = a **days-to-~4-weeks** call, entered from the
  next session, graded at ≥5 sessions.

The desk never averages the two — each row is graded on its own horizon. "Time stop" is the
day being flat-but-right becomes wrong (capital has an opportunity cost).

### Provenance & retention — what the calibration table does and doesn't include
- **Seed rows are excluded.** A few `source:"seed"` bootstrap examples (2026-06-18) ship so
  the desk isn't empty on day one; they **never** count toward the track record or lessons
  (`stats()` filters `source != "seed"` and reports how many it dropped).
- **It grades the desk, not your P&L.** The table is the *desk's own call history* (debate +
  engine reads), currently **global — not split by book, account, or roster**. A name appears
  only because it was journaled, so an **"A-share" row is a China name the desk read, not
  anyone's realized trade** — in particular it is **not** a separate person's roster
  (per-owner scoping is a planned change: tag each row with an `owner` and let the table
  filter). Hard tax/realized-P&L figures live off-repo in `~/.opentrading-private/` and never
  touch the journal.
- **Retention:** the decision journal is append-only and kept indefinitely (only `outcome`
  changes). What ages out is the news archive under `data/news-log/`, not decisions.

### Calibration-weighted fusion (planned, gated)
Once **~30 real graded calls** exist, the judge will weight each analyst by its *demonstrated*
hit-rate by name-class instead of voting equally. Until then, weights are equal and the number
is a humility check, not a statistic.

---

## Data sources & freshness

Yahoo (quotes/charts, incl. pre/post/overnight), CBOE (options + a cross-check vendor),
FinancialJuice (news RSS), CNN/crypto Fear&Greed, Polymarket, Hyperliquid, Eastmoney
(A/HK + 涨停池). `ot validate` cross-checks a quote across Yahoo query1/query2 and CBOE
(any pairing within 0.5% passes); disagreement is flagged before you trust a level.
TradingView (exchange-licensed, via the MCP) is the referee of record for drift disputes.

---

## Running & reproducing

```bash
ot rank NVDA META            # the composite score + its components (--format json)
ot quant NVDA --format json  # P(up), OOS hit-rate, empirical cone, drivers
ot options SPY --dte 7       # vs --dte 30 to see the wall shift
ot debate NVDA --log         # a full verdict, journaled
ot reflect grade --days 5    # grade everything ≥5 sessions old
ot reflect stats             # the calibration table (seed excluded)
```

Every tool takes `--format json`. Golden-file tests freeze the sizing math:
`python3 -m unittest discover tests`.

---

## Publishing these docs

These Markdown files render as-is on GitHub. To host a searchable docs site like the LangChain
/ LlamaIndex references — **no API keys or paid accounts needed**:

- **Simplest:** [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) (`pip install
  mkdocs-material`) → `mkdocs gh-deploy` publishes to **GitHub Pages** (free; just enable Pages
  in the repo settings). Point it at `docs/`.
- **Alternative:** [Docusaurus](https://docusaurus.io/) on **Cloudflare Pages** (also free)
  if you want React/versioned docs — this dovetails with the cross-device tier in
  [`CLOUD.md`](CLOUD.md) (same Cloudflare account, one Pages project).

Neither needs a key. The only setup is: (1) enable GitHub Pages on the repo, or (2) connect
the repo to a Cloudflare Pages project. Everything else is a config file in the repo.

Educational only — not financial advice.
