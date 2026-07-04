# `ot web` — local dashboard

An **optional** local web dashboard over the OpenTrading data stack — a clean,
professional panel (market indices + sparklines, your watchlist, and a per-ticker
analysis) inspired by the layout of modern ticker apps.

```bash
ot web                                        # serve http://127.0.0.1:8787 and open your browser
ot web --engine claude                        # default to the no-key Claude Code engine
ot web --engine openrouter --model z-ai/glm-5.2   # default to GLM 5.2 via OpenRouter
ot web --port 9000 --no-open                  # pick a port / don't auto-open
```

Deep links work too: `http://127.0.0.1:8787/#NVDA` opens straight into the
NVDA page, and `/#/news` opens the News tab.

Everything runs **on your machine** — positions never leave `localhost`.

## What you get

- **Scrolling ticker tape** — Gold · Silver · Oil · Bitcoin · Ethereum · US 10Y ·
  DXY · SPY · QQQ · GLD · TLT · VIX, live; every chip links out to the matching
  TradingView symbol page (pauses on hover).
- **Market Indices** — SPY / QQQ / DIA / IWM cards with a 1-month sparkline and the
  day change (colored by direction).
- **Macro & Flow** — the `ot` stack as dashboard cards: macro score (SOFR/TGA/2Y/10Y
  pills), equity + crypto Fear&Greed, BTC funding, and SPY dealer gamma (<7 DTE,
  net GEX + call/put walls). Cached 15 min.
- **My Watchlist** — every name in `watchlist.json` (positions + watch), with live
  quotes. Click any row to open it.
- **Ticker page — instant, keyless** — a hand-rolled SVG **candlestick chart**
  (1M/3M/6M/1Y + volume + 52-week range), key stats (prev close, MA10/20, RSI 14),
  and per-name news. The AI analysis runs **on demand** via the ⚡ Analyze button
  (staged progress + elapsed timer): summary, **action**
  (BUY/ADD/HOLD/WATCH/REDUCE/SELL/AVOID/ALERT), **trend**, sentiment **gauge**,
  **sniper levels** (ideal buy · secondary buy · stop · take-profit), sectors,
  risks, advice — stamped `engine · model · elapsed · finished (ET)` and **cached
  until you ↻ Re-run**.
- **News page** — the market tape with a time-window slider (6h–72h) and an
  optional ticker filter, plus a **🧠 AI read of the tape** button (summary ·
  RISK-ON/OFF/MIXED bias · drivers · portfolio tilt · what to watch next).
- **Per-name news fallback chain** — FinancialJuice ticker-tagged → Yahoo per-name
  RSS → the general tape (clearly labeled), so "Related News" is never empty on a
  quiet name.

## Two tiers

- **Keyless (default).** The strip, indices, sparklines, watchlist, technicals
  (MA10/MA20/RSI), and news all work with **no key** — same public endpoints as
  the rest of `ot`.
- **AI analysis (optional).** The per-ticker summary + action + sniper levels run
  on **your choice of engine + model** — one header dropdown lists every enabled
  combo by name (Gemini 2.5 Flash · GLM 5.2 · DeepSeek v4 · GPT-5.5 · Claude Code
  · … · "custom model slug" for anything else on OpenRouter). Pick the boot
  default with `ot web --engine … --model …` or `OT_LLM_ENGINE` in `.env`.
  Results are cached 10 min per (ticker, engine, model); the **↻ Re-run** button
  forces a fresh call.

  | Engine | Setup | Models |
  |---|---|---|
  | **Gemini** | `GEMINI_API_KEY` in `.env` (free — <https://aistudio.google.com>) | `gemini-2.5-flash` (default), `-pro`, … |
  | **OpenRouter** | `OPENROUTER_API_KEY` in `.env` (<https://openrouter.ai/settings/keys>) | **one key → any model**: GLM 5.2, DeepSeek v4, GPT-5.5/4o, Claude, Gemini, Grok, Qwen… pick from the list or type any slug |
  | **Claude Code** | **no key** — appears automatically when the `claude` CLI is on PATH | your Claude subscription (default / sonnet / opus / haiku) |

  ```env
  GEMINI_API_KEY=...                 # engine 1
  OPENROUTER_API_KEY=sk-or-v1-...    # engine 2 (OPENROUTER_MODEL=z-ai/glm-5.2 to set the default slug)
  OT_LLM_ENGINE=gemini               # default engine: gemini | openrouter | claude
  ```

  Without any engine the analysis page still shows the keyless data panels
  (price, technicals, news) and a hint to set one up.

## Privacy

- **100% local.** A stdlib `http.server` bound to `127.0.0.1` — nothing is exposed
  to the network, nothing is uploaded.
- `watchlist.json` (your positions) and `.env` (your key) are **git-ignored** and
  never committed — only this code ships.
- The dashboard reads `OT_WATCHLIST` if set, so you can point it at any roster.

## How it's built

- `server.py` — stdlib `ThreadingHTTPServer`; routes `/api/overview`,
  `/api/watchlist`, `/api/analyze`, `/api/engines`, `/api/news`. Data comes from the
  existing `ot` tools (via `--format json`) and Yahoo's no-key chart endpoint
  (quotes + sparklines).
- `index.html` — a single dependency-free page (vanilla JS + inline CSS); SVG
  sparklines and the sentiment gauge are hand-rolled (no chart library, no build step).
- `../llm/llm.py` — the engine dispatcher, over three tiny stdlib clients:
  `gemini.py` (urllib + curl fallback), `openrouter.py` (OpenAI-compatible
  `/chat/completions`), and `claude_cli.py` (headless `claude -p` on your
  subscription — the same pattern as the daily-email pipeline).

Educational only — not financial advice.
