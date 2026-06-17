#!/usr/bin/env python3
"""
report.py — gather macro + smart money + quotes + news into one data pack.

Runs the OpenTrading CLIs once (JSON), then assembles a single structured
markdown "data pack" (or --format json bundle) for the **market-report skill**
to reason over. report.py supplies the *data + a light regime read*; the skill
supplies the *logic* (cross-asset synthesis, per-position calls).

    python3 report.py                 # markdown data pack -> stdout
    python3 report.py --format json   # raw bundle
    python3 report.py --save          # also write data/reports/<date>.md

Stdlib only. Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    ET = None

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable or "python3"
REPORTS = ROOT / "data" / "reports"

TOOLS = {
    "macro":  [ROOT / "tools/macro/macro.py", "--format", "json"],
    "smart":  [ROOT / "tools/smartmoney/sm.py", "--format", "json"],
    "news":   [ROOT / "tools/financialjuice/fj.py", "fetch", "--minutes", "720",
               "--limit", "25", "--format", "json"],
    "quotes": [ROOT / "tools/quote/q.py", "SPY", "QQQ", "^VIX",
               "--watchlist", "--format", "json"],
    "options": [ROOT / "tools/options/opt.py", "SPY", "--dte", "7", "--format", "json"],
}


def run_json(args):
    try:
        out = subprocess.run([str(PY), *map(str, args)], capture_output=True,
                             text=True, timeout=90)
        return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else None
    except Exception:  # noqa: BLE001
        return None


def _curl(url, timeout=12):
    out = subprocess.run(["curl", "-s", "--max-time", str(timeout), url],
                         capture_output=True, text=True, timeout=timeout + 5)
    return out.stdout


def fetch_btc():
    """Coinbase is cleaner than Yahoo BTC-USD for 24/7 day-change."""
    try:
        spot = json.loads(_curl("https://api.coinbase.com/v2/prices/BTC-USD/spot"))
        stats = json.loads(_curl("https://api.exchange.coinbase.com/products/BTC-USD/stats"))
        px, op = float(spot["data"]["amount"]), float(stats["open"])
        return {"px": px, "chg": (px - op) / op * 100 if op else 0.0,
                "hi": float(stats["high"]), "lo": float(stats["low"])}
    except Exception:  # noqa: BLE001
        return None


def gather():
    b = {k: run_json(v) for k, v in TOOLS.items()}
    b["btc"] = fetch_btc()
    return b


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def qget(quotes, sym):
    for r in quotes or []:
        if r.get("symbol") == sym.upper():
            return r
    return None


def chg(quotes, sym):
    r = qget(quotes, sym)
    return r.get("chg_pct") if r else None


# --------------------------------------------------------------------------- #
# Regime (light, rule-based — the skill goes deeper)
# --------------------------------------------------------------------------- #
def regime(bundle):
    macro = bundle.get("macro") or {}
    smart = bundle.get("smart") or {}
    quotes = bundle.get("quotes") or []
    ms = macro.get("auto_score")
    spy = chg(quotes, "SPY")
    eq = (smart.get("equity_fng") or {})
    comps = eq.get("components") or {}

    tilt = "RISK-ON" if (ms or 0) >= 2 and (spy or 0) > 0.2 else \
           "RISK-OFF" if (ms or 0) <= -2 or (spy or 0) < -0.5 else "MIXED"
    tensions = []
    breadth = (comps.get("breadth") or {}).get("score")
    junk = (comps.get("junk-bond") or {}).get("score")
    if spy and spy > 0.3 and ((breadth is not None and breadth < 30) or (junk is not None and junk < 20)):
        tensions.append(f"gap-up on weak internals (breadth {breadth}, junk-bond demand {junk}) "
                        f"— narrow/credit-cautious tape")
    cf = (smart.get("crypto_fng") or {}).get("value")
    btc = (bundle.get("btc") or {}).get("chg")
    if cf is not None and cf <= 25 and (btc or 0) >= 0:
        tensions.append(f"crypto Fear&Greed {cf} (extreme fear) while BTC firm — contrarian-bull divergence")
    if eq.get("score") is not None and eq.get("month_ago") is not None and eq["month_ago"] - eq["score"] >= 15:
        tensions.append(f"sentiment deteriorating fast (F&G {eq['month_ago']:.0f}->{eq['score']:.0f} in a month)")
    op = (bundle.get("options") or [None])[0]
    if op and not op.get("error") and op.get("net_gex_usd_per_1pct") is not None:
        gb = op["net_gex_usd_per_1pct"] / 1e9
        if op["gex_sign"] == "positive":
            tensions.append(f"positive dealer gamma (${gb:+.1f}bn/1%): vol-suppressed, SPY likely "
                            f"pins near call wall {op['call_wall']:.0f} — a gap may stall/fade not trend")
        elif op["gex_sign"] == "negative":
            tensions.append(f"negative dealer gamma (${gb:+.1f}bn/1%): vol-amplifying — "
                            f"trend/squeeze risk, moves accelerate")
    return tilt, tensions


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def md_quotes(quotes):
    if not quotes:
        return ["_quotes unavailable_"]
    L = ["| Symbol | Last | Chg% | Session |", "|---|---|---|---|"]
    for r in quotes:
        if r.get("error"):
            L.append(f"| {r['symbol']} | err | | |")
            continue
        last = f"{r['last']:,.2f}" if r.get("last") is not None else "n/a"
        c = f"{r['chg_pct']:+.2f}%" if r.get("chg_pct") is not None else "n/a"
        L.append(f"| {r['symbol']} | {last} | {c} | {r.get('session','')} |")
    return L


def md_macro(macro):
    if not macro:
        return ["_macro unavailable_"]
    L = ["| Indicator | Value | Tilt |", "|---|---|---|"]
    for i in macro.get("auto_indicators", []):
        s = i.get("score")
        t = "bull" if s == 1 else "bear" if s == -1 else "neut"
        L.append(f"| {i['label']} | {i['value']} | {t} |")
    L.append("")
    L.append(f"Auto score **{macro.get('auto_score'):+d}** → {macro.get('bias','')}")
    return L


def md_smart(smart):
    if not smart:
        return ["_smart-money unavailable_"]
    L = []
    eq = smart.get("equity_fng")
    if eq:
        L.append(f"- **Equity Fear&Greed: {eq['score']:.0f} ({eq['rating']})** "
                 f"— 1w {eq['week_ago']:.0f}, 1m {eq['month_ago']:.0f}")
        comps = ", ".join(f"{k} {v['score']:.0f}" for k, v in (eq.get("components") or {}).items()
                          if v.get("score") is not None)
        L.append(f"  - components: {comps}")
    cf = smart.get("crypto_fng")
    if cf:
        L.append(f"- **Crypto Fear&Greed: {cf['value']} ({cf['rating']})**")
    fn = smart.get("btc_funding")
    if fn:
        L.append(f"- **BTC funding: {fn['rate_8h_pct']:+.4f}%/8h (~{fn['annualized_pct']:+.1f}%/yr)** — {fn['read']}")
    return L


def md_options(options):
    op = (options or [None])[0]
    if not op or op.get("error") or op.get("net_gex_usd_per_1pct") is None:
        return ["_options positioning unavailable_"]
    gx = f"${op['net_gex_usd_per_1pct']/1e9:+.2f}bn/1%"
    return [
        f"- **Net dealer GEX (SPY ≤7DTE): {gx}** → {op['gex_sign']} gamma "
        f"({'vol-suppressing / pins' if op['gex_sign']=='positive' else 'vol-amplifying / trends' if op['gex_sign']=='negative' else 'neutral'})",
        f"- **Put/Call: OI {op['pc_oi']:.2f} · vol {op['pc_vol']:.2f}**",
        f"- **Gamma walls:** call/resistance **{op['call_wall']:.0f}** · put/support **{op['put_wall']:.0f}** (spot {op['spot']:.0f})",
    ]


def md_news(news):
    items = (news or {}).get("items", [])
    if not items:
        return ["_no headlines (quiet tape)_"]
    return [f"- `{it.get('time_et','--:--')}` **{it.get('category','')}** — {it.get('headline','')}"
            for it in items[:15]]


def build_markdown(bundle, now):
    tilt, tensions = regime(bundle)
    sess = "PRE-MARKET" if now.weekday() < 5 and now.hour < 9 else "SESSION"
    L = [f"# OpenTrading Market Data Pack — {now:%Y-%m-%d %H:%M ET} ({sess})", ""]
    L += [f"## Regime (auto): **{tilt}**"]
    for t in tensions:
        L.append(f"- ⚠️ {t}")
    L += ["", "## Tape / Quotes", *md_quotes(bundle.get("quotes"))]
    btc = bundle.get("btc")
    if btc:
        L.append(f"- **BTC** ${btc['px']:,.0f} ({btc['chg']:+.1f}% 24h, "
                 f"range ${btc['lo']:,.0f}–${btc['hi']:,.0f})")
    L.append("")
    L += ["## Macro", *md_macro(bundle.get("macro")), ""]
    L += ["## Smart money / positioning", *md_smart(bundle.get("smart")), ""]
    L += ["## Options / dealer gamma (SPY)", *md_options(bundle.get("options")), ""]
    L += ["## News tape (last 12h)", *md_news(bundle.get("news")), ""]
    L += ["---", "_Data pack auto-gathered by OpenTrading. The market-report skill adds the synthesis. "
          "Educational only, not financial advice._"]
    return "\n".join(L)


def notify(title, subtitle, msg):
    def esc(s):
        return s.replace("\\", "").replace('"', "'")
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{esc(msg)}" with title "{esc(title)}" '
                        f'subtitle "{esc(subtitle)}" sound name "Submarine"'],
                       capture_output=True, timeout=10)
        return True
    except Exception:  # noqa: BLE001
        return False


def main(argv=None):
    p = argparse.ArgumentParser(prog="report", description="Gather the market data pack.")
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument("--json", dest="format", action="store_const", const="json",
                   help="Alias for --format json.")
    p.add_argument("--save", action="store_true", help="Also write data/reports/<date>.md")
    p.add_argument("--notify", action="store_true", help="Fire a macOS notification with the headline read.")
    a = p.parse_args(argv)
    now = datetime.now(ET) if ET else datetime.now()
    bundle = gather()

    if a.notify:
        tilt, _ = regime(bundle)
        spy = chg(bundle.get("quotes"), "SPY")
        vix = qget(bundle.get("quotes"), "^VIX") or {}
        op = (bundle.get("options") or [None])[0] or {}
        bits = []
        if spy is not None:
            bits.append(f"SPY {spy:+.1f}%")
        if vix.get("last") is not None:
            bits.append(f"VIX {vix['last']:.1f}")
        if op.get("gex_sign"):
            bits.append(f"{op['gex_sign']} gamma")
        notify(f"OpenTrading Report — {now:%a %m-%d}", tilt, " · ".join(bits))

    if a.format == "json":
        print(json.dumps(bundle, indent=2))
        return
    md = build_markdown(bundle, now)
    print(md)
    if a.save:
        REPORTS.mkdir(parents=True, exist_ok=True)
        path = REPORTS / f"{now:%Y-%m-%d}.md"
        path.write_text(md + "\n", encoding="utf-8")
        print(f"\n[report] saved {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
