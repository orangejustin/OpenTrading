---
title: Getting started
sidebar_position: 2
---

# Getting started

This walks you from a fresh clone to your first analysis in about five minutes.

## Prerequisites

- **Python 3.9+** (`python3 --version`)
- **git**
- macOS or Linux (Windows via WSL)
- *Optional:* an LLM key (Gemini or OpenRouter) **or** the Claude Code / Codex
  CLI, only if you want the narrative "AI analysis" and the debate. The data
  layer works without any of them.

## 1 · Clone & install

```bash
git clone https://github.com/orangejustin/OpenTrading.git
cd OpenTrading
bash install.sh          # puts `ot` on your PATH; no keys required
```

Verify the toolchain:

```bash
ot doctor                # checks python / deps / network
```

## 2 · Your first commands

Everything is fronted by a single command, `ot`. Try these — none need a key:

```bash
ot                       # full market report: macro + news + smart money + options
ot quote SPY QQQ ^VIX    # live quotes, incl. pre-market and ^VIX
ot macro                 # rates & liquidity → a put/call bias
ot decide NVDA --dte 7   # CALL / PUT / NO-ACTION + a range plan
ot whales                # on-chain: labeled-wallet ETH balances + deltas
```

Add `--format json` (or `--json`) to **any** tool for machine-readable output.

## 3 · Open the dashboard

```bash
ot web                   # → http://127.0.0.1:8787
```

Then type a ticker (e.g. `NVDA`) to see the full desk — the consensus strip, the
chart with dealer walls and forecast cones, the bull-vs-bear debate, and the
confluence ladder. See **[The web dashboard](./web-dashboard.md)**.

To use an LLM for the narrative layer, either export a key or pass an engine:

```bash
export GEMINI_API_KEY=...        # or OPENROUTER_API_KEY
ot web --engine gemini           # or: claude / codex / openrouter
```

## 4 · Make it yours (two git-ignored files)

Two files hold your private config and are **never committed**:

```bash
cp .env.example .env                     # SMTP creds, optional LLM keys
cp watchlist.example.json watchlist.json # your positions
```

Edit `watchlist.json` with the names you hold or track. Add a `recipient` field
if you want the daily email:

```json
{
  "recipient": "you@example.com",
  "positions": [
    {"ticker": "NVDA", "shares": 100},
    {"ticker": "SPY", "shares": 50}
  ]
}
```

:::tip Multiple books
You can keep several rosters (e.g. `watchlist.188284421.json`) and point the
dashboard at one with `OT_WATCHLIST=watchlist.188284421.json ot web`.
:::

## Next steps

- **[The web dashboard](./web-dashboard.md)** — read a ticker page end to end
- **[The daily email](./daily-email.md)** — a scheduled pre-market brief
- **[The prediction desk](./prediction-desk.md)** — how the pipeline works
