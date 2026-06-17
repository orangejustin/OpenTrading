# OpenTrading

**English** | [简体中文](README.zh-CN.md)

**Open-source, local-first Claude project for short-term trading analysis** —
stocks, options, derivatives, and crypto. It pairs an expert trading *skill*
(macro-first, risk-first) with small, dependency-free *data CLIs* that you can run
yourself or let Claude drive.

> Formerly *"Short-Term Trader Skill."* OpenTrading repackages it as a proper Claude
> Code project: an embedded skill under `.claude/skills/`, a root `CLAUDE.md`, and
> **real data tools that work locally with no proprietary/internal access**.

> ⚠️ **Educational only — not financial advice.** Trading involves substantial risk of loss.

> 📧 **Hands-free:** get a styled, position-aware pre-market brief in your inbox every
> weekday — see [Daily pre-market email](#daily-pre-market-email). 📈 Power users can bridge
> **TradingView** live — see [Optional power modules](#optional-power-modules).

---

## Quickstart

```bash
git clone https://github.com/orangejustin/OpenTrading
cd OpenTrading
bash install.sh            # puts `ot` on your PATH + runs a health check (no keys, nothing to compile)
```

Then everything is **one command, `ot`**:

```bash
ot                         # the morning read: macro + news + smart money + options + your positions
ot news --window premarket # live FinancialJuice headlines (public RSS — no account)
ot macro                   # scored intraday macro dashboard (no API key)
ot options SPY --dte 7     # put/call + dealer gamma (GEX) + gamma walls
ot help                    # every subcommand
```

> Not ready to touch your PATH? Skip `install.sh` and run it in place: `bin/ot …`

Then open the folder in **Claude Code** (or Claude Desktop) and just ask:

- *"Give me my morning macro brief — calls or puts on QQQ today?"*
- *"Any FinancialJuice news on NVDA in the last hour? Store it."*
- *"NVDA broke $950 on volume, RSI 62, account $30k — how do I trade it?"*

The embedded **short-term-trader** skill activates automatically and pulls live data
through `ot`.

**Requirements:** Python 3.9+ (standard library only; uses `certifi` if installed,
otherwise falls back to the system `curl`). No keys, no paid data feeds.

**Dependency management (uv):** for a reproducible dev environment, use
[`uv`](https://github.com/astral-sh/uv) (like TradingAgents / OpenHands) — `uv sync`
installs the locked deps from `uv.lock`, and `uv run …` runs against them. The runtime
CLI stays zero-config (`bin/ot` runs on plain `python3` too); `pyproject.toml` + `uv.lock`
are for development, CI, and future dependencies. Optional extras: `uv sync --extra ibkr`.

**Runner:** `ot` auto-prefers [`uv`](https://github.com/astral-sh/uv) when it's
installed — it runs a standalone CPython (PEP 723-ready for future dependencies, and
it sidesteps the macOS framework-Python launchd hang) — and otherwise falls back to
plain `python3`. Override with `OT_PYTHON=/path/to/python`; force-disable uv with
`OT_NO_UV=1`. `ot doctor` shows which runner is active.

---

## What's inside

| Piece | Path | Purpose |
|-------|------|---------|
| **`ot` CLI** | `bin/ot` | **One command that fronts every tool** (run `ot help`) |
| Installer | `install.sh` | Puts `ot` on PATH + `ot doctor` health check |
| Trading skills | `.claude/skills/` | `short-term-trader` (setups/options/risk) + `market-report` (fused macro+news+smart-money+options report) |
| FinancialJuice CLI | `tools/financialjuice/fj.py` | Real-time news squawk via the public RSS feed |
| Macro CLI | `tools/macro/macro.py` | SOFR, 2Y/10Y, TGA, RRP → scored bias (no key) |
| Smart-money CLI | `tools/smartmoney/sm.py` | CNN + crypto Fear&Greed, BTC funding — contrarian positioning |
| Options CLI | `tools/options/opt.py` | Put/Call + dealer gamma (GEX) + gamma walls (CBOE, no key) |
| Quotes CLI | `tools/quote/q.py` | No-key quotes incl premarket + ^VIX (Yahoo) — IBKR stand-in |
| China A-shares (optional) | `tools/china/cn.py` | A-share quotes 沪深/A股 via Eastmoney (no key) — `ot cn` |
| Live decision engine (optional) | `tools/sim/` | **`ot decide`** — CALL/PUT/NO-ACTION from the learned policy, no key |
| Report orchestrator | `tools/report/report.py` | Fuses all of the above + BTC + your positions into one report |
| Daily brief | `tools/brief/daily_brief.py` | Lighter daily push + macOS notification |
| Daily email | `tools/brief/daily_email_claude.sh` + `tools/brief/wrap_html.py` | Claude-written, position-aware **HTML** pre-market email (SMTP) |
| Project config | `CLAUDE.md`, `.claude/settings.json` | Wires the skills in and pre-approves the tools |
| Watchlist | `watchlist.json` (git-ignored) | Your positions; powers the position-aware sections |
| Data | `data/news-log/`, `data/reports/`, `data/briefs/` | Date-stamped output (git-ignored) |

---

## FinancialJuice CLI

Reads the **public** FinancialJuice RSS feed (`feed.ashx?xy=rss`) — no login, no
browser automation. Converts timestamps to ET, tags categories, caches for 60s, and
backs off on rate limits.

```bash
ot news                          # most recent
ot news --window open            # 09:30–10:30 ET
ot news --minutes 60             # last hour
ot news --ticker NVDA            # ticker-relevant only
ot news --category Fed           # Fed/macro/earnings/...
ot news --json                   # machine-readable
ot news digest --days 7          # multi-day digest (merges the stored archive + live)
ot news store --window premarket # -> data/news-log/
```

Full flag reference: [`tools/financialjuice/README.md`](tools/financialjuice/README.md).

> The public FinancialJuice RSS is **provider-agnostic** (no Bloomberg/CNBC/Reuters tags). For
> per-provider US-stock coverage, **aggregate direct feeds**: `ot news --feeds financialjuice,cnbc`
> or `--feeds yahoo --tickers AAPL,MSTR` (CNBC Top/Markets/Earnings/Economy + Yahoo per-ticker,
> each source-tagged; filter with `--source cnbc`). Reuters/Bloomberg dropped free RSS.
> `OT_FJ_FEED_URL` can also point at a personalized PRO feed.

## Macro dashboard CLI

Auto-fetches the no-API-key rates/liquidity indicators and scores each per the
thresholds in the skill's `macro-dashboard.md`:

```
INTRADAY MACRO DASHBOARD — auto-fetched (no-key public data)
  SOFR            3.60%  [+ bull]  down vs 3.63%
  TGA             $801B  [+ bull]  bull<900 / bear>925
  2Y Yield        4.09%  [+ bull]  bull<4.18 / bear>4.30
  10Y Yield       4.48%  [  neut]  bull<4.35 / bear>4.50
  AUTO SCORE: +3  (from 4 indicators)  ->  LEAN CALLS (bullish tilt)
```

Run it with `ot macro` (or `ot macro --json`). It also prints the two manual
indicators (Fed-cut odds on Polymarket, PCE nowcast) with their URLs to fold in by
hand. Details: [`tools/macro/README.md`](tools/macro/README.md).

---

## Market report (the full fusion)

One command gathers **macro + smart-money positioning + options/gamma + quotes + BTC +
news + your positions** into a single data pack with an auto-regime:

```bash
ot                 # markdown data pack -> stdout (this is the default command)
ot report --save   # also -> data/reports/<date>.md
ot report --notify # + macOS notification (used by the schedule)
```

Then ask Claude for **"the market report"** (or say *"monday report"*) — the
`market-report` skill reasons over the pack: cross-asset synthesis, sentiment/credit
**divergences**, dealer-gamma pin/trend read, and a per-position game plan. Schedule it
with `ot schedule` (see the macOS TCC caveat in `tools/brief/README.md`).

---

## The skill

`.claude/skills/short-term-trader/` is a standard Claude skill. Its workflows:

1. **Daily macro brief & put/call bias** — 8-indicator scored dashboard → CALLS / PUTS / NO TRADE
2. **FinancialJuice news** — fetch / filter / store / news-impact analysis on a ticker
3. **Trade setup analysis** — thesis, entry/stop/targets, R:R, position size
4. **Options analysis** — Greeks, IV rank, strategy selection, earnings plays
5. **Crypto trade analysis** — funding, leverage, liquidation-aware sizing
6. **Trade journal & P&L review** — R-multiple tracking, behavioral patterns
7. **Strategy backtesting** — metrics + overfitting checks
8. **Portfolio review & share management** — bull/bear desk → concrete +/- share calls with concentration & factor limits

Operating principles it enforces: **macro first → setup second → size third**,
**risk before opportunity**, **news only matters in context**, and an
educational-not-advice disclaimer on every analysis.

---

## Daily pre-market email

OpenTrading can email you a **position-aware pre-market brief** every weekday morning — the
same fusion as `ot report`, written up by Claude and delivered as a styled, **Outlook-safe
HTML** email (with a plain-text fallback). What it fuses, every run:

- **Macro** — SOFR / 2s10s / TGA / RRP → a scored directional bias
- **Smart money** — CNN + crypto Fear&Greed and BTC funding (contrarian)
- **Options EV** — SPY + your names: dealer gamma (GEX) sign and gamma walls
- **News, last 24h** — FinancialJuice headlines tied to *your* positions
- **Your book** — a $-weighted positions table (exposure, weight %, per-name read)
- **Concentration & watch-today** — the dominant factor risk + actionable levels

Enable it (plain tier — just SMTP creds, no other manual steps):

```bash
cp .env.example .env        # set OT_SMTP_* + OT_EMAIL_TO (Resend works with no 2FA)
ot email --dry-run          # confirm config resolves (no send)
ot email                    # one-off send
ot schedule email           # weekdays 08:30 local (macOS launchd)
ot schedule email 9 0       # change the time · `ot schedule email uninstall` to remove
```

Preview the HTML without sending:

```bash
OT_EMAIL_RENDER_ONLY=1 OT_EMAIL_HTML_OUT=/tmp/brief.html \
  bash tools/brief/daily_email_claude.sh && open /tmp/brief.html
```

**In Chinese:** add `--lang zh` (news email) or `OT_EMAIL_LANG=zh` (daily brief) to receive it in 简体中文.

> **Planned (v2): user-tunable feeds** — pick *which* sources the brief fuses (macro,
> FinancialJuice news, smart money, options EV, TradingView), opt-in per source, instead of
> always including everything. See [`RELEASE_NOTES.md`](RELEASE_NOTES.md).
>
> macOS: launchd can't read repos under `~/Desktop`, `~/Documents`, or `~/Downloads` (TCC) —
> keep the repo elsewhere (e.g. `~/OpenTrading`). Provider details: [`tools/email/README.md`](tools/email/README.md).

---

## Live decision engine (`ot decide`)

`ot decide TICKER --dte N` turns the skill's learned policy into a single concrete call —
**CALL / PUT / NO-ACTION** + conviction + size — from no-key data (price/gap/trend + `^VIX`).

```bash
ot decide QQQ  --dte 0              # 0DTE: fade-gap + VIX-confirm + skip-events + selectivity
ot decide NVDA --dte 5             # swing: momentum calls on names you read well
ot decide QQQ  --dte 0 --format json
```

It encodes the policy written up in the skill's
[`references/learned-strategy.md`](.claude/skills/short-term-trader/references/learned-strategy.md)
(selection > timing; 0DTE done right; a hard daily-loss stop; never size up after a loss), and
points you at `ot options` / `ot news` / `ot macro` for the live IV / gamma-wall / news
confirmation it can't see. **NO-ACTION is a position.**

> Your positions live only in git-ignored `watchlist.json`. Educational only — not financial advice.

---

## Privacy & your data

Your holdings and secrets **never** enter git and are **never** part of any release:

| What | Lives in | Status |
|------|----------|--------|
| Your positions (e.g. ORCL, SPCX, …) | `watchlist.json` | **git-ignored** — only `watchlist.example.json` is tracked |
| Email / API credentials | `.env` | **git-ignored** — only `.env.example` is tracked |
| Fetched news, reports, briefs | `data/` | **git-ignored** |

Recreate the two private files from their templates on any machine:

```bash
cp watchlist.example.json watchlist.json   # then edit with YOUR positions
cp .env.example .env                        # then add your SMTP creds
```

That separation is what makes the repo safe to share publicly — the `*.example` files are
placeholders; the real ones stay on your machine. **Never commit `.env` or `watchlist.json`.**

---

## Optional power modules

The core above is the **plain tier**: free, no API keys, no manual steps — `install.sh` just
works. The modules below add more but are **optional** and need **manual setup**; nothing in
the core depends on them.

### TradingView — live charts, in-session
Bridges your **TradingView Desktop** app to Claude via the
[`tradesdontlie/tradingview-mcp`](https://github.com/tradesdontlie/tradingview-mcp) server
(Chrome DevTools port). Once set up, ask Claude in-session — *"analyze MSTR with the TV
data"* — and it reads live quotes / study values / your Pine levels straight off your chart.
Manual steps: clone + `npm install` the MCP, `claude mcp add`, launch TradingView with the
debug port, restart Claude Code, run `tv_health_check`. *(ToS-gray, undocumented internal
APIs — runs against your own logged-in client.)*

### IBKR — planned (`tools/ibkr/`)
Interactive Brokers via [`ib_async`](https://github.com/ib-api-reloaded/ib_async): live
quotes, option chains, positions, and **paper** execution behind an explicit guard.
Read-only/paper first; never auto-submits live orders. Requires TWS / IB Gateway running.

---

## Roadmap

Short version (shipped history in [`RELEASE_NOTES.md`](RELEASE_NOTES.md); full detail in
[`ROADMAP.md`](ROADMAP.md)):

- **Email v2 — user-tunable feeds**: choose which sources the daily brief fuses.
- **Optional power modules** (manual setup, never required by the core):
  - **IBKR** (`tools/ibkr/`) — live quotes, option chains, positions, paper execution via `ib_async`.
  - **TradingView** — fold live chart / study / Pine levels into the report (today: in-session, on-demand).
- **More no-key data CLIs & APIs** — FRED, options IV/IVR, funding curves.
- **Multi-agent research desk** — *future exploration, not a current direction*: analyst →
  bull/bear debate → trader → risk-manager, learning from
  [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents).

---

## Credits & disclaimer

Built by [@orangejustin](https://github.com/orangejustin). The (future) multi-agent
direction draws inspiration from [TradingAgents](https://github.com/TauricResearch/TradingAgents).

This project provides analysis for **educational purposes only**. It is **not
financial advice**. Markets are risky; size accordingly and do your own research.
