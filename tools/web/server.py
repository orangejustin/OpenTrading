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
import json
import os
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
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PY = sys.executable or "python3"
UA = "Mozilla/5.0 (OpenTrading web)"
sys.path.insert(0, str(ROOT / "tools" / "llm"))
try:
    import llm  # tools/llm/llm.py — engine dispatcher (Gemini / OpenRouter / Claude Code CLI)
except Exception:  # noqa: BLE001
    llm = None

STRIP = [("GC=F", "Gold"), ("BTC-USD", "Bitcoin"), ("ETH-USD", "Ethereum")]
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


def _news_for(ticker: str | None) -> list:
    args = [ROOT / "tools/financialjuice/fj.py", "fetch", "--minutes", "1440"]
    if ticker:
        args += ["--ticker", ticker]
    raw = ot_json(*args) or []
    items = raw if isinstance(raw, list) else (raw.get("items") or raw.get("headlines") or [])
    out = []
    for it in items[:12]:
        if isinstance(it, dict):
            out.append({
                "title": it.get("title") or it.get("headline") or it.get("text") or "",
                "url": it.get("url") or it.get("link") or "",
                "time": it.get("time") or it.get("published") or it.get("date") or "",
            })
        elif isinstance(it, str):
            out.append({"title": it, "url": "", "time": ""})
    return [o for o in out if o["title"]]


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


# Re-analyzing the same name is expensive (LLM call) — cache per (ticker, engine,
# model) for 10 minutes; the UI's ↻ Re-run sends fresh=1 to bypass.
_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 600


def analyze(ticker: str, engine: str | None = None, model: str | None = None,
            fresh: bool = False) -> dict:
    key = (ticker.upper(), engine or "", model or "")
    if not fresh:
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < _CACHE_TTL:
            return hit[1]
    q = yahoo(ticker, "3mo", "1d")
    tech = technicals(q.get("series", []))
    smart = ot_json(ROOT / "tools/smartmoney/sm.py") or {}
    ctx = {
        "symbol": q["symbol"], "name": q.get("name"), "last": q.get("last"),
        "chg_pct": round(q["chg_pct"], 2) if q.get("chg_pct") is not None else None,
        "series": q.get("series", []), "technicals": tech,
        "market_fng": _extract_fng(smart), "news": _news_for(ticker), "ai": False,
    }
    if not (llm and llm.any_ok()):
        ctx["note"] = ("Set GEMINI_API_KEY or OPENROUTER_API_KEY in .env — or install "
                       "the claude CLI — to enable the AI analysis (data panels work without it).")
        return ctx
    try:
        t0 = time.time()
        ai, meta = llm.generate_json(_analysis_prompt(ctx), ANALYSIS_SCHEMA,
                                     engine=engine, model=model)
        ctx.update(ai)
        ctx["ai"] = True
        ctx["engine"] = meta
        ctx["elapsed"] = round(time.time() - t0, 1)
        with _CACHE_LOCK:
            _CACHE[key] = (time.time(), ctx)
    except Exception as e:  # noqa: BLE001
        ctx["error"] = f"AI analysis unavailable: {e}"
    return ctx


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
                return self._send(200, json.dumps({"items": _news_for(qs.get("ticker", [None])[0])}))
            if u.path == "/api/analyze":
                tk = (qs.get("ticker", [""])[0] or "").strip()
                if not tk:
                    return self._send(400, json.dumps({"error": "ticker required"}))
                eng = (qs.get("engine", [None])[0] or None)
                mdl = (qs.get("model", [None])[0] or None)
                fresh = qs.get("fresh", ["0"])[0] in ("1", "true")
                return self._send(200, json.dumps(analyze(tk, eng, mdl, fresh)))
            if u.path == "/api/engines":
                return self._send(200, json.dumps({
                    "engines": llm.engines() if llm else [],
                    "default": llm.default_engine() if llm else None,
                }))
            if u.path == "/api/health":
                return self._send(200, json.dumps({"ok": True, "ai": bool(llm and llm.any_ok())}))
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
