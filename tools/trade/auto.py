#!/usr/bin/env python3
"""
auto.py — the end-to-end desk run (`ot auto`).

Chains the whole SOP into one deterministic command:

    event gate  ->  ot debate  ->  ot propose  ->  ot risk  ->  STOP

and stops. It never calls `ot approve`. That is not a policy statement bolted on
top — `approve` requires an explicit human --yes carrying the exact proposal id,
and nothing in this file passes it. The automation's job is to arrive at a
staged, risk-checked proposal by the time a human looks at the screen; the
human's job is the last click.

    ot auto                       # the default book: RAM, TQQQ
    ot auto MU DRAM --dte 5
    ot auto TQQQ --size 5000 --budget 100000
    ot auto --dry-run             # run the desk, skip staging

No agentic tool use anywhere in the loop: every step is a subprocess call to an
existing `ot` CLI with a fixed argument list, so a run is reproducible and can
be replayed. The only LLM calls are the three inside `ot debate`.

Verdict -> side mapping (HOLD stages nothing, by design — a desk that finds a
trade every time it looks is not a desk):

    STRONG_BUY / BUY    -> LONG
    SELL / STRONG_SELL  -> SHORT
    HOLD                -> skipped

Educational only — not financial advice. This tool does not place orders.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OT = os.path.join(ROOT, "bin", "ot")

DEFAULT_BOOK = ["RAM", "TQQQ"]
SIDE = {"STRONG_BUY": "LONG", "BUY": "LONG", "SELL": "SHORT", "STRONG_SELL": "SHORT"}


def _run(args: list[str], timeout: int = 900) -> tuple[int, str]:
    try:
        out = subprocess.run([OT, *args], capture_output=True, text=True,
                             timeout=timeout, cwd=ROOT)
        return out.returncode, out.stdout
    except subprocess.TimeoutExpired:
        return 124, ""
    except Exception:  # noqa: BLE001
        return 1, ""


def _run_json(args: list[str], timeout: int = 900):
    rc, out = _run([*args, "--format", "json"], timeout=timeout)
    if rc != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def event_gate(days: int) -> tuple[bool, str]:
    """Step 0 of the desk's SOP: is a binary print near? Returns (clear, note)."""
    cat = _run_json(["catalysts", "--days", str(days)], timeout=120) or {}
    ev = cat.get("events") or []
    if not ev:
        return True, f"no Tier-1 print inside {days}d"
    names = ", ".join(str(e.get("label") or e.get("name") or e) for e in ev[:3])
    return False, f"{len(ev)} event(s) inside {days}d: {names}"


def run_one(t: str, a) -> dict:
    row: dict = {"ticker": t, "stage": "debate"}
    t0 = time.time()
    d = _run_json(["debate", t, "--dte", str(a.dte)]
                  + (["--lang", "zh"] if a.lang == "zh" else [])
                  + (["--log"] if a.log else []), timeout=1200)
    if not d:
        row.update(stage="failed", note="debate produced no verdict")
        return row
    row.update({
        "verdict": d.get("verdict"), "confidence": d.get("confidence"),
        "blocks": d.get("blocks_supporting"), "trigger": d.get("trigger"),
        "instrument": d.get("instrument"), "entry_price": d.get("entry_price"),
        "invalidation": d.get("invalidation"), "targets": d.get("targets"),
        "time_stop_days": d.get("time_stop_days"), "price": d.get("price"),
        "debate_s": round(time.time() - t0, 1),
    })

    side = SIDE.get(d.get("verdict") or "")
    if not side:
        row.update(stage="skipped", note=f"verdict {d.get('verdict')} — nothing to stage")
        return row

    entry, stop = d.get("entry_price"), d.get("invalidation")
    if entry is None or stop is None:
        row.update(stage="skipped",
                   note="judge gave no numeric entry/invalidation — cannot size a proposal")
        return row
    # A verdict whose stop sits on the winning side of entry is internally
    # inconsistent; stage nothing rather than "fix" the judge's arithmetic.
    if (side == "LONG" and stop >= entry) or (side == "SHORT" and stop <= entry):
        row.update(stage="skipped",
                   note=f"incoherent plan: {side} entry {entry} with stop {stop}")
        return row

    if a.dry_run:
        row.update(stage="dry-run", note="staging skipped (--dry-run)")
        return row

    targets = d.get("targets") or []
    args = ["propose", t, "--side", side, "--entry", str(entry), "--stop", str(stop),
            "--dte", str(a.dte), "--source", "auto",
            "--thesis", (d.get("rationale") or "")[:300]]
    if targets:
        args += ["--target", str(targets[0])]
    if d.get("trigger"):
        args += ["--trigger", d["trigger"][:300]]
    if a.size:
        args += ["--size", str(a.size)]
    if a.budget:
        args += ["--budget", str(a.budget)]
    rc, out = _run(args, timeout=120)
    pid = out.split()[1] if rc == 0 and out.startswith("staged ") else None
    if not pid:
        row.update(stage="failed", note="propose did not stage")
        return row
    row["proposal_id"] = pid

    risked = _run_json(["risk", pid], timeout=600) or {}
    row["stage"] = risked.get("status") or "unknown"
    gates = risked.get("gates") or []
    row["blocked_by"] = [g["gate"] for g in gates if not g["ok"] and g["blocking"]]
    row["warnings"] = [g["gate"] for g in gates if not g["ok"] and not g["blocking"]]
    row["gates"] = [{"gate": g["gate"], "ok": g["ok"], "msg": g["msg"]} for g in gates]
    return row


