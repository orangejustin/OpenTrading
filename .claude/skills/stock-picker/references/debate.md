# Stage 5 — Debate: multi-agent bull / bear / risk stress-test

**Lineage:** TradingAgents — https://github.com/TauricResearch/TradingAgents (LangGraph multi-agent).
You don't run LangGraph here — you **emulate the seats** in one reasoning pass, giving each a real turn.
Run on the finalists only. A name that can't beat its own strongest bear case is **demoted, not
shortlisted**.

## The seats (play each honestly, in order)

**1. Analyst team** — four short, parallel reads (cite numbers, no narrative):
- **Market** — trend / momentum / key technical levels (`ot decide` gives the levels)
- **News** — global + macro catalysts on the name (`ot news --ticker SYM`; CN names: general tape)
- **Sentiment** — social/retail positioning (and cross-check vs. Stage 4 trap signals)
- **Fundamentals** — the Stage 3 quality + Stage 1 chain role, condensed

**2. Researcher debate — Bull vs Bear** (strict alternation, ~1–2 rounds each):
- **Bull**: the strongest *evidenced* upside case (chain bottleneck + moat + MoS + catalyst).
- **Bear**: the strongest *evidenced* downside — pull the "biggest reason the thesis is wrong" carried
  from Stage 1 and the worst surviving flag from Stage 4. The bear must be a real adversary, not a strawman.

**3. Research Manager** — judge the bull/bear debate → a rating on the **5-point scale:
Buy / Overweight / Hold / Underweight / Sell.** Only **Buy / Overweight** earns a shortlist slot.

**4. Trader** — turn the rating into a concrete proposal: timing + magnitude + the entry/trim/stop
zones (hand to Stage 6 / `ot decide`).

**5. Risk debate — three seats (strict rotation Aggressive → Conservative → Neutral, ~1 round):**
- **Aggressive** — why size up / why the risk is acceptable
- **Conservative** — what kills the account; concentration, liquidity, event risk
- **Neutral** — the balanced sizing read

**6. Portfolio Manager** — synthesize the risk debate into the **final call + conviction grade (A/B/C)**,
informed by *reflection*: how did similar past picks play out? (For your book, this is the OpenTrading
decision log / prior shortlist outcomes — feed any available history in.)

## Conviction mapping (→ the output table)

| Grade | Means |
|---|---|
| **A** | Buy/Overweight + survives the strongest bear + conservative risk seat OK with sizing |
| **B** | Overweight/Hold but one open risk (an unresolved bear point or a thin-evidence chain claim) |
| **C** | Borderline — interesting but a real unresolved flag; goes to "watch next", not the shortlist |

## Discipline

- The bear seat has veto power on grade: an unrebutted, material bear point caps the name at **C**.
- Inject **reflection** — don't repeat a past mistake the decision log already recorded.
- Keep it tight: this is a stress-test to *demote weak names*, not an essay. One pass, real adversaries.

**Output of Stage 5:** each finalist with a 5-point rating, a conviction grade, the strongest bear case
written down, and the single disconfirming data point — straight into the output contract table.
