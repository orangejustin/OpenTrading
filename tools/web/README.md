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
- **Strategy — the action board** — one deterministic `ot decide` card per
  book/watch name: **Long / Short / Wait** badge, A–D grade, buy/add/trim zones,
  core, stop, horizon, the policy's reason and scenario warning. No LLM, loads in
  ~1s, cached 30 min (↻ Refresh reads). Held names sort first; click through to
  the full ticker page.
- **News page** — the market tape with a time-window slider (**6h–7d**; windows
  past 24h merge the local `ot news store` archive, since the public RSS only
  keeps the ~40 latest items), an instant **keyword/ticker filter**, dated ET
  timestamps, a red edge on market-moving flashes, the **Event Gate** strip
  (scheduled CPI/FOMC/OPEX catalysts from `ot catalysts`), and a **🧠 AI read of
  the tape** button (summary · RISK-ON/OFF/MIXED bias · drivers · portfolio tilt ·
  watch-next) that folds the event calendar into its prompt.
- **TV chart toggle (optional)** — the built-in chart is dependency-free; flip
  the "TV chart" switch on a ticker page to embed TradingView's interactive
  chart instead (loads tradingview.com — external, off by default, persisted).
- **Per-name news fallback chain** — FinancialJuice ticker-tagged → Yahoo per-name
  RSS → the general tape (clearly labeled), so "Related News" is never empty on a
  quiet name.
- **Crowd odds (Polymarket)** — a full-width Macro & Flow strip with the crowd's
  *priced* probabilities for the Step-0 questions: P(Fed holds next FOMC),
  P(25bp cut), P(HIKE this year), P(zero cuts), P(recession). Keyless, cached 15 min.
- **Prediction Desk (per ticker)** — the fusion pipeline on every ticker page:
  - **Forecast cones** — `ot quant`'s keyless logistic P(up) + empirical
    P10–P90 cone renders instantly; if the opt-in TimesFM module is installed
    (`bash install.sh --with-forecast`) its foundation-model cone renders below
    it. Two independent cones agreeing = a real range; disagreeing = the
    uncertainty *is* the signal.
  - **⚔️ Bull vs Bear debate** — one click runs `ot debate`: the evidence pack
    (decide plan · macro · earnings gate · crowd odds · quant + TimesFM cones ·
    48h news · past-call lessons) goes to a bull and a bear on **different
    engines**, then the judge commits — 5-tier verdict, confidence, entry,
    **invalidation**, time stop, plus the bear's direct attack on the bull.
    Runs only on click (a page visit never burns LLM calls), cached until ↻,
    and the verdict is **auto-journaled to `ot reflect`**.
- **Desk consensus + Confluence ladder (per ticker)** — the fusion layer that makes
  the panels compound instead of sitting side-by-side:
  - **Desk consensus strip** — one row atop the ticker page: engine (`ot decide`) ·
    quant tilt · TimesFM tilt · AI action · debate verdict as colored chips, plus an
    agreement verdict — **CONSENSUS LONG/SHORT** when the analysts align,
    **⚠ STAND ASIDE — models disagree** when they split (disagreement IS the signal).
  - **Confluence ladder** — every price level the desk emits (decide zones/stop ·
    quant + TimesFM P10/P50/P90 · dealer call/put walls · AI sniper levels · judge
    entry/invalidation · MA20 + true 52w marks) merged into ONE ladder; levels named
    by **2+ independent sources** get a confluence badge — those are the lines that
    matter. The quant cone band + dealer walls are also drawn on the candlestick
    chart itself. Assembled from cached parts — never triggers an LLM call.
- **Learn — the desk textbook** — every module carries a small **?** chip that jumps
  to `#/learn/<topic>`: a self-contained explainer page (concepts, the models used,
  how to interpret the output, a real annotated case, and numbered citations — TimesFM
  paper, GEX white paper, prediction-market literature, …) with real screenshots
  served from `docs/assets/learn/` via the `/assets/*` route.
- **Today's Top 3 + Morning desk (Strategy tab)** — `ot rank`'s composite score
  (grade + OOS-gated quant edge + cone tilt + zone proximity + today's debate −
  event risk) as a Top-3 strip; the action-board cards re-order by rank and carry
  their score. **⚔️ Run the desk** debates every HELD name sequentially and
  renders the morning verdict table (verdict · confidence · entry · invalidation ·
  time stop), each row cached 24 h and auto-journaled.
- **中文 / EN — full-dashboard language toggle** — the header switch (or a
  `?lang=zh` link) flips every label, badge, verdict and the whole Learn
  textbook to Simplified Chinese, persisted in `localStorage`. LLM output
  follows too: `lang=zh` is threaded into the analysis / tape-read / debate
  prompts (separate caches per language), and `ot debate --lang zh` writes its
  free-text fields in Chinese while keeping tickers, prices and JSON enums
  as-is.
- **Hyperliquid perps + Engine diagnostics (Macro & Flow)** — BTC/ETH funding
  and open interest from the keyless Hyperliquid info API (the BTC-beta
  crowd's leverage bill), and a per-engine health check: one click runs a tiny
  structured call through Gemini / OpenRouter / Claude Code / Codex and stamps
  latency + resolved model (or the exact error).
- **Desk Calibration (Strategy tab)** — `ot reflect`'s track record as a table
  (hit-rate · avg return · alpha, by action/grade/market) plus the exact
  lessons block that gets injected into every debate's judge prompt.

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
  | **Codex** | **no key** — appears automatically when the `codex` CLI is on PATH | your ChatGPT/Codex subscription, headless `codex exec` in a read-only sandbox |

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
  `/api/watchlist`, `/api/analyze`, `/api/engines`, `/api/news`, plus the
  prediction desk: `/api/poly`, `/api/quant`, `/api/forecast`, `/api/debate`
  (`peek=1` = cached-only, never triggers LLM calls), `/api/fusion` (confluence
  ladder + consensus row, assembled from cached parts), `/api/calibration`.
  Data comes from the existing `ot` tools (via `--format json`) and Yahoo's
  no-key chart endpoint (quotes + sparklines).
- `index.html` — a single dependency-free page (vanilla JS + inline CSS); SVG
  sparklines and the sentiment gauge are hand-rolled (no chart library, no build step).
- `../llm/llm.py` — the engine dispatcher, over three tiny stdlib clients:
  `gemini.py` (urllib + curl fallback), `openrouter.py` (OpenAI-compatible
  `/chat/completions`), and `claude_cli.py` (headless `claude -p` on your
  subscription — the same pattern as the daily-email pipeline).

Educational only — not financial advice.
