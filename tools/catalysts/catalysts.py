#!/usr/bin/env python3
"""catalysts.py — keyless market-catalyst calendar + event gate.

The event gate is Step 0 of the OpenTrading workflow: before any setup or size,
know what's on the calendar. A great name into a known high-impact print = smaller
size or wait. This tool aggregates the catalysts that move the tape:

  * FOMC decisions          — CONFIRMED, curated from federalreserve.gov (calendar.json)
  * Quad-witching / OPEX     — COMPUTED exact (3rd Friday; quad = Mar/Jun/Sep/Dec)
  * Quarter-end rebalance    — COMPUTED exact (last business day of Mar/Jun/Sep/Dec)
  * CPI / PCE / Jobs (NFP)   — rule-ESTIMATED (clearly flagged 'est' — verify on bls/bea)

Confirmed dates always win over estimates. To upgrade an 'est' print to confirmed,
paste the official date into calendar.json's "fixed" list.

Usage:
  catalysts.py                 next 14 days + event-gate verdict
  catalysts.py --days 30       look out 30 days
  catalysts.py --gate-days 2   gate fires only for high-impact events <=2 days out
  catalysts.py --format json   machine-readable (for the skill / email pipeline)

Stdlib only. Educational, not financial advice.
"""
import argparse
import calendar as _cal
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAL_JSON = os.path.join(HERE, "calendar.json")

KIND_ICON = {
    "fomc": "🏛", "cpi": "📈", "pce": "📈", "nfp": "👷",
    "opex": "🎰", "quad": "🎰", "qend": "🔁",
}
TIER_RANK = {"high": 3, "med": 2, "low": 1}


def nth_weekday(year, month, weekday, n):
    """The n-th `weekday` (Mon=0..Sun=6) of month. n=1 -> first, n=3 -> third."""
    first = dt.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + dt.timedelta(days=offset + 7 * (n - 1))


def last_business_day(year, month):
    last = dt.date(year, month, _cal.monthrange(year, month)[1])
    while last.weekday() >= 5:  # Sat/Sun -> step back
        last -= dt.timedelta(days=1)
    return last


