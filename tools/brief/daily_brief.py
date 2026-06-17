#!/usr/bin/env python3
"""
daily_brief.py — OpenTrading daily pre-market brief + macOS notification.

Shells out to the project CLIs (fj.py, macro.py) plus a no-key BTC quote,
synthesizes a risk-on/off regime + a portfolio lean, writes a markdown brief to
data/briefs/YYYY-MM-DD.md, and fires a macOS Notification Center banner.

Run manually any time:   python3 tools/brief/daily_brief.py
Scheduled via launchd:   see tools/brief/README.md

Stdlib only (Python 3.9+). Educational only — NOT financial advice.
"""
from __future__ import annotations

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
FJ = ROOT / "tools" / "financialjuice" / "fj.py"
MACRO = ROOT / "tools" / "macro" / "macro.py"
BRIEFS = ROOT / "data" / "briefs"

RISK_ON_KW = ["de-escalat", "ceasefire", "peace deal", "dovish", "rate cut", "cuts rates",
              "stimulus", "cooler", "cools", "softer", "weak data", "beats", "rally",
              "deal reached", "truce", "easing", "reopen"]
RISK_OFF_KW = ["escalat", "attack", "sanction", "hawkish", "hotter", "hot inflation",
               "strong jobs", "selloff", "plunge", "tariff", "missile", "default",
               "credit stress", "war", "strike", "invasion", "shutdown"]

SLEEVES = {
    "RISK-ON": {
        "ETFs (SPY/QQQ)": "long / call bias — favor dips that hold the prior close",
        "3x (TQQQ/SOXL)": "trend-confirm ADD only, intraday, half size (decay risk)",
        "BTC": "momentum long while above today's open; add on a 24h-high break",
        "Options": "defined-risk debit call spreads > naked calls; sell put spreads if IV is decent",
    },
    "RISK-OFF": {
        "ETFs (SPY/QQQ)": "reduce / hedge — put bias or raise cash",
        "3x (TQQQ/SOXL)": "avoid longs; SQQQ/SOXS only with confirmation, intraday",
        "BTC": "defensive — long only above reclaimed support, else stand aside",
        "Options": "long puts / put spreads for defined risk; don't sell naked premium into stress",
    },
    "MIXED": {
        "ETFs (SPY/QQQ)": "no directional edge — stay small, trade levels not bias",
        "3x (TQQQ/SOXL)": "skip — chop destroys leveraged products",
        "BTC": "range-trade the 24h hi/lo, no breakout chase",
        "Options": "harvest theta with defined-risk spreads if IV elevated; otherwise wait",
    },
}


def import_fj():
    """Best-effort import of fj.py so we can reuse its ticker matching."""
    try:
        sys.path.insert(0, str(FJ.parent))
        import fj  # noqa: E402
        return fj
    except Exception:  # noqa: BLE001
        return None


