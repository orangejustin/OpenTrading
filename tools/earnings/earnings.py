#!/usr/bin/env python3
"""earnings.py — keyless per-name earnings (财报) calendar + event gate.

The macro event gate (`ot catalysts`) is blind to single-stock prints — a name
can rip or gap on its own earnings with nothing on the macro calendar (e.g. MU
+15% after-hours dragging the whole memory complex). This tool closes that hole:
for YOUR held + watched names it answers "who reports, when, AMC/BMO, vs which
estimate" and raises a ⚠️ gate when a name reports inside the window — so the
desk note can take the call (buy-the-call into conviction / trim / hedge / hold
through) BEFORE the print instead of explaining the move after.

Source: Nasdaq's public earnings calendar (api.nasdaq.com, keyless — needs only a
browser User-Agent). Scanned by business day across the window and filtered to the
requested tickers; results cached under data/earnings/<date>.json (one fetch/day).
US listings only (A-share / HK earnings are a future Eastmoney extension).

Usage:
  earnings.py MU SNDK WDC               next 14 days for these names + gate
  earnings.py --watchlist               tickers from watchlist.json (US only)
  earnings.py MU --days 30 --gate-days 2
  earnings.py SNDK --format json        machine-readable (email pipeline / skill)

Stdlib only (Python 3.9+); certifi if present, else curl fallback. Educational,
not financial advice.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "earnings"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (OpenTrading)"
CAL_URL = "https://api.nasdaq.com/api/calendar/earnings?date={date}"
CACHE_TTL = 6 * 3600  # refetch a future/today calendar at most every 6h
WHEN = {"time-after-hours": "AMC", "time-pre-market": "BMO", "time-not-supplied": "—"}


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url, timeout=15):
    headers = {"User-Agent": UA, "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        curl = shutil.which("curl")
        if curl:
            out = subprocess.run(
                [curl, "-s", "--max-time", str(timeout), "-A", UA,
                 "-H", "Accept: application/json", url],
                capture_output=True, text=True, timeout=timeout + 5)
            if out.returncode == 0 and out.stdout:
                return out.stdout
        raise


def calendar_for(day, today):
    """Return Nasdaq earnings rows for `day` (list of dicts), cached on disk.

    Past days are cached permanently (the report happened); today/future are
    refreshed at most every CACHE_TTL so a moving estimate stays current."""
    key = day.isoformat()
    fp = CACHE / f"{key}.json"
    fresh = False
    if fp.exists():
        if day < today:
            fresh = True
        elif (time.time() - fp.stat().st_mtime) < CACHE_TTL:
            fresh = True
    if fresh:
        try:
            return json.loads(fp.read_text())
        except (OSError, ValueError):
            pass
    try:
        raw = http_get(CAL_URL.format(date=key))
        rows = (json.loads(raw).get("data") or {}).get("rows") or []
    except Exception:
        # On a fetch failure, fall back to any stale cache rather than nothing.
        if fp.exists():
            try:
                return json.loads(fp.read_text())
            except (OSError, ValueError):
                return []
        return []
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps(rows))
    except OSError:
        pass
    return rows


def business_days(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:  # skip Sat/Sun (Nasdaq lists Mon–Fri)
            yield d
        d += dt.timedelta(days=1)


def find_earnings(tickers, today, end):
    """Scan business-day calendars in [today, end]; return events for `tickers`."""
    want = {t.upper() for t in tickers}
    found = {}
    for day in business_days(today, end):
        if not want - set(found):  # every requested name already located
            break
        for row in calendar_for(day, today):
            sym = (row.get("symbol") or "").upper()
            if sym in want and sym not in found:
                found[sym] = {
                    "symbol": sym,
                    "name": row.get("name") or sym,
                    "date": day,
                    "when": WHEN.get(row.get("time"), row.get("time") or "—"),
                    "eps_forecast": row.get("epsForecast") or "",
                    "fiscal_quarter": row.get("fiscalQuarterEnding") or "",
                    "days_away": (day - today).days,
                }
    return sorted(found.values(), key=lambda e: (e["date"], e["symbol"]))


def gate(events, gate_days):
    hits = [e for e in events if 0 <= e["days_away"] <= gate_days]
    return hits[0] if hits else None


def render_text(events, tickers, today, window_days, gate_days):
    lines = ["=" * 64,
             f"EARNINGS (财报) — next {window_days} days  (as of {today:%a %b %d, %Y})",
             "=" * 64]
    g = gate(events, gate_days)
    if g:
        when = "TODAY" if g["days_away"] == 0 else f"in {g['days_away']} day{'s' if g['days_away'] != 1 else ''}"
        lines.append(f"  ⚠️  EARNINGS GATE: {g['symbol']} reports {when} "
                     f"({g['date']:%a %b %d} · {g['when']})")
        lines.append("      → take the call BEFORE the print: conviction=buy-the-call, "
                     "doubt=trim/hedge, else hold through. Read the sector through it.")
    else:
        lines.append(f"  ✅  No held/watched name reports in the next {gate_days} days.")
    lines.append("-" * 64)
    if not events:
        lines.append(f"  (none of {', '.join(t.upper() for t in tickers) or '—'} report in window)")
    for e in events:
        eps = f"est EPS {e['eps_forecast']}" if e["eps_forecast"] else "no est"
        lines.append(f"  {e['date']:%a %b %d}  (+{e['days_away']:>2})  📊 "
                     f"{e['symbol']:<6} {e['when']:<4} {eps:<16} {e['name'][:30]}")
    lines.append("=" * 64)
    lines.append("  Source: Nasdaq earnings calendar (keyless). US listings only.")
    lines.append("  Educational only — not financial advice.")
    return "\n".join(lines)


def to_json(events, today, gate_days):
    g = gate(events, gate_days)
    return json.dumps({
        "as_of": today.isoformat(),
        "gate": None if not g else {
            "symbol": g["symbol"], "date": g["date"].isoformat(),
            "when": g["when"], "days_away": g["days_away"],
        },
        "events": [{
            "symbol": e["symbol"], "name": e["name"], "date": e["date"].isoformat(),
            "when": e["when"], "eps_forecast": e["eps_forecast"],
            "fiscal_quarter": e["fiscal_quarter"], "days_away": e["days_away"],
        } for e in events],
    }, ensure_ascii=False, indent=2)


def watchlist_tickers(path=None):
    """US tickers from a roster file (positions + 'watch'/'alpha' pool)."""
    fp = Path(path) if path else (ROOT / "watchlist.json")
    try:
        d = json.loads(Path(fp).read_text())
    except (OSError, ValueError):
        return []
    pool = list(d.get("positions", [])) + list(d.get("alpha", [])) + list(d.get("watch", []))
    out = []
    for p in pool:
        tk = p.get("ticker")
        mkt = (p.get("market") or "US").upper()
        if tk and mkt == "US" and tk.upper() not in out:
            out.append(tk.upper())
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Keyless per-name earnings calendar + gate.")
    p.add_argument("tickers", nargs="*", help="symbols (e.g. MU SNDK WDC).")
    p.add_argument("--watchlist", nargs="?", const="", default=None,
                   help="use US tickers from watchlist.json (or a given roster path).")
    p.add_argument("--days", type=int, default=14, help="look-ahead window (default 14).")
    p.add_argument("--gate-days", type=int, default=3,
                   help="gate fires when a name reports within N days (default 3).")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--from", dest="frm", help="anchor date YYYY-MM-DD (default today).")
    args = p.parse_args(argv)

    tickers = list(args.tickers)
    if args.watchlist is not None:
        tickers += watchlist_tickers(args.watchlist or None)
    tickers = list(dict.fromkeys(t.upper() for t in tickers))  # de-dup, keep order

    today = (dt.datetime.strptime(args.frm, "%Y-%m-%d").date()
             if args.frm else dt.date.today())
    end = today + dt.timedelta(days=args.days)
    events = find_earnings(tickers, today, end) if tickers else []

    if args.format == "json":
        print(to_json(events, today, args.gate_days))
    else:
        print(render_text(events, tickers, today, args.days, args.gate_days))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
