# Options positioning CLI (`opt.py`)

Put/Call ratios + **dealer gamma exposure (GEX)** + gamma walls, from CBOE's free
delayed options chain (full Greeks + OI + volume, **no API key**).

```bash
ot options SPY
ot options SPY QQQ --dte 7     # default DTE window = 7
ot options SPY --dte 0         # 0DTE only
ot options SPY --json
```

(`ot options` is the wrapper; the underlying script is `python3 tools/options/opt.py`.)

## What it computes

| Field | Meaning |
|-------|---------|
| **Net GEX ($/1%)** | Σ(signed gamma × OI) × 100 × spot² × 1%. Calls +, puts −. |
| **gamma sign** | **positive** = dealers long gamma → vol-**suppressing**, mean-reverting, pins to walls. **negative** = short gamma → vol-**amplifying**, trends/squeezes accelerate. |
| **P/C OI / vol** | put/call open-interest and volume ratios (≥1.2 = put-heavy/hedged; ≤0.7 = call-heavy/complacent). |
| **Gamma walls** | strike with the largest call gamma (resistance/pin) and largest put gamma (support). |

## Caveats (read before trusting it)

- **GEX is a heuristic.** The dealer sign convention (long calls / short puts) is the
  common *naive* one and is debated; treat the **sign and relative magnitude** as the
  signal, not the absolute dollar figure.
- Data is CBOE **delayed** (not real-time). Fine for positioning context, not for execution.
- `--dte 7` captures the near-term gamma that drives intraday pin/trend behavior; widen
  `--dte` for a fuller picture.

Educational only — not financial advice.
