#!/usr/bin/env python3
"""
server.py — `ot web`: a local dashboard over the OpenTrading data stack.

OPTIONAL module. Serves a clean single-page dashboard at http://127.0.0.1:8787:
a live ticker strip + market-index cards with sparklines, your watchlist, and a
per-ticker analysis (summary · action · trend · Fear&Greed · entry/stop/target ·
sectors · risks · news).

Data is keyless (the same public endpoints as the rest of `ot`). The per-ticker
*AI analysis* runs on your choice of engine — Gemini (`GEMINI_API_KEY`),
OpenRouter (`OPENROUTER_API_KEY`, one key → any model incl. GLM/DeepSeek/GPT/
Claude), or your Claude Code subscription via the `claude` CLI (no key) — and
degrades to the keyless data panels when none is configured. Switch engines
from the header dropdown; results are cached 10 min per (ticker, engine, model).

    python3 tools/web/server.py                 # serve on 127.0.0.1:8787
    python3 tools/web/server.py --port 9000 --no-open

Everything stays on your machine — positions never leave localhost.
Stdlib only. Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import email.utils
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def _now_et() -> str:
    d = datetime.now(NY)
    return f"{d:%b} {d.day} · {d.hour % 12 or 12}:{d:%M} {d:%p} ET"

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PY = sys.executable or "python3"
UA = "Mozilla/5.0 (OpenTrading web)"
sys.path.insert(0, str(ROOT / "tools" / "llm"))
try:
    import llm  # tools/llm/llm.py — engine dispatcher (Gemini / OpenRouter / Claude Code CLI)
except Exception:  # noqa: BLE001
    llm = None

# The scrolling tape — the same macro set the daily email watches. ^TNX is the
# 10Y yield ×10 (the UI divides and renders %).
STRIP = [("GC=F", "Gold"), ("SI=F", "Silver"), ("CL=F", "Oil"), ("BTC-USD", "Bitcoin"),
         ("ETH-USD", "Ethereum"), ("^TNX", "US 10Y"), ("DX-Y.NYB", "DXY"),
         ("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("GLD", "GLD"), ("TLT", "TLT")]
INDICES = [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("DIA", "Dow Jones"), ("IWM", "Russell 2000")]

ACTIONS = ["BUY", "ADD", "HOLD", "WATCH", "REDUCE", "SELL", "AVOID", "ALERT"]
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "action": {"type": "string", "enum": ACTIONS},
        "trend": {"type": "string"},
        "sentiment_score": {"type": "integer"},
        "sentiment_label": {"type": "string"},
        "entries": {
            "type": "object",
            "properties": {
                "ideal_buy": {"type": "string"},
                "secondary_buy": {"type": "string"},
                "stop_loss": {"type": "string"},
                "take_profit": {"type": "string"},
            },
            "required": ["ideal_buy", "secondary_buy", "stop_loss", "take_profit"],
        },
        "technicals": {"type": "string"},
        "sectors": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "advice": {"type": "string"},
    },
    "required": ["summary", "action", "trend", "entries", "sectors", "risks", "advice"],
}


# --------------------------------------------------------------------------- #
# data helpers (keyless)
# --------------------------------------------------------------------------- #
def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        curl = shutil.which("curl")
        if curl:
            out = subprocess.run([curl, "-sL", "--max-time", str(timeout), "-A", UA, url],
                                 capture_output=True, timeout=timeout + 5)
            if out.returncode == 0 and out.stdout:
                return out.stdout.decode("utf-8", "replace")
        raise


def ot_json(*args):
    """Run an `ot` tool with --format json and return the parsed payload (or None)."""
    cmd = [PY, *[str(a) for a in args], "--format", "json"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(ROOT))
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
    except Exception:  # noqa: BLE001
        return None
    return None


def yahoo(sym: str, rng: str = "1mo", interval: str = "1d") -> dict:
    """One Yahoo chart call → last / prev / chg% / a close series for the sparkline."""
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(sym)}?range={rng}&interval={interval}&includePrePost=false")
    try:
        j = json.loads(_get(url))
        res = (j.get("chart", {}).get("result") or [{}])[0]
        meta = res.get("meta", {}) or {}
        q = (res.get("indicators", {}).get("quote") or [{}])[0]
        closes = [c for c in (q.get("close") or []) if c is not None]
        last = meta.get("regularMarketPrice")
        if last is None and closes:
            last = closes[-1]
        # DAILY change: prefer the true prior-day close; chartPreviousClose is the
        # pre-RANGE close (≈ a month ago here) and would yield a monthly change.
        prev = meta.get("previousClose")
        if prev is None:
            prev = closes[-2] if len(closes) >= 2 else meta.get("chartPreviousClose")
        chg = ((last - prev) / prev * 100) if (last is not None and prev) else None
        return {"symbol": sym.upper(), "name": meta.get("shortName") or sym,
                "last": last, "prev": prev, "chg_pct": chg, "series": closes[-40:]}
    except Exception as e:  # noqa: BLE001
        return {"symbol": sym.upper(), "name": sym, "last": None, "prev": None,
                "chg_pct": None, "series": [], "error": str(e)}


def yahoo_ohlc(sym: str, rng: str = "3mo", interval: str = "1d") -> dict:
    """Full OHLCV series + key stats for the ticker page's hand-rolled chart."""
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(sym)}?range={rng}&interval={interval}&includePrePost=false")
    j = json.loads(_get(url))
    res = (j.get("chart", {}).get("result") or [{}])[0]
    meta = res.get("meta", {}) or {}
    q = (res.get("indicators", {}).get("quote") or [{}])[0]
    ts = res.get("timestamp") or []
    rows = []
    for i, t in enumerate(ts):
        c = (q.get("close") or [None])[i] if i < len(q.get("close") or []) else None
        if c is None:
            continue
        rows.append({
            "t": t,
            "o": (q.get("open") or [None])[i], "h": (q.get("high") or [None])[i],
            "l": (q.get("low") or [None])[i], "c": c,
            "v": (q.get("volume") or [0])[i] or 0,
        })
    last = meta.get("regularMarketPrice") or (rows[-1]["c"] if rows else None)
    prev = meta.get("previousClose") or (rows[-2]["c"] if len(rows) >= 2 else None)
    return {
        "symbol": sym.upper(), "name": meta.get("shortName") or sym,
        "last": last, "prev": prev,
        "chg_pct": ((last - prev) / prev * 100) if (last is not None and prev) else None,
        "rows": rows,
        "hi52": meta.get("fiftyTwoWeekHigh"), "lo52": meta.get("fiftyTwoWeekLow"),
        "volume": meta.get("regularMarketVolume"),
        "currency": meta.get("currency"), "exchange": meta.get("fullExchangeName"),
    }


