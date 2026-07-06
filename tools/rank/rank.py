#!/usr/bin/env python3
"""
rank.py — `ot rank`: ONE composite score per name, shared by web + email.

Selection > timing. The morning question is never "is NVDA a buy?" — it's
"which 3 of my 14 names deserve attention TODAY?". Every desk module answers
a piece of that; this tool blends them into one transparent, sortable score:

    grade        ot decide's A–D conviction grade            (0–30 pts)
    quant edge   P(up)-50 signed TOWARD the plan's side,     (−15–15)
                 gated by the model's OOS hit-rate (a
                 coin-flip model contributes ~nothing)
    cone tilt    quant P50 drift signed toward the side      (−9–9)
    proximity    how close price is to the entry zone        (0–15)
    debate       today's journaled judge verdict, signed,    (−10–10)
                 scaled by confidence
    event        scheduled binary print near → penalty       (−8 or 0)

Score ≈ 0–70+. The components are always printed — the number is an ORDERING,
not an oracle. Deterministic, keyless, no LLM calls.

    python3 rank.py                       # whole watchlist.json
    python3 rank.py NVDA META ORCL        # explicit names
    python3 rank.py --top 3 --format json

Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable or "python3"
NY = ZoneInfo("America/New_York")

GRADE_PTS = {"A": 30, "B": 22, "C": 12, "D": 0}


def _tool(rel: str, *args, timeout: int = 120):
    try:
        out = subprocess.run([PY, str(ROOT / rel), *args, "--format", "json"],
                             capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
    except Exception:  # noqa: BLE001
        return None
    return None


def watchlist_names() -> tuple[list[str], set[str]]:
    path = Path(os.environ.get("OT_WATCHLIST") or (ROOT / "watchlist.json"))
    names, held = [], set()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for pos in (data.get("positions") or []):
                t = (pos.get("ticker") or "").upper()
                if t and t not in names:
                    names.append(t)
                    held.add(t)
            for w in (data.get("watch") or []):
                t = (w.get("ticker") or "").upper()
                if t and t not in names:
                    names.append(t)
        except Exception:  # noqa: BLE001
            pass
    return names[:20], held


def todays_verdict(ticker: str) -> dict | None:
    """Today's journaled debate verdict for this name (if the desk ran)."""
    path = ROOT / "data/journal/decisions.jsonl"
    if not path.exists():
        return None
    today = datetime.now(NY).strftime("%Y-%m-%d")
    hit = None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if (d.get("ticker") or "").upper() != ticker or str(d.get("date")) != today:
                continue
            # Only true DEBATE verdicts count — the daily pipeline also journals
            # plain `ot decide` reads (source: decide), and counting those would
            # double-weight the engine. Legacy debate rows (pre source-stamp)
            # are recognizable by their time-stop field.
            if d.get("source") == "debate" or (
                    d.get("source") == "manual" and d.get("time_stop_days") is not None):
                hit = d
    except Exception:  # noqa: BLE001
        return None
    return hit


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _num_or(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def score_one(ticker: str, held: set[str]) -> dict:
    d = _tool("tools/sim/decide.py", ticker) or {}
    q = _tool("tools/quant/quant.py", ticker) or {}
    plan = d.get("plan") or {}
    side = (plan.get("side") or "watch").lower()
    grade = plan.get("grade") or "D"
    price = d.get("price")
    comp: dict = {}

    comp["grade"] = GRADE_PTS.get(grade, 0)

    # quant edge, signed toward the plan's side, gated by OOS reliability
    edge_pts = 0.0
    p_up, oos = q.get("p_up"), q.get("oos_hit_rate")
    if isinstance(p_up, (int, float)):
        directional = (p_up - 50) if side != "short" else (50 - p_up)
        gate = 0.0 if not isinstance(oos, (int, float)) or oos < 55 else \
            0.5 if oos < 62 else 1.0
        edge_pts = _clamp(directional, -15, 15) * gate
    comp["quant_edge"] = round(edge_pts, 1)

    # cone tilt: P50 drift (%) toward the side, 3 pts per %
    tilt_pts = 0.0
    cone, last = q.get("cone") or {}, q.get("last")
    if cone.get("p50") and last:
        drift = (cone["p50"] / last - 1) * 100
        if side == "short":
            drift = -drift
        tilt_pts = _clamp(drift * 3, -9, 9)
    comp["cone_tilt"] = round(tilt_pts, 1)

    # proximity to the entry zone (both sides use plan.buy_zone as the zone)
    prox_pts = 0.0
    bz = plan.get("buy_zone")
    if isinstance(bz, (list, tuple)) and len(bz) == 2 and price:
        lo, hi = sorted(bz)
        if lo <= price <= hi:
            prox_pts = 15
        else:
            gap = min(abs(price - lo), abs(price - hi)) / price * 100
            prox_pts = 10 if gap <= 1 else 5 if gap <= 3 else 0
    comp["proximity"] = prox_pts

    # today's debate verdict (if journaled), signed toward the side
    deb_pts, verdict = 0.0, None
    j = todays_verdict(ticker)
    if j:
        verdict = j.get("action")  # CALL / PUT / NO-ACTION
        conf = _num_or(j.get("conviction"), 50)
        if verdict in ("CALL", "PUT"):
            agree = (verdict == "CALL") == (side != "short")
            deb_pts = (10 if agree else -10) * (conf / 100)
    comp["debate"] = round(deb_pts, 1)

    comp["event"] = -8 if d.get("event") else 0

    score = sum(comp.values())
    zone = f"{bz[0]:.2f}–{bz[1]:.2f}" if isinstance(bz, (list, tuple)) and len(bz) == 2 else "—"
    in_zone = prox_pts == 15
    return {"ticker": ticker, "score": round(score, 1), "side": side, "grade": grade,
            "action": d.get("action"), "price": price, "held": ticker in held,
            "event": d.get("event"), "in_zone": in_zone, "zone": zone,
            "verdict_today": verdict, "components": comp,
            "call": ("ENTER — price is inside the zone" if in_zone and side != "watch"
                     else f"WAIT for {zone}" if side != "watch" else "WATCH — no setup")}


def run(tickers: list[str], held: set[str]) -> list[dict]:
    with ThreadPoolExecutor(max_workers=5) as ex:
        rows = list(ex.map(lambda t: score_one(t, held), tickers))
    rows.sort(key=lambda r: -r["score"])
    return rows


def render(rows: list[dict], top: int) -> str:
    L = ["ot rank — composite desk score (grade + gated quant edge + cone tilt "
         "+ zone proximity + today's debate − event risk)", ""]
    L.append(f"{'':2}{'TICKER':<8}{'SCORE':>6}  {'SIDE':<6}{'GR':<3}{'PRICE':>9}  "
             f"{'ZONE':<19}{'CALL'}")
    for i, r in enumerate(rows):
        mark = "★" if i < top else " "
        px = f"{r['price']:.2f}" if r["price"] else "—"
        extra = ("  [HELD]" if r["held"] else "") + (f"  ⚠ {r['event']}" if r["event"] else "")
        L.append(f"{mark} {r['ticker']:<8}{r['score']:>6}  {r['side']:<6}{r['grade']:<3}"
                 f"{px:>9}  {r['zone']:<19}{r['call']}{extra}")
    L.append("")
    L.append(f"TOP {top}: " + " · ".join(
        f"{r['ticker']} ({r['score']})" for r in rows[:top]))
    L.append("components per name available with --format json · educational only")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(prog="ot rank",
                                description="Composite watchlist rank — selection > timing.")
    p.add_argument("tickers", nargs="*", help="names to rank (default: watchlist.json)")
    p.add_argument("--top", type=int, default=3)
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    if a.tickers:
        names, held = [t.upper() for t in a.tickers], watchlist_names()[1]
    else:
        names, held = watchlist_names()
    if not names:
        print(json.dumps({"error": "no tickers — pass names or create watchlist.json"})
              if a.format == "json" else "no tickers — pass names or create watchlist.json")
        return
    rows = run(names, held)
    if a.format == "json":
        print(json.dumps({"rows": rows, "top": [r["ticker"] for r in rows[:a.top]]}, indent=2))
    else:
        print(render(rows, a.top))


if __name__ == "__main__":
    main()
