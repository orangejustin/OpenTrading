---
title: Getting started
sidebar_position: 2
---

# Getting started

This walks you from a fresh clone to your first analysis in about five minutes.

## Prerequisites

- **Python 3.9+** (`python3 --version`) for the core — **3.10+** only if you want
  the optional TimesFM forecaster
- **git**
- macOS or Linux (Windows via WSL)
- *Optional, for the narrative layer:* an LLM key (Gemini or OpenRouter) **or** the
  Claude Code / Codex CLI — only for the "AI analysis" and the debate. The whole
  data layer works without any of them. See [Optional power-ups](#optional-power-ups).

## 1 · Clone & install

```bash
git clone https://github.com/orangejustin/OpenTrading.git
cd OpenTrading
bash install.sh                  # core: puts `ot` on your PATH, no keys, stdlib only
```

That's the whole core. For the **optional** TimesFM forecaster (a heavier,
opt-in dependency), also run:

```bash
bash install.sh --with-forecast  # adds the TimesFM module in an isolated venv
```

See [Optional power-ups](#optional-power-ups) below for what that pulls in and
its hardware needs. Verify the toolchain either way:

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

## Optional power-ups

The core is keyless. These two add-ons are entirely optional.

### LLM engines & keys (the narrative layer)

The "AI analysis" panel and the bull-vs-bear debate need one engine. Pick
whichever you already have — the dashboard's header dropdown switches between
them live.

| Engine | Get a key | Notes |
|---|---|---|
| **Gemini** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | has a **free tier**; fastest to set up |
| **OpenRouter** | [openrouter.ai/keys](https://openrouter.ai/keys) | one key → 300+ models (some free); pay-as-you-go |
| **Claude Code / Codex CLI** | — | **no key** — uses your existing CLI subscription |

Set a key in `.env` (or your shell), then start the dashboard on that engine:

```bash
# .env  (git-ignored)
GEMINI_API_KEY=...            # from Google AI Studio
# or
OPENROUTER_API_KEY=sk-or-v1-...   # from OpenRouter
```

```bash
ot web --engine gemini       # or: openrouter / claude / codex
```

With no key at all, the dashboard still runs — it just shows the keyless data
panels and a deterministic rules-based analysis instead of the LLM narrative.

### TimesFM forecasts (a foundation-model cone)

`ot forecast` adds a [TimesFM 2.5](https://github.com/google-research/timesfm)
quantile cone — Google Research's pretrained time-series foundation model — to
the forecast overlay. It's **opt-in** because it's a heavy dependency:

```bash
bash install.sh --with-forecast
```

- **Python 3.10+** (the core stays 3.9+); installed into an **isolated venv**
  (`.venv-forecast/`) so it never touches the keyless core.
- Pulls **`timesfm[torch]`** (~2 GB PyTorch stack) plus a **~500 MB** model
  checkpoint downloaded on first run.
- Model: **`TimesFM 2.5 200M`** (torch backend) — **CPU-friendly**, so an
  Apple-silicon or modern laptop runs it fine (first inference is slow while it
  compiles/loads; subsequent calls are quick). A GPU helps but isn't required.
- Exact hardware guidance and the model card are in Google's repo:
  [google-research/timesfm](https://github.com/google-research/timesfm).

If it isn't installed, `ot forecast` simply prints a hint and the rest of the
desk is unaffected.

## Next steps

- **[The web dashboard](./web-dashboard.md)** — read a ticker page end to end
- **[The daily email](./daily-email.md)** — a scheduled pre-market brief
- **[The prediction desk](./prediction-desk.md)** — how the pipeline works
