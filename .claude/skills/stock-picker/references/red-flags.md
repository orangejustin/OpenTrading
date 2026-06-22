# Stage 4 — Traps: red-flag & value-trap kill screen

**Lineage:** UZI-Skill — https://github.com/wbh604/UZI-Skill (22维 × 180条量化规则). Run on every
quality survivor. **Killing a trap is a win, not a loss** — this stage exists to *reject*. It has two
distinct layers; run both. Especially load-bearing for **A-share / HK** names.

## HARD rule — no fabrication

Every flag must be grounded in real data (filing, quote, search result). If a datum (related-party
detail, goodwill figure) isn't available, mark it **"unverified"** and treat the name as *higher risk*
— never invent a clean reading. UZI gates its own output on a 13-check anti-fabrication review; mirror that.

## Layer 1 — 杀猪盘 / pump-and-dump detector (8 signals, sentiment/promotion-pattern based)

Score the *promotion pattern*, not the chart. Count signals present:

- **S1 Account spam** — "{name} 推荐"-type results dominated by 0–100-follower / newly-created accounts clustered in 7–30 days
- **S2 Templated hype** — ≥2 of: 即将爆发 · 主力建仓完毕 · 目标翻倍 · 最后上车机会 · 底部反转信号 · 内部消息
- **S3 Paid funneling** — WeChat/VIP groups, QR codes, "teacher" contact, paid livestreams
- **S4 Fundamentals↔sentiment mismatch** — ROE < 5% / losses *while* 30-day discussion volume doubles
- **S5 Abnormal K-line** — ≥50% gain in the 30–60 days before a promotion cluster; concurrent discounted block trades
- **S6 Guru persona** — 老师/操盘手, luxury props, no Dragon-Tiger (龙虎榜) track record
- **S7 Cross-platform coordination** — identical recs on ≥3 of 小红书/抖音/B站/知乎/微博
- **S8 Fake reports/news** — disclaimers present; "research" lacking broker watermark / analyst signature

**Trap score 1–10 (lower = riskier):** 0–1 signals → 9–10 Safe · 2–3 → 6–8 Caution · 4–5 → 3–5 Alert ·
6+ → 1–2 Highly Suspicious. Keyword weight boosts: 朋友推荐/群里/老师 +1 · 内幕/稳赚 +2 · 必涨/翻倍 +1.
**Trap score ≤ 3 ⇒ auto-reject**, no matter how good the Stage 3 quality looked.

## Layer 2 — forensic accounting red flags

Assemble this from UZI's deep-analysis dimension + standard ratios (there is no single ready-made file):

| Check | Red flag → action |
|---|---|
| **Receivables vs revenue** | 应收账款/营收 **> 60%**, OR receivables YoY growth > revenue growth by **>20%** → stage-2 deep check |
| **Cash vs profit** | **FCF negative while net profit positive** → stage-2 deep check (earnings quality) |
| **Leverage** | debt ratio materially **> ~30%** → warn |
| **Inventory** | inventory accumulating faster than revenue → demand/channel-stuffing risk |
| **Related-party & goodwill** | large related-party transactions / goodwill impairment risk → **HARD-FACTCHECK** (must be in raw data) |
| **Profitability decay** | **ROE < 8% long-term**, or 3-yr ROE decline → quality alert |
| **Valuation sanity** | DCF/Comps coming out all-zero ⇒ implied financial-statement defect → investigate before trusting any number |

## Verdict

`overall_score = fundamentals × 0.6 + consensus × 0.4`, where consensus = (bullish + 0.6×neutral) /
active voters; bands 80 / 65 / 50 / 35. But treat this as secondary — **a single fatal flag (trap
score ≤3, FCF/NI divergence with receivables blowout, unverifiable related-party) rejects the name
outright**, regardless of the composite. Trap-aversion beats upside.

**Output of Stage 4:** survivors carry forward; rejected names are listed with the *specific* flag that
killed them (this is reporting signal, not noise).
