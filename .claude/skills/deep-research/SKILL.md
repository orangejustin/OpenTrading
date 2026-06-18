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

Produce an evidence-anchored verdict on ONE stock across two tracks — **能否长拿**
(fundamental hold-thesis) and **现在能不能做** (technical trade-setup) — graded
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

**Track A — 能否长拿 (hold-thesis · fundamental).** *"Would I own this 9–24 months?"*
- **护城河 (moat):** pricing power (sustained high 毛利), ROE durability, scale / switching costs / network effects. *A 毛利 ~70% held for years is itself a moat tell.*
- **管理层 / 资本配置 (management):** ROE vs cost of capital; buyback/dividend discipline; insider / major-holder behavior (A-share: **股东户数 trend — falling = big-money accumulation**); guidance-vs-delivery.
- **业绩 / 成长 (earnings/growth):** revenue + net-profit YoY, margin trajectory, durability — flag **low-base distortions** (净利 +500% off a tiny base ≠ structural).
- **估值 (valuation):** PE / PB vs the name's *own history* and peers — cheap / fair / rich? A great business at a nosebleed multiple is a **Quality-A / Valuation-D split — say so.**
→ emit a **Quality grade + a Valuation grade.**

**Track B — 现在能不能做 (trade-setup · technical).** *"Is the entry good right now?"*
- Trend (vs 20-day), **乖离 BIAS 6/12/24** (extended ⇒ don't chase; deeply negative ⇒ **错杀/oversold** candidate), **量比** (confirmation / anomaly), the **buy/trim/stop zones** from `ot decide`, catalyst timing.
- US adds **dealer gamma / walls** (pin vs squeeze) + **Fear&Greed**; A-share adds **人气榜 rank** (surging = retail crowding = over-extension risk) + **筹码** (dispersing vs tightening).
→ emit a **trade-timing call + the zones.**

## 3. Bull-vs-bear pass (stress test — do NOT skip)

Write a tight **BULL case** (growth · moat · catalyst · undervaluation · positioning) and a tight **BEAR case** (valuation · decelerating growth · competition · technical extension/crowding · balance-sheet risk). **Each must rebut the other's strongest point**, every claim tied to a §1 number. Then judge which side the evidence favors. *This adversarial step is what makes it research, not a data dump.*

## 4. Verdict (structured)

- **Grade A–D** — composite of Quality · Valuation · Trend · Catalyst, minus Risk. A = strong hold/buy-the-zone; D = avoid.
- **两轨结论:** one line each — **长拿** (yes/no + why) and **短做** (now / wait-for-zone / avoid).
- **Horizon:** 短(2–6周) · 中(2–6月) · 长(9–24月).
- **仓位计划:** size + the buy/trim/stop zones + the invalidation, tagged to the horizon.

## 5. Output format (the report)

`Verdict + Grade` → `两轨摘要 (长拿 vs 短做)` → `护城河 / Quality` → `管理层` → `业绩 / 财务` → `估值` → `技术面 (trend · BIAS · 量比 · zones)` → `情绪 / 筹码 (US: GEX · F&G / A: 人气 · 股东户数)` → `催化 & 风险` → `仓位计划 (horizon-tagged)` → disclaimer. Every line cites a real number from §1.

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
