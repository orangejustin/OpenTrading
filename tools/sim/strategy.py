#!/usr/bin/env python3
"""
strategy.py — portfolio constructor (`ot strategy [TICKERS...]`).

Turns a universe of names into ONE sized, graded, risk-budgeted book:
  * scores each name from the live signal (trend / momentum / edge / risk),
    weighted by style (balanced | momentum | defensive);
  * grades A-D, keeps the long-actionable A/B/C names, drops the rest;
  * ranks, takes the top-N for the risk profile, and allocates by score with a
    cash floor + per-name caps — each pick carries its range execution plan.

Inspired by the open-source ScaleAlpha-simulation strategy-engine (generateStrategy
/ RISK_RULES / STYLE_WEIGHTS), adapted to OpenTrading's no-key engine (reuses
tools/sim/decide.py). Stdlib only. Educational only — not financial advice.

    ot strategy VST NBIS HOOD MSTR OKLO --style momentum --risk medium
    ot strategy --roster jane --style balanced        # a multi-user roster (A-share + HK ok)
    ot strategy 688008 300394 --market A              # China A-shares (Yahoo .SS/.SZ)
    ot strategy --style defensive --risk low          # universe = watchlist.json
    ot strategy VST NBIS --format json
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import date

import decide   # same dir — reuses features / decide_swing / execution_plan / event_today
import symbols  # code + market -> Yahoo symbol (.SS / .SZ / .HK)

STYLE_WEIGHTS = {
    "balanced":  {"trend": 0.30, "momentum": 0.30, "edge": 0.20, "lowrisk": 0.20},
    "momentum":  {"trend": 0.35, "momentum": 0.45, "edge": 0.15, "lowrisk": 0.05},
    "defensive": {"trend": 0.30, "momentum": 0.12, "edge": 0.13, "lowrisk": 0.45},
}
RISK_RULES = {
    "low":    {"max_positions": 4, "cash_floor": 18, "target_vol": 9,  "name_cap": 0.22, "extend_cap": 0.08},
    "medium": {"max_positions": 5, "cash_floor": 10, "target_vol": 14, "name_cap": 0.28, "extend_cap": 0.12},
    "high":   {"max_positions": 6, "cash_floor": 4,  "target_vol": 21, "name_cap": 0.35, "extend_cap": 0.20},
}
HORIZON = {"short": "2-6 weeks", "medium": "2-6 months", "long": "9-24 months"}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def factor_scores(ft):
    """Live features -> 0..1 factor scores."""
    atr_pct = (ft["atr"] / ft["price"]) if ft["price"] else 0.03
    return {
        "trend": 1.0 if ft["trendup"] else 0.2,
        "momentum": clamp(0.5 + ft["prior5"] * 3.0, 0.0, 1.0),
        "edge": 1.0 if ft["is_edge"] else 0.4,
        "lowrisk": clamp(1.0 - atr_pct / 0.06, 0.0, 1.0),
    }


def score_name(ft, style, risk):
    w = STYLE_WEIGHTS.get(style, STYLE_WEIGHTS["balanced"])
    rules = RISK_RULES.get(risk, RISK_RULES["medium"])
    f = factor_scores(ft)
    score = clamp(round(sum(f[k] * w[k] for k in w) * 100), 0, 100)
    if ft["ext"] > rules["extend_cap"]:                  # docked for chasing extension
        score = clamp(score - round((ft["ext"] - rules["extend_cap"]) * 130), 0, 100)
    grade = "A" if score >= 72 else "B" if score >= 58 else "C" if score >= 44 else "D"
    return score, grade


def evaluate(item, style, risk, capital, ev_today):
    market = item["market"]
    ft = decide.features(symbols.to_yahoo(item["ticker"], market))
    ft["ticker"] = item["ticker"].upper()
    ft["event"] = ev_today if market == "US" else None      # US calendar only gates US names
    action, conv, _ = decide.decide_swing(ft)
    score, grade = score_name(ft, style, risk)
    plan = decide.execution_plan(ft, action, conv, "swing", capital)
    return dict(ticker=ft["ticker"], market=market, ccy=symbols.currency(market),
                price=round(ft["price"], 2), action=action,
                score=score, grade=grade, trendup=ft["trendup"], ext=round(ft["ext"], 4),
                atr_pct=round(ft["atr"] / ft["price"], 4) if ft["price"] else None, plan=plan)


def build(universe, style, risk, horizon, capital):
    rules = RISK_RULES.get(risk, RISK_RULES["medium"])
    evname, ev = decide.event_today(date.today())
    has_us = any(i["market"] == "US" for i in universe)
    us_event = evname if (ev and has_us) else None          # US event only matters if US names present
    ev_today = us_event

    evals, errors = [], []
    for item in universe:
        try:
            evals.append(evaluate(item, style, risk, capital, ev_today))
        except Exception as e:
            errors.append({"ticker": item["ticker"], "error": f"{type(e).__name__}: {e}"})

    longs = sorted([e for e in evals if e["grade"] != "D" and e["action"] == "CALL"],
                   key=lambda e: e["score"], reverse=True)
    picks = longs[: rules["max_positions"]]
    pick_set = {e["ticker"] for e in picks}
    dropped = [e["ticker"] for e in evals if e["ticker"] not in pick_set]

    cash_floor = rules["cash_floor"] + (8 if us_event else 0)   # US event day -> raise cash
    investable = max(0.0, 100 - cash_floor)

    raws = [max(0.05, (e["score"] / 100) * (1.05 - (e["atr_pct"] or 0.03) / 0.06 * 0.45)) for e in picks]
    tot = sum(raws) or 1.0
    name_cap = round(rules["name_cap"] * 100)
    for e, r in zip(picks, raws):
        e["allocation"] = min(round(r / tot * investable), name_cap)
    cash = round(100 - sum(e["allocation"] for e in picks))
    confidence = round(sum(e["score"] for e in picks) / len(picks)) if picks else 0

    return dict(style=style, risk=risk, horizon=HORIZON.get(horizon, horizon),
                event=ev_today, confidence=confidence, target_vol=rules["target_vol"],
                cash=cash, capital=capital, positions=picks, dropped=dropped, errors=errors,
                rules=[
                    "Rebalance when a holding slips to grade C or drifts 25% from its target weight.",
                    f"Keep estimated annualized volatility near {rules['target_vol']}%.",
                    f"Per-name cap {name_cap}% · cash floor {cash_floor}%"
                    + (" (raised for today's event)" if us_event else "") + ".",
                ])


def render(s):
    L = [f"ot strategy — {s['style'].title()} · {s['horizon']} · risk {s['risk']}",
         f"  confidence {s['confidence']}/100 · target vol ~{s['target_vol']}% · cash {s['cash']}%"
         + (f" · ⚠ {s['event']} today (cash raised)" if s["event"] else "")]
    if not s["positions"]:
        L.append("  (no long-actionable A/B/C names in this universe now — all watch/avoid)")
    for e in s["positions"]:
        pl, bz, tz = e["plan"], e["plan"]["buy_zone"], e["plan"]["trim_zone"]
        tag = "" if e.get("ccy", "USD") == "USD" else f" {e['ccy']}"
        L.append(f"  {e['ticker']:<7} {e['grade']} · score {e['score']:>3} · {e['allocation']:>3}%{tag}   "
                 f"buy {bz[0]:.2f}–{bz[1]:.2f} · trim {tz[0]:.2f}–{tz[1]:.2f} · stop {pl['stop']:.2f}")
    if s["dropped"]:
        L.append(f"  dropped (D / not uptrend / extended): {', '.join(s['dropped'])}")
    for er in s["errors"]:
        L.append(f"  {er['ticker']}: skipped — {er['error']}")
    L.append("  rules:")
    for r in s["rules"]:
        L.append(f"    - {r}")
    L.append("  Educational only — not financial advice.")
    return "\n".join(L)


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _items_from(wl):
    """Pull [{ticker, market}] from a watchlist's positions + watch (market defaults US)."""
    out, seen = [], set()

    def add(t, m):
        t = (t or "").upper()
        if t and t not in seen:
            seen.add(t)
            out.append({"ticker": t, "market": (m or "US").upper()})

    for p in wl.get("positions", []):
        add(p.get("ticker"), p.get("market"))
    for w in wl.get("watch", []):
        add(w, "US") if isinstance(w, str) else add(w.get("ticker"), w.get("market"))
    return out


