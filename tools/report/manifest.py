#!/usr/bin/env python3
"""
manifest.py — run-manifest snapshots + freshness gate (P2-8).

Every email/analysis run should leave a receipt: which sections were fed,
how big each was, and whether anything looked STALE or EMPTY — so a beautiful
email built on a dead feed can't pass silently (the email-freshness rule).

Reads section blobs from stdin as JSON ({"MACRO": "...", "NEWS7": "..."}),
writes data/manifests/<UTC-ts>.json, and prints a compact "### RUN MANIFEST"
block the composer appends to the prompt — the LLM is TOLD which feeds are
thin so it can hedge or refuse instead of inventing.

    echo '{"MACRO":"...","NEWS7":""}' | python3 manifest.py --run daily-email
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/manifests"

# a section smaller than this many bytes is EMPTY-grade; 10x = THIN
MIN_BYTES = {"NEWS7": 400, "MACRO": 120, "SMART": 80, "STRAT": 200,
             "PLANS": 150, "OPTS": 80, "CATAL": 40, "EARN": 20, "RANK": 80}


def main(argv=None):
    p = argparse.ArgumentParser(prog="manifest")
    p.add_argument("--run", default="run", help="run name, e.g. daily-email")
    p.add_argument("--owner", default="")
    a = p.parse_args(argv)
    try:
        sections = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        sections = {}
    now = datetime.now(timezone.utc)
    rows, warns = {}, []
    for name, blob in sections.items():
        size = len((blob or "").encode("utf-8", "replace"))
        floor = MIN_BYTES.get(name, 60)
        status = "ok" if size >= floor else ("thin" if size > 0 else "EMPTY")
        rows[name] = {"bytes": size, "status": status}
        if status != "ok":
            warns.append(f"{name} is {status} ({size}B)")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{now:%Y%m%dT%H%M%SZ}-{a.run}.json"
    path.write_text(json.dumps({
        "run": a.run, "owner": a.owner, "utc": now.isoformat(timespec="seconds"),
        "sections": rows, "warnings": warns}, indent=2), encoding="utf-8")
    # the block the composer appends to the prompt
    line = " · ".join(f"{k}:{v['status']}({v['bytes']}B)" for k, v in rows.items())
    print(f"run={a.run} utc={now:%Y-%m-%d %H:%M}Z  {line}")
    if warns:
        print("FEED WARNINGS — the sections above marked thin/EMPTY are unreliable: "
              + "; ".join(warns)
              + ". Do NOT invent content for them; say the feed was thin instead.")
    else:
        print("all feeds present and sized normally.")


if __name__ == "__main__":
    main()
