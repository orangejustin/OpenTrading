---
title: Introduction
sidebar_position: 1
slug: /intro
---

# What is OpenTrading?

**OpenTrading** is an open-source, local-first toolkit **and** Claude skill for
short-term trading analysis — stocks, options, derivatives, and crypto — with a
**macro-first, risk-first** workflow.

It is built on one idea: a good desk is not one clever model, it's *many
independent views* forced to reconcile. So OpenTrading runs a small ensemble of
forecasters, makes them argue, and then grades itself on what actually happened.

## The three layers

```
FORECASTERS            →   FUSION                 →   LEARNING
independent views          reconcile them             grade & remember
─────────────────          ──────────────────         ─────────────────
rules engine (ot decide)   consensus strip            ot reflect grade
logistic P(up) (ot quant)  confluence ladder          lessons → next judge
TimesFM cone (ot forecast) bull vs bear + judge
dealer gamma / GEX         (ot debate)
crowd odds (ot poly)
on-chain whales (ot whales)
```

1. **Forecasters** each produce a view from *different* information — a rules
   engine, a statistical model, a foundation model, dealer-positioning data, an
   LLM analyst, and a prediction-market crowd.
2. **Fusion** combines them: a consensus strip (which flips to **STAND ASIDE**
   the moment two analysts disagree), a confluence ladder (price levels named by
   2+ independent methods), and an adversarial **bull-vs-bear debate** whose
   judge commits to a call.
3. **Learning** grades every committed call afterwards and feeds the lessons back
   into future judgments.

## Design principles

- **Deterministic SOP, not an agent.** Scripts gather and compute the evidence,
  freeze it into a text pack, and *then* the model reads it. Nothing acts on its
  own; the same inputs always produce the same evidence.
- **Keyless & local-first.** The core depends on no API keys — just Python's
  standard library. Your positions live in a git-ignored file and never leave
  your machine.
- **Independence over agreement.** Five analysts sharing one brain equal one
  analyst. Each module deliberately uses different math, different data, and (in
  the debate) different vendors' models.

## Who it's for

A macro-first short-term trader who wants a **repeatable second opinion** — not
signals to follow blindly, but a structured desk that shows its work and keeps
score.

:::warning Educational only
Everything OpenTrading produces is **educational, not financial advice.** It is a
personal research tool. You are responsible for your own trades.
:::

Ready? Head to **[Getting started](./getting-started.md)**.