def load_watchlist():
    """Read the user's positions from watchlist.json (gitignored) if present."""
    for rel in ("watchlist.json", "data/watchlist.json"):
        p = ROOT / rel
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8")).get("positions", [])
            except Exception:  # noqa: BLE001
                return []
    return []


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def run_json(args, timeout=60):
    try:
        out = subprocess.run([str(PY), *map(str, args)], capture_output=True,
                             text=True, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
    if out.returncode != 0:
        return None, (out.stderr or "nonzero exit").strip().splitlines()[-1:][0] if out.stderr else "nonzero exit"
    try:
        return json.loads(out.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"bad json: {exc}"


def curl(url, timeout=12):
    out = subprocess.run(["curl", "-s", "--max-time", str(timeout), "-A", "ot-brief", url],
                         capture_output=True, text=True, timeout=timeout + 5)
    return out.stdout


def fetch_btc():
    try:
        spot = json.loads(curl("https://api.coinbase.com/v2/prices/BTC-USD/spot"))
        stats = json.loads(curl("https://api.exchange.coinbase.com/products/BTC-USD/stats"))
        px, op = float(spot["data"]["amount"]), float(stats["open"])
        return {"px": px, "chg": (px - op) / op * 100 if op else 0.0,
                "hi": float(stats["high"]), "lo": float(stats["low"])}
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Synthesis
# --------------------------------------------------------------------------- #
def news_tone(items):
    on = off = 0
    for it in items:
        h = it.get("headline", "").lower()
        on += sum(1 for k in RISK_ON_KW if k in h)
        off += sum(1 for k in RISK_OFF_KW if k in h)
    if on > off + 1:
        return "RISK-ON", on, off
    if off > on + 1:
        return "RISK-OFF", on, off
    return "MIXED", on, off


def get_ind(macro, label):
    for i in (macro or {}).get("auto_indicators", []):
        if i.get("label") == label:
            return i
    return None


def synthesize(macro, tone):
    score = (macro or {}).get("auto_score")
    macro_on, macro_off = (score is not None and score >= 2), (score is not None and score <= -2)
    if macro_on and tone != "RISK-OFF":
        return "RISK-ON"
    if macro_off and tone != "RISK-ON":
        return "RISK-OFF"
    if tone in ("RISK-ON", "RISK-OFF") and not (macro_on or macro_off):
        return tone
    return "MIXED"


def btc_position(btc):
    if not btc:
        return ""
    span = btc["hi"] - btc["lo"]
    pct = (btc["px"] - btc["lo"]) / span * 100 if span else 50
    where = "upper" if pct >= 66 else "lower" if pct <= 33 else "mid"
    return f"{where} of 24h range"


# --------------------------------------------------------------------------- #
# Render + notify
# --------------------------------------------------------------------------- #
def render_positions(positions, items, btc, fj_mod):
    if not positions:
        return []
    L = ["## Your positions", ""]
    for pos in positions:
        tk = str(pos.get("ticker", "")).upper()
        if not tk:
            continue
        driver = pos.get("driver", "")
        if fj_mod:
            hits = [it for it in items if fj_mod.ticker_matches(it.get("headline", ""), tk)]
        else:
            hits = [it for it in items if tk.lower() in it.get("headline", "").lower()]
        extra = ""
        if btc and "btc" in driver.lower():
            extra = f" · BTC {btc['chg']:+.1f}% ({'tailwind' if btc['chg'] >= 0 else 'headwind'})"
        L.append(f"- **{tk}** · _{driver}_{extra} — {len(hits)} headline(s)")
        for it in hits[:2]:
            L.append(f"   - `{it.get('time_et','--:--')}` {it.get('headline','')}")
        if pos.get("note"):
            L.append(f"   - ↳ {pos['note']}")
    L.append("")
    return L


def build_markdown(now_et, macro, mac_err, items, tone, on, off, btc, regime, positions, fj_mod):
    score = (macro or {}).get("auto_score")
    y10 = get_ind(macro, "10Y Yield")
    L = [f"# OpenTrading Daily Brief — {now_et:%Y-%m-%d} ({now_et:%H:%M} ET)", ""]

    score_str = f"{score:+d}" if score is not None else "n/a"
    L += [f"## Regime: **{regime}**  ·  macro {score_str}  ·  tape {tone}", ""]
    L += [f"> Auto-synthesis from macro tilt + news tone. Verify at the cash open. "
          f"Key swing level: 10Y yield (bearish >4.50%). "
          f"Reminder: SPY/QQQ/3x/BTC are one correlated risk-on bet — cap aggregate heat.", ""]

    # Macro
    L += ["## Macro (auto, no-key)", ""]
    if macro:
        L += ["| Indicator | Value | Tilt |", "|---|---|---|"]
        for i in macro.get("auto_indicators", []):
            s = i.get("score")
            tilt = "🟢 bull" if s == 1 else "🔴 bear" if s == -1 else "⚪ neut"
            L.append(f"| {i['label']} | {i['value']} | {tilt} |")
        L += ["", f"Auto score **{score_str}** → {(macro or {}).get('bias','')}",
              "Manual to-fold: Fed-cut odds (Polymarket), PCE nowcast (Cleveland Fed)."]
    else:
        L.append(f"_macro unavailable: {mac_err}_")
    L.append("")

    # BTC
    L += ["## Bitcoin", ""]
    if btc:
        L.append(f"**${btc['px']:,.0f}**  ({btc['chg']:+.1f}% 24h)  ·  "
                 f"range ${btc['lo']:,.0f}–${btc['hi']:,.0f}  ·  {btc_position(btc)}")
    else:
        L.append("_BTC quote unavailable_")
    L.append("")

    # Positions (only if watchlist.json present)
    L += render_positions(positions, items, btc, fj_mod)

    # News
    L += [f"## News tape — last 12h ({len(items)} headlines, tone {tone}: +{on}/-{off})", ""]
    if items:
        for it in items[:12]:
            L.append(f"- `{it.get('time_et','--:--')}` **{it.get('category','')}** — {it.get('headline','')}")
    else:
        L.append("_no headlines (quiet tape — trade technicals, reduce conviction)_")
    L.append("")

    # Lean
    L += ["## Portfolio lean (educational — verify before acting)", ""]
    for sleeve, txt in SLEEVES[regime].items():
        L.append(f"- **{sleeve}**: {txt}")
    if y10:
        L.append(f"- **Key level**: 10Y at {y10['value']} (bear >4.50%). ")
    L += ["", "---", "_Auto-generated by OpenTrading · educational only, not financial advice._", ""]
    return "\n".join(L)


def notify(title, subtitle, msg):
    def esc(s):
        return s.replace("\\", "").replace('"', "'")
    script = (f'display notification "{esc(msg)}" with title "{esc(title)}" '
              f'subtitle "{esc(subtitle)}" sound name "Submarine"')
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
        return True
    except Exception:  # noqa: BLE001
        return False


def main():
    now_et = datetime.now(ET) if ET else datetime.now()
    macro, mac_err = run_json([MACRO, "--format", "json"])
    news, _ = run_json([FJ, "fetch", "--minutes", "720", "--limit", "18", "--format", "json"])
    items = (news or {}).get("items", [])
    btc = fetch_btc()
    fj_mod = import_fj()
    positions = load_watchlist()

    tone, on, off = news_tone(items)
    regime = synthesize(macro, tone)
    md = build_markdown(now_et, macro, mac_err, items, tone, on, off, btc, regime,
                        positions, fj_mod)

    BRIEFS.mkdir(parents=True, exist_ok=True)
    path = BRIEFS / f"{now_et:%Y-%m-%d}.md"
    path.write_text(md + "\n", encoding="utf-8")

    score = (macro or {}).get("auto_score")
    y10 = get_ind(macro, "10Y Yield")
    title = f"OpenTrading — {now_et:%a %m-%d}"
    subtitle = f"{regime}" + (f" · macro {score:+d}" if score is not None else "")
    bits = []
    if btc:
        bits.append(f"BTC ${btc['px']:,.0f} ({btc['chg']:+.1f}%)")
    if y10:
        bits.append(f"10Y {y10['value']}")
    bits.append(f"tape {tone}")
    msg = " · ".join(bits)
    sent = notify(title, subtitle, msg)

    print(f"[brief] {regime} | {subtitle} | {msg}")
    print(f"[brief] wrote {path}")
    print(f"[brief] notification: {'sent' if sent else 'failed'}")


if __name__ == "__main__":
    main()