def technicals(series: list) -> dict:
    """MA10 / MA20 / 20d hi-lo / RSI14 from a daily close series — grounding for the LLM."""
    s = [x for x in series if isinstance(x, (int, float))]
    out = {"last": s[-1] if s else None}
    if len(s) >= 10:
        out["ma10"] = round(sum(s[-10:]) / 10, 2)
    if len(s) >= 20:
        out["ma20"] = round(sum(s[-20:]) / 20, 2)
        out["hi20"] = round(max(s[-20:]), 2)
        out["lo20"] = round(min(s[-20:]), 2)
    if len(s) >= 15:
        gains = losses = 0.0
        for a, b in zip(s[-15:-1], s[-14:]):
            d = b - a
            gains += max(d, 0)
            losses += max(-d, 0)
        rs = (gains / 14) / ((losses / 14) or 1e-9)
        out["rsi14"] = round(100 - 100 / (1 + rs), 1)
    return out


def _extract_fng(smart) -> dict:
    """Pull the Fear&Greed reading out of sm.py's JSON (equity_fng / crypto_fng)."""
    out = {"score": None, "label": None, "crypto": None}
    if isinstance(smart, dict):
        eq = smart.get("equity_fng") or {}
        if isinstance(eq, dict):
            if isinstance(eq.get("score"), (int, float)):
                out["score"] = int(round(eq["score"]))
            if eq.get("rating"):
                out["label"] = eq["rating"]
        cr = smart.get("crypto_fng") or {}
        if isinstance(cr, dict) and isinstance(cr.get("value"), (int, float)):
            out["crypto"] = int(cr["value"])
    return out


# Headlines that read as market-moving flashes get a red edge in the UI (the
# public RSS carries no importance flag, so this is an honest heuristic).
_HOT = re.compile(r"attack|strike|missile|\bwar\b|breaking|emergency|halt|crash|nuclear"
                  r"|invasion|explosion|assassinat|ceasefire|\bcoup\b|escalat", re.I)


def _fmt_iso(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso).astimezone(NY)
        ap = "am" if dt.hour < 12 else "pm"
        return f"{dt:%b} {dt.day} · {dt.hour % 12 or 12}:{dt:%M}{ap} ET"
    except Exception:  # noqa: BLE001
        return ""


