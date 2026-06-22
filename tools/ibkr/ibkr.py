#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["ib_async>=1.0.1"]
# ///
"""
ibkr.py — Interactive Brokers CLI (live quotes / chains / bars / positions / P&L,
plus a guarded paper-order path) via ib_async against a local TWS or IB Gateway.

    python3 ibkr.py quote SPY QQQ ^VIX
    python3 ibkr.py positions
    python3 ibkr.py pnl
    python3 ibkr.py bars MSTR --tf 5m --lookback 1d
    python3 ibkr.py chain SPY --expiry 20260717 --width 5
    python3 ibkr.py order MSTR --side buy --qty 10            # DRY-RUN preview
    python3 ibkr.py order MSTR --side buy --qty 10 --submit   # submit (paper only)
    python3 ibkr.py quote SPY --format json

Connection (never hard-coded; flags override env, env overrides paper defaults):
    IBKR_HOST       default 127.0.0.1
    IBKR_PORT       default 4002   (paper IB Gateway; paper TWS=7497, live 4001/7496)
    IBKR_CLIENT_ID  default 17
    IBKR_ACCOUNT    default = first managed account

Requires a running TWS / IB Gateway with the API enabled (Configure > Settings >
API > Enable ActiveX and Socket Clients). Defaults target the PAPER socket.

Needs the `ib_async` package: `uv run` auto-installs it from the header above; for
the plain python3 path run `pip install ib_async`.

Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Paper sockets — used to gate live order submission.
PAPER_PORTS = {4002, 7497}
# Common index symbols that must route as Index, not Stock.
INDEX_EXCHANGE = {
    "SPX": "CBOE", "VIX": "CBOE", "NDX": "NASDAQ", "RUT": "RUSSELL",
    "DJI": "CME", "DJX": "CBOE",
}


def _err(msg: str, code: int = 1):
    print(f"ibkr: {msg}", file=sys.stderr)
    sys.exit(code)


def _import_ib():
    """Import ib_async with an actionable message if it's missing."""
    try:
        import ib_async  # noqa: F401
        return ib_async
    except Exception:
        _err("ib_async not installed. Run via `uv run` (auto-installs) or "
             "`pip install ib_async`. See tools/ibkr/README.md.", 3)


def connect(args):
    """Open a synchronous ib_async connection from flags/env/paper-defaults."""
    ib_async = _import_ib()
    IB = ib_async.IB
    host = args.host or os.environ.get("IBKR_HOST") or "127.0.0.1"
    port = int(args.port or os.environ.get("IBKR_PORT") or 4002)
    client_id = int(args.client_id or os.environ.get("IBKR_CLIENT_ID") or 17)
    ib = IB()
    try:
        ib.connect(host, port, clientId=client_id, timeout=args.timeout, readonly=True)
    except Exception as e:
        _err(f"could not connect to {host}:{port} (clientId={client_id}): {e}\n"
             f"      Is TWS/IB Gateway running with the API enabled on that port?", 2)
    # Default to delayed-frozen data so quotes work without a realtime subscription;
    # --live-data opts into realtime (type 1) where the account is entitled.
    ib.reqMarketDataType(1 if args.live_data else 3)
    return ib_async, ib, port


def _contract(ib_async, sym: str):
    """Map a ticker string to an ib_async contract (Index for ^/known indices)."""
    s = sym.lstrip("^").upper()
    if sym.startswith("^") or s in INDEX_EXCHANGE:
        return ib_async.Index(s, INDEX_EXCHANGE.get(s, "CBOE"), "USD")
    return ib_async.Stock(s, "SMART", "USD")


def _round(x, n=2):
    return round(x, n) if isinstance(x, (int, float)) and x == x else None  # x==x drops nan


