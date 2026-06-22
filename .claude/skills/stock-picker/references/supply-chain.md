# Stage 1 — Direction: supply-chain decomposition & bottleneck hunting

**Lineage:** Serenity Skill — https://github.com/muxuuu/serenity-skill (拆产业链，找供应链瓶颈).
Use this stage when the user hands you a **theme**, not a list. Goal: turn a narrative into a concrete
architecture change, walk the chain, and surface the **under-priced chokepoint company** — *that's*
where candidates come from. Keep **"scarce layer"** and **"which company"** as two distinct questions.

## The 8-tier value chain (map top-down from demand, then traverse upstream)

1. Downstream **demand** (the end market that's inflecting)
2. **System integrators** (whole product / platform)
3. **Modules / subsystems**
4. **Chips / devices**
5. **Process & packaging**
6. **Equipment & testing**
7. **Materials & consumables**
8. Physical **infrastructure** (power, fab space, grid, logistics)

The bottleneck is rarely tier 1–2 (crowded, priced). It's usually a deep tier where one input gates the
whole stack.

## 9-step workflow

1. **Scope** the theme and the region.
2. **Translate** the narrative into a *concrete system/architecture change* ("AI inference → more HBM
   stacks per GPU → more advanced packaging → …"). No translation, no edge.
3. **Map** the chain across the 8 tiers.
4. **Find the scarce layer** — the tier under the most system pressure (below).
5. **Build a universe** of ≥ ~20 candidates at/around that layer (region-routed — see `universe.md`).
6. **Gather evidence** — aim for real primary sources (filings, transcripts, patents, regulator data).
7. **Rank** across the 8 factor dimensions minus the 8 penalties (below).
8. **State invalidation conditions** — what would kill the thesis.
9. **Give the next verification move** — the one thing to check before committing.

## Bottleneck signals (is this layer actually scarce?)

Low supplier count · long qualification/certification cycles · hard-to-expand capacity · critical
tacit know-how · material-purity requirements · specialized equipment · customer certification lock-in ·
long lead times. Rank the *constraint type* by system pressure: **power, latency, bandwidth, heat,
yield, purity, reliability, cycle-time, packaging density, regulation, grid connection.**

Graph heuristic: a **Funnel node** (many things depend on it, it depends on few — in-degree ≥2,
out-degree ≤1) = single point of failure; a **Hub node** (in ≥2, out ≥2) = hardest to bypass. Both are
chokepoints worth a candidate.

## Scoring — each 0–5

**8 factor scores (higher better):** demand inflection · architecture coupling · chokepoint severity ·
supplier concentration · expansion difficulty · evidence quality · valuation disconnect · catalyst timing.

**8 penalty scores (subtract):** dilution · governance · geopolitics · liquidity · hype · accounting
quality · cyclicality · alternative-design risk.

**Target definition:** *the smallest market cap that blocks the biggest constraint yet remains
unpriced.* That phrase is the filter — big enough to matter, small enough to re-rate, scarce enough to
have pricing power.

## Evidence ladder (required per candidate before it leaves this stage)

- ≥ 2 concrete evidence points
- ≥ 1 **strong primary** source (filing / transcript / patent / regulator)
- a strength label (strong / moderate / thin)
- **the single biggest reason the thesis is wrong** (carry this into Stage 5 debate)

**Output of Stage 1:** the scarce layer named, plus a region-routed candidate universe (~20) ranked by
(factors − penalties), ready for the Stage 2 factor screen.
