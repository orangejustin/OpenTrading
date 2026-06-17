# IBKR integration — planned (not yet implemented)

Interactive Brokers connectivity for live market data and (paper) execution.

> **Status: stub.** No code here yet — see [`ROADMAP.md`](../../ROADMAP.md). This
> README is the design contract so the implementation lands consistently.

## Planned approach

Use [`ib_async`](https://github.com/ib-api-reloaded/ib_async) (the maintained
successor to `ib_insync`) against a locally running **TWS** or **IB Gateway** with
the API enabled.

```bash
# (planned) prerequisites
pip install ib_async
# Start TWS or IB Gateway, enable: Configure > API > Enable ActiveX and Socket Clients
```

## Planned scope

Read-only first:

- `ibkr.py quote SYM` — live quote / NBBO
- `ibkr.py chain SYM [--expiry ...]` — option chain with Greeks + IV
- `ibkr.py bars SYM --tf 5m --lookback 1d` — historical bars for the technicals workflow
- `ibkr.py positions` / `ibkr.py pnl` — current positions and P&L (feeds Workflow 6)

Then execution, gated:

- `ibkr.py order ... --paper` — paper-trade only by default; live requires an explicit
  flag **and** an interactive confirm. Never auto-submit live orders.

## Safety rules

- Default to **read-only**; default any order to the **paper** account.
- A live order path must be opt-in, confirmed, and logged.
- Connection params (host/port/clientId) come from env or flags — never hard-code, never commit.

Output mirrors the other tools: human table by default, `--format json` for piping
into the skill.
