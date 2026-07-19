#!/usr/bin/env python3
"""
conc.py — what you are actually betting on (`ot conc`).

A position list flatters you: eight rows look like eight bets. Grouped by
*complex* — the map the risk gate already uses — the same book can be five
bets, two of them levered on top of their own unleveraged version.

This is the read the daily email leads with, because concentration is the risk
that compounds silently. Nobody discovers it from a row of tickers.

  ot conc                  the book by complex, with the levered share
  ot conc --format json    for the email pack
  ot conc --alerts         only the lines that warrant action (exit 1 if any)

Levered exposure is reported two ways: NOTIONAL (market value) and EFFECTIVE
(market value x the daily-reset multiple), because a 2x position is twice the
market risk of its dollar value. A book that looks 60% invested can carry 90%
effective exposure.

Reads the git-ignored watchlist.json. Never prints to anywhere shared.
Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WATCHLIST = os.environ.get("OT_WATCHLIST") or os.path.join(ROOT, "watchlist.json")
UA = "Mozilla/5.0 (OpenTrading conc-cli)"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from propose import LEVERAGED           # one map, one source of truth
except Exception:  # noqa: BLE001
    LEVERAGED = {}

# Thresholds worth a line in the morning note.
MAX_COMPLEX_PCT = 35.0      # any single complex above this is a concentration call
MAX_EFFECTIVE_PCT = 120.0   # effective exposure above this is levered beyond the book


def _ctx():
    try:
        import certifi
        import ssl
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        import ssl
        return ssl.create_default_context()


def quote(sym: str) -> float | None:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
           f"?range=1d&interval=1d")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=_ctx()) as r:
            m = json.loads(r.read().decode("utf-8", "replace"))["chart"]["result"][0]["meta"]
        return m.get("regularMarketPrice") or m.get("previousClose")
    except Exception:  # noqa: BLE001
        try:
            import shutil
            curl = shutil.which("curl")
            if not curl:
                return None
            out = subprocess.run([curl, "-sL", "--max-time", "15", "-A", UA, url],
                                 capture_output=True, text=True, timeout=20)
            m = json.loads(out.stdout)["chart"]["result"][0]["meta"]
            return m.get("regularMarketPrice") or m.get("previousClose")
        except Exception:  # noqa: BLE001
            return None


def build() -> dict | None:
    try:
        with open(WATCHLIST) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    cash = ((d.get("cash") or {}).get("amount") or 0) if isinstance(d.get("cash"), dict) \
        else (d.get("cash") or 0)

    holdings = []
    for p in d.get("positions") or []:
        t = str(p.get("ticker") or "").upper()
        sh = p.get("shares")
        if not t or not sh:
            continue
        px = quote(t)
        if px is None:
            continue
        mult, cx = LEVERAGED.get(t, (1.0, t.lower()))
        mv = px * sh
        holdings.append({"ticker": t, "shares": sh, "price": round(px, 4),
                         "market_value": round(mv, 2), "multiple": mult,
                         "complex": cx or t.lower(),
                         "effective_value": round(mv * abs(mult), 2)})
    if not holdings:
        return None
    invested = sum(h["market_value"] for h in holdings)
    total = invested + cash

    comps: dict = {}
    for h in holdings:
        c = comps.setdefault(h["complex"], {"complex": h["complex"], "names": [],
                                            "market_value": 0.0, "effective_value": 0.0,
                                            "levered_value": 0.0})
        c["names"].append(f"{h['ticker']}({h['multiple']:g}x)")
        c["market_value"] += h["market_value"]
        c["effective_value"] += h["effective_value"]
        if abs(h["multiple"]) > 1.0:
            c["levered_value"] += h["market_value"]

    rows = []
    for c in comps.values():
        stacked = (c["levered_value"] > 0 and len(c["names"]) > 1)
        rows.append({
            "complex": c["complex"], "names": c["names"],
            "market_value": round(c["market_value"], 2),
            "pct_of_book": round(100 * c["market_value"] / total, 1) if total else None,
            "effective_value": round(c["effective_value"], 2),
            "effective_pct_of_book": round(100 * c["effective_value"] / total, 1) if total else None,
            "levered_pct_of_complex": round(100 * c["levered_value"] / c["market_value"], 1)
            if c["market_value"] else 0.0,
            "stacked": stacked,
        })
    rows.sort(key=lambda r: -(r["market_value"]))

    eff_total = sum(h["effective_value"] for h in holdings)
    lev_mv = sum(h["market_value"] for h in holdings if abs(h["multiple"]) > 1.0)

    alerts = []
    for r in rows:
        if r["stacked"]:
            alerts.append(f"{r['complex'].upper()} is stacked — {' + '.join(r['names'])} are one "
                          f"bet, {r['pct_of_book']}% of book "
                          f"({r['levered_pct_of_complex']}% of it levered)")
        if r["pct_of_book"] and r["pct_of_book"] > MAX_COMPLEX_PCT:
            alerts.append(f"{r['complex'].upper()} is {r['pct_of_book']}% of book — above the "
                          f"{MAX_COMPLEX_PCT:g}% single-complex line")
    eff_pct = round(100 * eff_total / total, 1) if total else None
    if eff_pct and eff_pct > MAX_EFFECTIVE_PCT:
        alerts.append(f"effective exposure is {eff_pct}% of book — leverage is carrying more "
                      f"market risk than you have capital")

    return {
        "total_book": round(total, 2), "invested": round(invested, 2), "cash": round(cash, 2),
        "invested_pct": round(100 * invested / total, 1) if total else None,
        "effective_exposure": round(eff_total, 2), "effective_pct_of_book": eff_pct,
        "levered_market_value": round(lev_mv, 2),
        "levered_pct_of_invested": round(100 * lev_mv / invested, 1) if invested else 0.0,
        "complexes": rows, "holdings": holdings, "alerts": alerts,
    }


def render(r: dict, alerts_only: bool = False) -> str:
    if alerts_only:
        return "\n".join(f"  ⚠ {a}" for a in r["alerts"]) or "  no concentration alerts"
    L = ["ot conc — the book by COMPLEX (what you are actually betting on)",
         f"  book ${r['total_book']:,.0f}  ·  invested {r['invested_pct']}%"
         f"  ·  cash ${r['cash']:,.0f}",
         f"  effective exposure ${r['effective_exposure']:,.0f}"
         f" = {r['effective_pct_of_book']}% of book"
         f"   (leverage adds {r['effective_pct_of_book'] - r['invested_pct']:.1f}pt)",
         f"  {r['levered_pct_of_invested']}% of invested capital sits in daily-reset vehicles",
         ""]
    L.append(f"  {'complex':<10} {'% book':>7} {'eff %':>7} {'lev %':>7}  names")
    for c in r["complexes"]:
        flag = " ← STACKED" if c["stacked"] else ""
        L.append(f"  {c['complex']:<10} {c['pct_of_book']:>6.1f}% {c['effective_pct_of_book']:>6.1f}%"
                 f" {c['levered_pct_of_complex']:>6.0f}%  {', '.join(c['names'])}{flag}")
    if r["alerts"]:
        L.append("")
        for a in r["alerts"]:
            L.append(f"  ⚠ {a}")
    L.append("")
    L.append("  eff % = market value x the daily-reset multiple: what the tape actually moves.")
    L.append("  Educational only — not financial advice.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="conc", description="Portfolio concentration by complex.")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--alerts", action="store_true",
                    help="print only actionable lines; exit 1 when any fire")
    a = ap.parse_args(argv)
    r = build()
    if not r:
        print("ot conc — no priced positions (check watchlist.json)", file=sys.stderr)
        return 1
    if a.format == "json":
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 1 if (a.alerts and r["alerts"]) else 0
    print(render(r, alerts_only=a.alerts))
    return 1 if (a.alerts and r["alerts"]) else 0


if __name__ == "__main__":
    sys.exit(main())