# --------------------------------------------------------------------------- #
# read-only commands
# --------------------------------------------------------------------------- #
def cmd_quote(ib_async, ib, args):
    contracts = [_contract(ib_async, s) for s in args.symbols]
    ib.qualifyContracts(*contracts)
    tickers = ib.reqTickers(*contracts)
    rows = []
    for sym, t in zip(args.symbols, tickers):
        last = t.marketPrice()
        if last != last:  # nan
            last = t.last if (t.last == t.last) else t.close
        prev = t.close
        chg = (last - prev) if (last == last and prev == prev) else None
        pct = (chg / prev * 100) if (chg is not None and prev) else None
        rows.append({
            "symbol": sym, "last": _round(last), "change": _round(chg),
            "pct": _round(pct), "bid": _round(t.bid), "ask": _round(t.ask),
            "close": _round(prev),
        })
    return rows


def cmd_positions(ib_async, ib, args):
    rows = []
    for p in ib.positions(args.account or ""):
        c = p.contract
        rows.append({
            "account": p.account, "symbol": c.symbol, "secType": c.secType,
            "right": getattr(c, "right", "") or "", "strike": getattr(c, "strike", 0) or 0,
            "expiry": getattr(c, "lastTradeDateOrContractMonth", "") or "",
            "position": p.position, "avgCost": _round(p.avgCost),
        })
    return rows


def cmd_pnl(ib_async, ib, args):
    acct = args.account or (ib.managedAccounts()[0] if ib.managedAccounts() else "")
    summary = {av.tag: av.value for av in ib.accountSummary(acct)}
    totals = {
        "account": acct,
        "netLiquidation": _round(_f(summary.get("NetLiquidation"))),
        "totalCash": _round(_f(summary.get("TotalCashValue"))),
        "unrealizedPnL": _round(_f(summary.get("UnrealizedPnL"))),
        "realizedPnL": _round(_f(summary.get("RealizedPnL"))),
        "buyingPower": _round(_f(summary.get("BuyingPower"))),
    }
    positions = []
    for it in ib.portfolio(acct):
        positions.append({
            "symbol": it.contract.symbol, "position": it.position,
            "marketPrice": _round(it.marketPrice), "marketValue": _round(it.marketValue),
            "avgCost": _round(it.averageCost), "unrealizedPnL": _round(it.unrealizedPNL),
            "realizedPnL": _round(it.realizedPNL),
        })
    return {"totals": totals, "positions": positions}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


_TF = {"1m": "1 min", "2m": "2 mins", "5m": "5 mins", "15m": "15 mins",
       "30m": "30 mins", "1h": "1 hour", "1d": "1 day"}
_DUR = {"1d": "1 D", "2d": "2 D", "5d": "5 D", "1w": "1 W", "1mo": "1 M", "3mo": "3 M"}


def cmd_bars(ib_async, ib, args):
    (c,) = ib.qualifyContracts(_contract(ib_async, args.symbol)) or [None]
    if c is None:
        _err(f"could not qualify {args.symbol}")
    bars = ib.reqHistoricalData(
        c, endDateTime="", durationStr=_DUR.get(args.lookback, "1 D"),
        barSizeSetting=_TF.get(args.tf, "5 mins"), whatToShow="TRADES",
        useRTH=not args.ext, formatDate=2)
    return [{
        "time": str(b.date), "open": _round(b.open), "high": _round(b.high),
        "low": _round(b.low), "close": _round(b.close), "volume": b.volume,
    } for b in bars]


