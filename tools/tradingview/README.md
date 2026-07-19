# TradingView — read the live desktop chart (`ot tv`)

Reads the **running TradingView Desktop chart** over the Chrome DevTools Protocol
and prints what the chart already knows: symbol, resolution, every study's Data
Window values, VWAP, moving averages, MACD, and any Pine `table.new` box a study
draws. Deterministic — no LLM, no screenshot OCR, no API key.

```bash
ot tv                     # human table
ot tv --json              # machine-readable (alias for --format json)
ot tv --symbol AAPL       # SWITCHES the live chart to AAPL, then reads it
```

## Setup

TradingView Desktop is an Electron app, so its chart page speaks CDP when the
app is launched with a debug port. It is **not** on by default:

```bash
nohup /Applications/TradingView.app/Contents/MacOS/TradingView \
  --remote-debugging-port=9222 >/tmp/tv.log 2>&1 &
```

Verify: `curl -s http://127.0.0.1:9222/json/version`.

Override host/port with `OT_TV_CDP_HOST` / `OT_TV_CDP_PORT`. With TradingView
closed, `ot tv` prints the reason plus this relaunch line and exits 0 — it never
raises, so a report that embeds it still renders.

## What it returns

| Field | Source |
| --- | --- |
| `symbol`, `resolution` | `chartWidget.symbolWV()` / `resolutionWV()` |
| `symbol_info` | main series `symbolInfo()` — description, exchange, session, tz |
| `price`, `last` | main series Data Window (O/H/L/C, change, volume) |
| `vwap`, `vwap_delta_pct` | VWAP study, falling back to the MA study's VWAP plot |
| `moving_averages` | short/long MA + spread from "SPY Moving Averages and Signals" |
| `macd` | MACD / signal / histogram from `CM_MacD_Ult_MTF` |
| `options_overlay` | IVRank / IVx / skew + the Pine table rows and tooltip |
| `studies[]` | every visible study: name, pane, and all its plot name/value pairs |

Every value ships twice: `value` is the chart's own formatted string (`"−0.1866"`,
`"2.13 K"`), `num` is that parsed to a float (`-0.1866`, `2130.0`), or `null`
when the chart shows `∅`.

## How it works

Pure stdlib — CDP needs a WebSocket for `Runtime.evaluate`, so `tv.py` carries a
~120-line RFC 6455 client on `socket` (HTTP Upgrade handshake, client-masked text
frames, continuation reassembly). No `websockets`, no `requests`.

1. `GET /json` on the debug port → pick the target whose URL contains
   `tradingview.com/chart`.
2. Open its `webSocketDebuggerUrl`, then one `Runtime.evaluate` that walks the
   chart and returns a JSON string.

The page-side walk uses the desktop app's own globals:

```js
window._exposed_chartWidgetCollection.activeChartWidget.value()   // the chart
  .model().model().panes()[i].dataSources()                       // series + studies
```

- **Study names** — `source.metaInfo().description` (the clean name, e.g.
  `"SPY Moving Averages and Signals"`, not the raw title with all its inputs).
- **Study values** — `source.dataWindowView().items()`, the exact pairs the Data
  Window panel renders. **Do not call `view.update()` first**: it expects a UI
  event object and throws `Cannot read properties of undefined (reading 'type')`.
  `items()` alone is already current.
- **Pine tables** — `source.graphics().dwgtablecells()`, a `Map` of collections
  whose `_primitiveById` holds each cell's `{row, column, text, tooltip}`. Cells
  are regrouped into ordered rows.
- **`--symbol`** — `TradingViewApi.activeChart().setSymbol(...)`, then poll until
  the symbol resolves *and* a study reports a value, since studies recompute
  asynchronously (without that wait the first read comes back blank).

## The Options Overlay placeholder

When the Options Overlay study has nothing to show it draws a box containing only
`👉🏻 ✅`. `ot tv` detects this (a table whose rows carry no alphanumerics),
sets `populated: false` / `table_placeholder: true`, leaves `iv_rank` / `ivx_avg`
/ `skew` as `null`, and surfaces the study's own tooltip instead of inventing
data.

Worth knowing: on **QQQ** that placeholder is *not* a market-hours artifact. The
tooltip says the **[Lite]** version only supports `AAPL, AMZN, DIA, TSLA, ORCL` —
QQQ needs the [Pro] version. Verified by switching the chart to AAPL, where the
same study populates fully:

```
Options Overlay (IVRank / IVx / skew)
   IVRank 83.1   IVx avg 33.30   skew 3.00
   IVR 𝟴𝟯.𝟭 | IVx avg 𝟯𝟯.𝟯 | (3.84%) | CALL$ 𝟯% | 𝙂𝙀𝙓 🟢 🟢 | ⌛ 5
```

So the empty-table path and the populated path are both exercised.

## Limitations

- **Needs the app running with the debug port.** There is no headless mode; this
  reads the chart you are looking at.
- **`--symbol` mutates your live chart** and does not restore the previous
  symbol. Reading without `--symbol` is side-effect free.
- **Values are what the chart renders**, so a study that is silent pre-market
  (VWAP outside a session, `Risk Reward Optimiser` between signals) reports `[]`
  rather than a computed number. That is faithful, not a bug.
- **Study values are point-in-time** — the value at the last bar. History would
  need the plot data series, which this tool does not read.
- Some vendor scripts render stylized-unicode digits (`𝟴𝟯.𝟭`) in their Pine
  tables. The numeric fields come from the study's real plots, so they parse
  correctly; only the raw `table_rows` strings keep the fancy glyphs.
- Only the **active** chart widget is read. Multi-chart layouts report the
  focused one.

Educational only — not financial advice.
