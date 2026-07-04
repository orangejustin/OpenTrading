# `ot web` — local dashboard

An **optional** local web dashboard over the OpenTrading data stack — a clean,
professional panel (market indices + sparklines, your watchlist, and a per-ticker
analysis) inspired by the layout of modern ticker apps.

```bash
ot web                 # serve http://127.0.0.1:8787 and open your browser
ot web --port 9000     # pick a port
ot web --no-open       # don't auto-open the browser
```

Everything runs **on your machine** — positions never leave `localhost`.

## What you get

- **Ticker strip** — Gold · Bitcoin · Ethereum · VIX, live.
- **Market Indices** — SPY / QQQ / DIA / IWM cards with a 1-month sparkline and the
  day change (colored by direction).
- **My Watchlist** — every name in `watchlist.json` (positions + watch), with live
  quotes. Click any row to analyze it.
- **Ticker analysis** — search or click a ticker for: an AI summary, an **action**
  (BUY/ADD/HOLD/WATCH/REDUCE/SELL/AVOID/ALERT), a **trend** call, a Fear&Greed
  **gauge**, **sniper levels** (ideal buy · secondary buy · stop · take-profit),
  related sectors, risk alerts, and a news feed.

## Two tiers

- **Keyless (default).** The strip, indices, sparklines, watchlist, technicals
  (MA10/MA20/RSI), and news all work with **no key** — same public endpoints as
  the rest of `ot`.
- **AI analysis (optional).** The per-ticker summary + action + sniper levels run
  on **your choice of engine** — switch live from the header dropdown, and pick a
  model per engine. Results are cached 10 min per (ticker, engine, model); the
  **↻ Re-run** button forces a fresh call.

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
