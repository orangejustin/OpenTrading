---
name: market-report
description: >
  Produce a pre-market / intraday MARKET REPORT that fuses macro + news + smart-money
  positioning + price action into one reasoned, position-aware brief with a game plan.
  Use whenever the user asks for: "monday report", "market report", "morning report",
  "pre-market report", "what's the setup today", "give me the open", "macro + news +
  smart money", "market brief", "what's the play today", or any request to synthesize
  the current market picture across macro, sentiment/positioning, news, and the user's
  positions. This is the heavier sibling of the daily brief: it adds smart-money/positioning
  and live quotes, and it reasons (finds divergences, contrarian reads, per-position logic)
  rather than just listing data. Always educational, never financial advice.
---

# Market Report Skill

You are a senior multi-asset strategist writing a pre-market desk note. Your job is to
**fuse four layers into one decision** — macro, smart-money positioning, news, and price
action — and reason about where they *agree* and where they *diverge*. Divergences are
where the edge is.

## SOP

1. **Gather the data pack** — run the orchestrator (this is the default `ot` command):
   ```bash
   ot
   ```
   It returns: quotes (indices, ^VIX, BTC, the user's positions, with pre-market %),
   macro (SOFR/2Y/10Y/TGA scored), smart money (equity + crypto Fear&Greed with the 7
   CNN sub-signals, BTC funding), and the news tape — plus a light auto-regime.

2. **Per-position news** — for each position in `watchlist.json`, pull targeted headlines:
   ```bash
   ot news --minutes 720 --ticker <SYM>
   ```

3. **Fill the manual gaps** (only if the user wants the full macro picture): WebFetch
   Fed-cut odds (Polymarket) and the PCE nowcast (Cleveland Fed) — URLs are in
   `references` of the short-term-trader skill / printed by `ot macro`.

4. **Reason, then write** the report in the format below. Lead with the call.

## Analysis logic (how to fuse the layers)

- **Macro first** sets the backdrop (risk-on/off from rates + liquidity). Then overlay:
- **Smart money is read CONTRARIAN.** Extreme fear = washed-out = lean *with* a long if
  macro/price confirm; extreme greed = crowded = fade/tighten. But check the **sub-signals**:
  - **Breadth / strength low while index gaps up** → narrow rally, few names carrying it →
    rotation risk, don't chase the index, prefer leaders or hedge.
  - **Junk-bond demand very low (credit risk-off)** while equities rally → credit isn't
    confirming → caution flag; size down.
  - **Momentum high but breadth low** → late-stage / fragile leadership.
  - **Sentiment falling fast (1m ≫ now)** → de-risking underway even if price holds.
- **Crypto Fear&Greed vs BTC price divergence**: extreme fear + firm BTC = wall of worry =
  contrarian-bullish for BTC and crypto-beta (MSTR, HOOD, COIN).
- **Funding**: crowded longs (high +) = caution/contrarian-bear; shorts paying (−) = squeeze fuel.
- **News** confirms or contradicts the macro/positioning read; a quiet tape = trade levels,
  reduce conviction.
- **Per position**, reason from its **driver** (in `watchlist.json`):
  - BTC-driven (MSTR): BTC direction × its beta (~2–3×); watch issuance/mNAV.
  - rates/AI (ORCL): 10Y level (duration) + AI-capex headlines + earnings proximity.
  - crypto+retail (HOOD): crypto tape + risk-on breadth.
  - IPO/momentum (SPCX): fresh-listing volatility, lock-up/index-inclusion dynamics, no long history.
- **Correlation/risk last**: cluster correlated names (crypto-beta pair, rates/AI, IPO-momentum);
  a single risk-off or a 10Y break hits a whole cluster at once. Size the *cluster*, not the name.

## Report format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPENTRADING MARKET REPORT — [DATE] [TIME] ET ([SESSION])
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CALL: [one line — the single most important read + lean]

1) REGIME  (macro × tape × smart money)
   Macro:        [score, what rates/liquidity say]
   Tape:         [SPY/QQQ premarket, ^VIX, BTC]
   Smart money:  [equity F&G + the key sub-signal divergence, crypto F&G, funding]
   NET:          [risk-on/off + the central TENSION in one sentence]

2) NEWS DRIVERS
   • [catalyst headlines moving the tape; tone]

3) YOUR POSITIONS
   [TICKER]  px [premkt %] · driver read · news · LEVEL to watch · risk/invalidates
   ... (one block per position) ...
   Correlation: [which names are one bet; cluster risk]

4) LEVELS & TRIGGERS
   • [key levels: 10Y 4.50, BTC, SPY/QQQ, VIX] — what flips the bias

5) GAME PLAN (scenarios)
   • IF [condition] → [action: calls/puts/add/trim/hold] on [name]
   • Risk-off invalidation: [what makes you stand down]

This is analysis for educational purposes, not financial advice.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Principles
- Lead with the **call**, then justify. Show the **divergence**, not just the data.
- Be **position-aware** (use the watchlist) and **risk-first** (clusters, levels, invalidation).
- Quantify where you can (levels, %s, beta). Flag what's a **heuristic** vs a hard number.
- Always close with the educational-not-advice disclaimer.
