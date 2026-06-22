# Stages 2 & 6 — Screen (factor rank) and Validate (backtest sanity)

**Lineage:** QuantDinger — https://github.com/brokermr810/QuantDinger (rule/indicator workbench +
deterministic backtester). Two jobs: **Stage 2** ranks the universe into a long-list; **Stage 6**
sanity-checks each finalist's entry thesis. Honest scope note below — QuantDinger is a technical
rule/backtest engine, **not** a multi-factor academic model, and it has **no walk-forward / OOS /
formal overfitting controls**. Treat its output as a *filter and a reality check*, never as proof.

## Stage 2 — factor screen (universe → long-list ~10–20)

Rank candidates by objective, region-routed factors. State every filter and what it dropped — **no
silent cuts.** Reusable primitives (QuantDinger's indicator set):

- **Trend bias** — price vs EMA(20)/EMA(50); EMA(20) > EMA(50) = up-bias (dual-MA crossover)
- **Momentum** — RSI(14); use **45–50 as the floor** for a long bias (not overbought-chasing)
- **Breakout structure** — highest-high / lowest-low over **N=20** bars, with a **retest buffer 0.002**
- **Volume confirmation** — current volume **> 1.2× average**
- **Volatility** — ATR(14) for stop distance (feeds Stage 6 sizing)
- **Liquidity** — drop names too thin to enter at intended size (region-aware: A/HK board lots)
- **Quality/valuation pre-filter** — cheap-and-improving over cheap-and-melting (a light pass before the
  full Buffett gate in Stage 3)

Rank, take the top ~10–20, **report the cut** ("40 → 14; dropped 9 on trend, 12 on liquidity, 5 on RSI").

## Stage 6 — validate the finalist's thesis (entry + backtest sanity)

For each finalist coming out of the Stage 5 debate:

### 1. Range engine (the real entry plan)
- `ot decide TICKER [--market A|HK]` → **buy-zone · trim · stop** in local currency, plus the
  CALL/PUT/NO-ACTION read and the event gate (US names). This is the authoritative entry layer — the
  user trades **zones, not single points.**
- `ot strategy [--roster ID]` → how the name sits in a graded, allocated book (sizing context).

### 2. Backtest sanity (QuantDinger discipline)
Encode the entry/exit as concrete rules and check they'd have *survived*, not curve-fit:
- **Fill realism:** next-bar-open fill (not same-bar-close); closed bars only; commission + slippage on;
  `strictMode` to align backtest with live — **explicitly avoid look-ahead.**
- **Report:** per-trade P&L, equity curve, **max drawdown, Sharpe, win rate, exposure time.** A thesis
  that only works with perfect fills or in-sample tuning is **not validated.**
- **Default risk params** (starting points, then ATR-adjust): stop **2–3%**, target **5–6%**, entry size
  **20–25%** of intended, trailing stop **1.5–2%**, per-idea risk **~0.25**.

> **Scope honesty:** OpenTrading's public repo has the range engine, not a full backtester (the private
> sim/backtest tools live in `~/OpenTrading-lab`). So Stage 6 in practice = **`ot decide`/`ot strategy`
> for the zones + a manual/lab backtest for the rule check.** Don't overclaim statistical validation you
> didn't run — say "range-engine confirmed; rigorous walk-forward not run" when that's the case.

### 3. Final gate
- Re-apply the **macro/event gate** (US: FOMC/CPI/OPEX near? CN: note the missing calendar). A great name
  into a known event = smaller size or wait.
- If the entry zone is far above current price, the name is a **"watch next"**, not a buy-now shortlist
  entry — say so.

**Output of Stages 2 & 6:** Stage 2 → the ranked long-list with the cut shown; Stage 6 → each finalist's
buy/trim/stop zones, a backtest-discipline note (with honest scope), and the macro/event caveat — feeding
the final shortlist table in `SKILL.md`.
