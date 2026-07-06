# OpenTrading

Open-source, local-first toolkit **and** Claude skill for short-term trading
analysis — stocks, options, derivatives, and crypto — with a macro-first,
risk-first workflow.

This is a **Claude Code project**. The trading *expertise* lives in an embedded
skill; the live *data* lives in small, dependency-free Python CLIs.

> **New session / new machine?** Start with **[`README.md`](README.md)** (setup, the daily
> email, privacy, optional power modules) and **[`RELEASE_NOTES.md`](docs/RELEASE_NOTES.md)** (what
> shipped + future work). Recreate the two git-ignored files first: `.env` and `watchlist.json`.

## How this project is wired

- **Skill** — `.claude/skills/short-term-trader/` auto-activates on any trading
  query (trade setups, options, macro brief, news, risk, crypto, journaling,
  backtesting). It defines the workflows and loads its `references/*.md` on demand.
- **One CLI** — `bin/ot` fronts every data tool. **Prefer `ot` over manually
  browsing the web** and over the underlying `python3 tools/...` paths.
- **Output** — news logs / reports go to `data/` (git-ignored).

## The `ot` command (use this)

`bin/ot` is the single entry point — one verb per tool, plus a default that
produces the full market report. Run it from the project root as `bin/ot`
(or just `ot` after `bash install.sh` puts it on PATH):

```bash
ot                              # DEFAULT: full market report (macro+news+smart money+options+positions)
ot news --window premarket      # FinancialJuice squawk (public RSS, no login)
ot news --ticker NVDA --minutes 60
ot news store --window open      # -> data/news-log/
ot macro                        # SOFR / 2Y-10Y / TGA / RRP -> scored put/call bias
ot smart                        # CNN + crypto Fear&Greed, BTC funding (contrarian)
ot quote SPY QQQ ^VIX           # no-key quotes incl premarket + ^VIX
ot options SPY --dte 7          # put/call + dealer gamma (GEX) + walls
ot watch                        # your positions' live quotes (reads watchlist.json)
ot report --save --notify       # write data/reports/<date>.md + macOS notification
ot email                        # email the report via SMTP (.env creds; see tools/email/README.md)
ot decide   TICKER [--dte N] [--market US|A|HK]  # CALL/PUT/NO-ACTION + range plan (US + China A/HK via Yahoo)
ot strategy [TICKERS] [--roster ID]              # portfolio constructor: graded, allocated book (--style/--risk; A/HK ok)
ot doctor                       # python / deps / network health check

# --- prediction desk (the fusion pipeline; see docs/ROADMAP.md) ---
ot rank     [TICKERS] [--top 3] # composite desk score per name — the shared Top-3 (no LLM; web + email use it)
ot quant    TICKER              # keyless logistic P(up) + empirical range cone (OOS-gated)
ot forecast TICKER              # TimesFM 2.5 quantile cone (opt-in: install.sh --with-forecast)
ot poly                         # Polymarket crowd odds for the macro event gate
ot debate   TICKER [--log] [--lang zh]  # bull/bear/judge desk — 3 LLM calls on a deterministic pack
ot reflect  [stats|grade|lessons]       # decision journal + self-calibration (the learning loop)

# --- forecasters / positioning / data ---
ot hl       [BTC ETH SOL]       # Hyperliquid perp funding + OI (BTC-beta leverage bill)
ot whales                       # labeled-wallet ETH balances + Δ (public RPC; data/wallets.json)
ot cnpack   [--zt N|--cost b s n]  # A股 涨停池 + 净成本 math (for the CN-language roster email)
ot validate [TICKERS]           # cross-source quote sanity: yahoo q1 vs q2 vs CBOE
ot privacy-audit [--push|--install-hook]  # pre-push gate: branch/tracked-files/secret grep

# --- web ---
ot web [--engine gemini|openrouter|claude|codex] [--model SLUG]  # dashboard → 127.0.0.1:8787
#   OT_WATCHLIST=path ot web    # point the dashboard at another roster (e.g. a private-vault list)
```

> **Prediction desk in the web:** every ticker page fuses these into a **confluence
> ladder** (levels named by 2+ independent methods) + a **consensus strip**
> (STAND-ASIDE when analysts disagree); the **Learn** tab (`#/learn`) is the
> textbook. A header **中文/EN** toggle (or `?lang=zh`) flips the whole UI *and*
> the LLM output. Run `bash install.sh --with-forecast` only if you want TimesFM.

Add `--json` (or `--format json`) to any tool for machine-readable output.
`ot` shells out to the stdlib-only Python CLIs under `tools/` (Python 3.9+,
optional `certifi`, curl fallback); those still work directly if you need them.
The runner auto-prefers `uv run` when uv is installed (standalone CPython,
PEP 723-ready), else `python3` — override with `OT_PYTHON`, disable uv with
`OT_NO_UV=1`, inspect with `ot doctor`.
When a workflow needs news / macro / sentiment / options / quotes, **call `ot`**
instead of scraping — it handles ET timezones, categorization, caching, and backoff.

## Operating principles (the skill enforces these)

1. **Macro first, setup second, size third.**
2. **Risk first** — define the stop and the position size *before* the entry.
3. **News is signal only in context** — cross-reference FinancialJuice headlines
   against the macro dashboard before acting.
4. **Always disclaim**: analysis is educational, *not* financial advice.

## Roadmap

Optional, opt-in modules (details in `docs/ROADMAP.md`; shipped history in `docs/RELEASE_NOTES.md`).
The **plain tier stays zero-config**; these need manual setup and the core never depends on them:
- **TradingView** — live charts via MCP (shipped, optional); fold into the report (planned).
- **IBKR** (`tools/ibkr/`) — quotes / option chains / paper execution via `ib_async` (planned).
- **Email v2** — user-tunable feeds (pick which sources the daily brief fuses).
- **Multi-agent research loop** — *future exploration only*, learning from
  [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents).

## Conventions

- Keep tools dependency-free where possible (stdlib + optional `certifi`).
- New data sources go in `tools/<name>/` with a short README and a `--format json` mode.
- **Privacy:** never commit secrets/keys (`.env`) or your positions (`watchlist.json`);
  never commit `data/`. Only the `*.example` templates are tracked.
- **Workflow:** land changes on a short-lived branch and open a merge request (MR); `main`
  advances only through approved MRs — no direct pushes to `main`.
