#!/usr/bin/env python3
"""
research.py — no-key deep-research data pack (`ot research TICKER --market A|HK|US`).

Gathers the inputs for a single-stock deep-research thesis, NO API key / login:
  技术面 technical : trend + BIAS(6/12/24) + 量比 (volume ratio)        [Yahoo, all markets]
  估值 valuation   : PE(TTM) / PB / 市值                                  [Eastmoney push2, A+HK]
  业绩 financials  : EPS · 营收 · 净利 · 毛利 · ROE · YoY                 [Eastmoney F10, A+HK]
  筹码 chips       : 股东户数 trend -> 集中度 (big-money accumulation)    [Eastmoney, A-share only]
  人气 attention   : 东财人气榜 rank (A-share)                            [Eastmoney]
                    (proper 主力净流入 via the fflow endpoint is a follow-up)

Eastmoney endpoints are reverse-engineered (same ones akshare/cn.py use) — no key.
A/HK is the rich path; US covers technicals (deep US fundamentals = SEC EDGAR, a later
phase). The COGNITION (two-track hold/trade thesis, bull-vs-bear, grade) lives in the
deep-research skill; this tool just produces the facts. Stdlib + curl fallback.

Educational only — not financial advice.
"""
from __future__ import annotations
import argparse, json, shutil, ssl, subprocess, sys, time, urllib.parse, urllib.request

UA = "Mozilla/5.0 (OpenTrading research-cli)"
EM_HOSTS = ["https://push2delay.eastmoney.com", "https://push2.eastmoney.com"]  # rotate (push2delay first)
DC = "https://datacenter-web.eastmoney.com/api/data/v1/get"
DC_HK = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
RANK = "https://emappdata.eastmoney.com/stockrank/getCurrentList"


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


def http_post(url, body, timeout=15):
    curl = shutil.which("curl")
    if not curl:
        return None
    try:
        out = subprocess.run([curl, "-sL", "--max-time", str(timeout), "-A", UA,
                              "-H", "Content-Type: application/json", "-d", json.dumps(body), url],
                             capture_output=True, text=True, timeout=timeout + 5)
        return out.stdout if out.returncode == 0 else None
    except Exception:
        return None


def to_secid(code, market):
    code = str(code).strip().upper()
    if "." in code and code.split(".")[0] in ("0", "1", "116"):
        return code
    digits = "".join(ch for ch in code if ch.isdigit())
    if market == "HK":
        return "116." + digits.zfill(5)
    return ("1." if digits.startswith("6") else "0.") + digits   # A: SH 6xx/688, else SZ


def to_yahoo(code, market):
    code = str(code).strip().upper()
    digits = "".join(ch for ch in code if ch.isdigit())
    if market == "HK":
        return f"{int(digits):04d}.HK"
    if market == "A":
        return digits + (".SS" if digits.startswith("6") else ".SZ")
    return code                                                   # US pass-through


def secucode(code, market):
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if market == "HK":
        return digits.zfill(5) + ".HK"
    return digits + (".SH" if digits.startswith("6") else ".SZ")


def _scale(d, k, by=1.0):
    v = d.get(k)
    if v in (None, "-", ""):
        return None
    try:
        return round(float(v) / by, 2)
    except (TypeError, ValueError):
        return None


def _rnd(x, n=2):
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return x


def _big(v):
    """Format a raw CNY/HKD figure into 亿 / 万亿."""
    if v in (None, "-", "", 0):
        return "n/a"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "n/a"
    if abs(v) >= 1e12:
        return f"{v / 1e12:.2f}万亿"
    if abs(v) >= 1e8:
        return f"{v / 1e8:.1f}亿"
    return f"{v:.0f}"


def yahoo_tech(ysym):
    """Trend + BIAS(6/12/24) + 量比 from Yahoo daily closes (no key, all markets)."""
    now = int(time.time())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ysym)}"
           f"?period1={now - 70 * 86400}&period2={now + 86400}&interval=1d")
    try:
        r = json.loads(http_get(url))["chart"]["result"][0]
        q = r["indicators"]["quote"][0]
        closes = [c for c in q["close"] if c is not None]
        vols = [v for v in q.get("volume", []) if v is not None]
    except Exception:
        return {"error": "no Yahoo data"}
    if len(closes) < 25:
        return {"error": "not enough history"}
    px = closes[-1]
    sma = lambda n: sum(closes[-n:]) / n
    bias = lambda n: round((px / sma(n) - 1) * 100, 2)
    vr = round(vols[-1] / (sum(vols[-6:-1]) / 5), 2) if len(vols) >= 6 and sum(vols[-6:-1]) else None
    return {"price": round(px, 2), "trend": "UP" if px > sma(20) else "DOWN",
            "bias6": bias(6), "bias12": bias(12), "bias24": bias(24), "vol_ratio": vr}


