#!/usr/bin/env python3
"""
cnpack.py — `ot cnpack`: A股 daily pack — 涨停池 + net-of-cost math (P2-7).

For the A-share/HK roster (Jing's book): the two things a mainland retail
trader actually checks every close, keyless:

  涨停池 (limit-up pool)  Eastmoney push2ex — today's limit-up names with
                          连板数 (consecutive boards), 封单资金 (sealed-order
                          value), 换手率 — the tape's speculative temperature.
  净成本 (net-of-cost)    the REAL breakeven for a round trip: commission
                          (default 万2.5, ¥5 minimum), stamp tax 0.05% on the
                          sell (2023 rate), SH transfer fee 0.001%/side.

    python3 cnpack.py                          # 涨停池 top 10 by 连板
    python3 cnpack.py --zt 20
    python3 cnpack.py --cost 10.00 10.50 1000  # buy sell shares -> net P&L
    python3 cnpack.py --format json

Educational only — 仅供学习，非投资建议。Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import ssl
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

UA = "Mozilla/5.0 (OpenTrading cnpack)"
ZT_URL = ("https://push2ex.eastmoney.com/getTopicZTPool?cb=&ut=7eea3edcaed734bea9cbfc24409ed989"
          "&dpt=wz.ztzt&Pageindex=0&pagesize={n}&sort=lbc%3Adesc&date={d}")

# A-share round-trip cost model (2023+ rates)
COMMISSION_RATE = 0.00025   # 万2.5 per side
COMMISSION_MIN = 5.0        # ¥5 minimum per side
STAMP_TAX_SELL = 0.0005     # 0.05% on the SELL side only
TRANSFER_FEE = 0.00001      # 0.001% per side (SH; applied both for simplicity)


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def _get(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Referer": "https://quote.eastmoney.com/"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return r.read().decode("utf-8", "replace")


def zt_pool(n: int = 10) -> dict:
    """The date param is REQUIRED and must be a TRADING day (weekend/holiday
    dates return an empty body) — walk back from 'today in Shanghai' until the
    pool answers, max 6 calendar days."""
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    data = {}
    for _ in range(6):
        try:
            raw = json.loads(_get(ZT_URL.format(n=max(n, 10), d=day.strftime("%Y%m%d"))))
            data = raw.get("data") or {}
            if data.get("pool"):
                break
        except Exception:  # noqa: BLE001
            pass
        day -= timedelta(days=1)
    pool = []
    for it in (data.get("pool") or [])[:n]:
        pool.append({
            "code": it.get("c"), "name": it.get("n"),
            "price": (it.get("p") or 0) / 1000,          # scaled x1000
            "pct": round(it.get("zdp") or 0, 2),
            "boards": it.get("lbc"),                      # 连板数
            "seal_yi": round((it.get("fund") or 0) / 1e8, 2),   # 封单(亿)
            "turnover_pct": round(it.get("hs") or 0, 2),
            "first_seal": str(it.get("fbt") or "").zfill(6),
        })
    return {"date": str(data.get("qdate") or day.strftime("%Y%m%d")),
            "total": data.get("tc"), "pool": pool}


def net_cost(buy: float, sell: float, shares: int) -> dict:
    buy_amt, sell_amt = buy * shares, sell * shares
    commission = max(COMMISSION_MIN, buy_amt * COMMISSION_RATE) \
        + max(COMMISSION_MIN, sell_amt * COMMISSION_RATE)
    stamp = sell_amt * STAMP_TAX_SELL
    transfer = (buy_amt + sell_amt) * TRANSFER_FEE
    fees = commission + stamp + transfer
    gross = sell_amt - buy_amt
    net = gross - fees
    breakeven = buy * (1 + (fees / buy_amt) if buy_amt else 0)
    return {"buy": buy, "sell": sell, "shares": shares,
            "gross": round(gross, 2), "fees": round(fees, 2),
            "commission": round(commission, 2), "stamp_tax": round(stamp, 2),
            "transfer_fee": round(transfer, 2), "net": round(net, 2),
            "net_pct": round(net / buy_amt * 100, 3) if buy_amt else None,
            "breakeven_sell": round(breakeven, 3)}


def main(argv=None):
    p = argparse.ArgumentParser(prog="ot cnpack", description="A股 daily pack (keyless).")
    p.add_argument("--zt", type=int, default=10, help="limit-up pool size (default 10)")
    p.add_argument("--cost", nargs=3, metavar=("BUY", "SELL", "SHARES"),
                   help="net-of-cost round trip, e.g. --cost 10.00 10.50 1000")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)

    if a.cost:
        r = net_cost(float(a.cost[0]), float(a.cost[1]), int(a.cost[2]))
        if a.format == "json":
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(f"净成本 — 买 {r['buy']} 卖 {r['sell']} × {r['shares']} 股")
            print(f"  毛利 ¥{r['gross']:,}  费用 ¥{r['fees']:,} "
                  f"(佣金 {r['commission']} · 印花税 {r['stamp_tax']} · 过户费 {r['transfer_fee']})")
            print(f"  净利 ¥{r['net']:,} ({r['net_pct']}%)  保本卖价 ≥ {r['breakeven_sell']}")
        return

    try:
        r = zt_pool(a.zt)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": str(e)}) if a.format == "json" else f"涨停池不可用: {e}")
        return
    if a.format == "json":
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print(f"涨停池 {r['date']} — 共 {r['total']} 家（按连板数排序，前 {len(r['pool'])}）")
    print(f"  {'代码':<8}{'名称':<10}{'价':>8}{'连板':>5}{'封单(亿)':>9}{'换手%':>7}  首封")
    for x in r["pool"]:
        fs = x["first_seal"]
        print(f"  {x['code']:<8}{x['name']:<10}{x['price']:>8.2f}{x['boards']:>5}"
              f"{x['seal_yi']:>9}{x['turnover_pct']:>7}  {fs[:2]}:{fs[2:4]}")
    print("  连板越高、封单越大 = 情绪越强；炸板率与换手一起看。仅供学习 — 非投资建议。")


if __name__ == "__main__":
    main()
