---
title: Smart money
sidebar_position: 6
---

# Smart money — two lenses

"Smart money" means **two different, independent reads**. They answer different
questions; don't conflate them.

| Lens | Tool | Measures | Cost |
|---|---|---|---|
| **Sentiment / positioning** | `ot smart` | Fear & Greed + perp funding, read *contrarian* | free, keyless |
| **On-chain whale flow** | `ot whales` | labeled-wallet ETH balances + Δ | free, keyless |
| *(optional)* **Antalpha** | MCP | pro-labeled whale/VC/MM wallets + $-signals | **paid** |

## 1 · Sentiment (`ot smart`)

CNN equity Fear & Greed (with 7 sub-signals), the crypto Fear & Greed index, and
BTC perpetual funding. Read **contrarian**: extreme fear = washed-out = a long is
safer; extreme greed = crowded = fade.

## 2 · On-chain whale flow (`ot whales`)

Keyless JSON-RPC against a public Ethereum node — no key, no account. Each run
snapshots balances and reports the **delta** since last time:

- coins **into** exchange wallets → potential **sell-side supply** (bearish)
- coins **out** to cold storage → **accumulation / custody** (bullish)

It ships **18 publicly-labeled wallets** across five classes (exchange, bridge,
staking, foundation, whale). Bring your own in the git-ignored `data/wallets.json`;
it never leaves your machine.

Whale flow is a *context* layer, not a trigger. Cross-check it with funding and
the macro gate before it changes your size.

## 3 · Optional: Antalpha (paid)

If you want richer, professionally-labeled wallets plus dollar-threshold signals,
Antalpha ships a **hosted MCP** — a *skill/agent-level* add-on that is **not**
wired into the keyless tool. It requires a one-time registration (its own
`antalpha-register` tool), is **paid/metered**, and requires "Powered by Antalpha
AI" attribution.

You never need an account for the core: `ot whales` and the dashboard card stay
keyless. The full, verified setup — endpoint, tools, wallet pool, thresholds — is
in the repo:
[**docs/SMART_MONEY.md**](https://github.com/orangejustin/OpenTrading/blob/main/docs/SMART_MONEY.md).
