# Macro Dashboard CLI (`macro.py`)

Pulls the **free, no-API-key** macro indicators behind the skill's intraday
"Daily Macro Brief" and scores each per the thresholds in
`.claude/skills/short-term-trader/references/macro-dashboard.md`.

Stdlib-only (Python 3.9+). Uses `certifi` if installed, else falls back to `curl`.

## Usage

```bash
ot macro          # scored dashboard (table)
ot macro --json   # machine-readable
```

(`ot macro` is the wrapper; the underlying script is `python3 tools/macro/macro.py`.)

## Indicators

| Indicator | Source | Key needed | Scoring (per macro-dashboard.md) |
|-----------|--------|:---------:|----------------------------------|
| **SOFR** | NY Fed secured rates API | no | falling over 5d = bull, rising = bear |
| **2Y yield** | US Treasury daily par yield curve (XML) | no | `<4.18` bull, `>4.30` bear |
| **10Y yield** | US Treasury daily par yield curve (XML) | no | `<4.35` bull, `>4.50` bear |
| **TGA** | Treasury Fiscal Data API | no | `<$900B` bull, `>$925B` bear |
| **RRP** | NY Fed reverse-repo | no | declining = bull (best-effort; may degrade) |
| Fed cut odds | Polymarket | — | printed as a manual to-do with URL |
| PCE nowcast | Cleveland Fed | — | printed as a manual to-do with URL |
| News flow | FinancialJuice | — | use `ot news` |

The auto indicators are summed into an **AUTO SCORE** and mapped to a tilt
(`LEAN CALLS` / `NEUTRAL` / `LEAN PUTS`). Always fold in the three manual indicators
before committing to a bias — the CLI prints their URLs and rules.

## Robustness

- Each indicator is fetched independently; if one fails (e.g. RRP endpoint changes),
  it degrades to a `NOTES` line and the rest still score.
- The Treasury yield year is derived from the current date, with a previous-year
  fallback for the first days of January.

## Output (example)

```
INTRADAY MACRO DASHBOARD — auto-fetched (no-key public data)
  SOFR            3.60%  [+ bull]  down vs 3.63% (2026-06-11)
  TGA             $801B  [+ bull]  bull<900 / bear>925 (2026-06-11)
  2Y Yield        4.09%  [+ bull]  bull<4.18 / bear>4.30 (2026-06-12)
  10Y Yield       4.48%  [  neut]  bull<4.35 / bear>4.50 (2026-06-12)
  AUTO SCORE: +3  (from 4 indicators)  ->  LEAN CALLS (bullish tilt)
```

Thresholds are the skill author's defaults — tune them in `macro.py` (and keep
`macro-dashboard.md` in sync). Analysis for educational purposes, not financial advice.
