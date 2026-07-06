#!/usr/bin/env python3
"""
whales.py — `ot whales`: labeled-wallet ETH balances via public RPC (P2-6).

Keyless JSON-RPC (eth_getBalance) against a public node. Ships with a small
set of WELL-KNOWN, publicly documented exchange cold wallets as a starter
taxonomy; put YOUR labeled list (any wallets you track) in the git-ignored
`data/wallets.json`:

    [{"label": "binance-cold-1", "address": "0x...", "class": "exchange"}]

Each run snapshots balances to data/whales/last.json and prints the DELTA vs
the previous snapshot — exchange inflows (balance up) historically read as
sell-side supply; outflows as accumulation/custody.

    python3 whales.py
    python3 whales.py --format json

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

# public knowledge, widely documented exchange cold wallets (starter set —
# extend/replace via data/wallets.json, which never leaves your machine)
DEFAULT_WALLETS = [
    {"label": "binance-cold-7", "address": "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8", "class": "exchange"},
    {"label": "binance-cold-8", "address": "0xF977814e90dA44bFA03b6295A0616a897441aceC", "class": "exchange"},
    {"label": "bitfinex-cold", "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e", "class": "exchange"},
    {"label": "kraken-cold-4", "address": "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2", "class": "exchange"},
    {"label": "okx-cold-1", "address": "0x6Cc5F688a315f3dC28A7781717a9A798a59fDA7b", "class": "exchange"},
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
    return {"rows": rows, "exchange_net_flow_eth": round(inflow, 2),
            "read": ("exchange INFLOW — potential sell-side supply" if inflow > 100
                     else "exchange OUTFLOW — accumulation/custody" if inflow < -100
                     else "flat — no notable movement since last snapshot"),
            "prev_snapshot": bool(prev)}


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
