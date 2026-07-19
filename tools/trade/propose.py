#!/usr/bin/env python3
"""
propose.py — staged trade proposals with a risk gate (`ot propose|risk|approve`).

The execution half of the desk, built so that an agent can drive it end-to-end
WITHOUT being able to move money. Three separate verbs, three separate files,
one human step that no automation may perform:

  ot propose TICKER --side CALL|PUT|LONG|SHORT --entry P --stop P [...]
                                     stage a proposal   -> status: staged
  ot risk    ID                      run the gates      -> status: passed | blocked
  ot approve ID --yes                HUMAN ONLY         -> status: approved
  ot propose list [--status S]       the book of proposals
  ot propose show ID                 one proposal in full

Nothing here places an order. `approved` is a terminal state that a future
broker adapter may consume; the adapter is deliberately not written, and the
approve verb refuses to run unless a human passes --yes with the exact id.

The gates (QuantDinger's paper-first posture + MMR's propose/approve schema,
adapted to a book that is already concentrated and levered):

  G1 invalidation   a stop is mandatory and must sit on the losing side of entry
  G2 risk budget    max loss <= --max-loss-pct of the account (default 2%)
  G3 reward         R:R >= 1.0 when a target is given
  G4 leverage       daily-reset ETFs are flagged; stacking one on an existing
                    position in the SAME complex is blocked, because 2x on top
                    of a concentrated single-name book is one risk, not two
  G5 event clock    a Tier-1 print inside the horizon blocks initiation
  G6 0DTE liquidity a 0DTE proposal after the chain has expired is blocked —
                    the chain reads all-nulls and looks like a valid quote
  G7 calibration    warns when `ot reflect` shows this action type below 50%

Files (both git-ignored):
  data/proposals/<id>.json     the proposal + its gate results
  data/audit/proposals.jsonl   append-only: every state change, never rewritten

Educational only — not financial advice. This tool does not place orders.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROPDIR = os.path.join(ROOT, "data", "proposals")
AUDIT = os.path.join(ROOT, "data", "audit", "proposals.jsonl")
WATCHLIST = os.environ.get("OT_WATCHLIST") or os.path.join(ROOT, "watchlist.json")

SIDES = ["CALL", "PUT", "LONG", "SHORT"]
LONGISH = {"CALL", "LONG"}

# Hand-curated because no vendor dataset carries it: FinanceDatabase has no
# holdings column at all and does not even list LOFF/DRAM/RAM. `mult` is the
# daily reset multiple; `complex` groups instruments that are ONE bet.
LEVERAGED = {
    "TQQQ": (3.0, "nasdaq"),   "SQQQ": (-3.0, "nasdaq"),  "QLD": (2.0, "nasdaq"),
    "UPRO": (3.0, "sp500"),    "SPXU": (-3.0, "sp500"),   "SSO": (2.0, "sp500"),
    "SOXL": (3.0, "semis"),    "SOXS": (-3.0, "semis"),
    "RAM": (2.0, "memory"),    "DRAM": (1.0, "memory"),
    "LOFF": (2.0, "spacex"),   "SPCX": (1.0, "spacex"),
    "NVDL": (2.0, "nvda"),     "NVDA": (1.0, "nvda"),
    "MSTU": (2.0, "mstr"),     "MSTX": (2.0, "mstr"),     "MSTR": (1.0, "mstr"),
    "CONL": (2.0, "coin"),     "COIN": (1.0, "coin"),
    "TSLL": (2.0, "tsla"),     "TSLA": (1.0, "tsla"),
    "IBIT": (1.0, "btc"),      "FBTC": (1.0, "btc"),
    "QQQ": (1.0, "nasdaq"),    "SPY": (1.0, "sp500"),
    "MU": (1.0, "memory"),     "WDC": (1.0, "memory"),    "STX": (1.0, "memory"),
    "SNDK": (1.0, "memory"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tool_json(script: str, *args: str, timeout: int = 90):
    try:
        out = subprocess.run([sys.executable, os.path.join(ROOT, script), *args,
                              "--format", "json"],
                             capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else None
    except Exception:  # noqa: BLE001
        return None


def _audit(pid: str, event: str, detail: dict | None = None) -> None:
    os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
    with open(AUDIT, "a") as f:
        f.write(json.dumps({"ts": _now(), "id": pid, "event": event,
                            "detail": detail or {}}, ensure_ascii=False) + "\n")


def _path(pid: str) -> str:
    return os.path.join(PROPDIR, f"{pid}.json")


def _load(pid: str) -> dict | None:
    try:
        with open(_path(pid)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save(p: dict) -> None:
    os.makedirs(PROPDIR, exist_ok=True)
    with open(_path(p["id"]), "w") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def _book() -> tuple[dict, float | None]:
    """Current positions keyed by ticker, plus cash. Missing file = empty book."""
    try:
        with open(WATCHLIST) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}, None
    pos = {}
    for x in d.get("positions") or []:
        t = str(x.get("ticker") or "").upper()
        if t:
            pos[t] = x
    return pos, d.get("cash")


# --------------------------------------------------------------------------- propose

def cmd_propose(a) -> int:
    t = a.ticker.upper()
    side = a.side.upper()
    if side not in SIDES:
        print(f"propose: --side must be one of {'/'.join(SIDES)}", file=sys.stderr)
        return 1
    seq = 1
    while os.path.exists(_path(f"{t}-{date.today().isoformat()}-{seq}")):
        seq += 1
    pid = f"{t}-{date.today().isoformat()}-{seq}"

    p = {
        "id": pid, "status": "staged", "created": _now(),
        "ticker": t, "side": side, "market": a.market,
        "entry": a.entry, "stop": a.stop, "target": a.target,
        "dte": a.dte, "structure": a.structure,
        "size_usd": a.size, "budget_usd": a.budget,
        "thesis": a.thesis, "trigger": a.trigger,
        "source": a.source, "gates": None,
    }
    _save(p)
    _audit(pid, "staged", {"ticker": t, "side": side, "entry": a.entry, "stop": a.stop})
    print(f"staged {pid}  ({side} {t} @ {a.entry}, stop {a.stop})")
    print(f"  next: ot risk {pid}")
    return 0


# --------------------------------------------------------------------------- risk

def _gate(name, ok, msg, blocking=True):
    return {"gate": name, "ok": bool(ok), "blocking": blocking, "msg": msg}


def run_gates(p: dict) -> list[dict]:
    g: list[dict] = []
    t, side = p["ticker"], p["side"]
    entry, stop, target = p.get("entry"), p.get("stop"), p.get("target")
    longish = side in LONGISH

    # G1 — invalidation present and on the losing side of entry.
    if stop is None or entry is None:
        g.append(_gate("G1 invalidation", False,
                       "no stop: a proposal without an invalidation price cannot be sized"))
    elif (longish and stop >= entry) or (not longish and stop <= entry):
        where = "below" if longish else "above"
        g.append(_gate("G1 invalidation", False,
                       f"stop {stop} is on the wrong side of entry {entry} — a {side} "
                       f"stop must sit {where} the entry"))
    else:
        risk_pct = abs(entry - stop) / entry * 100
        g.append(_gate("G1 invalidation", True,
                       f"stop {stop} is {risk_pct:.1f}% from entry {entry}"))

    # G2 — the loss this proposal can actually inflict on the account.
    _, cash = _book()
    budget = p.get("budget_usd") or cash
    size = p.get("size_usd")
    if size and entry and stop:
        max_loss = size * abs(entry - stop) / entry
        p["max_loss_usd"] = round(max_loss, 2)
        if budget:
            pct = max_loss / budget * 100
            g.append(_gate("G2 risk budget", pct <= p.get("max_loss_pct", 2.0),
                           f"max loss ${max_loss:,.0f} = {pct:.2f}% of ${budget:,.0f}"
                           f" (limit {p.get('max_loss_pct', 2.0)}%)"))
        else:
            g.append(_gate("G2 risk budget", True,
                           f"max loss ${max_loss:,.0f}; no budget known — set --budget "
                           "or `cash` in the watchlist to enforce a limit", blocking=False))
    else:
        g.append(_gate("G2 risk budget", False,
                       "no --size: cannot compute max loss, so the trade cannot be sized"))

    # G3 — pay-off. Non-blocking: a scratch/scalp can be sub-1R by design.
    if target and entry and stop:
        rr = abs(target - entry) / max(abs(entry - stop), 1e-9)
        g.append(_gate("G3 reward", rr >= 1.0,
                       f"R:R {rr:.2f} ({'target' if rr >= 1 else 'target is inside the stop '
                                        'distance — you are risking more than you can win'})",
                       blocking=False))

    # G4 — the gate that matters most for a concentrated, levered book.
    pos, _ = _book()
    mult, cx = LEVERAGED.get(t, (1.0, None))
    if abs(mult) > 1.0:
        stacked = [k for k in pos
                   if k != t and LEVERAGED.get(k, (1.0, None))[1] == cx]
        if stacked:
            g.append(_gate("G4 leverage", False,
                           f"{t} is {abs(mult):g}x daily-reset on the '{cx}' complex and the "
                           f"book already holds {', '.join(stacked)} in that SAME complex — "
                           "that is one bet at higher leverage, not diversification"))
        else:
            g.append(_gate("G4 leverage", True,
                           f"{t} is {abs(mult):g}x daily-reset ({cx}). No same-complex position "
                           "in the book, but daily reset decays in chop: hold days, not weeks, "
                           "or express this unleveraged", blocking=False))
    elif cx:
        same = [k for k in pos if k != t and LEVERAGED.get(k, (1.0, None))[1] == cx]
        g.append(_gate("G4 leverage", True,
                       f"unleveraged. Book already in '{cx}' via {', '.join(same)} — this adds "
                       "to an existing bet" if same else f"unleveraged ({cx})", blocking=False))
    else:
        g.append(_gate("G4 leverage", True, "unleveraged / not a known levered vehicle",
                       blocking=False))

    # G5 — the event clock. Step 0 of the desk's own SOP.
    horizon = p.get("dte") if p.get("dte") is not None else 5
    cat = _tool_json("tools/catalysts/catalysts.py", "--days", str(max(horizon, 1)))
    ev = (cat or {}).get("events") or []
    if ev:
        names = ", ".join(str(e.get("label") or e.get("name") or e) for e in ev[:3])
        g.append(_gate("G5 event clock", False,
                       f"binary event inside the {horizon}d horizon: {names} — prefer patience "
                       "over initiation, or size for the gap"))
    else:
        g.append(_gate("G5 event clock", True, f"no Tier-1 print inside {horizon}d"))

    # G6 — the failure mode we hit live: after an expiry the 0DTE chain returns
    # all-nulls, which reads as a clean quote rather than as "there is no chain".
    if p.get("dte") == 0:
        ch = _tool_json("tools/options/opt.py", t, "--dte", "0")
        row = (ch[0] if isinstance(ch, list) and ch else ch) or {}
        empty = not row.get("call_oi") and not row.get("put_oi")
        g.append(_gate("G6 0DTE liquidity", not empty,
                       "0DTE chain is empty (expired or not yet listed) — every greek reads "
                       "null, which is not the same as zero" if empty
                       else f"0DTE chain live: call OI {row.get('call_oi')}, "
                            f"put OI {row.get('put_oi')}"))

    # G7 — argue against the desk's own base rate, not against nothing.
    st = _tool_json("tools/reflect/reflect.py")
    # The journal only ever records CALL/PUT/NO-ACTION, so a LONG/SHORT proposal
    # has to look up its directional equivalent or it silently skips the gate.
    key = {"LONG": "CALL", "SHORT": "PUT"}.get(side, side)
    ba = ((st or {}).get("by_action") or {}).get(key)
    if ba and ba.get("n"):
        hit = 100 * ba["right"] / ba["n"]
        g.append(_gate("G7 calibration", hit >= 50,
                       f"this desk is {hit:.0f}% on {side} over {ba['n']} graded calls"
                       + ("" if hit >= 50 else " — below a coin flip; demand a second "
                                               "independent block of evidence before sizing up"),
                       blocking=False))
    return g


def cmd_risk(a) -> int:
    p = _load(a.id)
    if not p:
        print(f"risk: no proposal {a.id}", file=sys.stderr)
        return 1
    if a.max_loss_pct is not None:
        p["max_loss_pct"] = a.max_loss_pct
    g = run_gates(p)
    blocked = [x for x in g if not x["ok"] and x["blocking"]]
    warned = [x for x in g if not x["ok"] and not x["blocking"]]
    p["gates"] = g
    p["status"] = "blocked" if blocked else "passed"
    p["risked"] = _now()
    _save(p)
    _audit(p["id"], p["status"],
           {"blocked": [x["gate"] for x in blocked], "warned": [x["gate"] for x in warned]})

    if a.format == "json":
        print(json.dumps(p, ensure_ascii=False, indent=2))
        return 0
    print(f"ot risk — {p['id']}  ({p['side']} {p['ticker']} @ {p.get('entry')})")
    for x in g:
        mark = "✓" if x["ok"] else ("✗" if x["blocking"] else "!")
        print(f"  {mark} {x['gate']:<18} {x['msg']}")
    print()
    if blocked:
        print(f"  BLOCKED by {len(blocked)} gate(s). Fix the proposal and re-run `ot risk {p['id']}`.")
    else:
        print(f"  PASSED{f' with {len(warned)} warning(s)' if warned else ''}."
              f"  A human may now run: ot approve {p['id']} --yes")
    print("  Educational only — not financial advice. This tool does not place orders.")
    return 0


# --------------------------------------------------------------------------- approve

def cmd_approve(a) -> int:
    p = _load(a.id)
    if not p:
        print(f"approve: no proposal {a.id}", file=sys.stderr)
        return 1
    if p.get("status") != "passed":
        print(f"approve: {p['id']} is '{p.get('status')}', not 'passed' — run `ot risk {p['id']}` "
              "and clear every blocking gate first.", file=sys.stderr)
        return 1
    if not a.yes:
        # The whole point of the verb. An agent that can pass --yes on its own
        # has removed the only control that matters, so this must stay manual.
        print(f"approve: refusing without --yes. Approval is the human step:\n"
              f"  ot approve {p['id']} --yes", file=sys.stderr)
        return 1
    p["status"] = "approved"
    p["approved"] = _now()
    p["approved_by"] = os.environ.get("USER", "?")
    _save(p)
    _audit(p["id"], "approved", {"by": p["approved_by"]})
    print(f"approved {p['id']}  ({p['side']} {p['ticker']} @ {p.get('entry')}, "
          f"stop {p.get('stop')})")
    print("  No order was placed — OpenTrading has no execution adapter wired. "
          "Place it yourself, or hand this id to a broker adapter you trust.")
    return 0


# --------------------------------------------------------------------------- list/show

def cmd_list(a) -> int:
    rows = []
    if os.path.isdir(PROPDIR):
        for fn in sorted(os.listdir(PROPDIR)):
            if fn.endswith(".json"):
                p = _load(fn[:-5])
                if p and (not a.status or p.get("status") == a.status):
                    rows.append(p)
    if a.format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("no proposals" + (f" with status '{a.status}'" if a.status else ""))
        return 0
    print(f"{'ID':<24} {'STATUS':<9} {'SIDE':<6} {'ENTRY':>9} {'STOP':>9}  THESIS")
    for p in rows:
        print(f"{p['id']:<24} {p.get('status',''):<9} {p.get('side',''):<6} "
              f"{str(p.get('entry','')):>9} {str(p.get('stop','')):>9}  "
              f"{(p.get('thesis') or '')[:44]}")
    return 0


def cmd_show(a) -> int:
    p = _load(a.id)
    if not p:
        print(f"show: no proposal {a.id}", file=sys.stderr)
        return 1
    print(json.dumps(p, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="propose",
                                 description="Staged trade proposals + risk gate (no execution).")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    sub = ap.add_subparsers(dest="cmd")

    n = sub.add_parser("new", help="stage a proposal")
    n.add_argument("ticker")
    n.add_argument("--side", required=True, help="CALL | PUT | LONG | SHORT")
    n.add_argument("--entry", type=float)
    n.add_argument("--stop", type=float, help="the invalidation price (mandatory in practice)")
    n.add_argument("--target", type=float)
    n.add_argument("--size", type=float, help="notional USD at risk in the position")
    n.add_argument("--budget", type=float, help="account size for the risk-budget gate")
    n.add_argument("--dte", type=int)
    n.add_argument("--structure", help="e.g. 'QQQ 690P 0DTE debit spread'")
    n.add_argument("--thesis")
    n.add_argument("--trigger", help="the observable condition that puts this trade ON")
    n.add_argument("--market", default="US")
    n.add_argument("--source", default="manual")

    r = sub.add_parser("risk", help="run the gates")
    r.add_argument("id")
    r.add_argument("--max-loss-pct", dest="max_loss_pct", type=float)

    p = sub.add_parser("approve", help="HUMAN ONLY — mark a passed proposal approved")
    p.add_argument("id")
    p.add_argument("--yes", action="store_true")

    l = sub.add_parser("list")
    l.add_argument("--status")
    s = sub.add_parser("show")
    s.add_argument("id")

    a = ap.parse_args(argv)
    for parser_dest in ("status", "id"):
        if not hasattr(a, parser_dest):
            setattr(a, parser_dest, None)
    if not hasattr(a, "format"):
        a.format = "text"

    if a.cmd == "new":
        return cmd_propose(a)
    if a.cmd == "risk":
        return cmd_risk(a)
    if a.cmd == "approve":
        return cmd_approve(a)
    if a.cmd == "show":
        return cmd_show(a)
    return cmd_list(a)


if __name__ == "__main__":
    sys.exit(main())
