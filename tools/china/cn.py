#!/usr/bin/env python3
"""
cn.py — China A-share quotes (Shanghai / Shenzhen) via Eastmoney's no-key endpoint.

OpenTrading's A-share (沪深 / A股) data layer for users who hold mainland China names.
Uses the public Eastmoney push2 quote API — no API key, no login — with the same
stdlib + curl-fallback approach as the other OpenTrading tools (no `akshare` dependency).

    python3 cn.py 600519 002594        # Kweichow Moutai, BYD
    python3 cn.py shcomp 000300        # Shanghai Composite, CSI 300
    python3 cn.py hk00700 09988        # Hong Kong: Tencent, Alibaba (market 116)
    python3 cn.py sh000001 sz399001    # explicit exchange prefix
    python3 cn.py 600519 --format json

Code resolution (Eastmoney secid = "<market>.<code>", market 1=SH, 0=SZ):
  - aliases: shcomp/上证, csi300/沪深300, chinext/创业板, star50/科创50, sse50/上证50, szcomp
  - prefix:  sh000001 -> 1.000001 ; sz399001 -> 0.399001 ; or pass "1.600519" directly
  - bare 6/5/688 -> Shanghai ; 0/3 -> Shenzhen.
  NOTE: bare 000001 = Ping An Bank (SZ stock); the Shanghai Composite **index** is
        shcomp / sh000001 / zs000001 (matches https://quote.eastmoney.com/zs000001.html).

Educational only — not financial advice. Stdlib only; certifi or curl for TLS.
"""
from __future__ import annotations

import argparse
import json
import shutil
import ssl
import subprocess
import urllib.request

API = "https://push2.eastmoney.com/api/qt/stock/get"
UA = "Mozilla/5.0 (OpenTrading cn-cli)"
# f43 last · f44 high · f45 low · f46 open · f47 vol · f48 amount · f57 code · f58 name
# f59 decimals · f60 prevclose · f86 time · f168 turnover% · f169 change · f170 pct(x100)
FIELDS = "f43,f44,f45,f46,f47,f48,f57,f58,f59,f60,f86,f168,f169,f170"

ALIASES = {
    "SHCOMP": "1.000001", "上证": "1.000001", "上证指数": "1.000001", "ZS000001": "1.000001",
    "SZCOMP": "0.399001", "深证成指": "0.399001",
    "CSI300": "1.000300", "HS300": "1.000300", "沪深300": "1.000300",
    "CHINEXT": "0.399006", "创业板": "0.399006",
    "STAR50": "1.000688", "科创50": "1.000688",
    "SSE50": "1.000016", "上证50": "1.000016",
}


def to_secid(code: str) -> str:
    """Resolve a user code/alias to an Eastmoney secid (market.code). Markets: 1=SH, 0=SZ, 116=HK."""
    c = code.strip().upper()
    if c in ALIASES:
        return ALIASES[c]
    if "." in c and c.split(".")[0] in ("0", "1", "116", "100"):
        return c                       # already a secid, e.g. 1.600519 / 116.00700
    if c.startswith("HK"):
        return "116." + c[2:].zfill(5)
    if c.startswith("SH"):
        return "1." + c[2:]
    if c.startswith("SZ"):
        return "0." + c[2:]
    if c.isdigit():
        if len(c) == 6:
            if c[0] in "65" or c.startswith(("688", "11")):
                return "1." + c       # Shanghai: 6xx, 5xx funds, 688 STAR, 11x bonds
            if c[0] in "0123":
                return "0." + c       # Shenzhen: 00x, 30x ChiNext, 39x indices
        if len(c) in (4, 5):
            return "116." + c.zfill(5)  # Hong Kong (HKEX 5-digit codes, market 116)
    return "1." + c                    # fallback: Shanghai


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        curl = shutil.which("curl")
        if curl:
            out = subprocess.run([curl, "-sL", "--max-time", str(timeout), "-A", UA, url],
                                 capture_output=True, text=True, timeout=timeout + 5)
            if out.returncode == 0 and out.stdout:
                return out.stdout
        raise


def _num(v, dec):
    """Eastmoney returns ints scaled by 10**decimals; '-' / None means n/a."""
    if v in (None, "-", ""):
        return None
    try:
        return float(v) / (10 ** dec)
    except (TypeError, ValueError):
        return None


def _currency(secid: str) -> str:
    m = secid.split(".")[0]
    return {"116": "HKD", "100": "HKD", "105": "USD", "106": "USD", "107": "USD"}.get(m, "CNY")


def quote(code: str) -> dict:
    secid = to_secid(code)
    d = (json.loads(http_get(f"{API}?secid={secid}&fields={FIELDS}")).get("data") or {})
    if not d or d.get("f43") in (None, "-"):
        return {"input": code, "secid": secid, "error": "no data (check code/secid)"}
    dec = d.get("f59") or 2
    return {
        "input": code, "secid": secid, "code": d.get("f57"), "name": d.get("f58"),
        "last": _num(d.get("f43"), dec), "prev_close": _num(d.get("f60"), dec),
        "open": _num(d.get("f46"), dec), "high": _num(d.get("f44"), dec),
        "low": _num(d.get("f45"), dec), "change": _num(d.get("f169"), dec),
        "pct": _num(d.get("f170"), 2),     # pct is always scaled x100
        "currency": _currency(secid),
    }


def _fmt(v, spec):
    return format(v, spec) if isinstance(v, (int, float)) else "n/a"


def render_table(rows):
    L = ["A / HK SHARES — Eastmoney (delayed)", "-" * 60,
         f"  {'CODE':<8}{'NAME':<12}{'LAST':>10} {'CCY':<4}{'CHG%':>8}"]
    for r in rows:
        if r.get("error"):
            L.append(f"  {r['input']:<8}{r['error']}")
            continue
        pct = r.get("pct") or 0
        arrow = "▲" if pct > 0 else "▼" if pct < 0 else "·"
        L.append(f"  {str(r.get('code') or r['input']):<8}{(r.get('name') or '')[:11]:<12}"
                 f"{_fmt(r.get('last'), '>10.2f')} {(r.get('currency') or ''):<4}"
                 f"{_fmt(r.get('pct'), '>7.2f')}% {arrow}")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(prog="cn", description="China A-share quotes (Eastmoney, no key).")
    p.add_argument("codes", nargs="*", default=["shcomp"],
                   help="A/HK codes/aliases (default shcomp). e.g. 600519 002594 csi300 hk00700 09988")
    p.add_argument("--format", choices=["table", "json"], default="table")
    a = p.parse_args(argv)
    rows = []
    for c in (a.codes or ["shcomp"]):
        try:
            rows.append(quote(c))
        except Exception as exc:  # noqa: BLE001
            rows.append({"input": c, "error": f"{type(exc).__name__}: {exc}"})
    print(json.dumps(rows, indent=2, ensure_ascii=False) if a.format == "json"
          else render_table(rows))


if __name__ == "__main__":
    main()
