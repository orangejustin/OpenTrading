# Portfolio constructor — `ot strategy`

Turns a universe of names into ONE sized, graded, risk-budgeted book. The per-name
layer is `ot decide` (range execution plan + A–D grade); **`ot strategy` is the
portfolio layer on top** — it scores, ranks, drops the weak, and allocates.

> ⚠️ Educational only — not financial advice. No-key data; confirm live.

## Run

```bash
ot strategy VST NBIS HOOD MSTR OKLO --style momentum --risk medium
ot strategy --roster jane --style balanced       # a multi-user roster (A-share + HK supported)
ot strategy 688008 300394 --market A             # China A-shares (Yahoo .SS/.SZ)
ot strategy --style defensive --risk low         # universe = watchlist.json (positions + watch)
ot strategy VST NBIS --format json               # structured, for the desk/email
```

## How it builds the book
1. **Score** each name 0–100 from the live signal — factors **trend / momentum / edge / lowrisk**, weighted by **style** (`momentum` rewards trend+5d momentum; `defensive` rewards low-vol + trend; `balanced` splits).
2. **Grade A–D** (≥72 A · ≥58 B · ≥44 C · else D); **extended names are docked** (chasing further above the 20-day than the risk profile tolerates).
3. **Keep long-actionable** (CALL + grade ≥ C), **rank by score**, take the **top-N** for the risk profile.
4. **Allocate** by score, risk-adjusted (more volatile → smaller), with a **cash floor** + **per-name cap**; the remainder is cash.
5. **Event gate:** on an FOMC/CPI/OPEX day the **cash floor is raised** automatically.

## A-share / HK (multi-market)
Yahoo carries A-shares and HK natively via suffixes (`688008`→`688008.SS`, `300394`→`.SZ`, `09988`→`9988.HK`), so the **same engine prices them with no new deps** — via the `tools/sim/symbols.py` normalizer (the TradingAgents `symbol_utils` pattern). A **roster** (`watchlist.<id>.json`) carries each name's `market` field, so `ot strategy --roster <id>` builds a mixed A/HK/US book; `ot decide CODE --market A|HK` does one name. Each pick shows its **local currency** (¥ CNY / HK$ HKD / $ USD); the **US event-gate is suppressed off-US**. *Caveat:* no China/HK event calendar yet — only US FOMC/CPI/OPEX is modeled.

Each pick carries its **range execution plan** (buy/trim/stop zones) — see [[execution-plan]].

## Risk profiles
| risk | max positions | cash floor | target vol | per-name cap | extend tolerance |
|---|---|---|---|---|---|
| low | 4 | 18% | ~9% | 22% | 8% |
| medium | 5 | 10% | ~14% | 28% | 12% |
| high | 6 | 4% | ~21% | 35% | 20% |

## Read the output
`TICKER  grade · score · alloc%   buy lo–hi · trim lo–hi · stop`, plus confidence
(avg score), target vol, cash, and rebalance rules. A near-empty book at high cash is
an honest "nothing's set up" — risk-first by design, not a bug.

Borrows the open-source ScaleAlpha-simulation `strategy-engine` (generateStrategy /
RISK_RULES / STYLE_WEIGHTS), adapted to OpenTrading's engine. See [[execution-plan]], [[portfolio-desk]], [[risk]].
