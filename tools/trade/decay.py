#!/usr/bin/env python3
"""
decay.py — what a daily-reset ETF actually costs you (`ot decay TICKER`).

Leveraged ETFs track the underlying's DAILY return times k, compounded. Over
more than one day that is not k times the underlying's move: the compounding of
a volatile series is worth less than the compounding of a smooth one, and the
gap widens with realized variance and with holding period. Traders call it
"decay"; it is just the variance drag, and it is computable, not folklore.

For a k-times fund on an underlying with daily log-vol sigma, the drag per day
is approximately

    drag/day  ~  -0.5 * k * (k - 1) * sigma^2

so a 3x fund on a 2%/day underlying bleeds ~0.12%/day even if the underlying
round-trips to exactly where it started, and a 2x bleeds ~0.04%/day. This tool
reports BOTH the closed-form estimate and the realized path — the empirical
number is the one to trust, because it also carries the fund's fee and its
financing cost.

  ot decay TQQQ                    # drag, realized vs theoretical, by holding period
  ot decay RAM --days 5            # what a 5-session hold has historically cost
  ot decay TQQQ --underlying QQQ   # override the inferred underlying

Reads the paired underlying from the same hand-curated complex map the risk
gate uses, so `ot decay RAM` knows to compare against DRAM.

Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UA = "Mozilla/5.0 (OpenTrading decay-cli)"

# ticker -> (multiple, underlying to measure against)
PAIRS = {
    "TQQQ": (3.0, "QQQ"), "SQQQ": (-3.0, "QQQ"), "QLD": (2.0, "QQQ"),
    "UPRO": (3.0, "SPY"), "SPXU": (-3.0, "SPY"), "SSO": (2.0, "SPY"),
    "SOXL": (3.0, "SOXX"), "SOXS": (-3.0, "SOXX"),
    "RAM": (2.0, "DRAM"),
    "LOFF": (2.0, "SPCX"),
    "NVDL": (2.0, "NVDA"), "MSTU": (2.0, "MSTR"), "MSTX": (2.0, "MSTR"),
    "CONL": (2.0, "COIN"), "TSLL": (2.0, "TSLA"),
}


def _ctx():
    try:
        import certifi
        import ssl
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        import ssl
        return ssl.create_default_context()


def closes(sym: str, rng: str = "1y"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
           f"?range={rng}&interval=1d")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20, context=_ctx()) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        res = d["chart"]["result"][0]
        ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
        return [(t, c) for t, c in zip(ts, cl) if c is not None]
    except Exception:  # noqa: BLE001
        try:
            import shutil
            import subprocess
            curl = shutil.which("curl")
            if not curl:
                return []
            out = subprocess.run([curl, "-sL", "--max-time", "20", "-A", UA, url],
                                 capture_output=True, text=True, timeout=25)
            res = json.loads(out.stdout)["chart"]["result"][0]
            ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
            return [(t, c) for t, c in zip(ts, cl) if c is not None]
        except Exception:  # noqa: BLE001
            return []


def realized_vol(series) -> float | None:
    """Daily log-return stdev over the whole series."""
    if len(series) < 20:
        return None
    rets = [math.log(series[i][1] / series[i - 1][1]) for i in range(1, len(series))]
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var)


def analyse(tk: str, under: str, k: float, rng: str, holds) -> dict | None:
    a, b = closes(tk, rng), closes(under, rng)
    if not a or len(b) < 20:
        return None
    # align on timestamp — the pair can have different listing histories
    bm = dict(b)
    pairs = [(t, ca, bm[t]) for t, ca in a if t in bm]
    if len(pairs) < 5:
        return None

    # Vol from the UNDERLYING's full history, not the paired window: a fund
    # listed three weeks ago has no usable sample of its own, but the thing it
    # tracks usually does, and the drag is a function of the underlying's
    # variance. This is what makes a brand-new listing analysable at all.
    sigma = realized_vol(b) or realized_vol([(t, u) for t, _, u in pairs])
    theo_day = -0.5 * k * (k - 1) * (sigma ** 2) * 100 if sigma else None

    rows = []
    for h in holds:
        if len(pairs) <= h:
            continue
        gaps = []
        for i in range(len(pairs) - h):
            u0, u1 = pairs[i][2], pairs[i + h][2]
            l0, l1 = pairs[i][1], pairs[i + h][1]
            u_ret = (u1 / u0 - 1)
            l_ret = (l1 / l0 - 1)
            # What you'd have got if the fund delivered k times the PERIOD move,
            # which is what most people assume it does.
            naive = k * u_ret
            gaps.append((l_ret - naive) * 100)
        if not gaps:
            continue
        gaps.sort()
        n = len(gaps)
        rows.append({
            "hold_days": h, "n": n,
            "median_gap_pct": round(gaps[n // 2], 3),
            "mean_gap_pct": round(sum(gaps) / n, 3),
            "p10_pct": round(gaps[int(n * 0.10)], 3),
            "p90_pct": round(gaps[int(n * 0.90)], 3),
            "worse_than_naive_pct": round(100 * sum(1 for g in gaps if g < 0) / n, 1),
            "theoretical_drag_pct": round(theo_day * h, 3) if theo_day is not None else None,
        })
    return {
        "ticker": tk, "underlying": under, "multiple": k, "range": rng,
        "sessions": len(pairs),
        "underlying_daily_vol_pct": round(sigma * 100, 3) if sigma else None,
        "underlying_annual_vol_pct": round(sigma * math.sqrt(252) * 100, 1) if sigma else None,
        "theoretical_drag_pct_per_day": round(theo_day, 4) if theo_day is not None else None,
        "by_hold": rows,
        "as_of": datetime.now(timezone.utc).date().isoformat(),
    }


def render(r: dict) -> str:
    L = [f"ot decay — {r['ticker']} ({r['multiple']:g}x on {r['underlying']})"
         f"  ·  {r['sessions']} paired sessions over {r['range']}"]
    v, av = r.get("underlying_daily_vol_pct"), r.get("underlying_annual_vol_pct")
    if v:
        L.append(f"  {r['underlying']} realized vol: {v:.2f}%/day ({av:.0f}% annualized)"
                 f"  ->  theoretical drag {r['theoretical_drag_pct_per_day']:+.3f}%/day")
    L.append("")
    L.append("  How far the fund landed from a naive 'multiple x the period move':")
    L.append(f"  {'hold':>6} {'n':>5} {'median':>9} {'mean':>9} {'p10':>9} {'p90':>9}"
             f" {'worse':>7}  {'theory':>8}")
    for row in r["by_hold"]:
        th = f"{row['theoretical_drag_pct']:+.2f}%" if row["theoretical_drag_pct"] is not None else "  n/a"
        L.append(f"  {row['hold_days']:>5}d {row['n']:>5} {row['median_gap_pct']:>+8.2f}%"
                 f" {row['mean_gap_pct']:>+8.2f}% {row['p10_pct']:>+8.2f}%"
                 f" {row['p90_pct']:>+8.2f}% {row['worse_than_naive_pct']:>6.0f}%  {th:>8}")
    L.append("")
    thin = [row for row in r["by_hold"] if row["n"] < 30]
    if thin or r["sessions"] < 40:
        L.append(f"  ⚠ {r['ticker']} has only {r['sessions']} paired sessions of history —"
                 " the empirical columns are noise at this sample size. Trust the")
        L.append("    `theory` column, which is driven by the underlying's measured"
                 " volatility and needs no history of the fund itself.")
        L.append("")
    L.append("  median/mean = the gap vs naive k x move (negative = the fund gave you less).")
    L.append("  worse = share of windows where the fund underperformed the naive expectation.")
    L.append("  p10 = the bad tail: 1 window in 10 was at least this far behind.")
    L.append("  Educational only — not financial advice.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="decay",
                                 description="Daily-reset drag on a leveraged ETF (no key).")
    ap.add_argument("tickers", nargs="*", default=["TQQQ"])
    ap.add_argument("--underlying", help="override the paired underlying")
    ap.add_argument("--multiple", type=float, help="override the daily multiple")
    ap.add_argument("--range", default="1y", help="Yahoo range: 6mo, 1y, 2y, 5y")
    ap.add_argument("--days", type=int, help="report a single holding period")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)

    holds = [a.days] if a.days else [1, 3, 5, 10, 21, 63]
    out = []
    for tk in [t.upper() for t in (a.tickers or ["TQQQ"])]:
        k, under = PAIRS.get(tk, (a.multiple or 2.0, a.underlying or ""))
        under = a.underlying or under
        k = a.multiple if a.multiple is not None else k
        if not under:
            print(f"decay: don't know {tk}'s underlying — pass --underlying", file=sys.stderr)
            continue
        r = analyse(tk, under, k, a.range, holds)
        if not r:
            print(f"decay: not enough paired history for {tk} vs {under}"
                  f" (a young listing needs a shorter --range)", file=sys.stderr)
            continue
        out.append(r)

    if a.format == "json":
        print(json.dumps(out if len(out) != 1 else out[0], ensure_ascii=False, indent=2))
        return 0
    for i, r in enumerate(out):
        if i:
            print()
        print(render(r))
    return 0 if out else 1


if __name__ == "__main__":
    sys.exit(main())
