#!/usr/bin/env python3
"""
tfm.py — TimesFM range forecast, the OPT-IN power module (`ot forecast`).

Google's TimesFM is a pretrained time-series foundation model that emits
QUANTILE forecasts — a proper probabilistic range cone, learned from 100B
timepoints, zero-shot on any series. It is the heavyweight upgrade to
`ot quant`'s empirical cone.

This module is strictly OUTSIDE the keyless zero-dep core:
  - deps: `timesfm[torch]` (~2 GB torch stack) + a ~500 MB checkpoint from
    HuggingFace on first run — never installed by the default quick start
  - lives in its own venv: `bash install.sh --with-forecast` creates
    `.venv-forecast/` and `bin/ot forecast` prefers its python automatically
  - degrades cleanly: without the venv it prints the install hint (text) or
    `{"available": false, ...}` (json) — `ot web` hides the panel

    ot forecast NVDA                 # 5-session quantile cone
    ot forecast BTC-USD --horizon 10
    ot forecast NVDA --json          # consumed by ot debate / ot web

Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HINT = "TimesFM not installed — run `bash install.sh --with-forecast` (opt-in, ~2 GB; keyless core unaffected)"

# Reuse quant's keyless Yahoo fetch — one price path for both forecasters.
sys.path.insert(0, str(ROOT / "tools/quant"))
from quant import daily_closes  # noqa: E402


def have_tfm() -> bool:
    try:
        import timesfm  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


_MODEL = None


def _load_model(horizon: int):
    """Load TimesFM 2.5 once per process (torch backend, CPU-friendly)."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    import timesfm
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
        timesfm.TimesFM_2p5_200M_torch.DEFAULT_REPO_ID)
    model.compile(timesfm.ForecastConfig(
        max_context=1024, max_horizon=max(horizon, 64), normalize_inputs=True,
        use_continuous_quantile_head=True, force_flip_invariance=True,
        infer_is_positive=True, fix_quantile_crossing=True))
    _MODEL = model
    return _MODEL


def run(ticker: str, horizon: int, years: int) -> dict:
    import numpy as np
    closes = daily_closes(ticker, years)
    if len(closes) < 64:
        raise RuntimeError(f"only {len(closes)} sessions of history — need >= 64")
    last = closes[-1]
    model = _load_model(horizon)
    # 2.5 API: forecast(horizon, inputs) -> (point [n, h], quantiles [n, h, 10])
    # where quantiles[..., 0] is the mean and 1..9 are deciles q0.1..q0.9.
    point, quant = model.forecast(horizon=horizon, inputs=[np.asarray(closes[-1024:])])
    ph = [float(v) for v in point[0][:horizon]]
    qlast = quant[0][horizon - 1]

    def qcol(decile):  # decile 1..9 -> column 1..9 (column 0 = mean)
        return float(qlast[decile])

    cone = {"p10": round(qcol(1), 2), "p25": round((qcol(2) + qcol(3)) / 2, 2),
            "p50": round(qcol(5), 2), "p75": round((qcol(7) + qcol(8)) / 2, 2),
            "p90": round(qcol(9), 2)}
    return {"ticker": ticker.upper(), "available": True, "last": round(last, 2),
            "horizon_days": horizon, "point_path": [round(v, 2) for v in ph],
            "point_end": round(ph[-1], 2), "cone": cone,
            "model": "timesfm-2.5-200m",
            "note": "zero-shot foundation-model cone — one analyst input to ot debate, "
                    "not an oracle; equities are near the noise floor for any forecaster"}


def render_text(r: dict) -> str:
    c = r["cone"]
    return "\n".join([
        f"ot forecast — {r['ticker']}  (TimesFM, last ${r['last']}, horizon {r['horizon_days']} sessions)",
        "",
        f"  point path  {' -> '.join(str(v) for v in r['point_path'])}",
        f"  cone        P10 {c['p10']} · P25 {c['p25']} · P50 {c['p50']} · P75 {c['p75']} · P90 {c['p90']}",
        "",
        f"  {r['note']}",
        "  Educational only — not financial advice.",
    ])


def main(argv=None):
    p = argparse.ArgumentParser(prog="forecast", description="TimesFM quantile forecast (opt-in power module)")
    p.add_argument("ticker")
    p.add_argument("--horizon", type=int, default=5)
    p.add_argument("--years", type=int, default=2)
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)

    if not have_tfm():
        if a.format == "json":
            print(json.dumps({"available": False, "ticker": a.ticker.upper(), "hint": HINT}))
            return 0
        print(f"forecast: {HINT}", file=sys.stderr)
        return 1
    try:
        r = run(a.ticker, a.horizon, a.years)
    except Exception as e:  # noqa: BLE001
        if a.format == "json":
            print(json.dumps({"available": False, "ticker": a.ticker.upper(), "error": str(e)}))
        else:
            print(f"forecast: {e}", file=sys.stderr)
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.format == "json" else render_text(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
