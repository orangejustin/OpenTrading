# Portfolio Review & Share Management Desk

A structured way to turn live data into **concrete share-level adjustments** (+/- N shares)
for an existing book — not single-trade ideas, but *"what do I do with the positions I hold
right now?"* It runs the position set through a multi-agent **desk**, then applies hard
**risk limits** before emitting changes.

Use whenever the user asks to *review my book / portfolio / positions*, *adjust / trim / add
shares*, *rebalance*, *de-risk*, *am I too concentrated*, or wants *intraday portfolio
insights*. Pair with `references/risk.md` (sizing) and `references/options.md` (dealer gamma).

> Method inspired by [TradingAgents](https://github.com/TauricResearch/TradingAgents):
> **Analyst team → Researcher (bull vs bear) → Trader → Risk / Portfolio Manager.**

---

## The desk pipeline (run for the whole book, then per name)

1. **Analyst team — gather facts (no opinion yet).**
   - Positions & marks: `ot watch` (reads `watchlist.json`).
   - Dealer gamma / walls / put-call: `ot options SPY <your tickers> --dte 7`.
   - Macro & liquidity: `ot macro`. Sentiment: `ot smart`. Crypto: BTC spot + funding.
   - News per name: `ot news --ticker <T> --days N` (or `ot news digest`).
   - Names with **no CBOE chain** (SPACs / fresh listings, e.g. SPCX): read the user's
     **TradingView** chart instead — `chart_set_symbol` then `data_get_study_values` /
     `data_get_pine_labels` for EMA / VWAP / MACD / targets / IV. Restore the chart after.
2. **Researcher — bull vs bear.** For each name, the strongest one-line bull case and the
   strongest one-line bear case from the analyst facts. Surface the disagreement, don't bury it.
3. **Trader — the call.** Resolve bull vs bear into an action — **HOLD / TRIM / ADD (increase)
   / NEW (open a position in another stock / ETF / option) / HEDGE** — with a **share (or
   contract) delta**, the **cash** it uses or frees, and the **levels** that trigger it
   (add-trigger, stop, target). You can *grow* the book, not just cut it: deploy idle **cash**
   into the highest-conviction adds or new ideas. Magnitude follows the risk rules below.
4. **Risk / Portfolio Manager — final overlay (can resize or veto).** Apply the limits below
   across the *whole* book. The portfolio manager has the last word: a trade that breaks a
   concentration / heat / event rule is trimmed or rejected even if the trader liked it.

---

## Position math (compute this first, every time)

For each position: **$ exposure = shares × last**, **weight = $ exposure / total book**
(include cash in the denominator once raised, so weights stay honest).

**Factor exposure** — group names by their dominant `driver` (from `watchlist.json`) and sum
the weights (e.g. BTC-beta = MSTR + HOOD; AI-capex = ORCL + NVDA). One macro variable moving a
large *summed* weight is the real risk — not any single ticker in isolation.

---

## Hard limits (the risk manager enforces these)

| Limit | Default guardrail | Action if breached |
|---|---|---|
| **Single-name weight** | ≤ ~25–30% of book (short-term book) | Trim toward the cap; the excess **is** the trim size |
| **Factor weight** (correlated names) | ≤ ~40% to one driver (BTC, AI-capex, rates) | Trim the weakest-thesis name(s) in the cluster |
| **Portfolio heat** (Σ risk-to-stops) | ≤ 5–6% of equity (see `risk.md`) | Tighten stops or cut size |
| **Event risk** | Don't *increase* gross exposure within ~24h of a known binary (FOMC, CPI, earnings) | Defer adds; raise cash or hedge |
| **Liquidity** | Thin / new listings sized smaller (no options hedge) | Cap the position; wider mental stop |

**Sizing a trim / add / new** (ties to `risk.md`):
- **Trim to a target weight:** `Δshares = (current_weight − target_weight) × book / last`, rounded to a clean lot.
- **Add or open NEW on confirmation only** (pyramid, never into a loser). Any added / new leg
  risks ≤ 1% of equity to its stop: `shares ≤ (equity × 1%) / (entry − stop)`; for **options**,
  risk = premium, so `contracts ≤ (equity × 1%) / (premium × 100)`. **Fund it from cash first**,
  then from trims — and show the cash drawn so weights stay honest.
- **NEW positions can be any instrument** — another stock, an **ETF** (clean sector/index
  expression), or an **option** (defined-risk leverage, or a hedge). Each gets a thesis + entry /
  stop / target, exactly like a fresh setup.
- **De-risk into events by raising cash.** Cash is a position — optionality + lower variance.

---

## Hedge logic (don't only think in shares)

- **Index dealer gamma:** if `ot options SPY` shows **negative GEX**, moves get *amplified* —
  a surprise is more violent. Into an event with negative gamma **and cheap VIX** (~<16–18), a
  small SPY put / VIX call can be a lower-friction alternative to trimming the whole book. With
  **positive GEX**, expect *pinning* toward the call/put walls — fade the extremes.
- Always state the trade-off: **trim shares** (certain, reduces upside) vs **buy a hedge**
  (keeps upside, costs premium). Let the user choose.

---

## Tier-based books, multi-market & multi-user

- **Shares unknown (tier-based book):** when a roster gives convictions, not counts
  (`tier`: core / secondary / watch = 重仓 / 次持仓 / 关注), weight by **tier** instead of $:
  **core** = the heavy sleeve, **secondary** = satellites, **watch** = not-yet-owned candidates.
  Calls become **qualitative + level-based** (add / trim / initiate / avoid, with target-weight
  *bands* and trigger levels) rather than exact share deltas — and say so explicitly.
- **Multi-market routing:** US → `ot quote` / `ot options`; **A-share & HK → `ot cn`**
  (Eastmoney; e.g. `ot cn 688008 hk09988` — A=CNY, HK=HKD). Keep each book's weights in its own
  base currency; don't add CNY and USD weights without converting. A-shares have no CBOE chain —
  use the user's **TradingView** chart (EMA / VWAP / MACD / IV overlay) for the technical read.
- **Multi-user:** a roster lives in `watchlist.<id>.json` with `owner` / `recipient` / `lang`.
  Build that person's review from *their* holdings, in *their* language, and send to *their*
  `recipient`. Never mix two users' books, and never expose one user's positions to another.

## Output format — Portfolio Review

```
PORTFOLIO REVIEW — [date / time]
Regime: [risk-on / off / mixed] — [biggest driver + key number]; [event risk in next 24h]

BOOK (ordered by weight; note total $ and any cash)
| Ticker | Shares | Last | $ Exp | Weight | Today | One-line read |

CONCENTRATIONS
- Single-name: [name] = NN% [over/under cap]
- Factor: [driver] = NN% across [names]

PER NAME — bull / bear → call
[Ticker] — [HOLD / TRIM N / ADD N] — bull: [...] · bear: [...] · trigger: add >X / stop <Y

RECOMMENDED ADJUSTMENTS  (actions: TRIM / HOLD / ADD / NEW / HEDGE; always include a Cash row)
| Ticker | Now | Action | Δ shares/contracts | $ used (cash ±) | After | Weight → |
  (ADD = grow an existing holding; NEW = open another stock / ETF / option funded from cash)

HEDGE & EVENT RISK
[gamma read; cheap-vol note; "don't add gross before <event>"]

WATCH
- [levels, catalysts, times]

This is analysis for educational purposes, not financial advice. Share-sizing is a
risk-management illustration, not a recommendation to buy or sell securities.
```

---

## Principles

- **Right-size before you re-direction.** Most portfolio damage is sizing, not selection —
  fixing a 50%+ single-name weight matters more than any one bull/bear call.
- **Trim winners that grew too big; never average down a loser** (that's adding risk to a
  failing thesis — the opposite of this desk's job).
- **Cash is a position.** Raising it into a binary is an active, defensible call.
- **Be specific:** every recommendation is a **share count** + the **price level** that
  triggers or voids it.
- **Educational only — not financial advice** on every output.
