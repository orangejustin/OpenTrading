#!/usr/bin/env python3
"""
decide.py — live CALL / PUT / NO-ACTION engine (`ot decide TICKER`).

Encodes the learned, forward-validated policy (see
references/learned-strategy.md):

  0DTE  : FADE the opening gap (don't chase it) + require VIX-direction
          confirmation + SKIP macro-event days + stay selective (NO-ACTION is a
          position). Calm VIX (<16) => chop risk => size down / pass.
  SWING : (>=3 DTE) momentum-continuation CALLS on names with demonstrated edge
          (NVDA/AMZN/GOOG); puts only on a strong downtrend (the put book was
          net-negative, so default is long-the-leader or no-action).
  RISK  : size on your capital, <=5% premium/trade, a hard daily-loss
          stop, never size up after a loss.

It computes the price/gap/trend/VIX/event signal from no-key Yahoo data; IV,
gamma-walls and news are LIVE-only (the backtest could not see them historically),
so it points you at `ot options` / `ot news` / `ot macro` to confirm before acting.

    python3 decide.py QQQ --dte 0
    python3 decide.py NVDA --dte 5 --capital 100000
    python3 decide.py QQQ --dte 0 --format json

Educational only — not financial advice. Stdlib only.
"""
from __future__ import annotations
import argparse, calendar, json, sys
from datetime import date

import yfhist

EDGE = {"NVDA", "AMZN", "GOOG", "GOOGL"}
# verified macro events (OPEX is computed below). FOMC = federalreserve.gov; CPI = bls.gov.
# Keep this current — a stale calendar silently disables event-risk flagging (see DECISION_LOG 2026-06-17).
KNOWN_EVENTS = {
    # 2025 Q4
    "2025-10-29": "FOMC", "2025-12-10": "FOMC", "2025-12-18": "CPI",
    # 2026 FOMC decision days (verified; Mar/Jun/Sep/Dec are SEP/dot-plot meetings)
    "2026-01-28": "FOMC", "2026-03-18": "FOMC", "2026-04-29": "FOMC", "2026-06-17": "FOMC",
    "2026-07-29": "FOMC", "2026-09-16": "FOMC", "2026-10-28": "FOMC", "2026-12-09": "FOMC",
    # 2026 CPI (partial — verified from BLS; extend as the year's dates publish)
    "2026-04-10": "CPI", "2026-07-14": "CPI",
}


def third_friday(y, m):
    fr = [d for d in calendar.Calendar().itermonthdates(y, m) if d.month == m and d.weekday() == 4]
    return fr[2]


def event_today(today):
    iso = today.isoformat()
    if iso in KNOWN_EVENTS:
        return KNOWN_EVENTS[iso], True
    if today == third_friday(today.year, today.month):
        return "OPEX", True
    return None, False


def features(ticker):
    bars = yfhist.fetch_recent(ticker)
    vix = yfhist.fetch_recent("^VIX")
    if len(bars) < 22:
        raise RuntimeError(f"not enough history for {ticker}")
    today = date.today().isoformat()
    last = bars[-1]
    has_today = last["d"] == today
    if has_today:
        cur, t_open, prev = last["c"], last["o"], bars[-2]["c"]
        closes = [b["c"] for b in bars[:-1]]
    else:
        cur, t_open, prev = last["c"], None, last["c"]
        closes = [b["c"] for b in bars]
    sma20 = sum(closes[-20:]) / 20
    vl = [b["c"] for b in vix]
    return dict(
        ticker=ticker.upper(), price=cur, prev=prev, t_open=t_open, has_today=has_today,
        gap=(t_open / prev - 1) if t_open else None,
        intraday=(cur / t_open - 1) if t_open else None,
        trendup=prev > sma20, sma20=sma20,
        prior5=prev / closes[-6] - 1,
        vix=vl[-1], vix_chg=vl[-1] / vl[-6] - 1 if len(vl) >= 6 else 0.0,
        is_edge=ticker.upper() in EDGE,
    )


