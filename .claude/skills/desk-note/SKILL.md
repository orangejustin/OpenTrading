---
name: desk-note
description: >-
  Produce and email the OpenTrading "desk note" — a clean, TABLE-based brief that
  fuses news, macro, sentiment, dealer gamma, per-name range plans, the engine
  allocation, the policy and the risk read into one email. Use whenever the user
  asks to email an intraday / daily / weekly portfolio analysis, a roster brief,
  a 日内总结 / 盘中速递, or "a desk note" — for their own book or another roster,
  US or China A/HK, in English or Chinese. Multi-region, language-agnostic, no-key.
---

# Desk Note — the fused, table-based portfolio brief

One skill that turns the whole `ot` stack into a single neat email:
**news + logic + price ranges + alpha + intraday decision + portfolio +/- +
新增标的建议 + the policy + 风控/纪律.** It reuses the existing chrome
(`tools/brief/wrap_html.py`) and transport (`tools/email/send_email.py`) — do not
reinvent them. Always **re-fetch fresh data** (never recycle a prior note).

## 0. Who + which language (read this first)

- Recipient + language come from the roster file: `watchlist.json` (the user, `lang: en`)
  or `watchlist.<id>.json` (e.g. Jing, `lang: zh`). **The user's own notes are ENGLISH;
  Chinese is only for a `lang: zh` roster.** Write the entire body in the roster's language
  (keep tickers, codes, numbers and HTML tags/class names exactly as-is).
- `send_email.py` has **no `--cc`** — put every recipient in `--to` (comma-separated).
- Never leak one roster's positions to another recipient.

## 1. Gather (fresh, region-aware)

Shared macro/regime (once):
```
ot news --window today      # or: ot news digest --days 7   (weekly note)
ot macro                    # auto-score -> LEAN PUTS/CALLS
ot smart                    # CNN + crypto Fear&Greed, BTC funding
```
Per market — positions come from the roster's `positions`, alpha from its `watch` (kind `apex`):

| Region | Quotes | Range plan + call | Extra edge | Benchmark |
|--------|--------|-------------------|-----------|-----------|
| **US** | `ot quote …` | `ot decide T --market US` | `ot options SPY QQQ <names> --dte 7` (GEX/walls), `ot strategy` | ^GSPC |
| **A-share** | `ot cn <codes>` | `ot decide <code> --market A` | 筹码/人气 via `ot research` (Eastmoney F10) | CSI300 000300.SS |
| **HK** | `ot cn <codes>` | `ot decide <code> --market HK` | `ot research` (F10, rates-sensitive) | ^HSI |

Every printed number in the note must trace to one of these — no fabricated levels.

## 2. Compose — the fragment (semantic HTML only, tables for everything scannable)

Emit a bare fragment (no `<html>/<head>/<body>`, no markdown/code-fences). `wrap_html.py`
inlines all CSS. Use only these tags/classes (they map to styled chrome):

- `<p class="regime">` — one dark callout: the single biggest driver + its number + the read.
- `<table>` with `<th>`/`<td>`; **`class="num"`** on number cells (right-aligned, tabular figures),
  **`class="tk"`** on the ticker cell (bold).
- Up/down: `<span class="up">`/`<span class="down">`. 
- Action/grade badges (chips): `<span class="buy">` `trim` `hold` `watch` `avoid` (action) and
  `<span class="grade">` (A/B/C/D). They degrade to bold colored text in Outlook.
- `<p class="disclaimer">` — educational-only footer line.

**Section order (this is the contract):**
1. **Regime** — `p.regime`. Macro score, breadth/credit, gamma, the one-line read.
2. **News → what it means** — 2-col table `Driver | Read for the book` (4–6 rows; each cites a number).
3. **Your book — levels & intraday call** — table `Name | Last | Day | Call | Levels (buy · trim · stop) | Read`,
   one row per held name; `tk` ticker (+ a muted `shares · tier` sub-line), `num` Last/Day, an action badge,
   the mechanical zones, a one-line read. This is the "+/- of current portfolio + intraday decision".
4. **Alpha watch & new-name ideas (新增标的建议)** — table `Name | Last | Day | Theme | Grade | Plan / levels`;
   grade badge + action badge; end with an `AVOID` row for downtrend names.
5. **Engine strategy** — short `<p>`: top weights + cash from `ot strategy`, flag extended names to wait on.
6. **The policy — our discipline** — 2-col table `Principle | The rule` (selection>timing · ranges-not-points ·
   0DTE-done-right · risk governor · apex lens · event-aware). Keep it stable; tie one rule to today (e.g. OPEX).
7. **Risk & discipline — today** — `<ul>`, 3 points tied to today's numbers.
8. `<p class="disclaimer">`.

Keep it ~500–650 words. Mark every move up/down with a span; state the "so what"; no filler.

## 3. Render + send

```
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python   # repo venv has certifi
$PY tools/brief/wrap_html.py --out /tmp/desk.html \
    --lang <en|zh> --header "<Intraday Desk Note | 盘中速递>" --date "<Wed … · 3:24 PM ET>" \
    < /tmp/fragment.html > /tmp/desk.txt          # stdout = plain-text alternative
$PY tools/email/send_email.py --subject "<…>" --to <recipient(s)> \
    --html-file /tmp/desk.html --env-file .env < /tmp/desk.txt
```
Sanity before send: `grep -c 'class=' /tmp/desk.html` must be **0** (all inlined);
confirm badge backgrounds + `text-align:right` are present; confirm no Chinese leaks into a `lang:en` note.

## Discipline

- **Separate the two tracks:** a *hold* thesis (ride ORCL to the target) is not a *trade* setup
  (the engine's CALL/PUT/NO-ACTION). Say which you mean.
- **Never chase the green candle** — buy the zone *below* spot; flag extended (`+x% vs 20d`),
  crowded, or nosebleed-valuation names as wait/take-profit, not initiate.
- **Event-aware** — name FOMC/CPI/OPEX when near; default to defer-adds/raise-cash.
- **Always disclaim** — educational only, not financial advice. Re-fetch every time.
