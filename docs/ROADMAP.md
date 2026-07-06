# OpenTrading Roadmap

Today OpenTrading is a single expert *skill* + no-key data CLIs + an autonomous daily email.
A **possible future end state** is a local, open-source trading research desk — multiple
specialized agents that gather data, debate, and produce a risk-checked decision, all
runnable from Claude Code with no proprietary access. That multi-agent direction is a
**later exploration, not a current focus**; its north star is
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents).

---

## Now — shipped

- ✅ Repackaged as a Claude Code project (`CLAUDE.md`, `.claude/skills/`, `.claude/settings.json`).
- ✅ **FinancialJuice CLI** (`tools/financialjuice/fj.py`) — public RSS squawk, ET-aware, categorized, cached.
- ✅ **Macro dashboard CLI** (`tools/macro/macro.py`) — SOFR, 2Y/10Y, TGA, RRP, no API key, scored.
- ✅ Skill workflows rewritten to call the CLIs instead of scraping a browser.
- ✅ **Daily brief** (`tools/brief/daily_brief.py`) — regime + macro + BTC + **position-aware**
  (watchlist) digest with a macOS notification. Manual run works anywhere; launchd
  scheduling needs a non-TCC-protected location (not `~/Desktop`).
- ✅ **Autonomous daily email** (`tools/brief/daily_email_claude.sh` + `wrap_html.py`) —
  position-aware, **Outlook-safe HTML**; fuses macro + smart money + 24h news + quotes +
  options/GEX + BTC, written by `claude -p`, delivered via SMTP, scheduled weekdays 08:30
  local (launchd). *Plain tier — needs only SMTP creds, no other manual steps.*
- ✅ **TradingView (optional power module)** — TradingView Desktop bridged via MCP and
  verified live (`tv_health_check`); drive it in-session for on-demand chart/study reads.
- ✅ **China A-shares (optional)** — `ot cn` no-key Eastmoney quotes for 沪深 / A股; the data
  layer for a future A-share portfolio review.
- ✅ **Chinese-language emails** — `--lang zh` / `OT_EMAIL_LANG=zh` writes the brief / news
  email in 简体中文.

---

## Next — live brokerage & charts (optional power modules)

> These are **opt-in** modules that require **manual setup** (a broker gateway, the
> TradingView Desktop app, etc.). The **plain tier never depends on them.**

### IBKR (`tools/ibkr/`)
Interactive Brokers via [`ib_async`](https://github.com/ib-api-reloaded/ib_async)
(maintained successor to `ib_insync`).

- Read-only first: live quotes, option chains + Greeks, historical bars, positions, P&L.
- Then **paper-trade** execution behind an explicit `--paper` guard and a confirm step.
- Requires TWS or IB Gateway running locally with the API enabled.
- **Safety:** default to read-only + paper; never auto-submit live orders.

### TradingView (`tools/tradingview/`)
No official public REST API, so:

- ✅ **MCP bridge (shipped, optional):** drive TradingView Desktop live from Claude
  in-session (quotes, study values, Pine levels) — see README → Optional power modules.
  The items below are still planned:
- **Webhook receiver** — a tiny local server that accepts TradingView alert webhooks
  and writes them as signals the skill can read (`data/signals/`).
- **Chart snapshots** — pull a chart image/levels for a symbol/timeframe for context.
- Optional Pine Script export of the skill's setups for alerting.

### Internationalization & multi-user (optional)
- ✅ **Chinese emails** — shipped (`--lang zh` / `OT_EMAIL_LANG=zh`).
- **A-share portfolio review** — extend the portfolio desk to 沪深 names via `ot cn` (China
  market hours / timezone, CNY sizing). Opt-in.
- **Multi-user delivery** — tailored emails to *other* users from their own watchlists (per-user
  `watchlist.<id>.json` + recipient), for people who share their book with you. Opt-in; never
  stores brokerage credentials.

---

### Daily-brief delivery
Getting the brief to you when away-from-desk:

- ✅ **Email (shipped)** — SMTP'd weekday mornings as styled **HTML** via launchd; headless,
  the most robust path. **Next:** user-tunable feeds (pick which sources the brief fuses —
  macro / news / smart money / options EV / TradingView). See `RELEASE_NOTES.md`.
- **Claude cloud routine** — a scheduled Claude agent runs the brief and emails/messages
  you. Survives a closed laptop (runs in the cloud / Cowork, not on your Mac).
- **Webhook** (Slack / Discord / Telegram) — POST the brief to a chat you read on mobile.
- **launchd notification** — local macOS banner; requires the repo outside `~/Desktop` (TCC).

---

## Later — the multi-agent desk

> **Future exploration, not a committed direction.** Captured so we can grow into it; the
> core stays a fast, no-dependency toolkit regardless. Inspired by, and learning from,
> [TradingAgents](https://github.com/TauricResearch/TradingAgents).

Map the existing skill workflows onto a TradingAgents-style pipeline, orchestrated
with Claude subagents (and/or the Agent SDK):

| TradingAgents role | OpenTrading mapping |
|--------------------|---------------------|
| **Analyst team** (fundamentals, sentiment, news, technical) | macro CLI + FinancialJuice CLI + technicals/options references |
| **Researcher team** (bull vs. bear debate) | two opposing subagents argue the setup; surface the disagreement |
| **Trader** | synthesizes into entry/stop/target/size (Workflow 3) |
| **Risk manager / portfolio** | risk.md rules: portfolio heat, correlation, drawdown gates |

Supporting pieces:

- **Backtesting engine** — turn Workflow 7 into a runnable `tools/backtest/`.
- **Journal store** — structured trade log (CSV/SQLite) feeding Workflow 6 analytics.
- **More no-key data** — FRED (with optional key), options IV/IVR, crypto funding rates.

---

## Principles for contributions

- Prefer **dependency-free stdlib** tools; make heavier deps (brokerage SDKs) optional and isolated per tool.
- Every data tool ships a `--format json` mode and a short README.
- Default to **read-only / paper**; any order-placing path must be explicit and confirmed.
- Keep secrets out of the repo; never commit `data/`.
- Everything stays **educational, not financial advice.**