def _iso_ts(it: dict) -> float:
    try:
        return datetime.fromisoformat(it.get("iso") or "").timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def _fj_items(minutes: int, ticker: str | None = None, limit: int = 12) -> list:
    """FinancialJuice headlines. The public RSS only holds the ~40 latest items,
    so windows past 24h merge the local news-log archive via `fj.py digest`
    (populated by `ot news store` / the scheduled email runs)."""
    if minutes > 1440 and not ticker:
        days = min(7, max(2, -(-minutes // 1440)))
        # digest defaults to --limit 200 (newest only) — that caps the window well
        # short of `days`, so 3d and 7d collapse to the same newest slice. Ask for
        # the whole window; the cutoff filter below trims it to `minutes`.
        raw = ot_json(ROOT / "tools/financialjuice/fj.py", "digest",
                      "--days", str(days), "--limit", "2000") or {}
        items = raw.get("items") if isinstance(raw, dict) else raw
        items = [i for i in (items or []) if isinstance(i, dict)]
        cutoff = time.time() - minutes * 60
        items = [i for i in items if _iso_ts(i) >= cutoff]
        items.sort(key=_iso_ts, reverse=True)
    else:
        args = [ROOT / "tools/financialjuice/fj.py", "fetch", "--minutes", str(minutes)]
        if ticker:
            args += ["--ticker", ticker]
        raw = ot_json(*args) or []
        items = raw if isinstance(raw, list) else (raw.get("items") or raw.get("headlines") or [])
    out = []
    for it in items[:limit]:
        if isinstance(it, dict):
            title = it.get("title") or it.get("headline") or it.get("text") or ""
            out.append({
                "title": title,
                "url": it.get("url") or it.get("link") or "",
                "time": _fmt_iso(it.get("iso") or "") or it.get("time")
                        or (it.get("time_et") and f"{it['time_et']} ET") or "",
                "cat": it.get("category") or it.get("cat") or "",
                "src": "FinancialJuice",
                "hot": bool(_HOT.search(title)),
            })
        elif isinstance(it, str):
            out.append({"title": it, "url": "", "time": "", "cat": "", "src": "FinancialJuice",
                        "hot": bool(_HOT.search(it))})
    return [o for o in out if o["title"]]


def _yahoo_rss(ticker: str, limit: int = 10) -> list:
    """Per-name headlines from Yahoo's keyless RSS — the fallback when the
    FinancialJuice squawk has no ticker-tagged items (common for quiet names)."""
    url = ("https://feeds.finance.yahoo.com/rss/2.0/headline?"
           + urllib.parse.urlencode({"s": ticker, "region": "US", "lang": "en-US"}))
    try:
        root = ET.fromstring(_get(url))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        when = ""
        try:
            dt = email.utils.parsedate_to_datetime(item.findtext("pubDate") or "").astimezone(NY)
            when = f"{dt:%b} {dt.day} {dt.hour % 12 or 12}:{dt:%M}{dt:%p} ET".replace("AM", "am").replace("PM", "pm")
        except Exception:  # noqa: BLE001
            pass
        out.append({"title": title, "url": (item.findtext("link") or "").strip(),
                    "time": when, "cat": "", "src": "Yahoo"})
        if len(out) >= limit:
            break
    return out


def _news_for(ticker: str | None, minutes: int = 1440) -> tuple[list, str]:
    """Headlines + scope. Fallback chain for a name: FJ ticker-tagged →
    Yahoo per-name RSS → the general market tape (labeled as such)."""
    if not ticker:
        # window-proportional render cap so a wider window visibly shows more
        # history instead of the same newest slice (min 120, ~80/day, max 500).
        cap = min(500, max(120, 80 * (-(-minutes // 1440))))
        return _fj_items(minutes, limit=cap), "market"
    items = _fj_items(minutes, ticker)
    if items:
        return items, "name"
    items = _yahoo_rss(ticker)
    if items:
        return items, "name"
    return _fj_items(minutes, limit=8), "market"


# --------------------------------------------------------------------------- #
# endpoints
# --------------------------------------------------------------------------- #
def overview() -> dict:
    syms = [s for s, _ in STRIP] + [s for s, _ in INDICES] + ["^VIX"]
    with ThreadPoolExecutor(max_workers=8) as ex:
        quotes = {q["symbol"]: q for q in ex.map(lambda s: yahoo(s, "1mo", "1d"), syms)}
    smart = ot_json(ROOT / "tools/smartmoney/sm.py") or {}
    fng = _extract_fng(smart)

    def pack(sym, label):
        q = quotes.get(sym.upper(), {})
        return {"symbol": sym.upper(), "label": label, "last": q.get("last"),
                "chg_pct": q.get("chg_pct"), "series": q.get("series", [])}

    vix = quotes.get("^VIX", {}).get("last")
    regime = "MIXED"
    if fng["score"] is not None:
        regime = "RISK-OFF" if fng["score"] < 35 else "RISK-ON" if fng["score"] > 65 else "MIXED"
    return {
        "strip": [pack(s, lbl) for s, lbl in STRIP],
        "indices": [pack(s, lbl) for s, lbl in INDICES],
        "vix": vix,
        "sentiment": fng,
        "regime": regime,
    }


_MACRO_CACHE: dict = {}


def macro_flow() -> dict:
    """The Macro & Flow panel: ot macro score + Fear&Greed + BTC funding + SPY GEX.
    All keyless; cached 15 min (opt.py's CBOE fetch is the slow leg)."""
    with _CACHE_LOCK:
        hit = _MACRO_CACHE.get("v")
    if hit and time.time() - hit[0] < 900:
        return hit[1]
    mac = ot_json(ROOT / "tools/macro/macro.py") or {}
    smart = ot_json(ROOT / "tools/smartmoney/sm.py") or {}
    opt = ot_json(ROOT / "tools/options/opt.py", "SPY", "--dte", "7") or []
    g = opt[0] if isinstance(opt, list) and opt else {}
    eq = smart.get("equity_fng") or {}
    cr = smart.get("crypto_fng") or {}
    fu = smart.get("btc_funding") or {}
    out = {
        "macro_score": mac.get("auto_score"),
        "macro_bias": mac.get("bias"),
        "indicators": [{"label": i.get("label"), "value": i.get("value"), "score": i.get("score")}
                       for i in (mac.get("auto_indicators") or [])],
        "equity_fng": {"score": round(eq["score"]) if isinstance(eq.get("score"), (int, float)) else None,
                       "rating": eq.get("rating")},
        "crypto_fng": {"score": cr.get("value"), "rating": cr.get("rating")},
        "btc_funding": {"rate_8h_pct": fu.get("rate_8h_pct"), "read": fu.get("read")},
        "gex": {"sign": g.get("gex_sign"),
                "net_usd_bn": round(g["net_gex_usd_per_1pct"] / 1e9, 2)
                if isinstance(g.get("net_gex_usd_per_1pct"), (int, float)) else None,
                "call_wall": g.get("call_wall"), "put_wall": g.get("put_wall"),
                "spot": g.get("spot")},
        "as_of": _now_et(),
    }
    with _CACHE_LOCK:
        _MACRO_CACHE["v"] = (time.time(), out)
    return out


NEWS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "macro_bias": {"type": "string", "enum": ["RISK-ON", "RISK-OFF", "MIXED"]},
        "drivers": {"type": "array", "items": {"type": "string"}},
        "portfolio_tilt": {"type": "string"},
        "watch": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "macro_bias", "drivers", "portfolio_tilt", "watch"],
}


def catalysts() -> dict:
    """The event gate: scheduled FOMC/CPI/PCE/NFP/OPEX-class catalysts (rule-based, keyless)."""
    return ot_json(ROOT / "tools/catalysts/catalysts.py") or {"events": []}


def news_analysis(minutes: int, engine: str | None, model: str | None) -> dict:
    if not (llm and llm.any_ok()):
        return {"error": "no LLM engine configured"}
    items, _ = _news_for(None, minutes)
    heads = "\n".join(f"- [{i.get('time', '')}] {i['title']}" for i in items[:60]) or "- (empty tape)"
    cal = catalysts()
    ev = "\n".join(f"- {e.get('date')} ({e.get('days_away')}d away): {e.get('event')} [{e.get('tier')}]"
                   for e in (cal.get("events") or [])[:8]) or "- none scheduled"
    prompt = f"""You are a disciplined, macro-first market strategist. Below is the last {minutes // 60}h of market headlines plus the scheduled event calendar. Read the TAPE as a whole — do not summarize item by item.

SCHEDULED CATALYSTS (the event gate — fold this risk into everything):
{ev}

HEADLINES:
{heads}

Return JSON: a 2-4 sentence summary of what the tape is really saying; macro_bias (RISK-ON / RISK-OFF / MIXED); 3-5 concrete drivers (each one line, tied to specific headlines); a one-paragraph portfolio_tilt (what a risk-first swing trader should tilt toward/away from — sectors, factors, hedges — respecting the event gate above); and 2-4 watch items (upcoming catalysts or confirmations to look for, with dates where known). Educational only, not financial advice."""
    try:
        t0 = time.time()
        data, meta = llm.generate_json(prompt, NEWS_SCHEMA, engine=engine, model=model)
        data.update({"engine": meta, "elapsed": round(time.time() - t0, 1),
                     "finished_at": _now_et(), "headline_count": len(items)})
        return data
    except Exception as e:  # noqa: BLE001
        return {"error": f"news analysis failed: {e}"}


_STRAT_CACHE: dict = {}


def strategy(fresh: bool = False) -> dict:
    """The action board: one `ot decide` card per book/watch name — direction,
    grade, zones, stop — deterministic (no LLM), cached 30 min."""
    with _CACHE_LOCK:
        hit = _STRAT_CACHE.get("v")
    if hit and not fresh and time.time() - hit[0] < 1800:
        return dict(hit[1], cached=True)
    path = Path(os.environ.get("OT_WATCHLIST") or (ROOT / "watchlist.json"))
    held, names = set(), []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for pos in (data.get("positions") or []):
                t = (pos.get("ticker") or "").upper()
                if t and t not in names:
                    held.add(t)
                    names.append(t)
            for w in (data.get("watch") or []):
                t = (w.get("ticker") or "").upper()
                if t and t not in names:
                    names.append(t)
        except Exception:  # noqa: BLE001
            pass
    names = names[:14]

    def one(t):
        d = ot_json(ROOT / "tools/sim/decide.py", t) or {}
        if not d.get("ticker"):
            return {"ticker": t, "held": t in held,
                    "error": "no read — thin history or fetch failed"}
        p = d.get("plan") or {}
        return {"ticker": t, "held": t in held, "action": d.get("action"),
                "conviction": d.get("conviction"), "price": d.get("price"),
                "event": d.get("event"), "reason": (d.get("reasons") or [""])[0],
                "side": p.get("side"), "grade": p.get("grade"), "horizon": p.get("horizon"),
                "buy_zone": p.get("buy_zone"), "core": p.get("core"),
                "add_zone": p.get("add_zone"), "trim_zone": p.get("trim_zone"),
                "stop": p.get("stop"), "scenario": p.get("scenario")}

    with ThreadPoolExecutor(max_workers=6) as ex:
        cards = list(ex.map(one, names))
    side_rank = {"long": 0, "buy": 0, "short": 1, "sell": 1}
    grade_rank = {"A": 0, "B": 1, "C": 2, "D": 3}
    cards.sort(key=lambda c: (not c["held"],
                              side_rank.get((c.get("side") or "watch"), 2),
                              grade_rank.get(c.get("grade") or "D", 3)))
    out = {"cards": cards, "as_of": _now_et()}
    with _CACHE_LOCK:
        _STRAT_CACHE["v"] = (time.time(), out)
    return out


def watchlist() -> dict:
    path = Path(os.environ.get("OT_WATCHLIST") or (ROOT / "watchlist.json"))
    names, syms = {}, []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for pos in (data.get("positions") or []):
                t = pos.get("ticker")
                if t:
                    syms.append(t)
                    names[t.upper()] = pos.get("name")          # may be None → use Yahoo's name
            for w in (data.get("watch") or []):
                t = w.get("ticker")
                if t and t.upper() not in {s.upper() for s in syms}:
                    syms.append(t)
                    names[t.upper()] = w.get("name")
        except Exception:  # noqa: BLE001
            pass
    syms = syms[:24]
    with ThreadPoolExecutor(max_workers=8) as ex:
        quotes = list(ex.map(lambda s: yahoo(s, "5d", "1d"), syms))
    for q in quotes:
        q["name"] = names.get(q["symbol"]) or q.get("name") or q["symbol"]
    return {"items": quotes}


def _analysis_prompt(ctx: dict) -> str:
    t = ctx["technicals"]
    heads = "\n".join(f"- {h['title']}" for h in ctx["news"][:8]) or "- (no fresh headlines)"
    fng = ctx["market_fng"]
    return f"""You are a disciplined, macro-first short-term trading analyst. Analyze {ctx['symbol']} ({ctx.get('name')}) for an educational dashboard. Ground EVERY claim in the data below — do not invent prices.

PRICE/TECHNICALS (daily):
- last {t.get('last')}, day change {ctx.get('chg_pct')}%
- MA10 {t.get('ma10')}, MA20 {t.get('ma20')}, 20d high {t.get('hi20')}, 20d low {t.get('lo20')}, RSI14 {t.get('rsi14')}

MARKET SENTIMENT: CNN Fear&Greed {fng.get('score')} ({fng.get('label')}), crypto F&G {fng.get('crypto')}.

RECENT HEADLINES:
{heads}

Return a JSON analysis: a 2-3 sentence summary; an action (one of {ACTIONS}); a trend call with timeframe; a 0-100 sentiment_score + sentiment_label for THIS name; concrete entry levels in `entries` (ideal_buy, secondary_buy, stop_loss, take_profit) as short strings with a $ level AND a one-phrase reason (e.g. "~$190 — near MA10 / prior support"); a one-line technicals read; 2-4 related sectors/themes; 2-4 concrete risks (events, invalidation); and one-paragraph advice. Risk-first: define the stop. Educational only, not financial advice."""


# The LLM call is expensive, so a generated analysis is cached per (ticker,
# engine, model) and stays until the user hits ↻ Re-run (24h safety TTL).
_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 24 * 3600


def analyze(ticker: str, engine: str | None = None, model: str | None = None,
            fresh: bool = False, mode: str = "auto") -> dict:
    """mode=auto → cached analysis if one exists, else the INSTANT keyless data
    view (price/technicals/news — no LLM). mode=ai → run the LLM on demand."""
    key = (ticker.upper(), engine or "", model or "")
    if not fresh:
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < _CACHE_TTL:
            return dict(hit[1], cached=True)
    q = yahoo(ticker, "3mo", "1d")
    tech = technicals(q.get("series", []))
    news, scope = _news_for(ticker)
    ctx = {
        "symbol": q["symbol"], "name": q.get("name"), "last": q.get("last"),
        "chg_pct": round(q["chg_pct"], 2) if q.get("chg_pct") is not None else None,
        "series": q.get("series", []), "technicals": tech,
        "news": news, "news_scope": scope, "ai": False,
        "can_ai": bool(llm and llm.any_ok()),
    }
    if not ctx["can_ai"]:
        ctx["note"] = ("Set GEMINI_API_KEY or OPENROUTER_API_KEY in .env — or install "
                       "the claude CLI — to enable the AI analysis (data panels work without it).")
    if mode != "ai" or not ctx["can_ai"]:
        return ctx
    smart = ot_json(ROOT / "tools/smartmoney/sm.py") or {}
    ctx["market_fng"] = _extract_fng(smart)
    try:
        t0 = time.time()
        ai, meta = llm.generate_json(_analysis_prompt(ctx), ANALYSIS_SCHEMA,
                                     engine=engine, model=model)
        ctx.update(ai)
        ctx["ai"] = True
        ctx["engine"] = meta
        ctx["elapsed"] = round(time.time() - t0, 1)
        ctx["finished_at"] = _now_et()
        with _CACHE_LOCK:
            _CACHE[key] = (time.time(), ctx)
    except Exception as e:  # noqa: BLE001
        ctx["error"] = f"AI analysis unavailable: {e}"
    return ctx


# --------------------------------------------------------------------------- #
# prediction desk — poly odds · quant cone · TimesFM cone · debate · calibration
# --------------------------------------------------------------------------- #
_POLY_CACHE: dict = {}
_DESK_CACHE: dict = {}


def poly_odds() -> dict:
    """Polymarket gate view, cached 15 min (the crowd doesn't reprice faster)."""
    with _CACHE_LOCK:
        hit = _POLY_CACHE.get("v")
    if hit and time.time() - hit[0] < 900:
        return dict(hit[1], cached=True)
    d = ot_json(ROOT / "tools/predict/poly.py") or {"error": "poly unavailable"}
    d["as_of"] = _now_et()
    with _CACHE_LOCK:
        _POLY_CACHE["v"] = (time.time(), d)
    return d


def quant_view(ticker: str) -> dict:
    """ot quant, cached 30 min per name (daily features barely move intraday)."""
    key = ("quant", ticker.upper())
    with _CACHE_LOCK:
        hit = _DESK_CACHE.get(key)
    if hit and time.time() - hit[0] < 1800:
        return dict(hit[1], cached=True)
    d = ot_json(ROOT / "tools/quant/quant.py", ticker) or {"error": "quant unavailable"}
    with _CACHE_LOCK:
        _DESK_CACHE[key] = (time.time(), d)
    return d


def forecast_view(ticker: str) -> dict:
    """TimesFM cone via the opt-in venv; {'available': False} when not installed."""
    venv_py = ROOT / ".venv-forecast/bin/python"
    if not venv_py.exists():
        return {"available": False,
                "hint": "opt-in module — bash install.sh --with-forecast (~2 GB, keyless core unaffected)"}
    key = ("tfm", ticker.upper())
    with _CACHE_LOCK:
        hit = _DESK_CACHE.get(key)
    if hit and time.time() - hit[0] < 1800:
        return dict(hit[1], cached=True)
    try:
        out = subprocess.run([str(venv_py), str(ROOT / "tools/forecast/tfm.py"),
                              ticker, "--format", "json"],
                             capture_output=True, text=True, timeout=420, cwd=str(ROOT))
        d = json.loads(out.stdout) if out.stdout.strip() else {"available": False,
                                                               "error": out.stderr[-200:]}
    except Exception as e:  # noqa: BLE001
        d = {"available": False, "error": str(e)}
    if d.get("available"):
        with _CACHE_LOCK:
            _DESK_CACHE[key] = (time.time(), d)
    return d


def debate_view(ticker: str, fresh: bool, bull: str | None, bear: str | None,
                judge: str | None, peek: bool = False) -> dict:
    """The bull/bear/judge desk — 3 LLM calls, so cached until ↻ (24h TTL).
    peek=True never runs the desk — it only reports a cached verdict (the
    ticker page uses this on load so a visit can't silently burn 3 LLM calls)."""
    key = ("debate", ticker.upper())
    if not fresh:
        with _CACHE_LOCK:
            hit = _DESK_CACHE.get(key)
        if hit and time.time() - hit[0] < _CACHE_TTL:
            return dict(hit[1], cached=True)
    if peek:
        return {"cached": False}
    cmd = [PY, str(ROOT / "tools/llm/debate.py"), ticker, "--format", "json", "--log"]
    for flag, val in (("--bull", bull), ("--bear", bear), ("--judge", judge)):
        if val:
            cmd += [flag, val]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        if out.returncode != 0:
            return {"error": (out.stderr or out.stdout)[-300:] or "debate failed"}
        d = json.loads(out.stdout)
    except Exception as e:  # noqa: BLE001
        return {"error": f"debate failed: {e}"}
    d["finished_at"] = _now_et()
    with _CACHE_LOCK:
        _DESK_CACHE[key] = (time.time(), d)
    return d


def calibration() -> dict:
    """ot reflect stats + the lessons block — the desk's own track record."""
    stats = ot_json(ROOT / "tools/reflect/reflect.py") or None
    try:
        out = subprocess.run([PY, str(ROOT / "tools/reflect/reflect.py"), "lessons"],
                             capture_output=True, text=True, timeout=30, cwd=str(ROOT))
        lessons = out.stdout.strip() if out.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        lessons = ""
    return {"stats": stats, "lessons": lessons, "as_of": _now_et()}


# --------------------------------------------------------------------------- #
# http
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/overview":
                return self._send(200, json.dumps(overview()))
            if u.path == "/api/watchlist":
                return self._send(200, json.dumps(watchlist()))
            if u.path == "/api/news":
                minutes = max(60, min(int(qs.get("minutes", ["720"])[0] or 720), 10080))
                items, scope = _news_for(qs.get("ticker", [None])[0], minutes)
                return self._send(200, json.dumps({"items": items, "scope": scope,
                                                   "minutes": minutes, "as_of": _now_et()}))
            if u.path == "/api/news_analysis":
                minutes = max(60, min(int(qs.get("minutes", ["720"])[0] or 720), 10080))
                return self._send(200, json.dumps(news_analysis(
                    minutes, qs.get("engine", [None])[0], qs.get("model", [None])[0])))
            if u.path == "/api/catalysts":
                return self._send(200, json.dumps(catalysts()))
            if u.path == "/api/strategy":
                fresh = qs.get("fresh", ["0"])[0] in ("1", "true")
                return self._send(200, json.dumps(strategy(fresh)))
            if u.path == "/api/chart":
                tk = (qs.get("ticker", [""])[0] or "").strip()
                if not tk:
                    return self._send(400, json.dumps({"error": "ticker required"}))
                rng = qs.get("range", ["3mo"])[0]
                if rng not in ("1mo", "3mo", "6mo", "1y"):
                    rng = "3mo"
                return self._send(200, json.dumps(yahoo_ohlc(tk, rng, "1d")))
            if u.path == "/api/macro":
                return self._send(200, json.dumps(macro_flow()))
            if u.path == "/api/analyze":
                tk = (qs.get("ticker", [""])[0] or "").strip()
                if not tk:
                    return self._send(400, json.dumps({"error": "ticker required"}))
                eng = (qs.get("engine", [None])[0] or None)
                mdl = (qs.get("model", [None])[0] or None)
                fresh = qs.get("fresh", ["0"])[0] in ("1", "true")
                mode = (qs.get("mode", ["auto"])[0] or "auto")
                return self._send(200, json.dumps(analyze(tk, eng, mdl, fresh, mode)))
            if u.path == "/api/engines":
                return self._send(200, json.dumps({
                    "engines": llm.engines() if llm else [],
                    "default": llm.default_engine() if llm else None,
                }))
            if u.path == "/api/poly":
                return self._send(200, json.dumps(poly_odds()))
            if u.path == "/api/quant":
                tk = (qs.get("ticker", [""])[0] or "").strip()
                if not tk:
                    return self._send(400, json.dumps({"error": "ticker required"}))
                return self._send(200, json.dumps(quant_view(tk)))
            if u.path == "/api/forecast":
                tk = (qs.get("ticker", [""])[0] or "").strip()
                if not tk:
                    return self._send(400, json.dumps({"error": "ticker required"}))
                return self._send(200, json.dumps(forecast_view(tk)))
            if u.path == "/api/debate":
                tk = (qs.get("ticker", [""])[0] or "").strip()
                if not tk:
                    return self._send(400, json.dumps({"error": "ticker required"}))
                return self._send(200, json.dumps(debate_view(
                    tk, qs.get("fresh", ["0"])[0] in ("1", "true"),
                    qs.get("bull", [None])[0], qs.get("bear", [None])[0],
                    qs.get("judge", [None])[0],
                    peek=qs.get("peek", ["0"])[0] in ("1", "true"))))
            if u.path == "/api/calibration":
                return self._send(200, json.dumps(calibration()))
            if u.path == "/api/health":
                return self._send(200, json.dumps({
                    "ok": True, "ai": bool(llm and llm.any_ok()),
                    "forecast": (ROOT / ".venv-forecast/bin/python").exists()}))
            return self._send(404, json.dumps({"error": "not found"}))
        except Exception as e:  # noqa: BLE001
            return self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}))


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="ot web", description="Local OpenTrading dashboard.",
        epilog="examples:  ot web --engine claude   ·   ot web --engine openrouter --model z-ai/glm-5.2")
    p.add_argument("--port", type=int, default=int(os.environ.get("OT_WEB_PORT") or 8787))
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-open", action="store_true", help="don't open a browser")
    p.add_argument("--engine", choices=["gemini", "openrouter", "claude"],
                   help="default AI engine (overrides OT_LLM_ENGINE; still switchable in the UI)")
    p.add_argument("--model", help="default model for the chosen engine (e.g. z-ai/glm-5.2, sonnet)")
    a = p.parse_args(argv)

    # load .env so GEMINI_API_KEY / OT_* are visible (reuse send_email's loader)
    try:
        sys.path.insert(0, str(ROOT / "tools" / "email"))
        import send_email
        send_email.load_env_file(str(ROOT / ".env"))
    except Exception:  # noqa: BLE001
        pass

    # CLI flags win over .env: pick the default engine/model for this run.
    if a.engine:
        os.environ["OT_LLM_ENGINE"] = a.engine
    if a.model:
        eng = a.engine or (os.environ.get("OT_LLM_ENGINE") or "").lower() \
            or (llm.default_engine() if llm else "")
        envkey = {"gemini": "GEMINI_MODEL", "openrouter": "OPENROUTER_MODEL",
                  "claude": "OT_CLAUDE_MODEL"}.get(eng)
        if envkey:
            os.environ[envkey] = a.model

    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    url = f"http://{a.host}:{a.port}"
    ai = llm.status_line() if llm else "off (tools/llm missing)"
    print(f"OpenTrading dashboard → {url}")
    print(f"AI engines: {ai}")
    print("Ctrl-C to stop.")
    if not a.no_open:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
        srv.shutdown()


if __name__ == "__main__":
    main()
