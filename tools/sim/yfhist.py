#!/usr/bin/env python3
"""
yfhist.py — fetch + cache historical daily OHLCV from Yahoo (no API key).

Foundation for the live decision engine: pulls daily bars for a basket of
tickers + ^VIX / ^TNX (vol & rates regime), caches to /tmp so repeated calls
don't re-hit the network. Stdlib + curl fallback,
same approach as the other OpenTrading tools.

    python3 yfhist.py                 # fetch the default basket
    python3 yfhist.py QQQ NVDA ^VIX   # specific tickers

Educational only — not financial advice.
"""
import json, os, sys, ssl, shutil, subprocess, urllib.request, urllib.parse, datetime

CACHE = "/tmp/ot_sim_cache"
UA = "Mozilla/5.0 (OpenTrading sim)"
P1, P2 = 1751328000, 1767225600      # 2025-07-01 .. 2026-01-01 (history window for moving averages)

DEFAULT = ["QQQ", "SPY", "^VIX", "^TNX", "NVDA", "AMZN", "GOOG", "META", "TSLA",
           "BABA", "HOOD", "AVGO", "ORCL", "MSFT", "AMD", "INTC", "MARA", "MSTR",
           "AAPL", "CIFR", "MU", "CRWV"]


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20, context=_ctx()) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        curl = shutil.which("curl")
        if curl:
            out = subprocess.run([curl, "-sL", "--max-time", "20", "-A", UA, url],
                                 capture_output=True, text=True, timeout=25)
            if out.returncode == 0 and out.stdout:
                return out.stdout
        raise


def fetch(tix, p1=P1, p2=P2):
    sym = urllib.parse.quote(tix)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?period1={p1}&period2={p2}&interval=1d")
    d = json.loads(http(url))
    r = d["chart"]["result"][0]
    ts, q = r["timestamp"], r["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(ts):
        c = q["close"][i]
        if c is None:
            continue
        bars.append(dict(d=str(datetime.date.fromtimestamp(t)),
                         o=q["open"][i], h=q["high"][i], l=q["low"][i],
                         c=c, v=q["volume"][i]))
    return bars


def fetch_recent(tix, days=160):
    """Live: fetch the last `days` of daily bars up to now (for `ot decide`)."""
    import time
    now = int(time.time())
    return fetch(tix, now - days * 86400, now + 86400)


def path_for(tix):
    return os.path.join(CACHE, tix.replace("^", "_") + ".json")


def load(tix):
    with open(path_for(tix)) as f:
        return json.load(f)


def load_or_fetch(tix):
    """Return cached bars, fetching + caching on a cache miss (so the backtest
    can resolve any underlying the ledger references without a manual prefetch)."""
    try:
        return load(tix)
    except (FileNotFoundError, ValueError):
        os.makedirs(CACHE, exist_ok=True)
        bars = fetch(tix)
        with open(path_for(tix), "w") as f:
            json.dump(bars, f)
        return bars


def main(tickers):
    os.makedirs(CACHE, exist_ok=True)
    for t in tickers:
        try:
            bars = fetch(t)
            with open(path_for(t), "w") as f:
                json.dump(bars, f)
            print(f"  {t:<6} {len(bars):>3} bars  {bars[0]['d']}..{bars[-1]['d']}  last {bars[-1]['c']:.2f}")
        except Exception as e:
            print(f"  {t:<6} ERROR {type(e).__name__}: {e}")


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
