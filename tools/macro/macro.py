#!/usr/bin/env python3
"""
macro.py — OpenTrading intraday macro dashboard (free, no-key data).

Pulls the public, no-API-key macro indicators behind the short-term-trader
"Daily Macro Brief" and scores each per the thresholds in
.claude/skills/short-term-trader/references/macro-dashboard.md.

Auto (fetched live, no key):
    SOFR          NY Fed secured rates API
    2Y / 10Y      US Treasury daily par yield curve (XML)
    TGA balance   Treasury Fiscal Data "operating cash balance"
    RRP           NY Fed reverse-repo (best effort; may need manual check)

Manual (printed with URL — fetch with WebFetch or the browser):
    Fed cut odds  Polymarket
    PCE nowcast   Cleveland Fed
    News flow     use  tools/financialjuice/fj.py  (FinancialJuice squawk)

Stdlib only (Python 3.9+).  Examples:
    python3 macro.py                 # scored dashboard
    python3 macro.py --format json   # machine-readable
"""
from __future__ import annotations

import json
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from xml.etree import ElementTree as ET

UA = "Mozilla/5.0 (OpenTrading macro-cli)"

SOFR_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/5.json"
YIELD_URL = ("https://home.treasury.gov/resource-center/data-chart-center/"
             "interest-rates/pages/xml?data=daily_treasury_yield_curve"
             "&field_tdr_date_value={year}")
TGA_URL = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/"
           "accounting/dts/operating_cash_balance?sort=-record_date&page%5Bsize%5D=30")
RRP_URL = "https://markets.newyorkfed.org/api/rp/reverserepo/all/results/latest.json"

MANUAL = [
    ("Fed cut odds", "https://polymarket.com/event/fed-decision-in-december",
     ">65% cut prob = bullish, <55% = bearish"),
    ("PCE nowcast", "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting",
     "below consensus = bullish, above = bearish"),
    ("News flow", "run: python3 tools/financialjuice/fj.py fetch --window premarket",
     "dovish/weak-data = bullish, hawkish/hot-data = bearish"),
]


# --------------------------------------------------------------------------- #
# HTTP (certifi -> default -> curl fallback; macOS Python can't see system CAs)
# --------------------------------------------------------------------------- #
def _ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        curl = shutil.which("curl")
        if curl:
            out = subprocess.run([curl, "-sL", "--max-time", str(timeout), "-A", UA, url],
                                 capture_output=True, timeout=timeout + 5)
            if out.returncode == 0 and out.stdout:
                return out.stdout.decode("utf-8", errors="replace")
        raise


def _safe(fn, *a):
    """Run a fetch/parse fn; return (result, None) or (None, error_str)."""
    try:
        return fn(*a), None
    except Exception as exc:  # noqa: BLE001 - indicators degrade independently
        return None, f"{type(exc).__name__}: {exc}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# --------------------------------------------------------------------------- #
# Indicators
# --------------------------------------------------------------------------- #
def get_sofr() -> dict:
    data = json.loads(http_get(SOFR_URL))
    rows = [r for r in data.get("refRates", [])
            if r.get("type") == "SOFR" and r.get("percentRate") is not None]
    rows.sort(key=lambda r: r["effectiveDate"])
    latest, oldest = rows[-1], rows[0]
    rate, prev = float(latest["percentRate"]), float(oldest["percentRate"])
    if rate < prev - 0.005:
        score, arrow = 1, "down"
    elif rate > prev + 0.005:
        score, arrow = -1, "up"
    else:
        score, arrow = 0, "flat"
    return {"label": "SOFR", "value": f"{rate:.2f}%",
            "detail": f"{arrow} vs {prev:.2f}% ({latest['effectiveDate']})", "score": score}


def _yield_rows(year: int) -> list[dict]:
    root = ET.fromstring(http_get(YIELD_URL.format(year=year)))
    rows = []
    for props in root.iter():
        if _local(props.tag) != "properties":
            continue
        d = {_local(c.tag): (c.text or "").strip() for c in props}
        if d.get("NEW_DATE"):
            rows.append(d)
    return rows


def get_yields() -> list[dict]:
    from datetime import datetime, timezone
    year = datetime.now(timezone.utc).year
    rows = _yield_rows(year) or _yield_rows(year - 1)  # early-Jan fallback
    rows.sort(key=lambda d: d["NEW_DATE"])
    last = rows[-1]
    y2, y10 = float(last["BC_2YEAR"]), float(last["BC_10YEAR"])
    date = last["NEW_DATE"][:10]
    s2 = 1 if y2 < 4.18 else -1 if y2 > 4.30 else 0
    s10 = 1 if y10 < 4.35 else -1 if y10 > 4.50 else 0
    return [
        {"label": "2Y Yield", "value": f"{y2:.2f}%",
         "detail": f"bull<4.18 / bear>4.30 ({date})", "score": s2},
        {"label": "10Y Yield", "value": f"{y10:.2f}%",
         "detail": f"bull<4.35 / bear>4.50 ({date})", "score": s10},
    ]


