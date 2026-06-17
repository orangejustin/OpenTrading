# Daily Brief (`daily_brief.py`) + macOS push

Generates a daily pre-market brief and fires a macOS notification — the "daily 推送."

## What it does
- Pulls `macro.py` + `fj.py` (last 12h news) + BTC spot/range (Coinbase, no key).
- Synthesizes a **regime** (RISK-ON / RISK-OFF / MIXED) from macro tilt + news tone.
- Writes `data/briefs/YYYY-MM-DD.md` with macro table, BTC, news tape, and a
  per-sleeve lean (ETFs / 3x / BTC / options) + key levels.
- Fires a macOS Notification Center banner with the headline read.

> This is the *lighter* sibling of the full report. For the fused macro + smart-money
> + options + positions pack, use **`ot`** (the default command). `ot brief` runs this.

## Run manually
```bash
ot brief          # wrapper for: python3 tools/brief/daily_brief.py
```

## Watchlist (position-aware)
Make the brief about *your* book. Copy the example and edit:
```bash
cp watchlist.example.json watchlist.json   # watchlist.json is git-ignored (private)
```
Each position has a `ticker`, a `driver` (the main thing that moves it), and a `note`.
The brief then adds a **Your positions** section: per-ticker headline matches (via
`fj.py`'s ticker aliases) plus a tie-in — e.g. a `BTC`-driver name like MSTR shows the
live BTC move as tailwind/headwind. Add aliases for new names in
`tools/financialjuice/fj.py` → `TICKER_ALIASES`.

## Schedule it (macOS launchd)
```bash
ot schedule            # Mon–Fri 05:30 local (= 08:30 ET pre-open)
ot schedule 6 0        # change to 06:00 local
ot schedule uninstall
```
(`ot schedule` wraps `tools/brief/install_schedule.sh`.)
- Label: `com.opentrading.dailybrief` · Log: `data/briefs/_launchd.log`
- **Runner:** uses `uv run` (absolute path) when uv is installed — a standalone
  CPython that avoids the python.org framework "Python.app" launchd startup hang —
  else Apple's `/usr/bin/python3`. `ot schedule` prints which one it wired in.
- Verify: `launchctl list | grep opentrading`
- `05:30 PT == 08:30 ET` (ET and PT share DST, so no twice-a-year drift). Pick whatever local time you want.
- launchd runs a missed calendar job on the next wake, so a sleeping Mac still gets the brief.

> ⚠️ **macOS TCC caveat:** a launchd job **cannot read a project under `~/Desktop`,
> `~/Documents`, or `~/Downloads`** (you'll see `Operation not permitted`). The
> *manual* run is unaffected. To schedule, either keep the repo in a non-protected
> location (e.g. `~/OpenTrading`, `~/code/…`), or grant the runner Full Disk Access.
> For away-from-desk delivery, a cloud routine (email / Claude) is cleaner — see `ROADMAP.md`.

## Notes
- The regime/lean is a **rule-based heuristic** — educational, verify at the cash open.
- Notifications use the built-in `osascript`. For a custom app icon, `brew install terminal-notifier`.
- This is the lightweight daily feed. The fuller `/decide` desk (bull/bear debate +
  correlation-aware sizing) is the next build — see `ROADMAP.md`.
