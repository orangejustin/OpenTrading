---
title: The web dashboard
sidebar_position: 3
---

# The web dashboard

```bash
ot web                   # → http://127.0.0.1:8787
```

The dashboard is the desk's front end. It runs locally, reads your watchlist, and
degrades gracefully to keyless data panels when no LLM engine is configured.

![OpenTrading web dashboard](/img/web-dashboard.png)

## Reading a ticker page (top to bottom)

1. **Consensus strip** — one chip per analyst (engine, quant, TimesFM, AI,
   debate), colored by its tilt. The verdict is computed from the votes:
   **CONSENSUS LONG/SHORT** when 2+ agree and none oppose, **NEUTRAL** with no
   majority, **THIN** when too few have reported, and **⚠ STAND ASIDE** the moment
   any two analysts point in opposite directions.
2. **Chart + walls + cones** — price with the dealer **call/put walls** and the
   forecast cones overlaid. The wall **DTE window is tunable** from the
   Confluence-ladder header (`0DTE / 5 / 7 / 14 / 30 / 45 / 60 / 90`) — pick 0DTE
   for intraday pin risk, longer windows for swing structure. The ladder shows
   the net GEX at that window, which shifts as you widen it.
3. **Bull vs Bear** — the committed call: a 5-tier verdict with entry,
   invalidation and a time stop. See [the debate](./prediction-desk.md).
4. **Confluence ladder** — every price level the desk emits on one axis; the rows
   named by **2+ independent methods** (marked `×2`) are the ones that matter.
5. **AI analysis** — a grounded second opinion: summary, action, sentiment gauge,
   sniper levels and risks.

## Switching the engine

The header has a **model dropdown**. It controls the AI Analysis and News
Analysis panels; results are cached per (ticker, engine, model).

The **debate** has its own `engines` chip — click it to cycle three modes:

- **diverse** (default) — bull and bear run on *different* engines for
  perspective diversity; the judge on Claude.
- **single** — all three roles run on the header engine·model you selected.
- **custom roles** — three small dropdowns appear: pick an engine·model for
  the bull, the bear and the judge independently (leave any on *auto* for the
  desk default). Great for A/B-ing judges or pitting two models against each
  other.

Switching costs no tokens; the new assignment applies on the next run. Note
that `Claude Code · default` (and Codex `default`) means *your CLI's own
default model* — change it with `/model` in the CLI, or pin one here.

## English / 中文

A **中文 / EN** toggle in the header (or `?lang=zh`) flips the entire UI *and* the
model's output between English and Simplified Chinese — the same desk for a US
book or an A-share / HK book.

## The Learn tab

`#/learn` is the built-in textbook. Every module on a ticker page has a **?** help
chip that jumps to the matching explainer — the confluence ladder, forecast
cones, dealer gamma, smart money, calibration — each with a worked real-world
example. Start there when a number isn't obvious.

## Macro & Flow

The dashboard home shows the global picture: the macro score (rates & liquidity),
Fear & Greed, BTC funding, SPY dealer gamma, Hyperliquid perps, **on-chain whale
flow**, engine diagnostics, and Polymarket crowd odds.
