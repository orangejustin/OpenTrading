#!/usr/bin/env python3
"""
quant.py — the keyless regression forecaster (`ot quant TICKER`).

One deterministic statistical "analyst" for the prediction desk: a pure-stdlib
logistic regression trained on THIS name's own daily history (no key, no
numpy, no model download) that emits

  - P(up over the next H sessions)  — walk-forward logistic on 6 features
    (5d/20d momentum, RSI14, MA10/MA20 spread, 20d realized vol, position
    in the 20d range), z-scored, L2-regularized, gradient descent
  - a range cone — empirical P10/P25/P50/P75/P90 of historical H-day moves
    scaled onto the last price (fat tails included, no normality assumed)
  - hit-rate of the same model over the trailing out-of-sample year

    ot quant NVDA                  # 5-session horizon (default)
    ot quant BTC-USD --horizon 10
    ot quant NVDA --json           # consumed by ot debate / ot web

This is an INPUT to the fusion layer (`ot debate`), not a signal by itself.
Stdlib + optional certifi, curl fallback. Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (OpenTrading quant-cli)"


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


def daily_closes(ticker: str, years: int = 2) -> list[float]:
    p1 = int(time.time()) - years * 365 * 86400
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}"
           f"?period1={p1}&period2={int(time.time()) + 86400}&interval=1d")
    r = json.loads(http_get(url))["chart"]["result"][0]
    return [c for c in r["indicators"]["quote"][0]["close"] if c is not None]


# --------------------------------------------------------------------------- #
# features
# --------------------------------------------------------------------------- #
def _rsi14(s: list[float], i: int) -> float:
    g = l = 0.0
    for j in range(i - 13, i + 1):
        d = s[j] - s[j - 1]
        g += max(d, 0.0)
        l += max(-d, 0.0)
    return 100.0 - 100.0 / (1.0 + (g / 14) / ((l / 14) or 1e-9))


def features_at(s: list[float], i: int) -> list[float] | None:
    """Feature vector at day i (needs >= 21 days of history behind it)."""
    if i < 21:
        return None
    win20 = s[i - 19:i + 1]
    ma10 = sum(s[i - 9:i + 1]) / 10
    ma20 = sum(win20) / 20
    rets = [s[j] / s[j - 1] - 1 for j in range(i - 19, i + 1)]
    vol20 = math.sqrt(sum(r * r for r in rets) / 20)
    hi20, lo20 = max(win20), min(win20)
    return [
        s[i] / s[i - 5] - 1,                                # 5d momentum
        s[i] / s[i - 20] - 1,                               # 20d momentum
        _rsi14(s, i) / 100 - 0.5,                           # RSI centered
        ma10 / ma20 - 1,                                    # MA spread
        vol20,                                              # realized vol
        (s[i] - lo20) / ((hi20 - lo20) or 1e-9) - 0.5,      # range position
    ]


FEATURE_NAMES = ["mom5", "mom20", "rsi", "ma_spread", "vol20", "range_pos"]


# --------------------------------------------------------------------------- #
# logistic regression — pure stdlib
# --------------------------------------------------------------------------- #
def _zscore_fit(X):
    n, k = len(X), len(X[0])
    mu = [sum(row[j] for row in X) / n for j in range(k)]
    sd = [math.sqrt(sum((row[j] - mu[j]) ** 2 for row in X) / n) or 1e-9 for j in range(k)]
    return mu, sd


def _zscore_apply(x, mu, sd):
    return [(x[j] - mu[j]) / sd[j] for j in range(len(x))]


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def train_logistic(X, y, epochs=300, lr=0.1, l2=0.01):
    """Batch gradient descent; X pre-z-scored. Returns (bias, weights)."""
    n, k = len(X), len(X[0])
    w, b = [0.0] * k, 0.0
    for _ in range(epochs):
        gw, gb = [0.0] * k, 0.0
        for row, yi in zip(X, y):
            e = _sigmoid(b + sum(w[j] * row[j] for j in range(k))) - yi
            gb += e
            for j in range(k):
                gw[j] += e * row[j]
        b -= lr * gb / n
        for j in range(k):
            w[j] -= lr * (gw[j] / n + l2 * w[j])
    return b, w


def run(ticker: str, horizon: int, years: int) -> dict:
    s = daily_closes(ticker, years)
    if len(s) < 120:
        raise RuntimeError(f"only {len(s)} sessions of history — need >= 120 for a meaningful fit")
    last = s[-1]

    # dataset: features at i -> did close rise over the next `horizon` sessions?
    rows, labels, fwd = [], [], []
    for i in range(21, len(s) - horizon):
        f = features_at(s, i)
        if f:
            rows.append(f)
            labels.append(1.0 if s[i + horizon] > s[i] else 0.0)
            fwd.append(s[i + horizon] / s[i] - 1)

    # walk-forward honesty check: train on the first 70%, score the last 30%
    cut = int(len(rows) * 0.7)
    mu, sd = _zscore_fit(rows[:cut])
    Xtr = [_zscore_apply(r, mu, sd) for r in rows[:cut]]
    b, w = train_logistic(Xtr, labels[:cut])
    hits = total = 0
    for r, yi in zip(rows[cut:], labels[cut:]):
        p = _sigmoid(b + sum(wj * xj for wj, xj in zip(w, _zscore_apply(r, mu, sd))))
        if p != 0.5:
            hits += 1 if (p > 0.5) == (yi == 1.0) else 0
            total += 1
    oos_hit = round(100 * hits / total, 1) if total else None

    # final model on ALL data -> today's probability
    mu, sd = _zscore_fit(rows)
    X = [_zscore_apply(r, mu, sd) for r in rows]
    b, w = train_logistic(X, labels)
    f_now = features_at(s, len(s) - 1)
    z_now = _zscore_apply(f_now, mu, sd)
    p_up = _sigmoid(b + sum(wj * xj for wj, xj in zip(w, z_now)))
    contrib = sorted(zip(FEATURE_NAMES, [round(wj * xj, 3) for wj, xj in zip(w, z_now)]),
                     key=lambda t: -abs(t[1]))

    # empirical cone: quantiles of ALL historical H-day moves, on the last price
    fs = sorted(fwd)

    def q(p):
        i = min(len(fs) - 1, max(0, int(p * (len(fs) - 1))))
        return round(last * (1 + fs[i]), 2)

    cone = {"p10": q(0.10), "p25": q(0.25), "p50": q(0.50), "p75": q(0.75), "p90": q(0.90)}

    base = round(100 * sum(labels) / len(labels), 1)  # how often it just went up anyway
    return {"ticker": ticker.upper(), "last": round(last, 2), "horizon_days": horizon,
            "p_up": round(p_up * 100, 1), "base_rate_up": base, "oos_hit_rate": oos_hit,
            "cone": cone, "top_drivers": [{"feature": k, "weight": v} for k, v in contrib[:3]],
            "n_train": len(rows), "years": years,
            "note": "empirical cone (no normality); logistic on this name's own history; "
                    "an input to ot debate, not a standalone signal"}


def render_text(r: dict) -> str:
    c = r["cone"]
    edge = r["p_up"] - r["base_rate_up"]
    drv = " · ".join(f"{d['feature']} {d['weight']:+}" for d in r["top_drivers"])
    return "\n".join([
        f"ot quant — {r['ticker']}  (last ${r['last']}, horizon {r['horizon_days']} sessions)",
        "",
        f"  P(up)      {r['p_up']}%   (base rate {r['base_rate_up']}% -> edge {edge:+.1f}pt)",
        f"  oos check  {r['oos_hit_rate']}% hit-rate on the held-out last 30% ({r['n_train']} samples, {r['years']}y)",
        f"  cone       P10 {c['p10']} · P25 {c['p25']} · P50 {c['p50']} · P75 {c['p75']} · P90 {c['p90']}",
        f"  drivers    {drv}",
        "",
        f"  {r['note']}",
        "  Educational only — not financial advice.",
    ])


def main(argv=None):
    p = argparse.ArgumentParser(prog="quant", description="keyless regression forecaster (P(up) + range cone)")
    p.add_argument("ticker")
    p.add_argument("--horizon", type=int, default=5, help="sessions ahead (default 5)")
    p.add_argument("--years", type=int, default=2, help="training history (default 2)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        r = run(a.ticker, a.horizon, a.years)
    except Exception as e:  # noqa: BLE001
        if a.format == "json":
            print(json.dumps({"error": str(e), "ticker": a.ticker.upper()}))
        else:
            print(f"quant: {e}", file=sys.stderr)
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.format == "json" else render_text(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