def month_iter(start, end):
    """Yield (year, month) for every month touched by [start, end]."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def computed_events(start, end):
    """Deterministic + rule-estimated recurring catalysts in the window."""
    out = []
    for y, m in month_iter(start, end):
        # --- exact ---
        opex = nth_weekday(y, m, 4, 3)  # 3rd Friday
        if m in (3, 6, 9, 12):
            out.append({"date": opex, "event": "Quad-witching OPEX", "kind": "quad",
                        "tier": "high", "est": False})
            qend = last_business_day(y, m)
            out.append({"date": qend, "event": "Quarter-end rebalance", "kind": "qend",
                        "tier": "med", "est": False})
        else:
            out.append({"date": opex, "event": "Monthly OPEX", "kind": "opex",
                        "tier": "med", "est": False})
        # --- rule-estimated (flagged) ---
        nfp = nth_weekday(y, m, 4, 1)  # 1st Friday (NFP, occasionally bumped by holidays)
        out.append({"date": nfp, "event": "Jobs / NFP", "kind": "nfp", "tier": "high", "est": True})
        cpi = nth_weekday(y, m, 2, 2)  # ~2nd Wednesday — CPI window
        out.append({"date": cpi, "event": "CPI window", "kind": "cpi", "tier": "high", "est": True})
        pce = last_business_day(y, m)  # PCE ~ last business day (Personal Income & Outlays)
        out.append({"date": pce, "event": "PCE / Personal Income", "kind": "pce", "tier": "high", "est": True})
    return out


def load_fixed():
    try:
        with open(CAL_JSON) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    rows = []
    for e in data.get("fixed", []):
        try:
            d = dt.datetime.strptime(e["date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        rows.append({"date": d, "event": e.get("event", e.get("kind", "event")),
                     "kind": e.get("kind", "event"), "tier": e.get("tier", "med"),
                     "est": False})
    return rows


def build(start, end):
    fixed = [e for e in load_fixed() if start <= e["date"] <= end]
    # A confirmed event suppresses a same-kind estimate in the same month.
    confirmed_key = {(e["kind"], e["date"].year, e["date"].month) for e in fixed}
    events = list(fixed)
    for e in computed_events(start, end):
        if e["est"] and (e["kind"], e["date"].year, e["date"].month) in confirmed_key:
            continue
        if start <= e["date"] <= end:
            events.append(e)
    events.sort(key=lambda e: (e["date"], -TIER_RANK.get(e["tier"], 0)))
    return events


def gate(events, today, gate_days):
    """The nearest high-tier event within gate_days, if any."""
    hits = [e for e in events if e["tier"] == "high"
            and 0 <= (e["date"] - today).days <= gate_days]
    return hits[0] if hits else None


def render_text(events, today, window_days, gate_days):
    lines = []
    lines.append("=" * 64)
    lines.append(f"MARKET CATALYSTS — next {window_days} days  (as of {today:%a %b %d, %Y})")
    lines.append("=" * 64)
    g = gate(events, today, gate_days)
    if g:
        days = (g["date"] - today).days
        when = "TODAY" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
        est = " (est — verify)" if g.get("est") else ""
        lines.append(f"  ⚠️  EVENT GATE: {g['event']} {when} "
                     f"({g['date']:%a %b %d}){est}")
        lines.append("      → trim size / no fresh risk into the print; this is Step 0.")
    else:
        lines.append(f"  ✅  Event gate clear — no high-impact print in the next {gate_days} days.")
    lines.append("-" * 64)
    if not events:
        lines.append("  (nothing scheduled in window)")
    for e in events:
        days = (e["date"] - today).days
        icon = KIND_ICON.get(e["kind"], "•")
        tier = e["tier"].upper()
        flag = " ·est" if e.get("est") else ""
        lines.append(f"  {e['date']:%a %b %d}  (+{days:>2})  {icon} {e['event']:<28}"
                     f"  [{tier}{flag}]")
    lines.append("=" * 64)
    lines.append("  Confirmed: FOMC (federalreserve.gov), OPEX/quad/quarter-end (computed).")
    lines.append("  'est' = rule-estimated CPI/PCE/NFP — verify exact date on bls.gov / bea.gov.")
    lines.append("  Educational only — not financial advice.")
    return "\n".join(lines)


def to_json(events, today, gate_days):
    g = gate(events, today, gate_days)
    return json.dumps({
        "as_of": today.isoformat(),
        "gate": None if not g else {
            "event": g["event"], "kind": g["kind"], "date": g["date"].isoformat(),
            "days_away": (g["date"] - today).days, "est": bool(g.get("est")),
        },
        "events": [{
            "date": e["date"].isoformat(), "days_away": (e["date"] - today).days,
            "event": e["event"], "kind": e["kind"], "tier": e["tier"], "est": bool(e.get("est")),
        } for e in events],
    }, ensure_ascii=False, indent=2)


def main(argv=None):
    p = argparse.ArgumentParser(description="Keyless market-catalyst calendar + event gate.")
    p.add_argument("--days", type=int, default=14, help="look-ahead window (default 14).")
    p.add_argument("--gate-days", type=int, default=3, help="gate fires for high events within N days (default 3).")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--from", dest="frm", help="anchor date YYYY-MM-DD (default today).")
    args = p.parse_args(argv)

    today = (dt.datetime.strptime(args.frm, "%Y-%m-%d").date()
             if args.frm else dt.date.today())
    end = today + dt.timedelta(days=args.days)
    events = build(today, end)

    if args.format == "json":
        print(to_json(events, today, args.gate_days))
    else:
        print(render_text(events, today, args.days, args.gate_days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
