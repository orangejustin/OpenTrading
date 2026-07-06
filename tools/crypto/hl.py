#!/usr/bin/env python3
"""
hl.py — `ot hl`: Hyperliquid perp positioning for the BTC-beta book (P2-9).

Keyless POST to api.hyperliquid.xyz/info — funding, open interest and mark
for the majors. Funding is the crowd's leverage bill: extreme positive =
longs pay shorts = crowded upside (contrarian caution for IBIT/HOOD/MSTR
beta); negative = shorts pay = washed out.

    python3 hl.py                 # BTC ETH SOL
    python3 hl.py BTC --format json

Educational only — not financial advice. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import ssl
import urllib.request

API = "https://api.hyperliquid.xyz/info"
UA = "Mozilla/5.0 (OpenTrading hl)"
DEFAULT = ["BTC", "ETH", "SOL"]


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def fetch() -> tuple[dict, list]:
    req = urllib.request.Request(
        API, data=json.dumps({"type": "metaAndAssetCtxs"}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15, context=_ctx()) as r:
        universe, ctxs = json.loads(r.read().decode())
    return universe, ctxs


def read_funding(rate_8h_pct: float) -> str:
    if rate_8h_pct >= 0.05:
        return "HOT — longs paying up, crowded upside (contrarian caution)"
    if rate_8h_pct >= 0.02:
        return "warm — mild long bias"
    if rate_8h_pct <= -0.02:
        return "NEGATIVE — shorts paying, washed out (contrarian support)"
    return "neutral — no leverage crowding"


def collect(symbols: list[str]) -> list[dict]:
    universe, ctxs = fetch()
    idx = {a["name"]: i for i, a in enumerate(universe.get("universe", []))}
    out = []
    for s in symbols:
        i = idx.get(s.upper())
        if i is None or i >= len(ctxs):
            out.append({"symbol": s.upper(), "error": "not listed"})
            continue
        c = ctxs[i]
        f1h = float(c.get("funding") or 0)         # hourly rate
        f8h = f1h * 8 * 100                        # % per 8h (BTC-perp convention)
        mark = float(c.get("markPx") or 0)
        oi_units = float(c.get("openInterest") or 0)
        out.append({
            "symbol": s.upper(), "mark": mark,
            "funding_8h_pct": round(f8h, 4),
            "funding_apr_pct": round(f1h * 24 * 365 * 100, 2),
            "open_interest": oi_units,
            "open_interest_usd": round(oi_units * mark, 0) if mark else None,
            "premium": c.get("premium"),
            "read": read_funding(f8h),
        })
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="ot hl",
                                description="Hyperliquid perp funding/OI (keyless).")
    p.add_argument("symbols", nargs="*", default=None)
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    rows = collect([s.upper() for s in (a.symbols or DEFAULT)])
    if a.format == "json":
        print(json.dumps({"rows": rows}, indent=2))
        return
    print("ot hl — Hyperliquid perp positioning (the BTC-beta crowd's leverage bill)")
    for r in rows:
        if r.get("error"):
            print(f"  {r['symbol']:<5} {r['error']}")
            continue
        oi = f"${r['open_interest_usd']/1e9:.2f}bn" if r.get("open_interest_usd") else "—"
        print(f"  {r['symbol']:<5} mark {r['mark']:>10,.1f}  funding {r['funding_8h_pct']:+.4f}%/8h"
              f" (≈{r['funding_apr_pct']:+.1f}% APR)  OI {oi}")
        print(f"        {r['read']}")
    print("  extreme positive funding = crowded longs — size IBIT/MSTR beta accordingly."
          "  Educational only.")


if __name__ == "__main__":
    main()