def cmd_chain(ib_async, ib, args):
    (c,) = ib.qualifyContracts(_contract(ib_async, args.symbol)) or [None]
    if c is None:
        _err(f"could not qualify {args.symbol}")
    params = ib.reqSecDefOptParams(c.symbol, "", c.secType, c.conId)
    smart = next((p for p in params if p.exchange == "SMART"), params[0] if params else None)
    if smart is None:
        _err(f"no option parameters for {args.symbol}")
    expiries = sorted(smart.expirations)
    strikes = sorted(smart.strikes)
    if not args.expiry:
        # listing mode: just expiries + strike range
        return {"symbol": c.symbol, "expirations": expiries,
                "strikeMin": strikes[0] if strikes else None,
                "strikeMax": strikes[-1] if strikes else None,
                "numStrikes": len(strikes)}
    # build an ATM window and pull greeks/IV
    (under,) = ib.reqTickers(c)
    spot = under.marketPrice()
    if spot != spot:
        spot = under.close
    near = sorted(strikes, key=lambda k: abs(k - spot))[: max(1, args.width)]
    near = sorted(near)
    opts = []
    for k in near:
        for right in ("C", "P"):
            opts.append(ib_async.Option(c.symbol, args.expiry, k, right, "SMART", tradingClass=c.symbol))
    ib.qualifyContracts(*opts)
    tickers = ib.reqTickers(*opts)
    rows = []
    for t in tickers:
        g = t.modelGreeks
        rows.append({
            "expiry": args.expiry, "strike": t.contract.strike, "right": t.contract.right,
            "bid": _round(t.bid), "ask": _round(t.ask), "last": _round(t.last),
            "iv": _round(g.impliedVol, 4) if g else None,
            "delta": _round(g.delta, 4) if g else None,
            "gamma": _round(g.gamma, 5) if g else None,
        })
    return {"symbol": c.symbol, "spot": _round(spot), "expiry": args.expiry, "rows": rows}


# --------------------------------------------------------------------------- #
# guarded order path — DRY-RUN by default; paper-only unless --allow-live
# --------------------------------------------------------------------------- #
def cmd_order(ib_async, ib, args, port: int):
    contract = _contract(ib_async, args.symbol)
    ib.qualifyContracts(contract)
    side = args.side.upper()
    if side not in ("BUY", "SELL"):
        _err("--side must be buy or sell")
    is_paper = port in PAPER_PORTS
    if not is_paper and not args.allow_live:
        _err(f"refusing to act on a non-paper port ({port}). Live needs --allow-live "
             f"AND --submit; default config targets paper.", 4)
    order_type = "LMT" if args.limit is not None else "MKT"
    order = ib_async.LimitOrder(side, args.qty, args.limit) if args.limit is not None \
        else ib_async.MarketOrder(side, args.qty)
    plan = {
        "account_port": port, "paper": is_paper, "symbol": contract.symbol,
        "side": side, "qty": args.qty, "type": order_type, "limit": args.limit,
        "submitted": False,
    }
    if not args.submit:
        plan["note"] = "DRY-RUN — pass --submit to place this order"
        return plan
    trade = ib.placeOrder(contract, order)
    ib.sleep(1.0)
    plan["submitted"] = True
    plan["orderId"] = trade.order.orderId
    plan["status"] = trade.orderStatus.status
    _log_order(plan)
    return plan


def _log_order(plan: dict):
    d = ROOT / "data" / "ibkr"
    d.mkdir(parents=True, exist_ok=True)
    plan = {"ts": datetime.now(timezone.utc).isoformat(), **plan}
    with (d / "orders.log").open("a") as f:
        f.write(json.dumps(plan) + "\n")


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def _fmt(v):
    return "" if v is None else (f"{v:,.2f}" if isinstance(v, float) else str(v))


