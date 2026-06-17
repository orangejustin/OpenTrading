#!/usr/bin/env python3
"""
sm.py — smart-money / positioning & sentiment read (no API key).

Sources:
  CNN equity Fear & Greed (+ 7 sub-signals: put/call, VIX, momentum, breadth,
    price strength, junk-bond demand, safe-haven demand)
  Crypto Fear & Greed (alternative.me)
  BTC perpetual funding (OKX)

Sentiment is read **contrarian**: extreme fear = washed-out = contrarian-bullish;
extreme greed = crowded = contrarian-bearish. Funding shows perp crowding.

    python3 sm.py
    python3 sm.py --format json

Stdlib only; uses certifi if present, else curl. Educational, not advice.
"""
from __future__ import annotations

import argparse
import json
import shutil
import ssl
import subprocess
import urllib.request

CNN = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
CNN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
    "Origin": "https://www.cnn.com",
}
CRYPTO_FNG = "https://api.alternative.me/fng/?limit=1"
OKX_FUNDING = "https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USD-SWAP"

COMPONENTS = [
    ("put_call_options", "put/call"),
    ("market_volatility_vix", "volatility(VIX)"),
    ("market_momentum_sp500", "momentum"),
    ("stock_price_strength", "strength"),
    ("stock_price_breadth", "breadth"),
    ("junk_bond_demand", "junk-bond"),
    ("safe_haven_demand", "safe-haven"),
]


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url, headers=None, timeout=15):
    headers = headers or {"User-Agent": "Mozilla/5.0 (OpenTrading sm)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        curl = shutil.which("curl")
        if curl:
            args = [curl, "-s", "--max-time", str(timeout)]
            for k, v in headers.items():
                args += ["-H", f"{k}: {v}"]
            out = subprocess.run(args + [url], capture_output=True, text=True, timeout=timeout + 5)
            if out.returncode == 0 and out.stdout:
                return out.stdout
        raise


def _safe(fn):
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def contrarian(score):
    """score 0-100 (0 = extreme fear, 100 = extreme greed) -> contrarian read."""
    if score is None:
        return "n/a"
    if score <= 25:
        return "contrarian BULLISH (washed out)"
    if score >= 75:
        return "contrarian BEARISH (crowded)"
    if score <= 44:
        return "fear (mild contrarian bull)"
    if score >= 56:
        return "greed (mild contrarian bear)"
    return "neutral"


def get_cnn():
    d = json.loads(http_get(CNN, headers=CNN_HEADERS))
    fg = d.get("fear_and_greed", {})
    out = {
        "score": fg.get("score"), "rating": fg.get("rating"),
        "week_ago": fg.get("previous_1_week"), "month_ago": fg.get("previous_1_month"),
        "components": {},
    }
    for key, label in COMPONENTS:
        comp = d.get(key) or {}
        out["components"][label] = {"score": comp.get("score"), "rating": comp.get("rating")}
    return out


def get_crypto_fng():
    row = json.loads(http_get(CRYPTO_FNG))["data"][0]
    return {"value": int(row["value"]), "rating": row["value_classification"]}


def get_funding():
    row = json.loads(http_get(OKX_FUNDING))["data"][0]
    rate = float(row["fundingRate"])
    if rate > 0.0005:
        read = "crowded LONGS (caution / contrarian-bear)"
    elif rate < -0.0001:
        read = "shorts paying (squeeze setup / contrarian-bull)"
    else:
        read = "balanced"
    return {"rate_8h_pct": rate * 100, "annualized_pct": rate * 3 * 365 * 100, "read": read}


def collect():
    cnn, e1 = _safe(get_cnn)
    crypto, e2 = _safe(get_crypto_fng)
    funding, e3 = _safe(get_funding)
    return {"equity_fng": cnn, "crypto_fng": crypto, "btc_funding": funding,
            "errors": [e for e in (e1, e2, e3) if e]}


def render_table(data):
    L = ["=" * 60, "SMART MONEY / POSITIONING (contrarian-read)", "=" * 60]
    eq = data["equity_fng"]
    if eq:
        sc = eq["score"]
        L.append(f"  Equity F&G : {sc:>4.0f} ({eq['rating']})  ->  {contrarian(sc)}")
        L.append(f"               trend: 1w {eq['week_ago']:.0f} · 1m {eq['month_ago']:.0f}")
        for label in (lbl for _, lbl in COMPONENTS):
            c = eq["components"].get(label, {})
            if c.get("score") is not None:
                L.append(f"                 - {label:<15} {c['score']:>4.0f}  {c.get('rating','')}")
    else:
        L.append("  Equity F&G : unavailable")
    cf = data["crypto_fng"]
    if cf:
        L.append(f"  Crypto F&G : {cf['value']:>4} ({cf['rating']})  ->  {contrarian(cf['value'])}")
    fn = data["btc_funding"]
    if fn:
        L.append(f"  BTC funding: {fn['rate_8h_pct']:+.4f}%/8h (~{fn['annualized_pct']:+.1f}%/yr)  ->  {fn['read']}")
    if data["errors"]:
        L.append("-" * 60)
        for e in data["errors"]:
            L.append(f"  ! {e}")
    L.append("=" * 60)
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(prog="sm", description="Smart-money / sentiment read (no key).")
    p.add_argument("--format", choices=["table", "json"], default="table")
    a = p.parse_args(argv)
    data = collect()
    if not any((data["equity_fng"], data["crypto_fng"], data["btc_funding"])):
        raise SystemExit("[sm] all sources failed:\n  " + "\n  ".join(data["errors"]))
    print(json.dumps(data, indent=2) if a.format == "json" else render_table(data))


if __name__ == "__main__":
    main()