def get_tga() -> dict:
    data = json.loads(http_get(TGA_URL)).get("data", [])
    for row in data:
        at = row.get("account_type", "")
        if "(TGA)" in at and "Opening Balance" in at:
            val = row.get("open_today_bal")
            if val not in (None, "null", ""):
                bn = float(val) / 1000.0
                score = 1 if bn < 900 else -1 if bn > 925 else 0
                return {"label": "TGA", "value": f"${bn:,.0f}B",
                        "detail": f"bull<900 / bear>925 ({row['record_date']})",
                        "score": score}
    raise ValueError("TGA opening balance row not found")


def get_rrp() -> dict:
    data = json.loads(http_get(RRP_URL))
    ops = data.get("repo", {}).get("operations", []) or data.get("operations", [])
    if not ops:
        raise ValueError("no RRP operation returned (check manually)")
    op = ops[0]
    amt = op.get("totalAmtAccepted") or op.get("totalAmtSubmitted")
    bn = float(amt) / 1_000_000_000 if amt else None
    return {"label": "RRP", "value": f"${bn:,.0f}B" if bn else "n/a",
            "detail": f"declining=bullish ({op.get('operationDate','?')})", "score": 0}


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def collect() -> tuple[list[dict], list[str]]:
    indicators: list[dict] = []
    errors: list[str] = []
    for fn in (get_sofr, get_tga, get_rrp):
        res, err = _safe(fn)
        if res:
            indicators.append(res)
        elif err:
            errors.append(f"{fn.__name__}: {err}")
    ys, err = _safe(get_yields)
    if ys:
        indicators.extend(ys)
    elif err:
        errors.append(f"get_yields: {err}")
    return indicators, errors


def bias_from_score(total: int) -> str:
    if total >= 2:
        return "LEAN CALLS (bullish tilt)"
    if total <= -2:
        return "LEAN PUTS (bearish tilt)"
    return "NEUTRAL — no directional edge from rates/liquidity alone"


def render_table(indicators: list[dict], errors: list[str]) -> str:
    scored = [i for i in indicators if i.get("score") is not None]
    total = sum(i["score"] for i in scored)
    sym = {1: "+ bull", -1: "- bear", 0: "  neut"}
    out = ["=" * 64, "INTRADAY MACRO DASHBOARD — auto-fetched (no-key public data)", "=" * 64]
    for i in indicators:
        sc = sym.get(i.get("score"), "  n/a ")
        out.append(f"  {i['label']:<11} {i['value']:>9}  [{sc}]  {i['detail']}")
    out += ["-" * 64,
            f"  AUTO SCORE: {total:+d}  (from {len(scored)} indicators)  ->  {bias_from_score(total)}",
            "-" * 64,
            "  STILL TO CHECK (fold into final bias):"]
    for label, url, rule in MANUAL:
        out.append(f"    - {label:<12} {rule}")
        out.append(f"      {url}")
    if errors:
        out.append("-" * 64)
        out.append("  NOTES (degraded indicators):")
        for e in errors:
            out.append(f"    ! {e}")
    out.append("=" * 64)
    out.append("  Analysis for educational purposes, not financial advice.")
    return "\n".join(out)


def render_json(indicators: list[dict], errors: list[str]) -> str:
    scored = [i for i in indicators if i.get("score") is not None]
    total = sum(i["score"] for i in scored)
    return json.dumps({
        "dashboard": "intraday_macro",
        "auto_indicators": indicators,
        "auto_score": total,
        "bias": bias_from_score(total),
        "manual_indicators": [{"label": l, "url": u, "rule": r} for l, u, r in MANUAL],
        "errors": errors,
    }, indent=2)


def main(argv: list[str] | None = None) -> None:
    import argparse
    p = argparse.ArgumentParser(prog="macro", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--format", choices=["table", "json"], default="table")
    args = p.parse_args(argv)
    indicators, errors = collect()
    if not indicators:
        sys.exit("[macro] All live indicators failed:\n  " + "\n  ".join(errors))
    print((render_json if args.format == "json" else render_table)(indicators, errors))


if __name__ == "__main__":
    main()
