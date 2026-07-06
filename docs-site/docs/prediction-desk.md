---
title: The prediction desk
sidebar_position: 5
---

# The prediction desk

Every ticker page runs the same pipeline. This page explains each stage and the
command behind it.

## 1 · Forecasters

Independent views, each from *different* information:

| Command | View | Method |
|---|---|---|
| `ot decide` | rules engine | CALL/PUT/NO-ACTION + a range plan |
| `ot quant` | logistic P(up) + range cone | keyless logistic regression, OOS-gated |
| `ot forecast` | TimesFM 2.5 quantile cone | foundation model (opt-in install) |
| `ot options` | dealer gamma (GEX) | signed gamma × OI per strike, from CBOE chains |
| `ot poly` | crowd odds | Polymarket prices for the macro event gate |
| `ot hl` | perp funding & OI | Hyperliquid — the crypto leverage bill |
| `ot whales` | on-chain flow | labeled-wallet ETH balances + deltas |

The point is *independence*: different math, different data. A cone from
statistics and a wall from dealer hedging that land on the same price is
tradeable structure neither shows alone.

## 2 · Fusion

- **Consensus strip** — one chip per analyst; the verdict flips to **STAND
  ASIDE** the moment two disagree. Disagreement is information.
- **Confluence ladder** — all the levels the desk emits, on one price axis. Rows
  named by **2+ methods** (`×2`) are the only ones that matter.

## 3 · The debate

```bash
ot debate NVDA           # 3 LLM calls on a frozen evidence pack
```

Three calls run over a deterministic evidence pack:

1. **Bull** — the strongest honest long case.
2. **Bear** — the strongest short/avoid case, *and* it must directly attack the
   bull's strongest point.
3. **Judge** — weighs both against the evidence and **commits**: a 5-tier verdict
   with confidence, entry, a mandatory invalidation level, and a time stop.

By default the bull and bear run on *different* engines (perspective diversity,
Condorcet-style); you can also run all three roles on one engine. Every verdict
auto-journals for grading.

:::info Deterministic SOP
The evidence pack is built and frozen by scripts *before* any model runs. The
models read; they never fetch or act. Same inputs → same pack → reproducible.
:::

## 4 · The learning loop

```bash
ot reflect grade         # grade calls that have ripened
ot reflect stats         # hit-rate by action / grade / market
ot reflect lessons       # the lessons injected into the next judge
```

Every committed call is later scored against what actually happened — right or
wrong, return vs SPY (alpha), worst adverse excursion, whether the invalidation
broke — and the lessons feed back into future judge prompts. See
**[Methodology](./methodology.md)** for exactly when and how a call is graded.
