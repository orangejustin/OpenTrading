#!/usr/bin/env python3
"""
q.py — no-key quotes via Yahoo Finance v8 chart, including pre/post-market.

A stand-in for a live quote feed (until IBKR lands): last price + % change for
stocks / ETFs / indices (e.g. ^VIX), with no API key.

    python3 q.py MSTR ORCL HOOD SPCX
    python3 q.py --watchlist                 # tickers from watchlist.json
    python3 q.py SPY QQQ ^VIX --format json

Stdlib only (Python 3.9+); uses certifi if present, else falls back to curl.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import ssl
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UA = "Mozilla/5.0 (OpenTrading q-cli)"
URL = ("https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
       "?includePrePost=true&interval=5m&range=1d")


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        curl = shutil.which("curl")
        if curl:
            out = subprocess.run([curl, "-s", "--max-time", str(timeout), "-A", UA, url],
                                 capture_output=True, text=True, timeout=timeout + 5)
            if out.returncode == 0 and out.stdout:
                return out.stdout
        raise


def quote(sym):
    d = json.loads(http_get(URL.format(sym=urllib.parse.quote(sym))))
    res = d["chart"]["result"][0]
    m = res["meta"]
    ts = res.get("timestamp") or []
    closes = ((res.get("indicators", {}).get("quote", [{}]) or [{}])[0] or {}).get("close") or []
    last = m.get("regularMarketPrice")
    last_ts = m.get("regularMarketTime")
    for i in range(len(closes) - 1, -1, -1):              # latest tick incl pre/post
        if closes[i] is not None:
            last = closes[i]
            last_ts = ts[i] if i < len(ts) else last_ts
            break
    reg_price = m.get("regularMarketPrice")               # last *regular* session price
    reg_time = m.get("regularMarketTime")
    prev_close = m.get("chartPreviousClose") or m.get("previousClose")
    # An extended-hours tick (after the regular close) is measured vs that close.
    if last_ts and reg_time and last_ts > reg_time + 300 and reg_price:
        baseline, session = reg_price, "EXT"
    else:
        baseline = prev_close
        last = reg_price if reg_price is not None else last
        session = "REG"
    chg = (last - baseline) / baseline * 100 if (last and baseline) else None
    return {"symbol": sym.upper(), "last": last, "prev": baseline, "chg_pct": chg,
            "session": session, "currency": m.get("currency")}


def load_watchlist_syms():
    # OT_WATCHLIST overrides the default path — lets the GitHub Actions market
    # email point at a position-free list without touching a real watchlist.json.
    p = Path(os.environ.get("OT_WATCHLIST") or (ROOT / "watchlist.json"))
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return [pos["ticker"] for pos in data.get("positions", []) if pos.get("ticker")]
        except Exception:
            return []
    return []


def get_many(syms):
    out = []
    for s in syms:
        try:
            out.append(quote(s))
        except Exception as exc:  # noqa: BLE001 - one bad symbol shouldn't kill the run
            out.append({"symbol": s.upper(), "error": str(exc)})
    return out


def render_table(rows):
    L = [f"{'SYM':<7} {'LAST':>10} {'CHG%':>9}  SESS"]
    for r in rows:
        if r.get("error"):
            L.append(f"{r['symbol']:<7} {'ERR':>10} {'':>9}  {r['error'][:34]}")
            continue
        last = f"{r['last']:,.2f}" if r.get("last") is not None else "n/a"
        chg = f"{r['chg_pct']:+.2f}%" if r.get("chg_pct") is not None else "n/a"
        c = r.get("chg_pct") or 0
        arrow = "▲" if c > 0 else "▼" if c < 0 else "·"
        L.append(f"{r['symbol']:<7} {last:>10} {chg:>9}  {arrow} {r.get('session','')}")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(prog="q", description="No-key quotes (Yahoo Finance).")
    p.add_argument("symbols", nargs="*", help="Tickers, e.g. MSTR SPY ^VIX")
    p.add_argument("--watchlist", action="store_true", help="Add tickers from watchlist.json.")
    p.add_argument("--format", choices=["table", "json"], default="table")
    a = p.parse_args(argv)
    syms = list(a.symbols)
    if a.watchlist:
        syms += load_watchlist_syms()
    if not syms:
        syms = ["SPY", "QQQ", "^VIX"]
    # de-dupe (case-insensitive, order-preserving) so a symbol is never quoted twice
    seen, uniq = set(), []
    for s in syms:
        k = s.upper()
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    syms = uniq
    rows = get_many(syms)
    print(json.dumps(rows, indent=2) if a.format == "json" else render_table(rows))


if __name__ == "__main__":
    main()
