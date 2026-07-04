---
name: deep-research
description: >-
  Deep single-stock research (个股深度研究) — the two-track verdict: "能否长拿"
  (can I hold this for years? — fundamentals/moat/valuation) AND "现在能不能做"
  (is it a trade now? — trend/BIAS/zones), graded A–D and stress-tested by a
  bull-vs-bear pass. Multi-region (US · China A-share · Hong Kong), all no-key.
  Activate on: "deep dive / deep research / 深度研究 / 个股研究 on TICKER", "can I
  hold X long-term", "moat / 护城河 / 业绩 / 估值 / fundamentals of X", "is X
  over-extended / 乖离 / 错杀 / oversold". This is the slow, evidence-anchored
  single-name thesis — distinct from the pre-market, intraday, and news flows.
---

# Deep single-stock research (个股深度研究)

Produce an evidence-anchored verdict on ONE stock across two tracks — **hold-thesis
(能否长拿 — can it be held long?)** and **trade-setup (现在能不能做 — is the entry
good now?)** — graded
A–D and stress-tested by a bull-vs-bear pass. Multi-region: the data sources and
the *weighting* differ by market; the cognition is shared. Educational only —
not financial advice.

> **Borrowed cognition.** TradingAgents: analyst passes → **bull/bear debate** →
> a structured verdict, with the rule *"every claim cites a number from the data;
> never fabricate a price, level, or figure."* ScaleAlpha: the 5-factor spine
> (**Trend / Quality / Valuation / Catalyst**, Risk as a *penalty*) re-weighted by
> intent (hold ⇒ quality+valuation, trade ⇒ trend+catalyst), an A–D grade, and
> explicit horizon bands so the long-thesis and the entry call never blur.

## 1. Gather — region-aware, all no-key

```bash
ot research TICKER --market US|A|HK      # the data pack (see the region map)
ot decide   TICKER --market US|A|HK      # range plan (buy/trim/stop) + A–D grade
ot news --ticker TICKER --minutes 4320   # ~3-day name news (catalyst + tone)
```
Region extras:
- **US:** `ot options TICKER --dte 7` (dealer gamma / walls) · `ot smart` (Fear&Greed — contrarian).
- **A/HK:** the `ot research` pack already carries **筹码 (股东户数)** + **人气榜 (A)** — that *is* the A-share positioning/sentiment layer.

## 2. Two-track analysis (the core)

**Track A — hold-thesis (fundamental · 能否长拿).** *"Would I own this 9–24 months?"*
- **Moat (护城河):** pricing power (sustained high gross margin), ROE durability, scale / switching costs / network effects. *A ~70% gross margin held for years is itself a moat tell.*
- **Management & capital allocation (管理层):** ROE vs cost of capital; buyback/dividend discipline; insider / major-holder behavior (A-share: **股东户数 trend — falling holder count = big-money accumulation**); guidance-vs-delivery.
- **Earnings & growth (业绩):** revenue + net-profit YoY, margin trajectory, durability — flag **low-base distortions** (net profit +500% off a tiny base ≠ structural).
- **Valuation (估值):** PE / PB vs the name's *own history* and peers — cheap / fair / rich? A great business at a nosebleed multiple is a **Quality-A / Valuation-D split — say so.**
→ emit a **Quality grade + a Valuation grade.**

**Track B — trade-setup (technical · 现在能不能做).** *"Is the entry good right now?"*
- Trend (vs 20-day), **BIAS 6/12/24 (乖离)** (extended ⇒ don't chase; deeply negative ⇒ **oversold (错杀)** candidate), **volume-ratio (量比)** (confirmation / anomaly), the **buy/trim/stop zones** from `ot decide`, catalyst timing.
- US adds **dealer gamma / walls** (pin vs squeeze) + **Fear&Greed**; A-share adds **popularity rank (人气榜)** (surging = retail crowding = over-extension risk) + **holder concentration (筹码)** (dispersing vs tightening).
→ emit a **trade-timing call + the zones.**

## 3. Bull-vs-bear pass (stress test — do NOT skip)

Write a tight **BULL case** (growth · moat · catalyst · undervaluation · positioning) and a tight **BEAR case** (valuation · decelerating growth · competition · technical extension/crowding · balance-sheet risk). **Each must rebut the other's strongest point**, every claim tied to a §1 number. Then judge which side the evidence favors. *This adversarial step is what makes it research, not a data dump.*

## 4. Verdict (structured)

- **Grade A–D** — composite of Quality · Valuation · Trend · Catalyst, minus Risk. A = strong hold/buy-the-zone; D = avoid.
- **Two-track verdict:** one line each — **hold** (yes/no + why) and **trade** (now / wait-for-zone / avoid).
- **Horizon:** short (2–6 wk) · medium (2–6 mo) · long (9–24 mo).
- **Position plan:** size + the buy/trim/stop zones + the invalidation, tagged to the horizon.

## 5. Output format (the report)

`Verdict + Grade` → `Two-track summary (hold vs trade)` → `Moat / Quality` → `Management` → `Earnings / Financials` → `Valuation` → `Technicals (trend · BIAS · volume-ratio · zones)` → `Sentiment / Positioning (US: GEX · F&G / A: 人气榜 · 股东户数)` → `Catalysts & Risks` → `Position plan (horizon-tagged)` → disclaimer. Every line cites a real number from §1. **One language per report:** English reports stay pure English; zh rosters get every section title translated (两轨摘要 · 护城河 · 管理层 · 业绩/财务 · 估值 · 技术面 · 情绪/筹码 · 催化与风险 · 仓位计划).

## Region tuning

| | US | China A-share | Hong Kong |
|---|---|---|---|
| Fundamentals | Yahoo crumb (PE/PB/利润率/营收增速/ROE) | **Eastmoney F10 — richest** (EPS/营收/净利/毛利/ROE/YoY) | Eastmoney HK F10 (EPS/营收/ROE/毛利) |
| Positioning / sentiment | dealer GEX + Fear&Greed | **股东户数→筹码集中度 + 人气榜** (retail-driven) | southbound-flow context (no 股东户数 — HKEX doesn't disclose) |
| Technicals | BIAS / 量比 / trend (Yahoo) | same | same |
| Macro lean | US rates / FOMC / USD | China policy & liquidity (**no US event-gate**) | **US-rates + USD sensitive** (liquidity headwind) |
| Tuning | options-EV heavy | 筹码 / 人气 are strong signals (retail-momentum market) | rates-up = HK headwind; value/dividend resilient |

## Discipline
- **Never fabricate a price / level / figure** — cite `ot research` / `ot decide`; if a metric is missing, write "n/a", don't invent.
- **Separate hold-thesis from trade-setup** — a great long-term business can be a poor entry today (and vice-versa).
- Flag **low-base distortions**, **crowding** (surging 人气/股东户数), **nosebleed valuation** (PE/PB vs history).
- Educational only — **not financial advice**.
