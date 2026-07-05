#!/usr/bin/env python3
"""
poly.py — Polymarket crowd odds for the macro gate (`ot poly`). No key.

Prediction markets are the crowd's *priced* forecast — real money on Fed
decisions, recession, inflation prints. That is exactly the Step-0 event-gate
question ("what is the market braced for?"), so this tool pulls the
macro-relevant Polymarket events (public Gamma API, keyless) and distills a
gate view: P(no change next FOMC), P(hike this year), P(zero cuts), plus the
top-volume economy markets.

    python3 poly.py                    # gate view + top macro markets
    python3 poly.py --tags fed         # one tag only
    python3 poly.py --format json      # machine-readable (for ot debate / web)

Stdlib + optional certifi; curl fallback. Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request

API = "https://gamma-api.polymarket.com/events"
UA = "Mozilla/5.0 (OpenTrading poly-cli)"
DEFAULT_TAGS = ["fed", "economy", "inflation"]


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        curl = shutil.which("curl")
        if curl:
            out = subprocess.run([curl, "-sL", "--max-time", str(timeout), "-A", UA, url],
                                 capture_output=True, text=True, timeout=timeout + 5)
            if out.returncode == 0 and out.stdout:
                return out.stdout
        raise


def fetch_events(tag: str, limit: int = 12) -> list[dict]:
    qs = urllib.parse.urlencode({"closed": "false", "limit": limit, "tag_slug": tag,
                                 "order": "volume24hr", "ascending": "false"})
    try:
        data = json.loads(http_get(f"{API}?{qs}"))
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def _yes_prob(m: dict) -> float | None:
    """P(first outcome) — Polymarket binary markets are ['Yes','No'] ordered."""
    try:
        prices = m.get("outcomePrices")
        if isinstance(prices, str):
            prices = json.loads(prices)
        return round(float(prices[0]) * 100, 1)
    except Exception:  # noqa: BLE001
        return None


def collect(tags: list[str], limit: int) -> list[dict]:
    """Flatten events -> markets with P(yes), deduped, volume-ranked."""
    seen, out = set(), []
    for tag in tags:
        for ev in fetch_events(tag, limit):
            title = ev.get("title") or ""
            for m in ev.get("markets") or []:
                q = (m.get("question") or "").strip()
                if not q or q in seen:
                    continue
                p = _yes_prob(m)
                if p is None:
                    continue
                seen.add(q)
                out.append({"event": title, "question": q, "p_yes": p, "tag": tag,
                            "volume24h": round(float(m.get("volume24hr") or 0)),
                            "end": (m.get("endDate") or "")[:10]})
    out.sort(key=lambda x: -x["volume24h"])
    return out


# Gate-view extraction: the handful of numbers the Step-0 gate actually wants.
GATE_PATTERNS = [
    ("no_change_next_fomc", r"no change in fed interest rates after the \w+ 2\d{3} meet"),
    ("cut_25_next_fomc",    r"decrease interest rates by 25 bps after the \w+ 2\d{3} meet"),
    ("hike_this_year",      r"^fed rate hike in 2\d{3}\?$"),
    ("zero_cuts_this_year", r"no fed rate cuts happen in 2\d{3}"),
    ("recession",           r"recession in 2\d{3}|us recession"),
]


def gate_view(markets: list[dict]) -> dict:
    """First (highest-volume) match per pattern — matches are already vol-ranked."""
    gate = {}
    for key, pat in GATE_PATTERNS:
        rx = re.compile(pat, re.I)
        for m in markets:
            if rx.search(m["question"]):
                gate[key] = {"p": m["p_yes"], "question": m["question"], "end": m["end"]}
                break
    return gate


def render_text(gate: dict, markets: list[dict], top: int) -> str:
    L = ["Polymarket — crowd odds (macro gate)  ·  gamma-api, no key", ""]
    labels = {"no_change_next_fomc": "P(Fed holds, next FOMC)",
              "cut_25_next_fomc":    "P(25bp cut, next FOMC)",
              "hike_this_year":      "P(Fed HIKE this year)",
              "zero_cuts_this_year": "P(zero cuts this year)",
              "recession":           "P(recession)"}
    if gate:
        L.append("  gate view:")
        for k, lbl in labels.items():
            if k in gate:
                L.append(f"    {lbl:<28} {gate[k]['p']:>5.1f}%   (to {gate[k]['end']})")
        L.append("")
    L.append(f"  top macro markets (by 24h volume, top {top}):")
    for m in markets[:top]:
        L.append(f"    {m['p_yes']:>5.1f}%  {m['question'][:78]}  [${m['volume24h']:,}]")
    L.append("")
    L.append("  Read: odds are the crowd's priced forecast — a gate input, not a signal by itself.")
    L.append("  Educational only — not financial advice.")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(prog="poly", description="Polymarket macro odds (no key).")
    p.add_argument("--tags", default=",".join(DEFAULT_TAGS),
                   help=f"comma tag slugs (default {','.join(DEFAULT_TAGS)})")
    p.add_argument("--limit", type=int, default=12, help="events per tag (default 12)")
    p.add_argument("--top", type=int, default=10, help="markets shown in text mode (default 10)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)

    tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    markets = collect(tags, a.limit)
    if not markets:
        print("poly: no markets returned (network or API change).", file=sys.stderr)
        return 1
    gate = gate_view(markets)
    if a.format == "json":
        print(json.dumps({"gate": gate, "markets": markets[:60], "tags": tags},
                         ensure_ascii=False, indent=2))
    else:
        print(render_text(gate, markets, a.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
