# Learned strategy — "how to win", distilled from your own trading

A playbook the **short-term-trader** skill loads on demand. The rules below are distilled
from your own realized trading (scored by your P&L) and then forward-validated. Kept here as
**qualitative policy only — no account figures** (those stay in your private, local tools).

> ⚠️ Educational analysis — not financial advice.

## TL;DR — the winning policy is an *ensemble*, not one rule

1. **Selection > timing.** Trade options on names you actually read well — **NVDA / AMZN / GOOG** — and ≥3 DTE for swings. Edge-name calls are your clearest positive-expectancy bucket.
2. **0DTE QQQ — keep it, but invert it.** FADE the open gap (don't chase), require **VIX-direction confirmation**, **SKIP event days**, stay selective (**NO-ACTION is a position**), size down when **VIX < 16** (chop).
3. **Direction:** calls in uptrends; puts only on a real downtrend thesis (puts have been your weaker book).
4. **Risk governor:** a **hard daily-loss stop** (sized to your capital), **never size up after a loss**, **≤5% premium/trade**, keep turnover low (few high-conviction trades, not constant churn).

## The leak — what loses money (qualitative)

- **Chasing gap-ups is the core leak** — buying calls into green opens and getting faded. Same pattern shows up in shares (buying strength, then holding).
- **Same-day / 0DTE index options are the biggest drain** — the lottery, not the edge.
- **Being directionally right isn't enough on 0DTE** — entry timing/execution still loses, because 0DTE leaves no margin.
- **It's a few tilt days, not a slow bleed** — and losses escalate over time when **sizing up into losses** (revenge trading).

## The edge — forward-validated (decide blind, then score)

- **Single-name calls on names you read (NVDA / AMZN / GOOG)** are your positive-expectancy bucket — majority win.
- **3–7 DTE beats 0DTE.**
- For **0DTE QQQ**, the forward-winning rules **invert the habit**: **VIX-direction confirm** and **fade-the-gap** beat **gap-follow** (the habit).

Counterintuitive, but true in *your* data:

- **Calm VIX is NOT safe for 0DTE** — low VIX is your worst win-rate (chop kills premium); higher-vol days are better. 0DTE wants movement, fears chop.
- **"With the trend" didn't save you** — the biggest-losing bucket *was* trend-aligned, because it *was* the gap-chase.

## How to trade your 0DTE QQQ right (at the open)

1. **Event day (FOMC / CPI / OPEX)? → NO-ACTION** (far deadlier).
2. **Read the gap and FADE it** — gap up → lean puts, gap down → lean calls. Don't chase.
3. **Require VIX-direction confirmation** — calls only if trend-up *and* VIX falling; puts only if trend-down *and* VIX rising. Disagree → **NO-ACTION**.
4. **VIX < 16?** Size down or pass (chop risk).
5. Apply it live: `ot decide QQQ --dte 0`.

## The method — keep learning (private)

**Forward** (decide blind, as-of the timestamp) → **backward** (score vs realized P&L), many
strategies in parallel. Re-derive specifics from your own trade history privately, then apply
the result live with `ot decide TICKER --dte N`.

## Honest caveats

- **Small sample** — the 0DTE findings are *suggestive, not proven*; confidence comes from independent slices agreeing, not any single cut.
- **Daily granularity** can't model intraday entry timing — exactly why "right but still lost" happens.
- **IV / gamma-walls / news can't be backfilled** — they're **live-only confirmation** (`ot options`, `ot news`, `ot macro`), not backtested signals.

> Educational only — not financial advice. Markets are risky; size accordingly and do your own research.
