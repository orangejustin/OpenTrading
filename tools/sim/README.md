# Live decision engine (`tools/sim/`)

Turns the skill's learned trading policy into one concrete, live call —
**CALL / PUT / NO-ACTION** + conviction + size — from no-key market data.

> ⚠️ **Educational analysis — not financial advice.**

## Commands

```bash
ot decide QQQ  --dte 0              # 0DTE mode: fade-gap + VIX-confirm + skip-events + selectivity
ot decide NVDA --dte 5             # swing mode (default): momentum calls on names you read well
ot decide QQQ  --dte 0 --format json
```

`--dte 0|1` selects 0DTE mode, `--dte >=3` (default 5) is swing mode, `--capital N` sizes the
suggestion, and `--format json` prints machine-readable output.

## Modules

| File | Command | What it does |
|------|---------|--------------|
| `decide.py` | `ot decide` | Applies the learned policy to a live ticker → action + conviction + size + stop |
| `yfhist.py` | — | No-key Yahoo daily bars + `^VIX` / `^TNX`, cached to `/tmp/ot_sim_cache` |

## The policy it encodes (forward-validated, no lookahead)

The policy was derived by deciding **blind** as of each historical setup — using only what was
knowable then (prior trend, overnight gap, `^VIX` level/direction, the macro-event calendar) —
then scoring each decision against what **actually happened**. The strategies that won that
forward test are exactly what `ot decide` applies live:

- **0DTE:** skip macro-event days; **fade** the opening gap (don't chase); require **VIX-direction
  confirmation**; stay selective (**NO-ACTION is a position**); size down in calm VIX (chop).
- **Swing (≥3 DTE):** momentum-continuation calls on names you read well; puts only on a real
  downtrend thesis.
- **Risk:** ≤5% premium/trade, a hard daily-loss stop, never size up after a loss.

Full write-up: [`learned-strategy.md`](../../.claude/skills/short-term-trader/references/learned-strategy.md).

## Data & calendar

- **Prices:** no-key Yahoo **daily** bars (`yfhist.py`). Intraday history isn't free far back, so
  the read is at the level of **day-character** (gap, range, open→close) — not tick-level timing.
- **Vol / rates regime:** `^VIX`, `^TNX`.
- **Macro events:** a built-in FOMC / CPI / OPEX calendar; OPEX (3rd Friday) is computed. Extend
  `decide.py`'s calendar as dates advance.
- **Live-only confirmation:** IV / gamma-walls / news can't be backfilled — confirm with
  `ot options` / `ot news` / `ot macro` before acting.

> Educational only — not financial advice. Markets are risky; size accordingly.