def render(rows: list[dict], gate_note: str, clear: bool) -> str:
    L = ["=" * 68,
         f"ot auto — desk run {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
         "=" * 68,
         f"  EVENT GATE  {'✓' if clear else '⚠'} {gate_note}",
         ""]
    for r in rows:
        px = r.get("price")
        L.append(f"  {r['ticker']}"
                 + (f"  ${px:.2f}" if isinstance(px, (int, float)) else ""))
        if r.get("verdict"):
            blocks = " + ".join(r.get("blocks") or []) or "?"
            L.append(f"     verdict    {r['verdict']} · confidence {r.get('confidence')}"
                     f" · sources {blocks}")
        if r.get("trigger"):
            L.append(f"     trigger    {r['trigger'][:150]}")
        if r.get("instrument"):
            L.append(f"     vehicle    {r['instrument'][:150]}")
        if r.get("entry_price") is not None:
            tg = ", ".join(f"{x:g}" for x in (r.get("targets") or [])) or "—"
            L.append(f"     plan       entry {r['entry_price']} · stop {r.get('invalidation')}"
                     f" · targets {tg} · time stop {r.get('time_stop_days')}d")
        status = r.get("stage")
        mark = {"passed": "✓", "blocked": "✗", "skipped": "·",
                "dry-run": "·", "failed": "!"}.get(status, "?")
        extra = ""
        if r.get("blocked_by"):
            extra = " — " + ", ".join(r["blocked_by"])
        elif r.get("note"):
            extra = f" — {r['note']}"
        L.append(f"     {mark} {status}{extra}"
                 + (f"   [{r['proposal_id']}]" if r.get("proposal_id") else ""))
        if r.get("warnings"):
            L.append(f"     ! warnings  {', '.join(r['warnings'])}")
        L.append("")
    passed = [r for r in rows if r.get("stage") == "passed"]
    L.append("-" * 68)
    if passed:
        L.append(f"  {len(passed)} proposal(s) PASSED the gates and are waiting for a human:")
        for r in passed:
            L.append(f"     ot approve {r['proposal_id']} --yes")
    else:
        L.append("  Nothing passed. No proposal is waiting for approval.")
    L.append("  This run did not approve or place anything — approval is the human step.")
    L.append("  Educational only — not financial advice.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="auto",
                                 description="End-to-end desk run: debate -> propose -> risk. "
                                             "Never approves.")
    ap.add_argument("tickers", nargs="*", help=f"default: {' '.join(DEFAULT_BOOK)}")
    ap.add_argument("--dte", type=int, default=5)
    ap.add_argument("--size", type=float, help="notional USD per proposal")
    ap.add_argument("--budget", type=float, help="account size for the risk-budget gate")
    ap.add_argument("--lang", choices=["en", "zh"], default="en")
    ap.add_argument("--log", action="store_true",
                    help="journal each verdict so it gets graded later (ot reflect)")
    ap.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="run the desk but stage nothing")
    ap.add_argument("--ignore-event-gate", dest="ignore_gate", action="store_true")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)

    tickers = [t.upper() for t in (a.tickers or DEFAULT_BOOK)]
    clear, note = event_gate(a.dte)
    if not clear and not a.ignore_gate:
        out = {"event_gate": {"clear": False, "note": note}, "runs": [],
               "aborted": "Tier-1 event inside the horizon"}
        if a.format == "json":
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(f"ot auto — ABORTED before any LLM call.\n  EVENT GATE ⚠ {note}\n"
                  "  A binary print inside the horizon outranks any setup. Re-run after it "
                  "clears, or pass --ignore-event-gate to override deliberately.")
        return 0

    rows = [run_one(t, a) for t in tickers]
    if a.format == "json":
        print(json.dumps({"event_gate": {"clear": clear, "note": note}, "runs": rows},
                         ensure_ascii=False, indent=2))
        return 0
    print(render(rows, note, clear))
    return 0


if __name__ == "__main__":
    sys.exit(main())
