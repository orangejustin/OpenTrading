#!/usr/bin/env python3
"""
whales.py — `ot whales`: labeled-wallet ETH balances via public RPC (P2-6).

Keyless JSON-RPC (eth_getBalance) against a public node. Ships with a starter
set of WELL-KNOWN, publicly documented wallets (Etherscan name-tags / official
docs) across five classes — exchange, bridge, foundation, staking, whale — so
exchange-inflow isn't the only signal. Put YOUR labeled list (any wallets you
track) in the git-ignored `data/wallets.json` to extend or replace it:

    [{"label": "my-whale-1", "address": "0x...", "class": "whale"}]

Each run snapshots balances to data/whales/last.json and prints the DELTA vs
the previous snapshot — exchange inflows (balance up) historically read as
sell-side supply; outflows as accumulation/custody. Output also carries a
per-class net delta (`by_class`).

    python3 whales.py
    python3 whales.py --format json

Optional paid upgrade: Antalpha's hosted "Smart Money Tracker" MCP adds richer,
professionally-labeled whale/VC/market-maker wallets + dollar-threshold signals.
It is a skill/agent-level MCP (register once, attribution required) — NOT wired
into this keyless tool. See docs/SMART_MONEY.md.

Educational only — not financial advice. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import ssl
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RPCS = ("https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com")
UA = "Mozilla/5.0 (OpenTrading whales)"
SNAP = ROOT / "data/whales/last.json"
USER_WALLETS = ROOT / "data/wallets.json"

# Publicly + reliably labeled Ethereum wallets (Etherscan name-tags / official
# docs), spanning five classes so exchange-inflow isn't the only signal. This is
# a STARTER set — extend or replace entirely via data/wallets.json, which never
# leaves your machine. Addresses are EIP-55 checksummed.
DEFAULT_WALLETS = [
    # exchanges — inflow reads as sell-side supply, outflow as accumulation/custody
    {"label": "coinbase-1", "address": "0x71660c4005BA85c37ccec55d0C4493E66Fe775d3", "class": "exchange"},
    {"label": "coinbase-2", "address": "0x503828976D22510aad0201ac7EC88293211D23Da", "class": "exchange"},
    {"label": "kraken-1", "address": "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2", "class": "exchange"},
    {"label": "kraken-4", "address": "0x267be1C1D684F78cb4F6a176C4911b741E4Ffdc0", "class": "exchange"},
    {"label": "binance-14", "address": "0x28C6c06298d514Db089934071355E5743bf21d60", "class": "exchange"},
    {"label": "binance-hot-20", "address": "0xF977814e90dA44bFA03b6295A0616a897441aceC", "class": "exchange"},
    {"label": "okx-1", "address": "0x6cC5F688a315f3dC28A7781717a9A798a59fDA7b", "class": "exchange"},
    {"label": "bitfinex-2", "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e", "class": "exchange"},
    {"label": "gemini-1", "address": "0xd24400ae8BfEBb18cA49Be86258a3C749cf46853", "class": "exchange"},
    # L2 bridges — rising locked ETH = capital rotating onto L2s
    {"label": "arbitrum-bridge", "address": "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a", "class": "bridge"},
    {"label": "optimism-gateway", "address": "0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1", "class": "bridge"},
    {"label": "polygon-ether-bridge", "address": "0x8484Ef722627bf18ca5Ae6BcF031c23E6e922B30", "class": "bridge"},
    {"label": "polygon-pos-bridge", "address": "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77", "class": "bridge"},
    {"label": "base-bridge", "address": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35", "class": "bridge"},
    # foundation / staking — structural, slow-moving supply
    {"label": "ethereum-foundation", "address": "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe", "class": "foundation"},
    {"label": "beacon-deposit", "address": "0x00000000219ab540356cBB839Cbe05303d7705Fa", "class": "staking"},
    {"label": "lido-steth", "address": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84", "class": "staking"},
    # a canonical whale, as a public example
    {"label": "vitalik-eth", "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "class": "whale"},
]


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def _rpc(method: str, params: list):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for host in RPCS:
        try:
            req = urllib.request.Request(host, data=body,
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=12, context=_ctx()) as r:
                return json.loads(r.read().decode()).get("result")
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def wallets() -> list[dict]:
    if USER_WALLETS.exists():
        try:
            user = json.loads(USER_WALLETS.read_text(encoding="utf-8"))
            if isinstance(user, list) and user:
                return user
        except Exception:  # noqa: BLE001
            pass
    return DEFAULT_WALLETS


def balance_eth(addr: str) -> float | None:
    try:
        wei = _rpc("eth_getBalance", [addr, "latest"])
        return round(int(wei, 16) / 1e18, 2) if wei else None
    except Exception:  # noqa: BLE001
        return None


def run() -> dict:
    prev = {}
    if SNAP.exists():
        try:
            prev = json.loads(SNAP.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            prev = {}
    rows = []
    for w in wallets():
        bal = balance_eth(w["address"])
        old = (prev.get("balances") or {}).get(w["address"])
        rows.append({**w, "eth": bal,
                     "delta_eth": round(bal - old, 2) if (bal is not None and old is not None) else None})
    SNAP.parent.mkdir(parents=True, exist_ok=True)
    SNAP.write_text(json.dumps({
        "balances": {r["address"]: r["eth"] for r in rows if r["eth"] is not None}},
        indent=2), encoding="utf-8")
    inflow = sum(r["delta_eth"] for r in rows
                 if r.get("class") == "exchange" and r.get("delta_eth"))
    by_class: dict[str, float] = {}
    for r in rows:
        if r.get("delta_eth"):
            c = r.get("class") or "other"
            by_class[c] = round(by_class.get(c, 0.0) + r["delta_eth"], 2)
    return {"rows": rows, "exchange_net_flow_eth": round(inflow, 2),
            "by_class": by_class,
            "read": ("exchange INFLOW — potential sell-side supply" if inflow > 100
                     else "exchange OUTFLOW — accumulation/custody" if inflow < -100
                     else "flat — no notable movement since last snapshot"),
            "prev_snapshot": bool(prev),
            "source": "keyless"}


def main(argv=None):
    p = argparse.ArgumentParser(prog="ot whales",
                                description="Labeled-wallet ETH balances + deltas (keyless RPC).")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    r = run()
    if a.format == "json":
        print(json.dumps(r, indent=2))
        return
    print("ot whales — labeled wallets (ETH), Δ vs last snapshot")
    for w in r["rows"]:
        d = (f"{w['delta_eth']:+,.1f}" if w.get("delta_eth") is not None
             else "first snapshot" if not r["prev_snapshot"] else "—")
        bal = f"{w['eth']:,.0f}" if w.get("eth") is not None else "err"
        print(f"  {w['label']:<16} {bal:>12} ETH   Δ {d}")
    print(f"  net exchange flow: {r['exchange_net_flow_eth']:+,.1f} ETH — {r['read']}")
    print("  starter set = public exchange cold wallets; your own list lives in "
          "data/wallets.json (git-ignored). Educational only.")


if __name__ == "__main__":
    main()
