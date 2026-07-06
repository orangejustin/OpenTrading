#!/usr/bin/env python3
"""
validate.py — `ot validate`: cross-source data sanity gate (F7).

Every OpenTrading number ultimately traces to a feed, and until now each feed
was checked only against itself. This tool diffs the SAME facts across
independent paths and flags disagreement:

    yahoo q1 vs q2   the two chart hosts (host skew / stale cache / 429 lies)
    yahoo vs cboe    price/close across two unrelated vendors (cdn.cboe.com
                     delayed quotes — the same keyless feed ot options trusts)

Thresholds: intra-Yahoo last > 0.10% = WARN (same vendor should agree);
cross-vendor > 0.50% = WARN after trying every honest pairing (CBOE is
~15-min delayed, so we accept a match on ANY of last/close/prev-close;
if NO pairing reconciles, somebody is wrong).

    python3 validate.py NVDA META SPY
    python3 validate.py --watchlist --format json

In-session, Claude can additionally cross-check against the TradingView MCP
feed (exchange-licensed) — this CLI covers the keyless, scriptable core.
Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UA = "Mozilla/5.0 (OpenTrading validate)"
INTRA_YAHOO_WARN = 0.10   # % — query1 vs query2 last
CROSS_VENDOR_WARN = 0.50  # % — yahoo last/prev vs cboe current/close/prev


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def _get(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return r.read().decode("utf-8", "replace")


def yahoo_last(sym: str, host: str) -> tuple[float | None, float | None]:
    """(last, regular prev/last close) from one Yahoo chart host."""
    url = (f"https://{host}/v8/finance/chart/{urllib.parse.quote(sym)}"
           "?interval=1d&range=5d&includePrePost=false")
    try:
        meta = (json.loads(_get(url)).get("chart", {}).get("result") or [{}])[0].get("meta", {})
        return meta.get("regularMarketPrice"), meta.get("previousClose")
    except Exception:  # noqa: BLE001
        return None, None


def cboe_quote(sym: str) -> dict | None:
    """Delayed quote from CBOE (independent vendor; stocks/ETFs, no indices)."""
    if sym.startswith("^"):
        return None
    try:
        d = json.loads(_get("https://cdn.cboe.com/api/global/delayed_quotes/quotes/"
                            f"{urllib.parse.quote(sym.upper())}.json")).get("data") or {}
        out = {k: d.get(k) for k in ("current_price", "close", "prev_day_close")}
        return out if any(v for v in out.values()) else None
    except Exception:  # noqa: BLE001
        return None


def _pct(a: float, b: float) -> float:
    return abs(a / b - 1) * 100


def check(sym: str) -> dict:
    with ThreadPoolExecutor(max_workers=3) as ex:
        f1 = ex.submit(yahoo_last, sym, "query1.finance.yahoo.com")
        f2 = ex.submit(yahoo_last, sym, "query2.finance.yahoo.com")
        fs = ex.submit(cboe_quote, sym)
    (l1, p1), (l2, _p2), cb = f1.result(), f2.result(), fs.result()
    issues = []
    if l1 is None and l2 is None:
        issues.append("yahoo unreachable on BOTH chart hosts")
    elif l1 is None or l2 is None:
        issues.append(f"yahoo host down: {'query1' if l1 is None else 'query2'}")
    elif l1 and l2 and _pct(l1, l2) > INTRA_YAHOO_WARN:
        issues.append(f"yahoo hosts disagree: q1 {l1} vs q2 {l2} "
                      f"({_pct(l1, l2):.2f}% > {INTRA_YAHOO_WARN}%)")
    # cross-vendor: CBOE is ~15-min delayed, so accept ANY honest pairing —
    # only "no pairing reconciles" counts as drift.
    matched = None
    if cb:
        for yv in (l1, l2, p1):
            for ck, cv in cb.items():
                if yv and cv and _pct(yv, cv) <= CROSS_VENDOR_WARN:
                    matched = (yv, ck, cv)
                    break
            if matched:
                break
    if cb is None:
        if not sym.startswith("^"):
            issues.append("cboe: no data (cross-vendor check skipped)")
    elif matched is None:
        issues.append(f"cross-vendor drift: yahoo {l1 or l2 or p1} vs cboe {cb} "
                      f"(no pairing within {CROSS_VENDOR_WARN}%) — verify before trusting levels")
    return {"symbol": sym.upper(), "yahoo_q1": l1, "yahoo_q2": l2,
            "yahoo_prev": p1, "cboe": cb,
            "ok": not issues, "issues": issues}


def watchlist_syms() -> list[str]:
    p = ROOT / "watchlist.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        out = [x.get("ticker") for x in (d.get("positions") or []) if x.get("ticker")]
        out += [x.get("ticker") for x in (d.get("watch") or []) if x.get("ticker")]
        return list(dict.fromkeys(out))[:20]
    except Exception:  # noqa: BLE001
        return []


def main(argv=None):
    p = argparse.ArgumentParser(prog="ot validate",
                                description="Cross-source quote sanity gate (keyless).")
    p.add_argument("symbols", nargs="*")
    p.add_argument("--watchlist", action="store_true")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    syms = [s.upper() for s in a.symbols]
    if a.watchlist or not syms:
        syms += [s for s in watchlist_syms() if s not in syms]
    if not syms:
        syms = ["SPY", "QQQ"]
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(check, syms))
    bad = [r for r in rows if not r["ok"]]
    if a.format == "json":
        print(json.dumps({"rows": rows, "ok": not bad}, indent=2))
    else:
        print("ot validate — cross-source sanity (yahoo q1 vs q2 · yahoo vs cboe)")
        for r in rows:
            mark = "✓" if r["ok"] else "✗"
            cb = r.get("cboe") or {}
            line = (f"{mark} {r['symbol']:<7} q1 {r['yahoo_q1']}  q2 {r['yahoo_q2']}  "
                    f"cboe {cb.get('current_price')}/{cb.get('close')}")
            print(line)
            for i in r["issues"]:
                print(f"    ⚠ {i}")
        print(f"\n{len(rows) - len(bad)}/{len(rows)} clean"
              + ("" if not bad else " — investigate the ⚠ rows before trusting levels"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
