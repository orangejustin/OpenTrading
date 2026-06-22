# IBKR integration

Interactive Brokers connectivity for live market data and (guarded) paper execution,
via [`ib_async`](https://github.com/ib-api-reloaded/ib_async) (the maintained successor
to `ib_insync`) against a locally running **TWS** or **IB Gateway** with the API enabled.

> **Status: read-only commands implemented + a guarded order path.** Live data and
> execution require a running gateway — see prerequisites.

## Prerequisites (one-time, broker side)

1. An IBKR account with a **paper-trading account** enabled (Account Settings → Paper Trading).
2. **IB Gateway** (lighter) or **TWS** installed and logged in to the **paper** account.
3. API enabled: **Configure → Settings → API → Settings → "Enable ActiveX and Socket Clients"**.
   Note the **Socket port**: paper Gateway `4002`, paper TWS `7497` (live `4001`/`7496`).

No pip step under `uv` — the script's PEP 723 header auto-installs `ib_async`. For the
plain `python3` path: `pip install ib_async`.

## Usage

```bash
ot ibkr quote SPY QQQ ^VIX            # live/delayed NBBO + % change
ot ibkr positions                     # current positions
ot ibkr pnl                           # account NLV / cash / uPnL + per-position P&L
ot ibkr bars MSTR --tf 5m --lookback 1d   # historical bars (technicals)
ot ibkr chain SPY                     # list expiries + strike range
ot ibkr chain SPY --expiry 20260717 --width 5   # ATM window with IV + Greeks
ot ibkr order MSTR --side buy --qty 10              # DRY-RUN preview (no submit)
ot ibkr order MSTR --side buy --qty 10 --submit     # submit — PAPER port only
ot ibkr quote SPY --json              # machine-readable (any subcommand)
```

## Connection (env or flags; flags win)

| Var / flag                        | Default       | Notes                       |
|-----------------------------------|---------------|-----------------------------|
| `IBKR_HOST` / `--host`            | `127.0.0.1`   | gateway host                |
| `IBKR_PORT` / `--port`            | `4002`        | **paper Gateway**           |
| `IBKR_CLIENT_ID` / `--client-id`  | `17`          | any unused client id        |
| `IBKR_ACCOUNT` / `--account`      | first managed | for multi-account logins    |
| `--live-data`                     | off (delayed) | realtime needs a subscription |

## Safety rules (enforced)

- The connection is opened **read-only** (`readonly=True`); market-data defaults to
  **delayed-frozen** so it works without a realtime subscription.
- `order` **dry-runs by default** — printing the plan, submitting nothing. `--submit`
  is required to place.
- A submit is **refused on any non-paper port** unless `--allow-live` is *also* given.
  Default config targets paper, so live is never one keystroke away.
- Submitted orders are appended to `data/ibkr/orders.log` (git-ignored).

Output mirrors the other tools: a human table by default, `--format json` (`--json`
via `ot`) for piping into the skill.
