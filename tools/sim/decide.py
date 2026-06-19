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
import argparse, calendar, json, os, sys
from datetime import date

import yfhist
import symbols

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
    # volatility unit (ATR-14) + recent structure — feeds the range execution plan
    trs = []
    for i in range(1, len(bars)):
        hi, lo, pc = bars[i].get("h"), bars[i].get("l"), bars[i - 1]["c"]
        if None in (hi, lo, pc):
            continue
        trs.append(max(hi - lo, abs(hi - pc), abs(lo - pc)))
    atr = (sum(trs[-14:]) / min(len(trs), 14)) if trs else cur * 0.02
    win = bars[-15:]
    lows = [b["l"] for b in win if b.get("l") is not None]
    highs = [b["h"] for b in win if b.get("h") is not None]
    swing_lo = min(lows) if lows else cur - 2 * atr
    swing_hi = max(highs) if highs else cur + 2 * atr
    vl = [b["c"] for b in vix]
    return dict(
        ticker=ticker.upper(), price=cur, prev=prev, t_open=t_open, has_today=has_today,
        gap=(t_open / prev - 1) if t_open else None,
        intraday=(cur / t_open - 1) if t_open else None,
        trendup=prev > sma20, sma20=sma20,
        prior5=prev / closes[-6] - 1,
        vix=vl[-1], vix_chg=vl[-1] / vl[-6] - 1 if len(vl) >= 6 else 0.0,
        is_edge=ticker.upper() in EDGE,
        atr=atr, swing_lo=swing_lo, swing_hi=swing_hi, ext=cur / sma20 - 1,
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


def conviction_grade(ft, conv):
    """A–D rating (ScaleAlpha-style), derived from the policy signal + edge."""
    if conv == "high":
        return "A" if ft["is_edge"] else "B"
    if conv == "medium":
        return "B" if (ft["trendup"] and ft["prior5"] > 0) else "C"
    if conv == "low":
        return "C"
    return "D"


def execution_plan(ft, action, conv, mode, capital):
    """Range-first execution plan: buy/add/trim ZONES + scale-out ladder + stop +
    risk-based sizing. Levels come from price, the 20d mean, ATR(14) and recent
    swing hi/lo — all no-key data. The user trades zones, not single points.
    Educational only — not financial advice."""
    p = ft["price"]
    atr = max(ft["atr"], p * 0.005)              # floor ATR so bands never collapse
    sma20, slo, shi = ft["sma20"], ft["swing_lo"], ft["swing_hi"]
    grade = conviction_grade(ft, conv)
    horizon = "swing · 3–7+ DTE / 2–6 wk"

    if action == "PUT":                           # short plan: sell into a bounce
        side = "short"
        z_lo, z_hi = p + 0.25 * atr, p + 1.5 * atr
        core = (z_lo + z_hi) / 2
        add_zone = (z_hi, p + 2.75 * atr)
        stop = max(max(sma20, shi) + 0.3 * atr, add_zone[1] + 0.2 * atr)
        t1, t2 = p - 1.5 * atr, p - 3.0 * atr     # cover targets (nearer first)
        buy_zone, trim_zone = (z_lo, z_hi), (t2, t1)
        inval, risk_per = f"> {stop:.2f} close", stop - core
    else:                                         # long (CALL) or watch (NO-ACTION)
        side = "long" if action == "CALL" else "watch"
        buy_hi = p - 0.25 * atr                   # don't chase — buy the pullback
        buy_lo = max(sma20, p - 1.5 * atr)
        if buy_lo >= buy_hi:                       # at/under the mean → pure ATR band
            buy_lo, buy_hi = p - 1.5 * atr, p - 0.25 * atr
        core = (buy_lo + buy_hi) / 2
        add_lo = max(slo, p - 3.0 * atr)
        add_zone = (min(add_lo, buy_lo - 0.1 * atr), buy_lo)
        stop = min(min(sma20, slo) - 0.3 * atr, add_zone[0] - 0.2 * atr)
        t1, t2 = p + 1.5 * atr, p + 3.0 * atr     # trim targets
        buy_zone, trim_zone = (buy_lo, buy_hi), (t1, t2)
        inval, risk_per = f"< {stop:.2f} close", core - stop

    # sizing — account-risk % by grade, capped by single-name weight
    risk_pct = {"A": 0.0125, "B": 0.010, "C": 0.006, "D": 0.0}[grade]
    max_wt = {"A": 0.12, "B": 0.09, "C": 0.05, "D": 0.0}[grade]
    shares = 0
    if risk_pct > 0 and risk_per > 0:
        shares = int(capital * risk_pct / risk_per)
        if shares * core > capital * max_wt:
            shares = int(capital * max_wt / core)

    scen = []
    if ft.get("event"):
        scen.append(f"{ft['event']} day: defer adds, hold core, size down")
    if ft["vix"] < 16:
        scen.append("VIX<16 chop: tighten or wait for the zone")
    if side == "long" and ft["ext"] > 0.08:
        scen.append(f"extended +{ft['ext']:.0%} vs 20d: wait for the pullback, don't chase")
    if side == "watch" and not ft["trendup"]:
        scen.insert(0, f"downtrend (below 20d): needs a reclaim > {sma20:.2f} to flip long")
    if not scen:
        scen.append("act only at the zones; hold core through noise")

    return dict(
        side=side, grade=grade, horizon=horizon,
        buy_zone=[round(buy_zone[0], 2), round(buy_zone[1], 2)], core=round(core, 2),
        add_zone=[round(add_zone[0], 2), round(add_zone[1], 2)],
        trim_zone=[round(trim_zone[0], 2), round(trim_zone[1], 2)],
        t1=round(t1, 2), t2=round(t2, 2), stop=round(stop, 2), invalidation=inval,
        shares=shares, dollar=round(shares * core), risk_dollar=round(shares * risk_per),
        risk_pct=risk_pct, scenario=scen,
    )


def run(ticker, dte, capital, market="US"):
    is_us = (market or "US").upper() == "US"
    ft = features(symbols.to_yahoo(ticker, market))
    ft["ticker"] = ticker.upper()                       # display the original code
    today = date.today()
    evname, ev = event_today(today) if is_us else (None, False)   # US calendar only gates US names
    mode = "0DTE" if dte <= 1 else "swing"
    if mode == "0DTE":
        action, conv, why = decide_0dte(ft, evname if ev else None)
    else:
        action, conv, why = decide_swing(ft)
    risk = round(capital * (0.05 if conv in ("high", "medium") else 0.025))
    if conv == "low":
        risk = round(capital * 0.015)
    ft["event"] = evname if ev else None
    plan = execution_plan(ft, action, conv, mode, capital) if mode == "swing" else None
    return dict(ticker=ft["ticker"], mode=mode, dte=dte, action=action, conviction=conv,
                reasons=why, gap=ft["gap"], trendup=ft["trendup"], prior5=ft["prior5"],
                vix=ft["vix"], vix_chg=ft["vix_chg"], price=ft["price"], event=evname,
                max_premium=risk, daily_stop=round(capital * 0.10), capital=capital,
                market=(market or "US").upper(), ccy=symbols.ccy_symbol(market),
                currency=symbols.currency(market), plan=plan)


def render(r, ft_event):
    c = r.get("ccy", "$")
    mk = r.get("market", "US")
    mtag = "" if mk == "US" else f"{mk}·{r.get('currency', '')} "
    g = f"{r['gap']:+.2%}" if r["gap"] is not None else "pre-open"
    ev_txt = r["event"] or ("US-only — n/a off-US" if mk != "US" else "none known (verify FOMC/CPI)")
    L = [f"ot decide {r['ticker']}  ({mtag}{r['mode']}, {r['dte']} DTE, capital {c}{r['capital']:,.0f})",
         f"  price {c}{r['price']:.2f} | gap {g} | trend {'UP' if r['trendup'] else 'DOWN'} (20d) | "
         f"prior5 {r['prior5']:+.1%} | VIX {r['vix']:.1f} ({r['vix_chg']:+.0%}/wk) | "
         f"event: {ev_txt}",
         f"  >> {r['action']}   conviction {r['conviction'].upper()}"]
    for w in r["reasons"]:
        L.append(f"     - {w}")
    if r["action"] not in ("NO-ACTION", "WAIT"):
        L.append(f"  size: <= {c}{r['max_premium']:,} premium · daily stop -{c}{r['daily_stop']:,} · never size up after a loss")
    pl = r.get("plan")
    if pl:
        bz, az, tz = pl["buy_zone"], pl["add_zone"], pl["trim_zone"]
        labels = {"short": ("Sell zone", "Add (bounce)", "Cover/Tgt"),
                  "watch": ("Buy-if-setup", "Add zone", "Trim/Sell"),
                  "long": ("Buy zone", "Add zone", "Trim/Sell")}[pl["side"]]
        L.append(f"  EXECUTION PLAN (range) · grade {pl['grade']} · {pl['horizon']}")
        L.append(f"    {labels[0]}: {bz[0]:.2f}–{bz[1]:.2f}  (core {pl['core']:.2f})")
        L.append(f"    {labels[1]}: {az[0]:.2f}–{az[1]:.2f}  (deeper; risk-on only)")
        L.append(f"    {labels[2]}: {tz[0]:.2f}–{tz[1]:.2f}  (⅓ {pl['t1']:.2f} · ⅓ {pl['t2']:.2f} · runner)")
        L.append(f"    Stop/inval: {pl['invalidation']}")
        if pl["shares"]:
            L.append(f"    Size: ~{pl['shares']} sh (~{c}{pl['dollar']:,}) · risk {c}{pl['risk_dollar']:,} ≈ {pl['risk_pct'] * 100:.2f}% acct")
        else:
            L.append(f"    Size: watch only — wait for the zone (grade {pl['grade']})")
        L.append(f"    Scenario: {'; '.join(pl['scenario'])}")
    L.append(f"  confirm live (not in backtest): ot options {r['ticker']} · ot news --ticker {r['ticker']} · ot macro")
    L.append("  Educational only — not financial advice.")
    return "\n".join(L)


def _journal_append(r):
    """Auto-log this call to the reflect journal (best-effort; one row per name per day)."""
    try:
        jdir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "data", "journal")
        jf = os.path.join(jdir, "decisions.jsonl")
        today = date.today().isoformat()
        if os.path.exists(jf):
            with open(jf) as fh:
                for line in fh:
                    if f'"{r["ticker"]}"' in line and f'"{today}"' in line and '"decide"' in line:
                        return
        os.makedirs(jdir, exist_ok=True)
        plan = r.get("plan") or {}
        with open(jf, "a") as fh:
            fh.write(json.dumps({"date": today, "id": f'{r["ticker"]}-{today}', "ticker": r["ticker"],
                                 "market": r.get("market", "US"), "action": r["action"],
                                 "conviction": r.get("conviction"), "grade": plan.get("grade"),
                                 "entry_price": r.get("price"), "source": "decide"}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main(argv=None):
    p = argparse.ArgumentParser(prog="decide", description="Live CALL/PUT/NO-ACTION engine (backtest-learned).")
    p.add_argument("ticker")
    p.add_argument("--dte", type=int, default=5, help="days to expiry you're considering (<=1 => 0DTE mode)")
    p.add_argument("--capital", type=float, default=100000)
    p.add_argument("--market", choices=["US", "A", "HK"], default="US",
                   help="US | A (China A-share) | HK — maps the code to Yahoo (.SS/.SZ/.HK)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        r = run(a.ticker, a.dte, a.capital, a.market)
    except Exception as e:
        print(f"decide: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    _journal_append(r)
    print(json.dumps(r, indent=2) if a.format == "json" else render(r, None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
