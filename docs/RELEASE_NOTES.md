# Release Notes

Internal development changelog for **OpenTrading**. We are **not publicly released yet** —
there are no published packages, git tags, or GitHub Releases. We develop on our own and
cut internal versions here so the history reads like a real project. Newest first.

> 🔒 **Private by design.** Your positions and secrets live only in git-ignored files
> (`watchlist.json`, `.env`) and are **never** committed or released publicly. See
> [README → Privacy & your data](../README.md#privacy--your-data).
>
> ⚠️ **Educational only — not financial advice.**

---

## How we ship (internal workflow)

- **Versioning** — internal SemVer-ish `v0.MAJOR.MINOR`. No public tags / GitHub Releases yet.
- **Branches → MR** — every change lands on a short-lived branch and merges via a **merge
  request (MR)** the maintainer approves. `main` advances *only* through merged MRs; no
  direct pushes to `main`.
- **Tiers stay honest** — the **plain** install must keep working with **zero keys and zero
  manual steps**. Anything that needs manual setup (TradingView, IBKR) is an **optional
  power-user module** the core never depends on.

---

## [Unreleased]

_Nothing in flight. Open ideas live in [Future work](#future-work) and [`ROADMAP.md`](ROADMAP.md)._

---

## v0.6.0 — 2026-06-17 — "Simulation engine: learn a winning policy from your own P&L"

### Added
- **`tools/sim/` — live decision engine.** `ot decide TICKER [--dte N]` emits a concrete
  **CALL / PUT / NO-ACTION** + conviction + size from a learned, forward-validated policy
  (0DTE: fade-gap + VIX-confirm + skip-events + selectivity; swings: momentum calls on names you
  read well), using no-key data.
  - `yfhist.py` — no-key Yahoo daily bars + `^VIX`/`^TNX`, cached to `/tmp/ot_sim_cache`.
- **Skill:** `references/learned-strategy.md` (the qualitative winning policy), `references/intraday-email.md`
  (intraday 盘中 analysis + Chinese email template + the apex-predator asymmetric-multibagger lens),
  and **Workflow 9 — Backtest-Informed Decision**.

### Notes
- **Privacy:** your positions live only in git-ignored `watchlist.json`; the `/tmp` cache and `.venv`
  are git-ignored. Educational analysis only — **not financial advice**.
- **Honest limits:** daily granularity (intraday entry timing not modeled); IV / gamma-walls / news
  are live-only confirmation (`ot options` / `ot news` / `ot macro`), not historically backfillable.

---

## v0.5.0 — 2026-06-17 — "Multi-user rosters, HK quotes, grow-the-book desk"

### Added
- **Hong Kong quotes:** `ot cn hk00700 09988` (Eastmoney market 116, HKD) — currency is now
  derived per market (CNY / HKD / USD) and shown in the table + JSON. Verified live.
- **Multi-user rosters:** `watchlist.<id>.json` (git-ignored) with `owner` / `recipient` /
  `lang`, tier-based positions (`tier`: core / secondary / watch when share counts are unknown),
  and per-position `market` (US / A / HK). `watchlist.example.json` documents the full schema,
  including a **`cash`** field (dry powder).
- **Grow-the-book desk:** the portfolio-desk skill now recommends **ADD / NEW / HEDGE**, not
  just TRIM / HOLD — deploy cash into adds or **new stocks / ETFs / options**, with multi-market
  routing (US → `ot quote` / `ot options`, A & HK → `ot cn`) and tier-weighting for share-less books.

### Changed
- **`.env.example`** rewritten Gmail-first (the path that emails *anyone*), documenting the
  hard-won caveats: Resend free = owner-only, **Outlook personal SMTP app-passwords disabled by
  Microsoft (535)**, Gmail app-password = reliable.
- **`.gitignore`** now also excludes `watchlist.*.json` (per-user rosters) and `.env.bak`.

---

## v0.4.0 — 2026-06-16 — "i18n + A-shares + feed flexibility"

### Added
- **China A-shares (optional):** `ot cn` — no-key Eastmoney quotes for 沪深 / A股 (indices +
  stocks, aliases `shcomp`/`csi300`/…, `--format json`). Stdlib + curl, no `akshare` dependency.
  The data layer for a future A-share portfolio review. (`tools/china/`)
- **Chinese-language emails:** `--lang zh` (news email) / `OT_EMAIL_LANG=zh` (daily brief) write
  the entire email in fluent 简体中文 (tickers / prices / levels kept in original form).
- **Multi-source news:** `ot news --feeds financialjuice,cnbc` aggregates direct provider RSS
  (CNBC Top/Markets/Earnings/Economy + Yahoo per-ticker via `--tickers`), each headline
  **source-tagged**; `--source cnbc` filters by source. The public FinancialJuice RSS stays the
  default (provider-agnostic, single author); `OT_FJ_FEED_URL` can point at a personalized PRO
  feed. Reuters/Bloomberg dropped their free RSS, so they're not included.

### Notes
- Verified live: `ot cn` (上证指数 / 茅台 / 比亚迪), Chinese render (~1.4k CJK chars), the
  `--source` word-boundary filter, and both email scripts `bash -n` clean.

---

## v0.3.0 — 2026-06-16 — "Pre-market email, styled"

The daily brief became a real, good-looking, autonomous email — and the first optional
power module (TradingView) came online and was verified live.

### Highlights
- 📧 **Autonomous daily pre-market email** — weekdays 08:30 PT, position-aware, delivered
  with no machine babysitting (proven in production 2026-06-16: launchd fired and sent at
  08:30, exit 0).
- 🎨 **Styled, Outlook-safe HTML** brief — regime banner, $-weighted positions table, and
  Macro / Smart-money / Options-EV / 24h-News / Concentration / Watch-today sections, every
  claim tied to a real number.
- 📈 **TradingView** wired up as the first **optional** power module and **verified live**.

### Added
- `tools/brief/wrap_html.py` — stdlib-only, Outlook-safe HTML renderer: inlines per-tag CSS
  (Outlook ignores `<head>` styles), drops unsafe tags, wraps in a 640px branded shell, and
  emits a plain-text multipart alternative. `--raw` wraps the data pack as a fallback.
- `tools/brief/daily_email_claude.sh` (HTML rewrite) — gather (macro + smart money + 24h
  news + quotes + options/GEX + BTC, position-aware) → `claude -p` (no tools, no prompts →
  HTML fragment) → render → SMTP send. Falls back to emailing the raw data pack if Claude
  returns nothing. Preview without sending:
  `OT_EMAIL_RENDER_ONLY=1 OT_EMAIL_HTML_OUT=/tmp/x.html bash tools/brief/daily_email_claude.sh`.
- launchd schedule (`ot schedule email`, weekdays 08:30 local) — verified firing in the real
  launchd context (`data/briefs/_launchd.log`).
- **TradingView MCP** (optional, manual setup) — [`tradesdontlie/tradingview-mcp`](https://github.com/tradesdontlie/tradingview-mcp)
  bridged to TradingView Desktop over the Chrome DevTools port; `tv_health_check` verified
  (`cdp_connected: true`, `api_available: true`). Drive it live in-session ("analyze MSTR
  with the TV data").

### Fixed
- `tools/options/opt.py` — `render_table` crashed (`NoneType` format) when a position had no
  options chain (e.g. SPCX), blanking the **entire** dealer-gamma section. Now degrades to
  `n/a` per field via a `_fmt()` helper + `.get()`.

### Changed
- Repo relocated to `~/OpenTrading` (out of `~/Desktop`): macOS TCC blocks launchd from
  reading `~/Desktop`, `~/Documents`, `~/Downloads`. Old path left as a convenience symlink.
- `HANDOVER.md` retired → folded into this file (changelog + future work) and `README.md`
  (user-facing setup, privacy, optional modules).

### Ops notes / gotchas (carried forward)
- **macOS TCC** — launchd cannot read repos under `~/Desktop`, `~/Documents`, `~/Downloads`.
- **Runner** — `bin/ot` prefers `uv run --no-project` (dodges the framework-Python launchd
  hang), else `python3`. `OT_PYTHON` overrides, `OT_NO_UV=1` disables, `ot doctor` shows it.
- **SSL on macOS** — framework Python ships an empty cert dir; `send_email.py` repairs the
  context (`SSL_CERT_FILE` → certifi → `/etc/ssl/cert.pem` → homebrew bundle).
- **Git identity is repo-local** — `orangejustin <zechengli@outlook.com>`, set inside this
  repo only so a separate work identity stays untouched.
- **TradingView `quote_get` gotcha** — it returns the **current chart symbol** only; its
  `symbol` arg is ignored. `chart_set_symbol` first (exchange-qualified, e.g. `NASDAQ:MSTR`),
  then read on the next call. Prefer `tv_launch` over `open -a` (handles kill + debug port).

---

## v0.2.0 — "Autonomous daily email (text)" · commit `5489d5f`

- `tools/email/send_email.py` — provider-preset SMTP sender (Resend / Gmail / Outlook / …),
  macOS SSL repair, dry-run, `--html-file` multipart. Credentials from git-ignored `.env`.
- `tools/brief/daily_email_claude.sh` (first version) — Claude-written plain-text brief.
- Cross-machine setup handover doc (the predecessor of this file).

## v0.1.0 — "Unified `ot` CLI + no-key data toolkit" · commits `522275f…fdd979f`

- Single dispatcher `bin/ot` fronting every tool (`macro | smart | news | quote | options |
  watch | report | email | brief | schedule | doctor`).
- No-API-key data CLIs: FinancialJuice RSS news, gov macro (SOFR / 2s10s / TGA / RRP),
  CNN/crypto Fear&Greed + BTC funding, CBOE options (GEX / walls), Yahoo quotes, Coinbase BTC.
- `uv`-aware runner + symlink-safe root; `install.sh` puts `ot` on PATH and runs `ot doctor`.
- Embedded Claude skills (`short-term-trader`, `market-report`); position-aware watchlist.

---

## Future work

Near-term, concrete plans (the long view lives in [`ROADMAP.md`](ROADMAP.md)):

- **Email v2 — user-tunable feeds.** Let each user choose *which* sources the brief fuses
  — macro · FinancialJuice 24h news · smart money · options EV/GEX · TradingView — opt-in
  per source via `.env` / `watchlist.json` config. Today the brief always includes them all.
- **More optional power modules** (manual setup, never required by the core):
  - **IBKR** (`tools/ibkr/`) — live quotes / option chains / positions; paper execution
    behind an explicit guard, via [`ib_async`](https://github.com/ib-api-reloaded/ib_async).
  - **TradingView** — fold live chart / study / Pine levels into the report (today:
    in-session, on-demand only).
- **More no-key data CLIs & APIs** — FRED, options IV/IVR, funding curves.
- **Multi-agent research desk (future exploration).** *Not a current direction* — a later
  goal to grow multi-agent capabilities (analyst → bull/bear debate → trader → risk manager),
  learning from [TradingAgents](https://github.com/TauricResearch/TradingAgents). The core
  stays a fast, no-dependency toolkit regardless.

---
*Educational only — not financial advice.*
