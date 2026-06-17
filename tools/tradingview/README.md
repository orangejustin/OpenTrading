# TradingView integration — planned (not yet implemented)

Bring TradingView charts and alerts into the OpenTrading workflow.

> **Status: stub.** No code here yet — see [`ROADMAP.md`](../../ROADMAP.md). TradingView
> has **no official public REST API**, so this integration is built around the
> mechanisms that *are* supported.

## Planned approach

1. **Webhook receiver** (primary) — a tiny local HTTP server that accepts TradingView
   **alert webhooks** (Pro feature) and writes each as a structured signal the skill
   can read:

   ```
   tools/tradingview/tv_webhook.py  ->  data/signals/<ts>_<symbol>.json
   ```

   Configure a TradingView alert's "Webhook URL" to point at this server (expose it via
   a tunnel like cloudflared/ngrok if alerts fire while you're away). The alert message
   body is JSON you define in Pine, e.g. `{"sym":"NVDA","side":"long","price":950}`.

2. **Chart snapshot** — fetch a chart image / key levels for a symbol+timeframe to give
   the skill visual context (via the chart image endpoint or an unofficial library).

3. **Pine export** — emit Pine Script alert conditions for the skill's setups so they
   can be wired back into TradingView.

## Planned scope

- `tv_webhook.py serve --port 8787` — receive alerts → `data/signals/`
- `tv.py signals [--symbol SYM] [--since ...]` — list/parse received signals for the skill
- `tv.py snapshot SYM --tf 1h` — chart image + levels (best-effort)

## Notes

- Webhooks are the only first-party automation path; everything else is unofficial and
  may break — keep those parts isolated and optional.
- Never expose the webhook receiver without a shared secret / token check.
- Signals are advisory context for the skill, not auto-execution.
