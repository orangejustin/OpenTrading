# OpenTrading

**A local-first trading copilot for Claude Code — macro-first, risk-first, zero API keys.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#requirements)
[![API keys: none](https://img.shields.io/badge/API_keys-none-success.svg)](#requirements)
[![Claude Code: native](https://img.shields.io/badge/Claude_Code-native-8A2BE2.svg)](#ask-claude)

**English** | [简体中文](README.zh-CN.md)

OpenTrading fuses **macro, news, smart-money positioning, and options gamma** into one
opinionated read — then turns it into a concrete **CALL / PUT / NO-ACTION** through a
decision engine that follows a learned, risk-first policy. Everything runs on your
machine: no SaaS, no keys, no data leaving your laptop. It's the **open alternative to
closed alpha-simulation platforms** — pair the trading *skill* (the expertise) with small,
dependency-free *data CLIs* (the live data), and let Claude drive both.

> ⚠️ **Educational only — not financial advice.** Trading carries substantial risk of loss.

---

## Quickstart

```bash
git clone https://github.com/orangejustin/OpenTrading
cd OpenTrading
bash install.sh        # puts `ot` on PATH + a health check — no keys, nothing to compile
```

Everything is **one command, `ot`**:

```bash
ot                     # the morning read: macro + news + smart money + options + your book
ot news --window premarket   # live FinancialJuice headlines (public RSS — no account)
ot macro               # scored intraday macro dashboard (SOFR / 2s10s / TGA / RRP)
ot options SPY --dte 7 # put/call + dealer gamma (GEX) + gamma walls
ot decide QQQ --dte 0  # one concrete call: CALL / PUT / NO-ACTION + conviction + size
ot help                # every subcommand
```

> Don't want to touch your PATH? Skip `install.sh` and run in place: `bin/ot …`

**New here?** Start with the three [hero workflows](WORKFLOWS.md) — *morning read*, *is it
safe to size up?*, and *grade my book* — each is one command plus one prompt to Claude.

---

## Why it's different

- **Local & keyless.** Every core tool runs on public, no-auth endpoints (or a `curl`
  fallback). Nothing to sign up for, nothing phoning home.
- **Opinionated, not a data dump.** It doesn't just fetch — it *scores* macro, flags
  sentiment/credit divergences, reads dealer gamma, and gives a per-position game plan.
- **A policy, not vibes.** `ot decide` encodes a written, risk-first strategy
  (selection > timing, 0DTE done right, a hard daily-loss stop) — auditable in the repo.
- **Claude-native.** An embedded skill activates on any trading question and pulls live
  data through `ot` for you. Open it in Claude Code and just ask.
- **Private by design.** Your positions and secrets are git-ignored and never shippable
  (see [Privacy](#privacy)).

---

## What you get

| Piece | Command | What it does |
|-------|---------|--------------|
| **Market report** | `ot` | Fuses macro + news + smart money + options + your book → one regime read |
| **Deep report** | `ot report --deep` | Splits the pack into parallel analyst desks + a synthesis pass (multi-agent prototype) |
| **News** | `ot news` | FinancialJuice squawk (public RSS) — windowed, ticker-filtered, storable |
| **Macro** | `ot macro` | SOFR / 2s10s / TGA / RRP → scored put/call bias |
| **Smart money** | `ot smart` | CNN + crypto Fear&Greed, BTC funding (contrarian) |
| **Options** | `ot options` | Put/Call + dealer gamma (GEX) + gamma walls (CBOE) |
| **Event gate** | `ot catalysts` / `ot earnings` | FOMC/CPI/PCE/NFP/OPEX + per-name 财报 → size-up verdict |
| **Quotes** | `ot quote` | No-key quotes incl premarket + `^VIX`; `ot cn` for China A-shares |
| **Decision engine** | `ot decide` | CALL / PUT / NO-ACTION + conviction + size, from the learned policy |
| **Daily email** | `ot email` / `ot schedule` | Position-aware, Outlook-safe HTML pre-market brief via SMTP |

Add `--json` to any tool for machine-readable output. Full help: `ot help`.

---

## Ask Claude

Open the folder in **Claude Code** (or Claude Desktop) and just ask — the embedded
**short-term-trader** skill activates automatically and pulls live data through `ot`:

- *"Give me my morning macro brief — calls or puts on QQQ today?"*
- *"Any FinancialJuice news on NVDA in the last hour? Store it."*
- *"NVDA broke $950 on volume, RSI 62, account $30k — how do I trade it?"*

The skill enforces the house rules on every answer: **macro first → setup second → size
third**, **risk before opportunity**, **news only matters in context**, and an
educational-not-advice disclaimer. Its eight workflows cover macro bias, news-impact,
trade setups, options, crypto sizing, the P&L journal, backtesting, and portfolio review.

---

## Daily pre-market email

A **position-aware** pre-market brief in your inbox every weekday — the same fusion as
`ot`, written up by Claude and delivered as styled, **Outlook-safe HTML** (plain-text
fallback). Each run fuses macro bias, smart-money sentiment, options gamma, last-24h news
tied to *your* names, a $-weighted book table, and the day's event gate.

```bash
cp .env.example .env       # set OT_SMTP_* + OT_EMAIL_TO  (Resend works with no 2FA)
ot email --dry-run         # confirm config (no send)
ot email                   # one-off send   ·   --lang zh for 简体中文
ot schedule email          # weekdays 08:30 local (macOS launchd) · `… email uninstall` to remove
```

> macOS: launchd can't read repos under `~/Desktop`, `~/Documents`, or `~/Downloads` (TCC)
> — keep the repo elsewhere (e.g. `~/OpenTrading`). Details: [`tools/email/README.md`](tools/email/README.md).

---

## `ot decide` — the policy in one call

`ot decide TICKER --dte N` turns the skill's written policy into a single concrete call —
**CALL / PUT / NO-ACTION** + conviction + size — from no-key data (price/gap/trend + `^VIX`):

```bash
ot decide QQQ  --dte 0     # 0DTE: fade-gap + VIX-confirm + skip-events + selectivity
ot decide NVDA --dte 5     # swing: momentum calls on names you read well
```

It encodes [`references/learned-strategy.md`](.claude/skills/short-term-trader/references/learned-strategy.md)
(selection > timing; a hard daily-loss stop; never size up after a loss) and points you at
`ot options` / `ot news` / `ot macro` for the IV / gamma-wall / news confirmation it can't
see. **NO-ACTION is a position.**

---

## Privacy

Your holdings and secrets **never** enter git and are **never** part of any release:

| What | Lives in | Status |
|------|----------|--------|
| Your positions | `watchlist.json` | **git-ignored** — only `watchlist.example.json` is tracked |
| Email / API credentials | `.env` | **git-ignored** — only `.env.example` is tracked |
| Fetched news, reports, briefs | `data/` | **git-ignored** |

```bash
cp watchlist.example.json watchlist.json   # then edit with YOUR positions
cp .env.example .env                        # then add your SMTP creds
```

The `*.example` files are placeholders; the real ones stay on your machine. That
separation is what makes the repo safe to share. **Never commit `.env` or `watchlist.json`.**

---

## Optional power modules

The core above is the **plain tier**: free, keyless, zero manual steps. These add more but
are **optional** and need manual setup — nothing in the core depends on them.

- **TradingView (shipped)** — bridge your TradingView Desktop app to Claude via the
  [`tradingview-mcp`](https://github.com/tradesdontlie/tradingview-mcp) server, then ask
  *"analyze MSTR with the TV data"* and it reads live quotes / study values / your Pine
  levels off your chart. *(ToS-gray; runs against your own logged-in client.)*
- **IBKR (planned, `tools/ibkr/`)** — Interactive Brokers via
  [`ib_async`](https://github.com/ib-api-reloaded/ib_async): live quotes, option chains,
  positions, and **paper** execution behind an explicit guard. Never auto-submits live orders.

---

## Roadmap

Where it's headed (shipped history in [`RELEASE_NOTES.md`](RELEASE_NOTES.md); detail in [`ROADMAP.md`](ROADMAP.md)):

- **From email → web.** An interactive, local dashboard over the same data/news fusion —
  charts, the event calendar, opportunity cards, and a personalized strategy lab.
- **Personalized simulation.** A transparent, local strategy simulator that tunes the
  decision policy to *your* trading — open, auditable, on your own machine.
- **Multi-agent research desk.** Claude/Codex as the mastermind: specialist agents
  (macro, news, options, risk) run in parallel and a synthesis pass fuses them — more
  coverage, fewer tokens. Learning from [TradingAgents](https://github.com/TauricResearch/TradingAgents).
- **Email v2 — user-tunable feeds.** Pick which sources the daily brief fuses, opt-in per source.
- **More no-key data** — FRED, options IV/IVR, funding curves.

---

## Requirements

Python 3.9+ (standard library only; uses `certifi` if installed, else falls back to system
`curl`). No keys, no paid feeds. For a reproducible dev environment, `ot` auto-prefers
[`uv`](https://github.com/astral-sh/uv) when installed (`uv sync` for locked deps) and
otherwise runs on plain `python3` — override with `OT_PYTHON`, disable uv with `OT_NO_UV=1`,
inspect with `ot doctor`.

---

## Credits & disclaimer

Built by [@orangejustin](https://github.com/orangejustin). The multi-agent direction draws
inspiration from [TradingAgents](https://github.com/TauricResearch/TradingAgents).

Analysis is for **educational purposes only** — **not financial advice**. Markets are
risky; size accordingly and do your own research.
