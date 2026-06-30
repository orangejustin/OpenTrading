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
- **AI analysis (optional).** The per-ticker summary + action + sniper levels use
  **Gemini**. Add a key to `.env` (a free key works — <https://aistudio.google.com>):

  ```env
  GEMINI_API_KEY=your_key_here
  GEMINI_MODEL=gemini-2.5-flash          # optional (default shown)
  GEMINI_MODEL_FALLBACK=gemini-2.0-flash # optional, comma-separated
  ```

  Without a key the analysis page still shows the keyless data panels (price,
  technicals, news) and a hint to set the key.

## Privacy

- **100% local.** A stdlib `http.server` bound to `127.0.0.1` — nothing is exposed
  to the network, nothing is uploaded.
- `watchlist.json` (your positions) and `.env` (your key) are **git-ignored** and
  never committed — only this code ships.
- The dashboard reads `OT_WATCHLIST` if set, so you can point it at any roster.

## How it's built

- `server.py` — stdlib `ThreadingHTTPServer`; routes `/api/overview`,
  `/api/watchlist`, `/api/analyze`, `/api/news`. Data comes from the existing `ot`
  tools (via `--format json`) and Yahoo's no-key chart endpoint (quotes + sparklines).
- `index.html` — a single dependency-free page (vanilla JS + inline CSS); SVG
  sparklines and the sentiment gauge are hand-rolled (no chart library, no build step).
- `../llm/gemini.py` — a tiny stdlib Gemini client (urllib + curl fallback) used only
  when `GEMINI_API_KEY` is present.

Educational only — not financial advice.
