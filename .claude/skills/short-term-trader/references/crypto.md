# Crypto Trading Reference

## How Crypto Markets Differ From Equities

| Factor | Equities | Crypto |
|---|---|---|
| Market hours | 9:30–4:00 ET (with pre/after) | 24/7/365 |
| Circuit breakers | Yes (halts at ±7%, ±13%, ±20%) | No |
| Regulatory oversight | SEC, FINRA | Varies by jurisdiction |
| Leverage availability | 2:1 retail, 4:1 pattern day traders | Up to 100x+ on derivatives |
| Volatility | SPY ADR ~0.8%. Individual stocks 2–5% | BTC ADR ~3–5%. Alts 5–20%+ |
| Manipulation risk | Lower (large cap) | Higher (especially small caps) |
| Market structure | Highly regulated, audited | Fragmented, varies by exchange |

**Implication**: Crypto requires tighter stops, smaller position sizes, and constant awareness that markets never close.

---

## Key Crypto Market Dynamics

### Bitcoin (BTC) as Market Leader
- BTC dominance (BTC's % of total crypto market cap) is a key indicator
- Rising BTC dominance → capital flows to BTC, alts often fall (risk-off)
- Falling BTC dominance → alt season, small caps outperform
- BTC leads the market. Most altcoins are highly correlated with BTC on big moves

### Altcoin Behavior
- Large caps (ETH, SOL, BNB): ~0.7–0.9 correlation to BTC
- Mid/small caps: can move 3–5x BTC's % move (both up and down)
- Low liquidity alts: prone to wash trading, manipulation, pump-and-dump schemes
- **Rule**: Treat altcoin positions as higher-beta BTC positions unless there's a specific catalyst

### Funding Rates (Perpetual Futures)
- Perpetual contracts have no expiry; funding rate keeps price anchored to spot
- Positive funding: longs pay shorts (market is bullish/overleveraged long)
- Negative funding: shorts pay longs (market is bearish/overleveraged short)
- **Extreme positive funding (> 0.1%/8h)**: overcrowded longs → contrarian bearish signal; potential long squeeze
- **Extreme negative funding**: overcrowded shorts → contrarian bullish signal; potential short squeeze

### Open Interest (OI) in Derivatives
- Total value of open futures/options contracts
- Rising OI + rising price = new longs entering (trend confirmation)
- Rising OI + falling price = new shorts entering (bearish pressure)
- Falling OI + price reversal = short/long squeeze (positions being liquidated)

### Liquidations
- Leveraged positions get auto-liquidated at certain price levels
- Large liquidation clusters at key levels → if price reaches those levels, cascading moves
- Tools: Coinglass, Hyblock — show liquidation heatmaps
- **Liquidation cascade**: price hits a cluster → triggers liquidations → more selling/buying → bigger move

---

## On-Chain Signals

### Exchange Net Flow
- Net inflow to exchanges (coins moving to exchanges): potential sell pressure
- Net outflow from exchanges (coins leaving to wallets): accumulation, bullish signal
- Large BTC inflows to exchanges historically precede selloffs

### Whale Activity
- Large wallet movements tracked on-chain
- "Dormant whale" wallets moving after years of inactivity → often precedes price moves
- Watch: Whale Alert (Twitter/X), Nansen, Arkham Intelligence

### MVRV Ratio (Market Value to Realized Value)
- Realized value = sum of all coins valued at last time they moved (avg cost basis)
- MVRV > 3.5: market is historically overextended (near tops)
- MVRV < 1: coins are worth less than their cost basis (near bottoms)
- Best for macro positioning, not short-term trades

### Fear & Greed Index
- 0 = Extreme Fear, 100 = Extreme Greed
- Contrarian use: extreme fear = buy opportunity; extreme greed = take profits
- Best combined with technical levels, not used in isolation

---

## Crypto Technical Analysis Nuances

### Same Patterns Apply, Different Parameters
- All TA patterns work: flags, triangles, H&S, double tops/bottoms
- But moves are more volatile → use **wider stops** (1.5–2× ATR vs 1× for equities)
- Support/resistance levels from high-volume periods are more reliable
- Round numbers ($30K, $50K, $100K BTC) act as major psychological levels

### Key Intraday Levels
- **Asian session high/low**: often forms the day's range. Breakout from Asian range is a common trigger
- **Previous day high/low**: most watched levels by crypto traders
- **Coinbase premium**: BTC price difference between Coinbase and Binance. Positive premium = US retail/institutions buying

### Market Sessions (UTC)
- **Asia**: 00:00–08:00 UTC (lower volume, range-bound)
- **Europe**: 07:00–16:00 UTC (increasing volume)
- **US**: 13:00–22:00 UTC (highest volume, most volatility)
- Significant news / liquidation events can happen any time

---

## Crypto Derivatives

### Perpetual Futures
- Most popular crypto derivative. No expiry.
- Leverage: use conservatively. 3–5× maximum for swing trades; higher only for very short scalps
- **Risk**: liquidation price. Always know yours before entry.
- Margin types: Cross margin (riskier: entire account as collateral) vs. Isolated margin (recommended: only allocated margin at risk)

### Crypto Options
- Available on Deribit (most liquid), OKX, Binance
- Same principles as equity options apply
- IV tends to be much higher than equities (BTC IV often 60–100%+)
- Bitcoin options drive significant price action around large expiries (last Friday of each month)
- Max pain at option expiry is widely watched

---

## DeFi Trading Considerations

### Spot DEX Trading (Uniswap, etc.)
- **Slippage**: on illiquid pairs, large orders move price significantly. Set max slippage carefully.
- **MEV / Sandwich attacks**: bots can front-run your transaction on-chain. Use DEX aggregators (1inch, Paraswap) or private RPC (Flashbots Protect) to minimize.
- **Gas costs**: ETH gas can make small trades uneconomical. Consider on L2s (Arbitrum, Base, Optimism).

### Perpetual DEXs (GMX, Hyperliquid, dYdX)
- Decentralized perpetuals with on-chain settlement
- Hyperliquid: most liquid decentralized perps, high-frequency trade data public on-chain
- Counterparty: you trade against the protocol's liquidity pool, not other users
- **Advantage**: no KYC, no withdrawal limits, self-custody
- **Risk**: smart contract exploits; protocol insolvency events

---

## Crypto Risk Management Specifics

| Rule | Rationale |
|---|---|
| Never risk > 1% per trade in crypto | Volatility is 3–5× equities |
| Keep leverage < 5× for swings, < 10× for scalps | Leverage liquidations have no mercy |
| Always use isolated margin, not cross margin | Limits total loss to position, not account |
| Have a hardware wallet for long-term holds | Exchange insolvency risk (FTX, etc.) is real |
| Don't trade low-liquidity alts without knowing exit | Can't exit in a crash; bid disappears |
| Set liquidation price alert before sleeping | Crypto never sleeps; you need to know your levels |

**Weekend liquidity warning**: Crypto markets are thin on weekends, especially Saturday night. Moves can be exaggerated in either direction. Reduce position sizes Friday-Saturday if holding leveraged positions.
