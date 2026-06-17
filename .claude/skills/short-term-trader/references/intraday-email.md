# Intraday analysis & email (盘中) + the apex-predator lens

The **on-demand, market-open** counterpart to the pre-market daily email. Pre-market
runs on a schedule (launchd, see [[opentrading-daily-email]]); **intraday is requested**
("盘中分析", "real-time portfolio", "between-market read", "intraday actions"). Output is a
position-aware Chinese (or `--lang en`) note with **concrete +/- actions** and **new ideas**,
delivered via the same Gmail pipeline.

> ⚠️ Educational analysis only — not financial advice.

## 0. Event-calendar gate — DO THIS FIRST

**Before any analysis, check scheduled catalysts.** A book that walks into FOMC/CPI/OPEX
un-warned is the documented failure mode (2026-06-17: an intraday note missed it was an FOMC
day; the BTC-beta name (MSTR) then fell on the hawkish hold — see private DECISION_LOG).

```bash
ot decide QQQ                          # prints "event: FOMC/CPI/OPEX" if today is one
ot news --grep "fomc|cpi|powell|fed"   # confirm the catalyst + timing on the tape
```
- **Within ~24h of a binary (FOMC / CPI / major earnings / OPEX):** LEAD the note with it —
  defer adds, raise cash or hedge, and **size down the highest-beta name**. For a BTC-beta book
  that's **MSTR / IBIT on a Fed day** (chain: FOMC → rates/USD → BTC → MSTR).
- If `ot decide` says "none known", still sanity-check the Fed/BLS calendar — the hardcoded
  `KNOWN_EVENTS` in `tools/sim/decide.py` can lag; extend it when it does.

## 1. Gather live context

```bash
ot watch                               # your book + live marks (reads watchlist.json)
ot quote MSTR ORCL ... QQQ ^VIX        # book + the watchlist 'watch' universe + vol
ot macro                               # intraday rates/liquidity score
ot smart                               # CNN + crypto Fear&Greed, BTC funding (contrarian)
ot news --window today                 # intraday tape
ot decide <TICKER> --dte 5             # learned-policy CALL/PUT/NO-ACTION per name
```
Also read `watchlist.json` → `positions` (shares/cash) **and** `watch` (macro ETFs +
apex candidates to fold in: GLD/SLV/IBIT/TLT, NBIS/ASTS/SNDK/OKLO/RKLB, …).

## 2. Analysis structure (the template)

1. **盘中定位 (regime box, `p.regime`)** — index vs. leaders (divergence = narrow rally),
   VIX level/Δ, macro score, the news tape, Fear&Greed. One conclusive lean: *selective /
   risk-on / defensive*.
2. **持仓快照 (table)** — `标的 | 股数 | 现价 | 今日 | 占股票仓 | 操作`. Compute **weights**;
   flag any single-name > ~30–40% (concentration).
3. **逐仓操作** — per name: `ot decide` read + the **learned discipline**: lock winners into
   spikes (don't let them round-trip), trim the **heaviest-and-weakest**, never add into a
   parabolic candle. Respect user-set levels (e.g. "hold ORCL to $200").
4. **新增标的建议** — edge-name dip-buys (NVDA/AMZN/GOOG: uptrend + pullback) **plus the
   apex-predator lens (§3)**.
5. **现金与风控** — cash plan + the governor: ≤5% premium/trade, **never size up after a
   loss**, no index 0DTE on a jumpy/event tape; 0DTE QQQ only fade-gap + VIX-confirm.
6. **disclaimer (`p.disclaimer`)**.

## 3. The apex-predator lens (顶尖掠食者) — hunt asymmetry, enter with discipline

The user wants **asymmetric multibaggers** (their hits: SNDK ~10x 2025, NBIS $100→$284, ASTS).
Be a predator *and* a survivor:

- **Hunt by theme, name the early leaders:** AI-power/nuclear (OKLO, SMR, VST), AI-neocloud
  (NBIS, CRWV), memory supercycle (SNDK, MU), space/direct-to-cell (ASTS, RKLB), quantum
  (IONQ), stablecoin/crypto-infra (CRCL, IBIT).
- **Asymmetry, not YOLO:** apex bets are **small (≈1–3% each)** with **10x potential and
  defined, losable risk** — a basket of lottery tickets, never a concentrated bet.
- **DISCIPLINE is the edge:** **do not chase the green candle.** `ot decide` catches the trap —
  a **gap-up in a downtrend reads as a fade/PUT** (e.g. ASTS/RKLB on a +4% pop). Enter on a
  **pullback in an uptrend** (e.g. VST) or a **base/reclaim**, never a +6% blowoff or a +20%
  5-day extension (e.g. NBIS when hot → wait for the dip).
- **Respect the cycle:** a name that **already 10x'd** (SNDK/MU memory) is **late/crowded** →
  that's where you *take profits*, not initiate. Hunt early/mid-innings themes instead.
- **Tie to the book:** prefer apex names that **diversify** the existing BTC-beta + AI-capex
  concentration, or that the macro tape favors (e.g. TLT/GLD when VIX rises).

## 4. Render + send (Chinese, Gmail)

Write the analysis as a semantic HTML *fragment* (tags: `p.regime`, `h2`, `table`,
`ul/li`, `span.up/down`, `p.disclaimer`), then:

```bash
# render -> Outlook-safe HTML (+ plain-text on stdout)
python3 tools/brief/wrap_html.py --out /tmp/intraday_zh.html \
  --date "盘中速递 · <日期> · 美东<HH:MM>" < /tmp/frag.html > /tmp/intraday_zh.txt
# localize the English chrome -> 中文 (header "· Pre-Market Read" -> "· 盘中组合分析";
# footer English -> 中文); then send via the .env Gmail creds:
python3 tools/email/send_email.py \
  --subject "OpenTrading — 盘中组合分析与操作（中文）· <日期>" \
  --html-file /tmp/intraday_zh.html --body-file /tmp/intraday_zh.txt
```
(`OT_EMAIL_TO` in `.env` is the default recipient; pass `--to` for someone else.)

> Privacy: `watchlist.json` stays git-ignored and is never committed.
> Educational only — not financial advice.