def em_quote(secid):
    """Valuation (PE/PB/mktcap) + 主力净流入 from Eastmoney push2 (host-rotated)."""
    for host in EM_HOSTS:
        try:
            url = f"{host}/api/qt/stock/get?secid={secid}&fields=f57,f58,f116,f162,f167"
            d = json.loads(http_get(url)).get("data") or {}
            if d.get("f58"):
                pe = _scale(d, "f162", 100)
                return {"name": d.get("f58"), "pe_ttm": pe if pe else None,
                        "pb": _scale(d, "f167", 100), "mktcap": d.get("f116")}
        except Exception:
            continue
    return {}


def em_financials(code, market):
    """业绩/财务 main indicators from Eastmoney F10 (RPT_* clean floats, no scaling)."""
    sc = urllib.parse.quote(f'"{secucode(code, market)}"')
    try:
        if market == "HK":
            url = (f"{DC_HK}?reportName=RPT_HKF10_FN_MAININDICATOR&columns=REPORT_DATE,BASIC_EPS,"
                   f"OPERATE_INCOME,OPERATE_INCOME_YOY,HOLDER_PROFIT,HOLDER_PROFIT_YOY,"
                   f"GROSS_PROFIT_RATIO,ROE_AVG&filter=(SECUCODE={sc})&pageSize=5&"
                   f"sortColumns=REPORT_DATE&sortTypes=-1&source=F10&client=PC")
            keys = ("REPORT_DATE", "BASIC_EPS", "OPERATE_INCOME", "OPERATE_INCOME_YOY",
                    "HOLDER_PROFIT", "HOLDER_PROFIT_YOY", "GROSS_PROFIT_RATIO", "ROE_AVG")
        else:
            url = (f"{DC}?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=REPORT_DATE,EPSJB,"
                   f"TOTALOPERATEREVE,TOTALOPERATEREVETZ,PARENTNETPROFIT,PARENTNETPROFITTZ,"
                   f"XSMLL,ROEJQ&filter=(SECUCODE={sc})&pageSize=5&sortColumns=REPORT_DATE&"
                   f"sortTypes=-1&source=HSF10&client=PC")
            keys = ("REPORT_DATE", "EPSJB", "TOTALOPERATEREVE", "TOTALOPERATEREVETZ",
                    "PARENTNETPROFIT", "PARENTNETPROFITTZ", "XSMLL", "ROEJQ")
        rows = ((json.loads(http_get(url)).get("result") or {}).get("data")) or []
        if not rows:
            return {}
        r = rows[0]
        return {"as_of": (r.get(keys[0]) or "")[:10], "eps": _rnd(r.get(keys[1])),
                "revenue": r.get(keys[2]), "rev_yoy": _rnd(r.get(keys[3])),
                "net_profit": r.get(keys[4]), "np_yoy": _rnd(r.get(keys[5])),
                "gross_margin": _rnd(r.get(keys[6])), "roe": _rnd(r.get(keys[7]))}
    except Exception:
        return {}


def em_holders(code):
    """股东户数 series -> 筹码集中度 (A-share only; falling holders = accumulation)."""
    digits = urllib.parse.quote(f'"{"".join(c for c in str(code) if c.isdigit())}"')
    try:
        url = (f"{DC}?reportName=RPT_HOLDERNUMLATEST&columns=END_DATE,HOLDER_NUM,HOLDER_NUM_RATIO,"
               f"AVG_HOLD_NUM&filter=(SECURITY_CODE={digits})&pageSize=5&sortColumns=END_DATE&"
               f"sortTypes=-1&source=WEB&client=WEB")
        rows = ((json.loads(http_get(url)).get("result") or {}).get("data")) or []
        if not rows:
            return {}
        nums = [x.get("HOLDER_NUM") for x in rows if x.get("HOLDER_NUM")]
        trend = ("concentrating (chips tightening — accumulation)" if len(nums) >= 2 and nums[0] < nums[-1]
                 else "dispersing (chips loosening)" if len(nums) >= 2 and nums[0] > nums[-1] else "flat")
        return {"as_of": (rows[0].get("END_DATE") or "")[:10], "holder_num": rows[0].get("HOLDER_NUM"),
                "qoq_pct": _rnd(rows[0].get("HOLDER_NUM_RATIO")), "avg_hold": _rnd(rows[0].get("AVG_HOLD_NUM"), 0),
                "trend": trend}
    except Exception:
        return {}