def render_table(cmd, data):
    if cmd == "pnl":
        t = data["totals"]
        lines = [f"account {t['account']}  NLV {_fmt(t['netLiquidation'])}  "
                 f"cash {_fmt(t['totalCash'])}  uPnL {_fmt(t['unrealizedPnL'])}  "
                 f"rPnL {_fmt(t['realizedPnL'])}"]
        for p in data["positions"]:
            lines.append(f"  {p['symbol']:<8} {p['position']:>8}  @ {_fmt(p['avgCost'])}"
                         f"  mv {_fmt(p['marketValue'])}  uPnL {_fmt(p['unrealizedPnL'])}")
        return "\n".join(lines)
    if cmd == "order":
        tag = "PAPER" if data["paper"] else "LIVE"
        head = "SUBMITTED" if data["submitted"] else "DRY-RUN"
        extra = f"  id={data.get('orderId')} status={data.get('status')}" if data["submitted"] else ""
        return (f"[{head}/{tag}] {data['side']} {data['qty']} {data['symbol']} "
                f"{data['type']}{'' if data['limit'] is None else ' @ '+_fmt(data['limit'])}{extra}")
    if cmd == "chain" and isinstance(data, dict) and "rows" not in data:
        return (f"{data['symbol']}  expiries={len(data['expirations'])}  "
                f"strikes {data['strikeMin']}–{data['strikeMax']} ({data['numStrikes']})\n"
                f"  next: {', '.join(data['expirations'][:8])}")
    if cmd == "chain":
        lines = [f"{data['symbol']}  spot {_fmt(data['spot'])}  exp {data['expiry']}"]
        for r in data["rows"]:
            lines.append(f"  {r['strike']:>9} {r['right']}  bid {_fmt(r['bid'])} ask {_fmt(r['ask'])}"
                         f"  IV {_fmt(r['iv'])}  Δ {_fmt(r['delta'])}  Γ {_fmt(r['gamma'])}")
        return "\n".join(lines)
    # list-of-rows commands: quote / positions / bars
    rows = data
    if not rows:
        return "(no rows)"
    cols = list(rows[0].keys())
    w = {c: max(len(c), *(len(_fmt(r.get(c))) for r in rows)) for c in cols}
    out = ["  ".join(c.ljust(w[c]) for c in cols)]
    for r in rows:
        out.append("  ".join(_fmt(r.get(c)).ljust(w[c]) for c in cols))
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(prog="ibkr", description="Interactive Brokers CLI (ib_async)")
    p.add_argument("--host"); p.add_argument("--port"); p.add_argument("--client-id", dest="client_id")
    p.add_argument("--account", default="")
    p.add_argument("--timeout", type=float, default=8.0)
    p.add_argument("--live-data", action="store_true", help="realtime data (default: delayed)")
    p.add_argument("--format", choices=["table", "json"], default="table")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("quote"); sp.add_argument("symbols", nargs="+")
    sub.add_parser("positions")
    sub.add_parser("pnl")
    sb = sub.add_parser("bars"); sb.add_argument("symbol")
    sb.add_argument("--tf", default="5m"); sb.add_argument("--lookback", default="1d")
    sb.add_argument("--ext", action="store_true", help="include extended hours")
    sc = sub.add_parser("chain"); sc.add_argument("symbol")
    sc.add_argument("--expiry", help="YYYYMMDD; omit to list expiries")
    sc.add_argument("--width", type=int, default=5, help="strikes around ATM")
    so = sub.add_parser("order"); so.add_argument("symbol")
    so.add_argument("--side", required=True, choices=["buy", "sell", "BUY", "SELL"])
    so.add_argument("--qty", type=float, required=True)
    so.add_argument("--limit", type=float, help="limit price (omit = market)")
    so.add_argument("--submit", action="store_true", help="actually place (default: dry-run)")
    so.add_argument("--allow-live", action="store_true", help="permit a non-paper port")

    args = p.parse_args(argv)
    ib_async, ib, port = connect(args)
    try:
        if args.cmd == "quote":
            data = cmd_quote(ib_async, ib, args)
        elif args.cmd == "positions":
            data = cmd_positions(ib_async, ib, args)
        elif args.cmd == "pnl":
            data = cmd_pnl(ib_async, ib, args)
        elif args.cmd == "bars":
            data = cmd_bars(ib_async, ib, args)
        elif args.cmd == "chain":
            data = cmd_chain(ib_async, ib, args)
        elif args.cmd == "order":
            data = cmd_order(ib_async, ib, args, port)
        else:
            _err(f"unknown command {args.cmd}")
    finally:
        ib.disconnect()

    if args.format == "json":
        print(json.dumps(data, indent=2))
    else:
        print(render_table(args.cmd, data))


if __name__ == "__main__":
    main()
