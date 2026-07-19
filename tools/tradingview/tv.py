#!/usr/bin/env python3
"""
tv.py — read the LIVE TradingView Desktop chart (`ot tv`).

TradingView Desktop is an Electron app, so when it is launched with
`--remote-debugging-port=9222` its chart page speaks the **Chrome DevTools
Protocol**. This tool attaches to that page and reads the chart's own
internals — no screenshot OCR, no API key, no LLM in the loop:

  - chart state: symbol, resolution, exchange/session, study list
  - every visible study's Data Window values (the exact name/value pairs the
    chart itself renders in its Data Window panel)
  - the highlights the desk actually asks for: VWAP, the short/long MA pair
    from "SPY Moving Averages and Signals", MACD/signal/histogram from
    CM_MacD_Ult_MTF
  - any Pine `table.new` text a study draws (Options Overlay's IVRank / IVx /
    CALL-PUT skew box), including its tooltip
  - last price and price vs VWAP in %

    python3 tv.py                    # human table
    python3 tv.py --format json      # machine-readable (for ot report / ot rank)
    python3 tv.py --symbol AAPL      # SWITCHES the live chart, then reads it

CDP needs a WebSocket for Runtime.evaluate, so this file carries a ~120-line
stdlib WebSocket client (handshake + client-masked frames). Nothing outside the
stdlib is imported. Every failure degrades to None / a note rather than raising,
so a closed TradingView never breaks a report that embeds this.

Stdlib only (Python 3.9+). Educational only — not financial advice.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import struct
import time
import urllib.request

CDP_HOST = os.environ.get("OT_TV_CDP_HOST", "127.0.0.1")
CDP_PORT = int(os.environ.get("OT_TV_CDP_PORT", "9222"))
CHART_URL_HINT = "tradingview.com/chart"
LAUNCH_HINT = ("nohup /Applications/TradingView.app/Contents/MacOS/TradingView "
               "--remote-debugging-port=%d >/tmp/tv.log 2>&1 &" % CDP_PORT)

# Chart "sources" that are bookkeeping, not studies the trader added.
INTERNAL_STUDY_IDS = ("Dividends@", "Splits@", "Earnings@", "BarSetContinuousRollDates@")

# TradingView renders "no value" as U+2205 and uses typographic minus/thin space.
EMPTY_MARKS = ("∅", "n/a", "NaN", "")
_SUFFIX = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _safe(fn, default=None):
    """Every read is best-effort — a missing study must never break the report."""
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


# --------------------------------------------------------------------------- #
# Minimal WebSocket client (RFC 6455 client side, text frames only)            #
# --------------------------------------------------------------------------- #
class _WS:
    """Just enough WebSocket to drive CDP: handshake, masked send, reassembled recv."""

    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def __init__(self, url, timeout=15):
        if "://" not in url:
            raise ValueError("bad ws url")
        hostport, _, path = url.split("://", 1)[1].partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            "GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"
            % (path, hostport, key)
        ).encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("connection closed during handshake")
            head += chunk
        head, _, self.buf = head.partition(b"\r\n\r\n")
        if b" 101" not in head.split(b"\r\n")[0]:
            raise ConnectionError("websocket upgrade refused")
        expect = base64.b64encode(hashlib.sha1((key + self.GUID).encode()).digest())
        if expect not in head:
            raise ConnectionError("bad Sec-WebSocket-Accept")

    def send(self, text):
        payload = text.encode("utf-8")
        n = len(payload)
        if n < 126:
            header = struct.pack("!BB", 0x81, 0x80 | n)
        elif n < 1 << 16:
            header = struct.pack("!BBH", 0x81, 0x80 | 126, n)
        else:
            header = struct.pack("!BBQ", 0x81, 0x80 | 127, n)
        mask = os.urandom(4)
        self.sock.sendall(header + mask
                          + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise ConnectionError("connection closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        """Return one complete text message (continuation frames reassembled)."""
        parts = []
        while True:
            b0, b1 = self._read(2)
            fin, opcode, masked, length = b0 & 0x80, b0 & 0x0F, b1 & 0x80, b1 & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if masked else None
            data = self._read(length) if length else b""
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:  # close
                raise ConnectionError("server closed the websocket")
            if opcode in (0x9, 0xA):  # ping / pong — ignore, keep reading
                continue
            parts.append(data)
            if fin:
                return b"".join(parts).decode("utf-8", "replace")

    def close(self):
        _safe(self.sock.close)


class _CDP:
    """A DevTools session against one page target."""

    def __init__(self, ws_url, timeout=15):
        self.ws = _WS(ws_url, timeout=timeout)
        self._id = 0

    @staticmethod
    def chart_target(host=CDP_HOST, port=CDP_PORT, timeout=5):
        """The page whose URL looks like a TradingView chart (None if not found)."""
        url = "http://%s:%d/json" % (host, port)
        with urllib.request.urlopen(url, timeout=timeout) as r:
            targets = json.loads(r.read().decode("utf-8", "replace"))
        for t in targets:
            if t.get("type") == "page" and CHART_URL_HINT in (t.get("url") or ""):
                return t.get("webSocketDebuggerUrl")
        return None

    def evaluate(self, expression, timeout_ms=10000):
        """Runtime.evaluate -> the JS return value (we always return a JSON string)."""
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({
            "id": mid, "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True,
                       "awaitPromise": True, "timeout": timeout_ms},
        }))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") != mid:
                continue  # an event, not our reply
            if "error" in msg:
                raise RuntimeError(msg["error"].get("message", "CDP error"))
            result = msg.get("result", {})
            if "exceptionDetails" in result:
                desc = (result["exceptionDetails"].get("exception") or {}).get("description")
                raise RuntimeError("page exception: %s" % (desc or "unknown"))
            return (result.get("result") or {}).get("value")

    def close(self):
        _safe(self.ws.close)


# --------------------------------------------------------------------------- #
# The page-side probe                                                          #
# --------------------------------------------------------------------------- #
# Reads the chart widget collection the desktop app exposes on `window`, then
# for each pane/source pulls (a) metaInfo for the human study name, (b) the
# Data Window view's items() — the same name/value pairs the Data Window panel
# shows — and (c) any Pine table cells the study drew.
_PROBE_JS = r"""
(() => {
  const fail = (m) => JSON.stringify({error: m});
  try {
    const col = window._exposed_chartWidgetCollection;
    if (!col || !col.activeChartWidget) return fail("chart widget collection not on window");
    const cw = col.activeChartWidget.value();
    if (!cw) return fail("no active chart widget");
    const model = cw.model().model();

    let info = null;
    try {
      const si = model.mainSeries().symbolInfo() || {};
      info = {name: si.name, full_name: si.full_name, description: si.description,
              exchange: si.exchange, type: si.type, session: si.session, timezone: si.timezone};
    } catch (e) { info = null; }

    // Pine table.new cells drawn by a study (graphics().dwgtablecells()).
    const tableCells = (src) => {
      const out = [];
      if (!src.graphics) return out;
      let g; try { g = src.graphics(); } catch (e) { return out; }
      let cells; try { cells = g.dwgtablecells(); } catch (e) { return out; }
      if (!cells || typeof cells.forEach !== "function") return out;
      cells.forEach((coll) => {
        const byId = coll && coll._primitiveById;
        if (!byId || typeof byId.forEach !== "function") return;
        byId.forEach((c) => {
          out.push({row: c.row, col: c.column, text: c.text == null ? null : String(c.text),
                    tooltip: c.tooltip == null ? null : String(c.tooltip)});
        });
      });
      return out;
    };

    const studies = [];
    let series = null;
    model.panes().forEach((pane, pi) => {
      pane.dataSources().forEach((src) => {
        let view = null;
        try { view = src.dataWindowView && src.dataWindowView(); } catch (e) { view = null; }
        if (!view || typeof view.items !== "function") return;
        // NOTE: do NOT call view.update() — it expects a UI event object and throws.
        let items = [];
        try {
          items = (view.items() || []).map((it) => ({
            title: it._title == null ? "" : String(it._title),
            value: it._value == null ? "" : String(it._value),
            visible: it._visible !== false,
          }));
        } catch (e) { items = []; }

        let meta = null;
        try { meta = src.metaInfo ? src.metaInfo() : null; } catch (e) { meta = null; }
        if (!meta) {                       // the main price series
          if (!series) series = {pane: pi, values: items};
          return;
        }
        studies.push({pane: pi, name: meta.description || meta.shortDescription || "?",
                      short_name: meta.shortDescription || null, id: meta.id || null,
                      values: items, tables: tableCells(src)});
      });
    });

    return JSON.stringify({
      symbol: cw.symbolWV().value(),
      resolution: cw.resolutionWV().value(),
      symbol_info: info, series: series, studies: studies,
    });
  } catch (e) { return fail(String(e && e.message || e)); }
})()
"""

_SET_SYMBOL_JS = """
(() => {
  try {
    const api = window.TradingViewApi;
    if (!api || !api.activeChart) return JSON.stringify({error: "TradingViewApi unavailable"});
    const chart = api.activeChart();
    chart.setSymbol(%s);
    return JSON.stringify({ok: true, symbol: chart.symbol()});
  } catch (e) { return JSON.stringify({error: String(e && e.message || e)}); }
})()
"""

_READ_SYMBOL_JS = """
(() => { try {
  const cw = window._exposed_chartWidgetCollection.activeChartWidget.value();
  return JSON.stringify({symbol: cw.symbolWV().value()});
} catch (e) { return JSON.stringify({error: String(e)}); } })()
"""


# --------------------------------------------------------------------------- #
# Parsing the chart's *formatted* values back into numbers                     #
# --------------------------------------------------------------------------- #
def _num(text):
    """'693.66' / '−0.09 (−0.01%)' / '2.13 K' -> float, or None when the chart
    shows no value (∅, blank). The chart formats with U+2212 and U+202F."""
    if text is None:
        return None
    s = str(text).strip().replace("−", "-").replace(" ", "").replace(" ", "")
    s = s.replace(",", "")
    if s in EMPTY_MARKS:
        return None
    m = re.match(r"^-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    val = float(m.group(0))
    tail = s[m.end():m.end() + 1].upper()
    return val * _SUFFIX[tail] if tail in _SUFFIX else val


def _has_data(text):
    """True when the chart is actually showing something (not ∅ / blank)."""
    return bool(text) and str(text).strip() not in EMPTY_MARKS


def _plot(study, *needles):
    """First plot value in `study` whose title matches any needle (case-insensitive)."""
    for needle in needles:
        for item in (study or {}).get("values", []):
            if needle.lower() in (item.get("title") or "").lower():
                return item.get("value")
    return None


def _study(studies, *needles):
    """First study whose name matches any needle (case-insensitive substring)."""
    for needle in needles:
        for s in studies:
            hay = "%s %s" % (s.get("name") or "", s.get("short_name") or "")
            if needle.lower() in hay.lower():
                return s
    return None


def _tables(study):
    """Group a study's Pine table cells into ordered rows of text.

    Returns (rows, tooltip, placeholder). `placeholder` is True when the study
    drew a box with no alphanumeric content — e.g. the Options Overlay renders
    a bare "👉🏻 ✅" when it has nothing to report for this symbol/session."""
    cells = (study or {}).get("tables") or []
    if not cells:
        return [], None, False
    grid = {}
    tooltip = None
    for c in cells:
        row, col = c.get("row") or 0, c.get("col") or 0
        text = re.sub(r"\s+", " ", (c.get("text") or "")).strip()
        grid.setdefault(row, {})[col] = text
        if not tooltip and c.get("tooltip"):
            tooltip = re.sub(r"[ \t]+", " ", c["tooltip"]).strip()
    rows = [" | ".join(grid[r][c] for c in sorted(grid[r])) for r in sorted(grid)]
    rows = [r for r in rows if r.strip(" |")]
    placeholder = not any(re.search(r"[A-Za-z0-9]", r) for r in rows)
    return rows, tooltip, placeholder


# --------------------------------------------------------------------------- #
# Collection                                                                   #
# --------------------------------------------------------------------------- #
def collect(symbol=None, timeout=15):
    """Attach to the live chart and return the full read (never raises)."""
    out = {"connected": False, "cdp": "%s:%d" % (CDP_HOST, CDP_PORT), "error": None,
           "symbol": None, "resolution": None, "symbol_info": None, "last": None,
           "vwap": None, "vwap_delta_pct": None, "moving_averages": None, "macd": None,
           "options_overlay": None, "studies": [], "price": {}}
    cdp = None
    try:
        ws_url = _CDP.chart_target(timeout=5)
    except Exception as exc:  # noqa: BLE001 — TradingView closed / port not open
        out["error"] = ("cannot reach TradingView DevTools on %s:%d (%s) — is TradingView "
                        "Desktop running with --remote-debugging-port=%d?"
                        % (CDP_HOST, CDP_PORT, type(exc).__name__, CDP_PORT))
        return out
    if not ws_url:
        out["error"] = ("TradingView is running but no chart tab was found "
                        "(no target URL containing '%s')" % CHART_URL_HINT)
        return out

    try:
        cdp = _CDP(ws_url, timeout=timeout)
        switched = _switch_symbol(cdp, symbol) if symbol else False
        raw = cdp.evaluate(_PROBE_JS)
        data = json.loads(raw) if raw else {}
        # Studies recompute asynchronously after a symbol change — re-probe until
        # at least one of them reports a value, so `--symbol` isn't all-blank.
        for _ in range(6) if switched else ():
            if _any_study_value(data):
                break
            time.sleep(0.7)
            raw = cdp.evaluate(_PROBE_JS)
            data = json.loads(raw) if raw else data
    except Exception as exc:  # noqa: BLE001
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
        return out
    finally:
        if cdp:
            cdp.close()

    if data.get("error"):
        out["error"] = "chart probe failed: %s" % data["error"]
        return out

    out["connected"] = True
    out["symbol"] = data.get("symbol")
    out["resolution"] = data.get("resolution")
    out["symbol_info"] = data.get("symbol_info")

    # --- price, straight from the chart's own Data Window ------------------- #
    series = (data.get("series") or {}).get("values") or []
    price = {}
    for item in series:
        key = (item.get("title") or "").strip().lower()
        if key in ("open", "high", "low", "close", "change", "vol", "last day change"):
            price[key.replace(" ", "_")] = item.get("value")
    out["price"] = price
    out["last"] = _num(price.get("close"))

    # --- studies ------------------------------------------------------------ #
    studies = [s for s in (data.get("studies") or [])
               if not str(s.get("id") or "").startswith(INTERNAL_STUDY_IDS)]
    out["studies"] = [{
        "name": s.get("name"), "pane": s.get("pane"),
        "values": [{"name": v["title"], "value": v["value"], "num": _num(v["value"])}
                   for v in s.get("values", []) if v.get("visible") and v.get("title")],
    } for s in studies]

    # --- the highlights the desk asks for ----------------------------------- #
    vwap_study = _study(studies, "Volume Weighted Average Price", "VWAP")
    vwap = _num(_plot(vwap_study, "VWAP"))
    mas = _study(studies, "SPY Moving Averages and Signals", "MAs & Signals")
    if mas:
        short, long = _num(_plot(mas, "Short Period Moving Average")), \
                      _num(_plot(mas, "Long Period Moving Average"))
        out["moving_averages"] = {"study": mas.get("name"), "short": short, "long": long,
                                  "spread": (short - long) if (short and long) else None}
        if vwap is None:  # this study carries its own VWAP plot — use it as fallback
            vwap = _num(_plot(mas, "VWAP"))
    out["vwap"] = vwap
    if out["last"] is not None and vwap:
        out["vwap_delta_pct"] = (out["last"] - vwap) / vwap * 100.0

    macd_study = _study(studies, "CM_MacD_Ult_MTF", "MacD")
    if macd_study:
        out["macd"] = {
            "study": macd_study.get("name"),
            "macd": _num(_plot(macd_study, "MACD")),
            "signal": _num(_plot(macd_study, "Signal Line", "Signal")),
            "histogram": _num(_plot(macd_study, "Histogram")),
        }

    ov = _study(studies, "Options Overlay", "Options Oscillator")
    if ov:
        rows, tooltip, placeholder = _tables(ov)
        skew, ivr, ivx = (_plot(ov, "skew"), _plot(ov, "IVR"), _plot(ov, "IVx"))
        populated = any(_has_data(x) for x in (skew, ivr, ivx)) or (rows and not placeholder)
        out["options_overlay"] = {
            "study": ov.get("name"), "populated": bool(populated),
            "skew": _num(skew), "iv_rank": _num(ivr), "ivx_avg": _num(ivx),
            "table_rows": rows, "table_placeholder": placeholder, "tooltip": tooltip,
            "note": None if populated else
                    "study drew a placeholder box (no IVRank/IVx/skew for this symbol "
                    "or session) — see 'tooltip' for the study's own explanation",
        }
    return out


def _any_study_value(data):
    """True once at least one study has recomputed onto the current series."""
    for s in (data or {}).get("studies") or []:
        if str(s.get("id") or "").startswith(INTERNAL_STUDY_IDS):
            continue
        if any(_has_data(v.get("value")) for v in s.get("values") or []):
            return True
    return False


def _switch_symbol(cdp, symbol, wait=8.0):
    """Point the LIVE chart at `symbol`, then wait for it to resolve. Best-effort."""
    want = symbol.strip().upper()
    _safe(lambda: cdp.evaluate(_SET_SYMBOL_JS % json.dumps(want)))
    deadline = time.time() + wait
    while time.time() < deadline:
        got = _safe(lambda: (json.loads(cdp.evaluate(_READ_SYMBOL_JS)) or {}).get("symbol"))
        if got and (got.upper() == want or got.upper().split(":")[-1] == want):
            time.sleep(0.6)  # let the studies recompute on the new series
            return True
        time.sleep(0.4)
    return False


# --------------------------------------------------------------------------- #
# Rendering                                                                    #
# --------------------------------------------------------------------------- #
def _fmt(v, spec):
    """Format a number, or 'n/a' — one silent study must not break the block."""
    return format(v, spec) if isinstance(v, (int, float)) and not isinstance(v, bool) else "n/a"


def _tooltip_reason(tooltip):
    """Pick the most informative plain-ASCII line out of a Pine tooltip.

    Vendors often open these boxes with stylized-unicode banners (𝙂𝙤𝙤𝙙 𝙣𝙚𝙬𝙨…)
    that carry no information; the actual reason is in the plain-text lines."""
    best = ""
    for line in (tooltip or "").splitlines():
        line = line.strip()
        if len(re.findall(r"[A-Za-z]", line)) > len(re.findall(r"[A-Za-z]", best)):
            best = line
        if len(best) > 30:
            break
    return best


def render_table(d):
    W = 68
    L = ["=" * W, "TRADINGVIEW — live desktop chart (CDP)", "=" * W]
    if not d.get("connected"):
        L.append("  not connected: %s" % (d.get("error") or "unknown"))
        L.append("")
        L.append("  Relaunch TradingView with the debug port:")
        L.append("    %s" % LAUNCH_HINT)
        L += ["=" * W, "  Educational only — not financial advice."]
        return "\n".join(L)

    info = d.get("symbol_info") or {}
    desc = info.get("description")
    L.append("  Chart   : %s  ·  %s  %s" % (d.get("symbol") or "?", d.get("resolution") or "?",
                                            ("(%s)" % desc) if desc else ""))
    if info.get("exchange") or info.get("session"):
        L.append("            %s · session %s · %s"
                 % (info.get("exchange") or "?", info.get("session") or "?",
                    info.get("timezone") or "?"))

    p = d.get("price") or {}
    if d.get("last") is not None:
        L.append("  Last    : %s   O %s  H %s  L %s   chg %s   vol %s"
                 % (_fmt(d["last"], ".2f"), p.get("open", "n/a"), p.get("high", "n/a"),
                    p.get("low", "n/a"), p.get("change", "n/a"), p.get("vol", "n/a")))
    if d.get("vwap") is not None:
        delta = d.get("vwap_delta_pct")
        side = "above" if (delta or 0) > 0 else "below" if (delta or 0) < 0 else "at"
        L.append("  VWAP    : %s   ->  price %s VWAP by %s"
                 % (_fmt(d["vwap"], ".2f"), side,
                    (_fmt(delta, "+.2f") + "%") if delta is not None else "n/a"))
    else:
        L.append("  VWAP    : n/a (study silent — pre/post session or no data yet)")

    ma = d.get("moving_averages")
    if ma:
        L.append("  MAs     : short %s  ·  long %s  ·  spread %s"
                 % (_fmt(ma.get("short"), ".2f"), _fmt(ma.get("long"), ".2f"),
                    _fmt(ma.get("spread"), "+.2f")))
    m = d.get("macd")
    if m:
        hist = m.get("histogram")
        lean = "bullish" if (hist or 0) > 0 else "bearish" if (hist or 0) < 0 else "flat"
        L.append("  MACD    : %s  signal %s  hist %s  ->  %s"
                 % (_fmt(m.get("macd"), ".4f"), _fmt(m.get("signal"), ".4f"),
                    _fmt(hist, ".4f"), lean))

    ov = d.get("options_overlay")
    if ov:
        L.append("-" * W)
        L.append("  Options Overlay (IVRank / IVx / skew)")
        if ov.get("populated"):
            L.append("     IVRank %s   IVx avg %s   skew %s"
                     % (_fmt(ov.get("iv_rank"), ".1f"), _fmt(ov.get("ivx_avg"), ".2f"),
                        _fmt(ov.get("skew"), ".2f")))
            for row in ov.get("table_rows") or []:
                L.append("     %s" % row[:60])
        else:
            L.append("     no values yet — the study drew a placeholder box")
            if ov.get("table_rows"):
                L.append("     box shows : %s" % " / ".join(ov["table_rows"])[:52])
            reason = _tooltip_reason(ov.get("tooltip"))
            if reason:
                L.append("     study says: %s" % reason[:52])

    L.append("-" * W)
    L.append("  Studies on chart (%d) — Data Window values" % len(d.get("studies") or []))
    for s in d.get("studies") or []:
        shown = [v for v in s.get("values") or [] if _has_data(v.get("value"))]
        L.append("     %s  [pane %s]" % ((s.get("name") or "?")[:52], s.get("pane")))
        if not shown:
            L.append("        (no values right now)")
        for v in shown[:8]:
            L.append("        %-30s %s" % ((v.get("name") or "")[:30], v.get("value")))
    L += ["=" * W, "  Educational only — not financial advice."]
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(prog="tv", description="Read the live TradingView Desktop chart over CDP.")
    p.add_argument("--symbol", help="Switch the LIVE chart to this symbol before reading.")
    p.add_argument("--format", choices=["table", "json"], default="table")
    p.add_argument("--timeout", type=float, default=15, help="CDP socket timeout (s).")
    a = p.parse_args(argv)
    data = collect(symbol=a.symbol, timeout=a.timeout)
    print(json.dumps(data, indent=2, ensure_ascii=False) if a.format == "json" else render_table(data))


if __name__ == "__main__":
    main()
