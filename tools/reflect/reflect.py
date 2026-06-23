#!/usr/bin/env python3
"""
reflect.py — the decision journal + self-calibration flywheel (`ot reflect`).

A no-key learning loop (QuantDinger's reflection/calibration pattern, done
local-first): log every call, verify it against the ACTUAL price after a few
days, and recalibrate — so the toolkit grades its own track record and learns.
`ot decide` auto-logs; the email pipeline can pipe its picks in too.

  ot reflect log  < decide.json     # append a call (or --ticker/--market/--action/--grade/--price)
  ot reflect grade [--days N]        # verify open calls >= N days old vs price (return, vs SPY/index)
  ot reflect stats                   # hit-rate + avg return + alpha, by grade/action/market (calibration)
  ot reflect                         # the calibration table (same as stats)

Journal: data/journal/decisions.jsonl (git-ignored). Benchmarks: US ^GSPC,
A-share CSI300 (000300.SS), HK ^HSI. No-key Yahoo daily closes. Stdlib + curl.
Educational only — not financial advice.
"""
from __future__ import annotations
import argparse, json, os, shutil, ssl, subprocess, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JOURNAL = os.path.join(ROOT, "data", "journal", "decisions.jsonl")
UA = "Mozilla/5.0 (OpenTrading reflect-cli)"
BENCH = {"US": "^GSPC", "A": "000300.SS", "HK": "^HSI"}


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
            out = subprocess.run([curl, "-sL", "--max-time", str(timeout), "-A", UA, url],
                                 capture_output=True, text=True, timeout=timeout + 5)
            if out.returncode == 0 and out.stdout:
                return out.stdout
        raise


def to_yahoo(ticker, market):
    t = str(ticker).strip().upper()
    if t.startswith("^") or t.endswith((".SS", ".SZ", ".HK")):
        return t
    digits = "".join(c for c in t if c.isdigit())
    if market == "HK" and digits:
        return f"{int(digits):04d}.HK"
    if market == "A" and digits:
        return digits + (".SS" if digits.startswith("6") else ".SZ")
    return t


def closes_since(ysym, since_iso):
    """Daily closes from `since` to now (no key); list of (date, close)."""
    try:
        p1 = int(datetime.strptime(since_iso, "%Y-%m-%d").timestamp()) - 5 * 86400
    except ValueError:
        return []
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ysym)}"
           f"?period1={p1}&period2={int(time.time()) + 86400}&interval=1d")
    try:
        r = json.loads(http_get(url))["chart"]["result"][0]
        ts, cl = r["timestamp"], r["indicators"]["quote"][0]["close"]
        return [(datetime.fromtimestamp(t, timezone.utc).date().isoformat(), c) for t, c in zip(ts, cl) if c is not None]
    except Exception:
        return []