def decide_0dte(ft, ev):
    why = []
    if ev:
        return "NO-ACTION", "n/a", [f"{ev} event day — 0DTE was far deadlier on event days (the documented leak). Stand down."]
    if ft["gap"] is None:
        return "WAIT", "n/a", ["pre-open: gap not set yet — the validated edge fades the OPEN gap, so wait for it."]
    g = ft["gap"]
    fade = "PUT" if g > 0.004 else "CALL" if g < -0.004 else None
    confirm = "CALL" if (ft["trendup"] and ft["vix_chg"] < 0) else "PUT" if (not ft["trendup"] and ft["vix_chg"] > 0) else None
    if fade and confirm and fade == confirm:
        act, conv = fade, "high"
        why.append(f"gap {g:+.2%} -> FADE {fade}, and VIX-direction confirms {confirm}. Both agree.")
    elif fade and not confirm:
        act, conv = fade, "medium"
        why.append(f"gap {g:+.2%} -> FADE {fade} (don't chase the gap); no macro confirmation, so medium.")
    elif confirm and not fade:
        act, conv = confirm, "medium"
        why.append(f"small gap; VIX-direction leans {confirm}.")
    else:
        return "NO-ACTION", "n/a", [f"gap {g:+.2%} and VIX-direction disagree or both flat — selectivity says pass."]
    if ft["vix"] < 16:
        conv = "low"
        why.append(f"VIX {ft['vix']:.1f} <16 = calm/chop (historically the worst 0DTE win-rate). Size down or pass.")
    if ft["gap"] is not None and abs(g) > 0.001 and ((g > 0) == (act == "CALL")):
        why.append("NOTE: this would be chasing the gap — your documented leak. The edge is to fade it.")
    return act, conv, why


def decide_swing(ft):
    if ft["trendup"] and ft["prior5"] > 0:
        conv = "high" if ft["is_edge"] else "medium"
        why = [f"uptrend (>20d) + positive 5d momentum ({ft['prior5']:+.1%}); swing >=3DTE."]
        if ft["is_edge"]:
            why.append(f"{ft['ticker']} is an edge name — your strongest positive-expectancy bucket.")
        else:
            why.append("not an edge name — keep size modest; your edge concentrates in NVDA/AMZN/GOOG.")
        return "CALL", conv, why
    if not ft["trendup"] and ft["prior5"] < -0.02:
        return "PUT", "low", ["downtrend + negative momentum — but puts have been your weaker book; keep small or prefer NO-ACTION."]
    return "NO-ACTION", "n/a", ["no clear trend+momentum edge; the highest-EV action here is to pass."]


def run(ticker, dte, capital):
    ft = features(ticker)
    today = date.today()
    evname, ev = event_today(today)
    mode = "0DTE" if dte <= 1 else "swing"
    if mode == "0DTE":
        action, conv, why = decide_0dte(ft, evname if ev else None)
    else:
        action, conv, why = decide_swing(ft)
    risk = round(capital * (0.05 if conv in ("high", "medium") else 0.025))
    if conv == "low":
        risk = round(capital * 0.015)
    return dict(ticker=ft["ticker"], mode=mode, dte=dte, action=action, conviction=conv,
                reasons=why, gap=ft["gap"], trendup=ft["trendup"], prior5=ft["prior5"],
                vix=ft["vix"], vix_chg=ft["vix_chg"], price=ft["price"], event=evname,
                max_premium=risk, daily_stop=round(capital * 0.10), capital=capital)


def render(r, ft_event):
    g = f"{r['gap']:+.2%}" if r["gap"] is not None else "pre-open"
    L = [f"ot decide {r['ticker']}  ({r['mode']}, {r['dte']} DTE, capital ${r['capital']:,})",
         f"  price {r['price']:.2f} | gap {g} | trend {'UP' if r['trendup'] else 'DOWN'} (20d) | "
         f"prior5 {r['prior5']:+.1%} | VIX {r['vix']:.1f} ({r['vix_chg']:+.0%}/wk) | "
         f"event: {r['event'] or 'none known (verify FOMC/CPI)'}",
         f"  >> {r['action']}   conviction {r['conviction'].upper()}"]
    for w in r["reasons"]:
        L.append(f"     - {w}")
    if r["action"] not in ("NO-ACTION", "WAIT"):
        L.append(f"  size: <= ${r['max_premium']:,} premium · daily stop -${r['daily_stop']:,} · never size up after a loss")
    L.append(f"  confirm live (not in backtest): ot options {r['ticker']} · ot news --ticker {r['ticker']} · ot macro")
    L.append("  Educational only — not financial advice.")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(prog="decide", description="Live CALL/PUT/NO-ACTION engine (backtest-learned).")
    p.add_argument("ticker")
    p.add_argument("--dte", type=int, default=5, help="days to expiry you're considering (<=1 => 0DTE mode)")
    p.add_argument("--capital", type=float, default=100000)
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        r = run(a.ticker, a.dte, a.capital)
    except Exception as e:
        print(f"decide: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(r, indent=2) if a.format == "json" else render(r, None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
