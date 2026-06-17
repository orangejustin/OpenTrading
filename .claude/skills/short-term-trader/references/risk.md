# Risk Management & Position Sizing Reference

## The Fundamental Law of Survival

**You cannot make money if you blow up your account.**

The math of loss recovery is asymmetric and brutal:
- Lose 10% → need 11% to recover
- Lose 25% → need 33% to recover
- Lose 50% → need 100% to recover
- Lose 75% → need 300% to recover

The goal of risk management is to stay in the game long enough for your edge to express itself over many trades.

---

## The 1% Rule (Fixed Fractional Position Sizing)

**Never risk more than 1–2% of total account equity on a single trade.**

This is the most widely used rule among professional traders for good reason: even a 10-trade losing streak (which happens) only costs you 10–18% of your account.

**Formula:**
```
Position size = (Account equity × Risk %) / (Entry price − Stop price)
```

**Example:**
- Account: $50,000
- Risk per trade: 1% = $500
- Entry: $100. Stop: $97 (risk = $3/share)
- Position size = $500 / $3 = 166 shares
- Dollar exposure = 166 × $100 = $16,600 (33% of account)

**For options:**
- Risk per trade = max loss = premium paid (for long options)
- Or: (spread width − credit received) × number of contracts × 100

---

## Portfolio Heat

**Total portfolio risk at any time = sum of all open trade risks**

Conservative guideline: keep total portfolio heat ≤ 5–6% of account

**Correlated positions amplify risk.** Three long tech positions all move together — treat them as partially correlated. If SPY drops 3% and all three hit stops, you might lose 3% at once, not 1% × 3.

**Correlation-adjusted heat:**
- If you have 3 correlated positions each risking 1%, effective risk ≈ 2–2.5%
- Diversify: different sectors, different strategies (long + short, or long equity + short options)

---

## Stop Loss Placement

**A stop loss is a thesis invalidation point, not just a number.**

Ask: "At what price does my reason for being in this trade no longer hold?"

**Types of stops:**

| Stop Type | Description | Best For |
|---|---|---|
| Structure stop | Below the last swing low / above last swing high | Swing trades, clean chart setups |
| ATR stop | Entry ± 1.5–2× ATR(14) | Volatile stocks, adapts to volatility |
| % stop | Fixed % from entry (e.g., 5–8%) | Simple baseline, less precise |
| Time stop | Exit if thesis doesn't play out within X bars | Theta decay management |
| Moving average stop | Trail stop to 8/21 EMA | Trend-following swing trades |

**Never move a stop to a worse position.** You can trail stops to lock in gains; never widen a stop to avoid a loss.

---

## Risk/Reward (R:R) Ratios

**Minimum acceptable R:R by trade type:**
- Scalp: 1.5:1 (taking more trades, lower win rate acceptable)
- Intraday swing: 2:1
- Overnight swing: 2.5:1 (carries overnight risk premium)
- Position trade: 3:1+

**Expected Value (EV) calculation:**
```
EV = (Win rate × Avg win) − (Loss rate × Avg loss)
```

For EV to be positive, you don't need a high win rate — you need wins to be larger than losses:

| Win Rate | Min R:R for Positive EV |
|---|---|
| 30% | 2.3:1 |
| 40% | 1.5:1 |
| 50% | 1:1 |
| 60% | 0.67:1 |

A 40% win rate with 2:1 R:R has positive EV. Most traders fail by chasing high win rates and accepting bad R:R.

---

## Kelly Criterion (Optional: for sizing confidence levels)

Kelly % = W − [(1 − W) / R]

Where:
- W = win rate (as decimal)
- R = average win / average loss ratio

**Example:** W = 0.55, R = 2.0 → Kelly = 0.55 − (0.45/2) = 0.55 − 0.225 = 32.5%

**Practical use:** Never bet full Kelly — it's theoretically optimal but leads to massive drawdowns. Use **half Kelly** (16% here) or **quarter Kelly** as a max position size.

For most retail traders, Kelly is an academic reference. The 1% rule is more practical.

---

## Drawdown Management

**What to do when you're in a drawdown:**

| Drawdown Level | Action |
|---|---|
| −5% | Review recent trades, identify patterns |
| −10% | Reduce position sizes by 50% |
| −15% | Take a 1–3 day break from trading |
| −20% | Full stop. Reassess strategy before returning |

**Why:** Psychology degrades under losses. Tilt (emotional trading) after losses causes larger losses. The solution is to reduce exposure until you're back to breakeven thinking.

---

## Pre-Trade Checklist

Before entering any trade, confirm:

- [ ] Thesis: what's the specific reason I'm entering?
- [ ] Stop: defined BEFORE entry (not after)
- [ ] Size: calculated using 1% risk rule
- [ ] R:R: at least 2:1 before commissions
- [ ] Catalyst: is there a news event / earnings that could blow through my stop?
- [ ] Market context: is the broader market aligned with this trade direction?
- [ ] Correlation: am I already in a similar trade in this sector?
- [ ] Exit plan: what's my take-profit plan? Scale out at 1R? Hold to target?

---

## Scaling In and Out

**Scaling in (pyramiding):** Add to winners, never to losers
- Initial position: 50–60% of intended size
- Add after confirmation (breakout, pullback holds)
- Move stop on initial position to entry or slightly above

**Scaling out (taking profits):**
- Option 1: Take 50% off at 1R, let remainder run to 2R+
- Option 2: Trail with moving average and let winners run
- Consistency matters more than the exact method

---

## Options-Specific Risk Rules

| Rule | Rationale |
|---|---|
| Never risk > 1–2% of account on a single options trade | Premium can go to zero quickly |
| Set max loss at 2× premium paid for long options | Avoids letting a lottery ticket become a black hole |
| Close losing spread at 2× credit received | Prevents max loss; saves buying power |
| Never hold through earnings unless that's the explicit plan | IV crush destroys long options; undefined risk on shorts |
| Don't sell naked options unless you have defined P/L targets | Unlimited risk; manage aggressively at 50% profit |
