# earnings — per-name earnings (财报) calendar + gate

Keyless. The macro event gate (`ot catalysts`) only sees market-wide prints
(FOMC/CPI/PCE/NFP/OPEX) — it is blind to single-stock earnings. A name can rip or
gap on its own report with nothing on the macro calendar (e.g. MU +15% AH dragging
the whole memory complex). This tool closes that hole for **your** held + watched
names: who reports, when, AMC/BMO, and against which estimate — so the desk note
can take the call **before** the print, not explain the move after.

## Use

```bash
ot earnings MU SNDK WDC            # next 14 days for these names + ⚠️/✅ gate
ot earnings --watchlist           # US tickers from watchlist.json (positions + watch pool)
ot earnings MU --days 30 --gate-days 2
ot earnings SNDK --json           # machine-readable (email pipeline / skill)
```

Flags: `--days N` (window, default 14) · `--gate-days N` (gate fires when a name
reports within N days, default 3) · `--watchlist [path]` (roster file; default
`watchlist.json`) · `--from YYYY-MM-DD` (anchor date) · `--format text|json`.

## Source & caching

Nasdaq's public earnings calendar (`api.nasdaq.com/api/calendar/earnings?date=…`,
keyless — needs only a browser User-Agent). The window is scanned by business day
and filtered to the requested tickers; each day's calendar is cached under
`data/earnings/<date>.json` (git-ignored) so a day is fetched at most once
(future/today refreshed every 6h, past days kept). Stdlib only; certifi if present,
else curl fallback.

## Scope

US listings only. A-share / HK earnings (e.g. for the China rosters) would need an
Eastmoney source — a future extension. The gate verdict is wired into the daily
roster email's data pack alongside the macro event gate.

Educational only — not financial advice.
