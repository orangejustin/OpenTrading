#!/usr/bin/env python3
"""
opt.py — options positioning: put/call, dealer gamma exposure (GEX), gamma walls.

Uses CBOE's free delayed options chain (greeks + OI + volume, no API key) to
compute a "smart money" options signal:

  - Put/Call ratios (open interest and volume)
  - Net dealer Gamma Exposure (GEX), in $ per 1% move
  - Gamma walls: the call strike (resistance/pin) and put strike (support)

GEX sign (naive dealer convention: dealers long calls, short puts):
  positive GEX -> dealers long gamma -> vol-SUPPRESSING, mean-reverting, pins to walls
  negative GEX -> dealers short gamma -> vol-AMPLIFYING, trends/squeezes accelerate

    python3 opt.py SPY
    python3 opt.py SPY QQQ --dte 7
    python3 opt.py SPY --format json

Heuristic — educational, not financial advice. Stdlib only; certifi or curl for TLS.
"""
from __future__ import annotations

import argparse
import json
import shutil
import ssl
import subprocess
import urllib.request
from datetime import date, datetime

URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json"
UA = "Mozilla/5.0 (OpenTrading opt-cli)"
CONTRACT = 100  # shares per option


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        curl = shutil.which("curl")
        if curl:
            out = subprocess.run([curl, "-s", "--max-time", str(timeout), "-A", UA, url],
                                 capture_output=True, text=True, timeout=timeout + 5)
            if out.returncode == 0 and out.stdout:
                return out.stdout
        raise


def parse_occ(sym):
    """'SPY260615C00500000' -> (root, 'YYYY-MM-DD', 'C'|'P', strike)."""
    strike = int(sym[-8:]) / 1000.0
    cp = sym[-9]
    exp = f"20{sym[-15:-13]}-{sym[-13:-11]}-{sym[-11:-9]}"
    return sym[:-15], exp, cp, strike


def analyze(symbol, dte_max, today):
    d = json.loads(http_get(URL.format(sym=symbol.upper())))
    data = d.get("data", {})
    spot = data.get("current_price") or data.get("close")
    rows = data.get("options", [])
    call_oi = put_oi = call_vol = put_vol = 0
    net_gamma = 0.0                      # signed Σ gamma*OI (calls +, puts -)
    by_strike: dict[float, float] = {}
    for o in rows:
        try:
            _, exp, cp, strike = parse_occ(o["option"])
            dte = (datetime.strptime(exp, "%Y-%m-%d").date() - today).days
        except Exception:
            continue
        if dte < 0 or (dte_max is not None and dte > dte_max):
            continue
        oi = o.get("open_interest") or 0
        vol = o.get("volume") or 0
        gamma = o.get("gamma") or 0.0
        g = gamma * oi * (1 if cp == "C" else -1)
        net_gamma += g
        by_strike[strike] = by_strike.get(strike, 0.0) + g
        if cp == "C":
            call_oi += oi; call_vol += vol
        else:
            put_oi += oi; put_vol += vol
    # $ GEX per 1% move = Σ(signed gamma*OI) * 100 * spot^2 * 0.01
    dollar_gex = net_gamma * CONTRACT * spot * spot * 0.01 if spot else None
    call_wall = max(by_strike.items(), key=lambda kv: kv[1], default=(None, 0))[0]
    put_wall = min(by_strike.items(), key=lambda kv: kv[1], default=(None, 0))[0]
    return {
        "symbol": symbol.upper(), "spot": spot, "dte_max": dte_max,
        "pc_oi": (put_oi / call_oi) if call_oi else None,
        "pc_vol": (put_vol / call_vol) if call_vol else None,
        "net_gex_usd_per_1pct": dollar_gex,
        "gex_sign": ("positive" if (dollar_gex or 0) > 0 else "negative" if (dollar_gex or 0) < 0 else "flat"),
        "call_wall": call_wall, "put_wall": put_wall,
        "call_oi": call_oi, "put_oi": put_oi,
    }


def pc_read(pc):
    if pc is None:
        return ""
    if pc >= 1.2:
        return "put-heavy (hedged/bearish; contrarian-bull if extreme)"
    if pc <= 0.7:
        return "call-heavy (complacent/bullish)"
    return "balanced"


def gex_read(sign):
    return {"positive": "vol-suppressing, mean-reverting, pins to gamma walls",
            "negative": "vol-amplifying — moves/squeezes accelerate",
            "flat": "neutral"}.get(sign, "")


def _fmt(v, spec):
    """Format a number, or 'n/a' if it's missing — so one thin ticker (no chain,
    null OI/walls) degrades gracefully instead of crashing the whole batch."""
    return format(v, spec) if isinstance(v, (int, float)) and not isinstance(v, bool) else "n/a"


def render_table(results):
    L = ["=" * 64, "OPTIONS POSITIONING — CBOE delayed chain (dealer GEX heuristic)", "=" * 64]
    for r in results:
        if r.get("error"):
            L.append(f"  {r['symbol']}: {r['error']}")
            continue
        gex = r.get("net_gex_usd_per_1pct")
        gx = f"${gex/1e9:+.2f}bn/1%" if isinstance(gex, (int, float)) else "n/a"
        L.append(f"  {r['symbol']}  spot {_fmt(r.get('spot'), '.2f')}  (DTE<= {r.get('dte_max','?')})")
        L.append(f"     Net GEX : {gx}  ->  {r['gex_sign']} gamma ({gex_read(r['gex_sign'])})")
        L.append(f"     P/C OI  : {_fmt(r.get('pc_oi'), '.2f')}   P/C vol: {_fmt(r.get('pc_vol'), '.2f')}   ->  {pc_read(r.get('pc_oi'))}")
        L.append(f"     Walls   : call/resistance {_fmt(r.get('call_wall'), '.0f')}  ·  put/support {_fmt(r.get('put_wall'), '.0f')}")
    L.append("=" * 64)
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(prog="opt", description="Options positioning (CBOE, no key).")
    p.add_argument("symbols", nargs="*", default=["SPY"], help="Tickers (default SPY).")
    p.add_argument("--dte", type=int, default=7, help="Max days-to-expiry to include (default 7; 0=0DTE).")
    p.add_argument("--format", choices=["table", "json"], default="table")
    a = p.parse_args(argv)
    today = date.today()
    results = []
    for s in (a.symbols or ["SPY"]):
        try:
            results.append(analyze(s, a.dte, today))
        except Exception as exc:  # noqa: BLE001
            results.append({"symbol": s.upper(), "error": f"{type(exc).__name__}: {exc}"})
    print(json.dumps(results, indent=2) if a.format == "json" else render_table(results))


if __name__ == "__main__":
    main()
