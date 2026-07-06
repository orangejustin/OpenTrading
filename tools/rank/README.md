# `ot rank` — the composite Top-3

Selection > timing. This tool blends everything the desk already computes into
**one transparent score per name**, so the morning question — *"which 3 of my
names deserve attention today?"* — has a single, shared answer: the web
Strategy tab and the daily email both consume it.

```bash
ot rank                    # whole watchlist.json, ranked
ot rank NVDA META ORCL     # explicit names
ot rank --top 3 --format json
```

## The score (all deterministic, no LLM)

| component | source | points |
|---|---|---|
| grade | `ot decide` A–D conviction | A 30 · B 22 · C 12 · D 0 |
| quant edge | `ot quant` P(up)−50, signed toward the plan's side, **gated by OOS hit-rate** (<55% → ×0, 55–62% → ×0.5, ≥62% → ×1) | −15…15 |
| cone tilt | quant P50 drift toward the side, 3 pts/% | −9…9 |
| proximity | price inside the entry zone 15 · within 1% 10 · within 3% 5 | 0…15 |
| debate | today's journaled judge verdict, signed, × confidence | −10…10 |
| event | scheduled binary print on the name | −8 |

The components are always emitted (`--format json`) — the score is an
**ordering**, not an oracle. A coin-flip quant model contributes ~nothing by
construction; an A-grade setup sitting inside its zone with an aligned fresh
verdict tops the board.

Educational only — not financial advice.