def em_popularity(code, secid):
    """东方财富人气榜 rank (retail attention; A-share only)."""
    mkt = secid.split(".")[0]
    prefix = {"1": "SH", "0": "SZ"}.get(mkt)
    if not prefix:
        return {}
    digits = "".join(c for c in str(code) if c.isdigit())
    raw = http_post(RANK, {"appId": "appId01", "globalId": "786e4c21743646e8", "marketType": "",
                           "srcSecurityCode": prefix + digits})
    try:
        data = (json.loads(raw).get("data") or []) if raw else []
        if data:
            return {"rank": data[-1].get("rank")}
    except Exception:
        pass
    return {}


def research(ticker, market):
    market = (market or "US").upper()
    out = {"ticker": ticker.upper(), "market": market, "technical": yahoo_tech(to_yahoo(ticker, market))}
    if market in ("A", "HK"):
        secid = to_secid(ticker, market)
        q = em_quote(secid)
        out["name"] = q.get("name")
        out["valuation"] = {"pe_ttm": q.get("pe_ttm"), "pb": q.get("pb"), "mktcap": q.get("mktcap")}
        out["financials"] = em_financials(ticker, market)
        if market == "A":
            out["chips"] = em_holders(ticker)
            out["popularity"] = em_popularity(ticker, secid)
    else:
        out["fundamentals_note"] = "US deep fundamentals via SEC EDGAR — later phase (technicals only here)."
    return out


def render(r):
    name = f" · {r['name']}" if r.get("name") else ""
    L = [f"ot research {r['ticker']}  ({r['market']}{name})"]
    t = r.get("technical", {})
    if "error" not in t:
        L.append(f"  技术面: {t.get('trend')} · {t.get('price')} · "
                 f"BIAS 6/12/24 {t.get('bias6')}/{t.get('bias12')}/{t.get('bias24')}% · 量比 {t.get('vol_ratio')}")
    else:
        L.append(f"  技术面: {t.get('error')}")
    v = r.get("valuation") or {}
    if any(v.values()):
        L.append(f"  估值: PE(TTM) {v.get('pe_ttm') or 'n/a'} · PB {v.get('pb')} · 市值 {_big(v.get('mktcap'))}")
    f = r.get("financials") or {}
    if f:
        L.append(f"  业绩 ({f.get('as_of')}): EPS {f.get('eps')} · 营收 {_big(f.get('revenue'))} (YoY {f.get('rev_yoy')}%) · "
                 f"净利 {_big(f.get('net_profit'))} (YoY {f.get('np_yoy')}%) · 毛利 {f.get('gross_margin')}% · ROE {f.get('roe')}")
    c = r.get("chips") or {}
    if c:
        L.append(f"  筹码 ({c.get('as_of')}): 股东户数 {c.get('holder_num')} (QoQ {c.get('qoq_pct')}%) · {c.get('trend')}")
    p = r.get("popularity") or {}
    if p.get("rank"):
        L.append(f"  人气: 东财人气榜 rank {p.get('rank')}")
    if r.get("fundamentals_note"):
        L.append(f"  note: {r['fundamentals_note']}")
    L.append("  Educational only — not financial advice.  (data pack; the verdict/grade = deep-research skill)")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(prog="research", description="No-key deep-research data pack (US + China A/HK).")
    p.add_argument("ticker")
    p.add_argument("--market", choices=["US", "A", "HK"], default="US",
                   help="US | A (China A-share) | HK")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        r = research(a.ticker, a.market)
    except Exception as e:
        print(f"research: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(r, indent=2, ensure_ascii=False) if a.format == "json" else render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
