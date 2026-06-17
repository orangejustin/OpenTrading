# Options Trading Reference

## The Greeks — What They Tell You

### Delta (Δ)
- How much the option price moves per $1 move in the underlying
- Call delta: 0 to 1. Put delta: -1 to 0
- ATM ≈ 0.50 delta. Deep ITM ≈ 0.80–0.99. Far OTM ≈ 0.05–0.20
- **Rule of thumb**: Delta ≈ approximate probability the option expires ITM

### Gamma (Γ)
- Rate of change of delta. Highest at ATM, highest near expiration
- Long gamma (bought options): you benefit from large moves in either direction
- Short gamma (sold options): you lose when the underlying makes big moves
- **Gamma risk**: short options near expiry can explode if the underlying moves sharply

### Theta (Θ)
- Time decay — how much an option loses in value per day
- Always negative for long options, positive for short options
- Accelerates rapidly in the last 2–3 weeks before expiration
- **Rule**: Don't buy options with < 21 DTE unless you're playing a specific near-term catalyst

### Vega (V)
- Sensitivity to implied volatility (IV) changes
- Higher IV → higher option prices (all else equal)
- **IV crush**: after earnings, IV collapses, destroying option value even if the move is right
- Long vega = benefits from IV expansion. Short vega = benefits from IV contraction

### Rho (ρ)
- Sensitivity to interest rates. Mostly irrelevant for short-term trades.

---

## Implied Volatility (IV) — The Single Most Important Options Concept

### What Is IV?
IV is the market's forward-looking expectation of volatility, derived from option prices. It's expressed as an annualized percentage (e.g., IV = 30% means the market expects ~1.9% daily moves).

**Daily expected move ≈ IV / √252**

**Weekly expected move ≈ IV / √52**

### IV Rank (IVR) and IV Percentile (IVP)
- **IVR** = (current IV − 52-week low IV) / (52-week high IV − 52-week low IV) × 100
- **IVP** = % of days in the past year where IV was lower than current IV
- IVR/IVP > 50: IV is relatively high → favor selling premium
- IVR/IVP < 30: IV is relatively low → favor buying options

### IV Crush
Post-earnings IV always collapses. Even if you correctly predicted direction, you can lose money if IV drops more than the directional gain. To profit from earnings moves via long options, the actual move must **exceed** the expected move (priced into IV).

**Expected move formula (from options chain)**:
Expected Move ≈ ATM straddle price (nearest expiry)

---

## Options Strategies Reference

### Directional — Bullish

**Long Call**
- View: strongly bullish, needs to move enough to overcome theta
- Max loss: premium paid
- Max gain: unlimited
- Break-even: strike + premium
- When to use: low IV environment, expecting a large move

**Bull Call Spread (Debit Spread)**
- Buy lower strike call, sell higher strike call (same expiry)
- Reduces cost vs. naked call; caps the upside
- Max loss: net debit paid. Max gain: spread width − debit
- When to use: moderately bullish, high IV environment

**Cash-Secured Put / Naked Put**
- Sell a put at a strike you'd be happy owning
- Max gain: premium. Max loss: strike − premium (can be large)
- When to use: want to acquire stock at a discount, high IV preferred

### Directional — Bearish

**Long Put**
- View: strongly bearish
- Use same principles as long call but in reverse

**Bear Put Spread**
- Buy higher strike put, sell lower strike put
- Same logic as bull call spread, bearish version

### Neutral / Range-Bound

**Iron Condor**
- Sell OTM call spread + sell OTM put spread
- Profit zone: stock stays between the two short strikes at expiry
- Max gain: net credit. Max loss: width of wider spread − credit
- When to use: high IVR (> 50), low conviction on direction, expecting range-bound price action
- **Ideal DTE**: 30–45 DTE, close at 50% of max profit

**Short Strangle**
- Sell OTM call + sell OTM put (undefined risk)
- Higher credit than iron condor, but unlimited upside risk
- Only for accounts with defined margin/buying power rules
- Manage at 50% profit or when tested by the underlying

**Short Straddle**
- Sell ATM call + ATM put
- Maximum premium collected, but tested immediately on any move
- Very high maintenance trade

### Volatility Plays

**Long Straddle**
- Buy ATM call + ATM put (same strike, same expiry)
- Profits if underlying makes a large move in either direction
- Loses to theta every day it sits still
- When to use: very low IVR, binary event expected (earnings, FDA), conviction on big move but not direction

**Long Strangle**
- Buy OTM call + OTM put
- Cheaper than straddle, requires even larger move to profit

---

## Earnings Plays

### The Core Problem
IV is artificially inflated before earnings → options are expensive. After earnings, IV collapses regardless of the move (IV crush).

### Four Approaches:

**1. Short Strangle / Iron Condor (sell IV)**
- Best when stock historically moves less than the expected move
- Look at historical post-earnings moves vs. current expected move
- If stock has moved less than expected move in 7/8 of last quarters → edge to sell

**2. Long Straddle/Strangle (buy IV)**
- Best when stock historically blows past the expected move
- Or when you have strong directional conviction + expect a large move

**3. Directional Debit Spread**
- You have a directional view but want to reduce IV exposure
- The sold short leg helps offset IV crush

**4. Skip the trade**
- If IV crush risk is too high and historical moves are mixed, the edge is unclear
- No trade is a valid trade

---

## Reading an Options Chain

Key things to look for:
1. **Open interest** — higher OI = more liquidity = tighter spreads
2. **Volume** — today's activity; high volume relative to OI signals unusual interest
3. **Bid-ask spread** — wide spreads kill profitability. Target spreads < 10% of mid price
4. **Max pain** — the strike where options sellers profit most (stock gravitation theory)
5. **Put/call ratio** — contrarian signal. Very high P/C → crowded bearish positioning

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Buying OTM options with < 21 DTE | Use 45–60 DTE, buy ATM or one strike OTM |
| Ignoring IV when buying | Check IVR. Never buy high-IV options |
| Not accounting for spread costs | Use mid-price, size for realistic fills |
| Holding through earnings unintentionally | Know your earnings dates. Exit or hedge before |
| Letting losers run past 2x debit paid | Set hard stop at 2x debit for long options |
