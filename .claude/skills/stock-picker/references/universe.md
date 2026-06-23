# Stage 0 — Frame the universe (region routing)

Pin these four before screening anything. Get them from the user; infer sensibly and state your
assumption if they're vague.

1. **Region** — `US` | `A` (China A-share) | `HK`. Routes all data (below). One region per run;
   for a cross-region theme, run the funnel once per region and compare at the end.
2. **Universe** — one of:
   - a **sector / theme** ("AI power", "光伏", "memory", "China consumer") → go to Stage 1
     (supply-chain) to *generate* candidates;
   - an **index slice** (e.g. "Nasdaq-100 semis", "沪深300 银行") → that's the long-list input;
   - the user's **`watch` / `alpha`** lists from `watchlist.json` (or a roster) → pre-curated input;
   - an explicit **ticker list** the user pasted.
3. **Horizon** — swing (weeks) vs. position (months). This skill is **not** intraday; hand entries to
   `short-term-trader` once a name is picked.
4. **The bar** — what "truly potential" means *here*: secular growth, a re-rating catalyst, moat
   compounding, a turnaround, or a supply-chain chokepoint. The bar decides which later stages weigh most.

## Data routing by region

| Region | Quotes | Range plan (entry/trim/stop) | News | Event gate | Currency |
|---|---|---|---|---|---|
| **US** | `ot quote SYM…` | `ot decide SYM` | `ot news --ticker SYM` | FOMC/CPI/OPEX **on** | $ USD |
| **A-share** | `ot cn 600519 002594` | `ot decide 600519 --market A` | (no FinancialJuice CN feed — use general macro) | US gate **off** | ¥ CNY |
| **HK** | `ot cn 00700 09988` | `ot decide 09988 --market HK` | partial (HK names appear in global tape) | US gate **off** | HK$ HKD |

**Symbol mapping (A/HK via Yahoo, under the hood):** A-share `6xxxxx` → `.SS` (Shanghai),
`0|2|3xxxxx` → `.SZ` (Shenzhen); HK → `str(int(code)).zfill(4)+".HK"`. `ot decide --market A|HK` and
`ot strategy --roster <id>` already do this mapping and are currency-aware; `ot cn` (Eastmoney) is the
throttled quote fallback. **Caveat:** OpenTrading models only the **US** event calendar — there is **no
China/HK event calendar** (PBoC, NPC, mainland holidays). Note that gap when timing a CN pick.

## The macro gate (run before Stage 2)

- `ot macro` → rates / liquidity → a put/call lean. Risk-off regime ⇒ tilt the screen toward quality &
  cash flow (Buffett stage weighs more); risk-on ⇒ momentum/beta can earn their place.
- `ot smart` → Fear & Greed + funding. Extreme fear can be a contrarian *entry* backdrop for an already
  high-quality survivor — but it is never a reason to lower the quality/trap bar.
- The regime is **context for the screen**, not a stock picker itself. It changes weights, not the rules.

## Funnel bookkeeping

Track the count at every stage and report it: `universe N → long-list → quality → traps → debate →
shortlist`. This makes the narrowing auditable and exposes where the universe died (all traps? no moats?
no margin of safety?) — itself a useful finding.