def _load():
    if not os.path.exists(JOURNAL):
        return []
    out = []
    with open(JOURNAL) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def _save(entries):
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    with open(JOURNAL, "w") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def log_entry(entry):
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    entry.setdefault("date", date.today().isoformat())
    entry.setdefault("id", f"{entry.get('ticker', '?')}-{entry['date']}")
    with open(JOURNAL, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _days(a_iso, b_iso):
    return (datetime.strptime(b_iso, "%Y-%m-%d") - datetime.strptime(a_iso, "%Y-%m-%d")).days


def grade(min_days):
    """Verify every ungraded call >= min_days old against the actual price + benchmark."""
    entries = _load()
    today = date.today().isoformat()
    bench_cache = {}
    n = 0
    for e in entries:
        if e.get("outcome") or not e.get("entry_price") or _days(e["date"], today) < min_days:
            continue
        mkt = e.get("market", "US")
        cs = closes_since(to_yahoo(e["ticker"], mkt), e["date"])
        if not cs:
            continue
        cur, entry_px = cs[-1][1], float(e["entry_price"])
        ret = (cur / entry_px - 1) * 100
        bsym = BENCH.get(mkt, "^GSPC")
        if bsym not in bench_cache:
            bench_cache[bsym] = closes_since(bsym, e["date"])
        bcs = bench_cache[bsym]
        bret = ((bcs[-1][1] / bcs[0][1] - 1) * 100) if len(bcs) >= 2 else None
        alpha = (ret - bret) if bret is not None else None
        act = (e.get("action") or "").upper()
        right = (ret > 0) if act == "CALL" else (ret < 0) if act == "PUT" else (abs(ret) < 3)
        e["outcome"] = {"graded": today, "days": _days(e["date"], today), "current_price": round(cur, 2),
                        "return_pct": round(ret, 2), "bench": bsym,
                        "bench_return_pct": round(bret, 2) if bret is not None else None,
                        "alpha_pct": round(alpha, 2) if alpha is not None else None, "was_right": right}
        n += 1
    _save(entries)
    return n


def _agg(entries, key):
    g = {}
    for e in entries:
        k = str(e.get(key) or "?")
        b = g.setdefault(k, {"n": 0, "right": 0, "ret": 0.0, "alpha": 0.0, "na": 0})
        o = e["outcome"]
        b["n"] += 1
        b["right"] += 1 if o["was_right"] else 0
        b["ret"] += o["return_pct"]
        if o.get("alpha_pct") is None:
            b["na"] += 1
        else:
            b["alpha"] += o["alpha_pct"]
    return g


def stats():
    graded = [e for e in _load() if e.get("outcome")]
    if not graded:
        return None
    return {"total": len(graded), "by_grade": _agg(graded, "grade"),
            "by_action": _agg(graded, "action"), "by_market": _agg(graded, "market")}


def _render_groups(title, g):
    L = [f"  {title}:"]
    for k, b in sorted(g.items(), key=lambda kv: -kv[1]["n"]):
        hit = 100 * b["right"] / b["n"]
        navg = b["n"] - b["na"]
        aa = f" · α {b['alpha'] / navg:+.1f}%" if navg else ""
        L.append(f"    {k:<10} n={b['n']:<3} 命中 {hit:>3.0f}% · 均收益 {b['ret'] / b['n']:+.1f}%{aa}")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(prog="reflect", description="Decision journal + self-calibration (no-key).")
    p.add_argument("--format", choices=["text", "json"], default="text")
    sub = p.add_subparsers(dest="cmd")
    pl = sub.add_parser("log")
    for f in ("ticker", "market", "action", "grade", "conviction"):
        pl.add_argument(f"--{f}")
    pl.add_argument("--price", type=float)
    sub.add_parser("grade").add_argument("--days", type=int, default=5)
    sub.add_parser("stats")
    a = p.parse_args(argv)

    if a.cmd == "log":
        entry = None
        if not sys.stdin.isatty():
            raw = sys.stdin.read().strip()
            if raw:
                try:
                    d = json.loads(raw)
                    entry = {"ticker": d.get("ticker"), "market": d.get("market", "US"), "action": d.get("action"),
                             "conviction": d.get("conviction"), "grade": (d.get("plan") or {}).get("grade"),
                             "entry_price": d.get("price"), "source": "pipe"}
                except ValueError:
                    pass
        if entry is None:
            entry = {"ticker": a.ticker, "market": a.market or "US", "action": a.action, "grade": a.grade,
                     "conviction": a.conviction, "entry_price": a.price, "source": "manual"}
        if not entry.get("ticker"):
            print("reflect log: need a ticker (stdin JSON or --ticker)", file=sys.stderr)
            return 1
        e = log_entry(entry)
        print(f"logged: {e['ticker']} {e.get('action')} grade {e.get('grade')} @ {e.get('entry_price')} ({e['date']})")
        return 0

    if a.cmd == "grade":
        print(f"graded {grade(a.days)} call(s) (>= {a.days}d old) vs actual price.")
        return 0

    s = stats()
    if a.format == "json":
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    if not s:
        print("ot reflect — nothing graded yet. Calls auto-log from `ot decide`; then `ot reflect grade`.")
        return 0
    print(f"ot reflect — self-calibration from {s['total']} graded call(s):")
    print(_render_groups("by grade", s["by_grade"]))
    print(_render_groups("by action", s["by_action"]))
    print(_render_groups("by market", s["by_market"]))
    print("  Educational only — not financial advice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
