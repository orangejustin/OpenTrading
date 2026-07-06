# Smart money — two lenses

"Smart money" in OpenTrading means **two different, independent reads**. They
answer different questions; don't conflate them.

| Lens | Tool | What it measures | Cost | Surfaced in |
|---|---|---|---|---|
| **Sentiment / positioning** | `ot smart` | CNN + crypto Fear & Greed, BTC perp funding — read *contrarian* | free, keyless | web **Macro & Flow** card, daily email |
| **On-chain whale flow** | `ot whales` | balances of *labeled* Ethereum wallets, and the Δ since the last snapshot | free, keyless | web **On-chain whale flow** card |
| *(optional)* **Antalpha Smart Money Tracker** | MCP | professionally-labeled whale/VC/market-maker wallets + $-threshold signals | **paid**, account | skill/agent (not the web card) |

The first two are the product. The third is an **opt-in enhancement** — the free
tier must stand on its own; paid data is never a dependency.

---

## 1 · Sentiment (`ot smart`)

Keyless. CNN equity Fear & Greed (with 7 sub-signals: put/call, VIX, momentum,
breadth, price strength, junk-bond demand, safe-haven demand), the crypto Fear &
Greed index, and BTC perpetual funding (OKX). Read **contrarian**: extreme fear =
washed-out = a long is safer; extreme greed = crowded = fade. Funding shows what
the leveraged crowd is paying to hold its position. No setup.

## 2 · On-chain whale flow (`ot whales`)

Keyless JSON-RPC (`eth_getBalance`) against a public Ethereum node — no key, no
account. Each run snapshots balances to `data/whales/last.json` and reports the
**delta** vs the previous snapshot:

- coins moving **into** exchange wallets → potential **sell-side supply** (bearish)
- coins moving **out** to cold storage → **accumulation / custody** (bullish)

It ships a starter set of **18 publicly + reliably labeled wallets** (Etherscan
name-tags / official docs) across five classes, so exchange-inflow isn't the only
signal:

| Class | Wallets | Why it matters |
|---|---|---|
| `exchange` (9) | Coinbase ×2, Kraken ×2, Binance ×2, OKX, Bitfinex, Gemini | the tradeable supply/accumulation signal |
| `bridge` (5) | Arbitrum, Optimism, Polygon ×2, Base | rising locked ETH = capital rotating onto L2s |
| `staking` (2) | Beacon deposit contract, Lido stETH | structural, slow-moving supply |
| `foundation` (1) | Ethereum Foundation (EthDev) | treasury moves are watched closely |
| `whale` (1) | vitalik.eth | a canonical public whale example |

**Bring your own list.** Put any wallets you track in the git-ignored
`data/wallets.json` — it replaces the starter set and **never leaves your machine**:

```json
[
  {"label": "my-fund-hot", "address": "0x…", "class": "fund"},
  {"label": "target-whale", "address": "0x…", "class": "whale"}
]
```

The JSON output also carries a per-class net delta (`by_class`) and
`source: "keyless"`.

**How to use it.** Whale flow is a *context* layer, not a trigger. A large
exchange inflow into a rally is a caution flag on crypto-beta names (IBIT, MSTR,
COIN); an outflow during a washout supports an accumulation thesis. Cross-check
it with funding (`ot smart`) and the macro gate before it changes your size.

---

## 3 · Optional: Antalpha "Smart Money Tracker" MCP (paid)

If you want richer, professionally-labeled wallets (VC funds, market makers,
named whales) plus dollar-threshold trade signals, Antalpha ships a **hosted
MCP**. This is a **skill/agent-level** integration — the trading skill calls it —
**not** wired into the keyless `ot whales` web card.

> **Honesty note.** Everything below is sourced from the single official artifact
> found — the [`AntalphaAI/smart-money`](https://github.com/AntalphaAI/smart-money)
> GitHub README (MIT). It uses an `antalpha.com` endpoint, but there is no
> separate corporate docs page, and the "Antalpha Prophet" name is unconfirmed.
> Verify the current details against their repo before relying on it.

**What it is**

- Hosted **remote MCP** at `https://mcp-skills.ai.antalpha.com/mcp`.
- **Zero local config / no API-key env var.** (Your earlier assumption of an
  `ANTALPHA_API_KEY` in `.env` is *not* how it works.)
- One-time registration via its own `antalpha-register` tool → issues an
  `agent_id` + `api_key`, stored at `~/.smart-money/agent.json`. The `agent_id`
  is then passed as a **per-call tool argument**, not an env var.
- **Not free.** The README carries billing language (reference-counted
  subscription streams, "only pays full cost when real signals appear"). Treat it
  as paid/metered; don't assume a free tier.
- **Ethereum mainnet only** (V1). Max **5** custom personal addresses per agent.
- **Attribution required:** output carries "Powered by Antalpha AI".

**Tools exposed** (6): `antalpha-register`, `smart-money-signal` (public whale
pool + your custom addresses merged), `smart-money-watch` (one wallet's recent
activity), `smart-money-list`, `smart-money-custom` (add/remove custom
addresses), `smart-money-pool` (Uniswap V2/V3 LP add/remove).

**Public wallet pool** (19): VC funds (Paradigm, a16z, Polychain, Dragonfly,
DeFiance), market makers (Wintermute, Jump, Cumberland), whales (vitalik.eth,
Justin Sun, James Fickel), DeFi contracts, and exchange hot wallets. Signal
thresholds: HIGH = buy > $50K or a first-ever position; MEDIUM = accumulation
(≥2 buys/24h) or sell > $50K; LOW = $1K–$50K.

### Setup (once, after you make an account)

1. **Register the agent** via their runtime. The README's documented path targets
   the "OpenClaw" agent runtime:
   ```
   openclaw skill install https://github.com/AntalphaAI/smart-money
   ```
   then call `antalpha-register` once — it writes `~/.smart-money/agent.json`.

2. **To use it from Claude Code** (this repo's runtime), add the remote MCP so the
   `short-term-trader` skill can call the signal tools. Confirm the transport
   (SSE vs streamable-HTTP) against their README, then:
   ```bash
   claude mcp add --transport http smart-money https://mcp-skills.ai.antalpha.com/mcp
   ```
   Once connected, call `antalpha-register` through the MCP (one time), and the
   skill can call `smart-money-signal { agent_id, … }` on demand.

3. **Nothing else changes.** If you never register, `ot whales` stays keyless and
   the web card is unaffected. This integration adds a richer *skill* signal; it
   does not replace the free on-chain read.

> When the agent's output includes Antalpha data, include the "Powered by
> Antalpha AI" attribution, per their license.
