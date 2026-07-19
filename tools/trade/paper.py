#!/usr/bin/env python3
"""
paper.py — the paper broker and the live-promotion gate (`ot paper`).

Why this is forward-only, and not a backtest
--------------------------------------------
The evidence pack is fetched LIVE: news, dealer gamma, Fear&Greed and the event
calendar all describe right now, and nothing archives them point-in-time.
Replaying the SOP over history would therefore hand a June decision today's
headlines — future leakage that manufactures alpha out of nothing. So this
module does not simulate a past. It fills forward, marks to market, and lets a
real track record accumulate one session at a time.

  ot paper fill ID [--price P] [--shares N]   open a position from an APPROVED proposal
  ot paper mark                               mark to market; auto-exit on stop/target/time
  ot paper close ID [--price P]               close manually
  ot paper pnl [--format json]                the paper track record
  ot paper gate                               may the live adapter run yet?

Fills record slippage against the proposal's intended entry rather than
pretending the intended price was achieved — a paper record that always fills
at the plan is the same lie as a backtest without costs.

The gate
--------
`ot paper gate` is the single authority a live adapter must consult. It refuses
until the PAPER record shows a real edge:

    n >= 30 closed positions   AND   mean trade alpha > 0   AND   win rate >= 50%

This is deliberately not a judgement call. The desk's deterministic engine
measures 50% / -0.5% alpha over 654 graded calls, which is why nothing is
allowed near live money yet.

Ledger: data/paper/positions.jsonl (git-ignored, append-only semantics).
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
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "data", "paper", "positions.jsonl")
PROPDIR = os.path.join(ROOT, "data", "proposals")
UA = "Mozilla/5.0 (OpenTrading paper-cli)"
BENCH = {"US": "^GSPC", "A": "000300.SS", "HK": "^HSI"}

MIN_N = 30          # closed positions before the gate can even be considered
MIN_WIN = 50.0      # percent


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
           f"?range=1d&interval=1m")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=_ctx()) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        m = d["chart"]["result"][0]["meta"]
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


def _load() -> list[dict]:
    if not os.path.exists(LEDGER):
        return []
    out = []
    with open(LEDGER) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def _save(rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _proposal(pid: str) -> dict | None:
    try:
        with open(os.path.join(PROPDIR, f"{pid}.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _sign(side: str) -> int:
    return 1 if side in ("LONG", "CALL") else -1


# --------------------------------------------------------------------------- fill

def cmd_fill(a) -> int:
    p = _proposal(a.id)
    if not p:
        print(f"paper fill: no proposal {a.id}", file=sys.stderr)
        return 1
    # The paper book is downstream of the same human gate as any real adapter —
    # if paper could fill un-approved proposals, the track record it produces
    # would not be a record of the process we actually intend to run live.
    if p.get("status") != "approved":
        print(f"paper fill: {a.id} is '{p.get('status')}', not 'approved'. Paper fills the "
              "same approved proposals a live adapter would — approve it first.",
              file=sys.stderr)
        return 1
    if any(r["proposal_id"] == a.id for r in _load()):
        print(f"paper fill: {a.id} is already in the paper book", file=sys.stderr)
        return 1

    px = a.price if a.price is not None else quote(p["ticker"])
    if px is None:
        print(f"paper fill: no price for {p['ticker']} — pass --price", file=sys.stderr)
        return 1
    intended = p.get("entry")
    # Slippage is signed against the trade: paying up on a long is negative.
    slip = None
    if intended:
        slip = (px - intended) / intended * 100 * -_sign(p["side"])

    size = p.get("size_usd")
    shares = a.shares if a.shares is not None else (round(size / px, 4) if size else None)
    row = {
        "proposal_id": a.id, "ticker": p["ticker"], "market": p.get("market", "US"),
        "side": p["side"], "status": "open",
        "opened": _now(), "open_date": date.today().isoformat(),
        "intended_entry": intended, "fill_price": round(px, 4),
        "slippage_pct": round(slip, 3) if slip is not None else None,
        "shares": shares, "size_usd": size,
        "stop": p.get("stop"), "target": p.get("target"),
        "time_stop_days": p.get("dte") or 5,
        "bench": BENCH.get(p.get("market", "US"), "^GSPC"),
        "bench_at_open": quote(BENCH.get(p.get("market", "US"), "^GSPC")),
    }
    rows = _load()
    rows.append(row)
    _save(rows)
    s = f"{slip:+.2f}%" if slip is not None else "n/a"
    print(f"paper filled {a.id}: {p['side']} {p['ticker']} @ {px:.4f}"
          f" (intended {intended}, slippage {s})")
    return 0


# --------------------------------------------------------------------------- mark

def _close_row(r: dict, px: float, reason: str) -> None:
    sgn = _sign(r["side"])
    ret = (px / r["fill_price"] - 1) * 100 * sgn
    r["status"] = "closed"
    r["closed"] = _now()
    r["close_date"] = date.today().isoformat()
    r["exit_price"] = round(px, 4)
    r["exit_reason"] = reason
    r["trade_return_pct"] = round(ret, 3)
    b0, b1 = r.get("bench_at_open"), quote(r.get("bench") or "^GSPC")
    if b0 and b1:
        bret = (b1 / b0 - 1) * 100
        r["bench_return_pct"] = round(bret, 3)
        r["trade_alpha_pct"] = round(ret - bret * sgn, 3)
    if r.get("shares"):
        r["pnl_usd"] = round((px - r["fill_price"]) * r["shares"] * sgn, 2)


def cmd_mark(a) -> int:
    rows = _load()
    open_rows = [r for r in rows if r["status"] == "open"]
    if not open_rows:
        print("paper mark: no open positions")
        return 0
    today = date.today()
    lines = []
    for r in open_rows:
        px = quote(r["ticker"])
        if px is None:
            lines.append(f"  {r['ticker']:<6} no quote — left open")
            continue
        sgn = _sign(r["side"])
        unreal = (px / r["fill_price"] - 1) * 100 * sgn
        held = (today - date.fromisoformat(r["open_date"])).days
        reason = None
        if r.get("stop") is not None and (
                (sgn > 0 and px <= r["stop"]) or (sgn < 0 and px >= r["stop"])):
            reason = "stop"
        elif r.get("target") is not None and (
                (sgn > 0 and px >= r["target"]) or (sgn < 0 and px <= r["target"])):
            reason = "target"
        elif held >= (r.get("time_stop_days") or 5):
            reason = "time-stop"
        if reason and not a.no_exit:
            _close_row(r, px, reason)
            lines.append(f"  {r['ticker']:<6} CLOSED {reason:<9} @ {px:.4f}"
                         f"  {r['trade_return_pct']:+.2f}%")
        else:
            lines.append(f"  {r['ticker']:<6} open  {held}d  @ {px:.4f}"
                         f"  {unreal:+.2f}% unrealized")
    _save(rows)
    print(f"ot paper mark — {len(open_rows)} open position(s)")
    print("\n".join(lines))
    return 0


def cmd_close(a) -> int:
    rows = _load()
    for r in rows:
        if r["proposal_id"] == a.id and r["status"] == "open":
            px = a.price if a.price is not None else quote(r["ticker"])
            if px is None:
                print("paper close: no price — pass --price", file=sys.stderr)
                return 1
            _close_row(r, px, "manual")
            _save(rows)
            print(f"closed {a.id} @ {px:.4f}  {r['trade_return_pct']:+.2f}%")
            return 0
    print(f"paper close: no open position for {a.id}", file=sys.stderr)
    return 1


# --------------------------------------------------------------------------- pnl + gate

def stats() -> dict:
    rows = _load()
    closed = [r for r in rows if r["status"] == "closed"]
    open_n = sum(1 for r in rows if r["status"] == "open")
    if not closed:
        return {"closed": 0, "open": open_n, "win_rate_pct": None,
                "mean_return_pct": None, "mean_alpha_pct": None,
                "mean_slippage_pct": None, "total_pnl_usd": None}
    rets = [r["trade_return_pct"] for r in closed]
    alphas = [r["trade_alpha_pct"] for r in closed if r.get("trade_alpha_pct") is not None]
    slips = [r["slippage_pct"] for r in closed if r.get("slippage_pct") is not None]
    pnls = [r["pnl_usd"] for r in closed if r.get("pnl_usd") is not None]
    by_reason: dict = {}
    for r in closed:
        by_reason.setdefault(r.get("exit_reason") or "?", []).append(r["trade_return_pct"])
    return {
        "closed": len(closed), "open": open_n,
        "win_rate_pct": round(100 * sum(1 for x in rets if x > 0) / len(rets), 1),
        "mean_return_pct": round(sum(rets) / len(rets), 3),
        "mean_alpha_pct": round(sum(alphas) / len(alphas), 3) if alphas else None,
        "mean_slippage_pct": round(sum(slips) / len(slips), 3) if slips else None,
        "total_pnl_usd": round(sum(pnls), 2) if pnls else None,
        "by_exit_reason": {k: {"n": len(v), "avg_pct": round(sum(v) / len(v), 3)}
                           for k, v in by_reason.items()},
    }


def gate() -> tuple[bool, list[str]]:
    """May a live adapter run? Returns (allowed, reasons)."""
    s = stats()
    fails = []
    if s["closed"] < MIN_N:
        fails.append(f"only {s['closed']} closed paper trades (need {MIN_N})")
    if s["mean_alpha_pct"] is None or s["mean_alpha_pct"] <= 0:
        fails.append(f"mean paper alpha {s['mean_alpha_pct']} is not positive")
    if s["win_rate_pct"] is None or s["win_rate_pct"] < MIN_WIN:
        fails.append(f"paper win rate {s['win_rate_pct']}% is below {MIN_WIN}%")
    return (not fails), fails


def cmd_pnl(a) -> int:
    s = stats()
    if a.format == "json":
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    print("ot paper — the paper track record (forward-measured, never backfilled)")
    print(f"  closed {s['closed']}  ·  open {s['open']}")
    if s["closed"]:
        print(f"  win rate      {s['win_rate_pct']}%")
        print(f"  mean return   {s['mean_return_pct']:+.3f}%   (direction-adjusted)")
        print(f"  mean alpha    {s['mean_alpha_pct']}")
        print(f"  mean slippage {s['mean_slippage_pct']}%  (vs the intended entry)")
        if s["total_pnl_usd"] is not None:
            print(f"  total P&L     ${s['total_pnl_usd']:,.2f}")
        for k, v in (s.get("by_exit_reason") or {}).items():
            print(f"    exit {k:<10} n={v['n']:<3} avg {v['avg_pct']:+.2f}%")
    print("  Educational only — not financial advice.")
    return 0


def cmd_gate(a) -> int:
    ok, fails = gate()
    s = stats()
    if a.format == "json":
        print(json.dumps({"live_allowed": ok, "blocking": fails, "stats": s},
                         ensure_ascii=False, indent=2))
        return 0 if ok else 1
    print("ot paper gate — may a live adapter run?")
    if ok:
        print(f"  ALLOWED — {s['closed']} closed trades, {s['win_rate_pct']}% win, "
              f"alpha {s['mean_alpha_pct']:+.3f}%")
        print("  This clears the statistical bar only. It is not advice to trade live.")
    else:
        print("  REFUSED. The paper record has not earned live money:")
        for f in fails:
            print(f"    - {f}")
        print(f"  Bar: n >= {MIN_N} closed, mean alpha > 0, win rate >= {MIN_WIN}%.")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="paper",
                                 description="Forward paper broker + live-promotion gate.")
    sub = ap.add_subparsers(dest="cmd")
    f = sub.add_parser("fill")
    f.add_argument("id")
    f.add_argument("--price", type=float)
    f.add_argument("--shares", type=float)
    m = sub.add_parser("mark")
    m.add_argument("--no-exit", dest="no_exit", action="store_true",
                   help="report only; do not auto-close on stop/target/time")
    c = sub.add_parser("close")
    c.add_argument("id")
    c.add_argument("--price", type=float)
    for name in ("pnl", "gate"):
        q = sub.add_parser(name)
        q.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    if not hasattr(a, "format"):
        a.format = "text"

    if a.cmd == "fill":
        return cmd_fill(a)
    if a.cmd == "mark":
        return cmd_mark(a)
    if a.cmd == "close":
        return cmd_close(a)
    if a.cmd == "gate":
        return cmd_gate(a)
    return cmd_pnl(a)


if __name__ == "__main__":
    sys.exit(main())