def load_roster(roster_id):
    with open(os.path.join(_repo_root(), f"watchlist.{roster_id}.json")) as f:
        return _items_from(json.load(f))


def load_watchlist_universe():
    try:
        with open(os.path.join(_repo_root(), "watchlist.json")) as f:
            return _items_from(json.load(f))
    except Exception:
        return []


def resolve_universe(a):
    if a.roster:
        return load_roster(a.roster)
    if a.tickers:
        return [{"ticker": t.upper(), "market": a.market} for t in a.tickers]
    return load_watchlist_universe()


def main(argv=None):
    p = argparse.ArgumentParser(prog="strategy", description="Portfolio constructor (range plans + allocation).")
    p.add_argument("tickers", nargs="*", help="universe (default: watchlist.json positions + watch)")
    p.add_argument("--roster", help="load watchlist.<ID>.json (multi-user roster) as the universe")
    p.add_argument("--market", choices=["US", "A", "HK"], default="US",
                   help="market for positional TICKERS (default US; a roster carries its own per-name market)")
    p.add_argument("--style", choices=list(STYLE_WEIGHTS), default="balanced")
    p.add_argument("--risk", choices=list(RISK_RULES), default="medium")
    p.add_argument("--horizon", choices=list(HORIZON), default="medium")
    p.add_argument("--capital", type=float, default=100000)
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        universe = resolve_universe(a)
    except Exception as e:
        print(f"strategy: could not load universe: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if not universe:
        print("strategy: no tickers given and no watchlist found", file=sys.stderr)
        return 1
    try:
        s = build(universe, a.style, a.risk, a.horizon, a.capital)
    except Exception as e:
        print(f"strategy: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(s, indent=2) if a.format == "json" else render(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
