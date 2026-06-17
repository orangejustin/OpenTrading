# Range-first execution plan (the desk's default output)

The user trades in **zones, not single points** — a buy-in range, an add zone, a
trim/sell range with a scale-out ladder, a hard invalidation, and risk-based size.
Every per-name recommendation (CLI, desk, email) should be expressed this way.

> ⚠️ Educational only — not financial advice. Levels are mechanical (no-key data);
> always confirm live with `ot options` / `ot news` / `ot macro`.

## Generate it

```bash
ot decide TICKER                    # swing (default 5 DTE) -> full range execution plan
ot decide TICKER --capital 150000   # size against your account
ot decide TICKER --format json      # structured plan for the email/desk to render
```

Computed from no-key data: **price · 20-day mean · ATR(14) · recent 15-bar swing
high/low**. `--dte 0` keeps the fade-the-gap 0DTE logic (a range plan is a swing /
position concept), so it shows the intraday call, not zones.

## The fields

| Field | Meaning |
|---|---|
| **Buy zone** `[lo–hi]` (core) | entry band — *buy the pullback, don't chase*. `core` = fill midpoint. |
| **Add zone** `[lo–hi]` | deeper-dip pyramid band; **risk-on only**. |
| **Trim/Sell** `[lo–hi]` | exit band; ladder = **⅓ at T1 · ⅓ at T2 · runner**. |
| **Stop / invalidation** | `< X close` (long) / `> X close` (short) — thesis broken here. |
| **Size** | shares + $ exposure + $ risk, from **account-risk % × grade**, capped by single-name weight. |
| **Grade A–D** | conviction: A = edge-name + trend + momentum … D = no-action / watch. |
| **Horizon** | swing 3–7+ DTE / 2–6 wk. |
| **Scenario** | if-X-then-Y guards: event day → defer adds; extended → wait the pullback; downtrend → reclaim level. |

Risk % by grade: A 1.25% · B 1.0% · C 0.6% · D 0. Single-name weight caps: A 12% · B 9% · C 5%.

## Render in an email (中文)

```
VST · AI电力 · 信心B · 2–6周
  建仓区  151.82–157.20  (核心 154.51)
  加仓区  139.22–151.82  (更深回调，risk-on only)
  止盈区  168.64–178.44  (⅓ 168.64 · ⅓ 178.44 · 跑利润)
  止损    < 135.95 收盘
  仓位    ~53股 (~$8,189) · 风险 $984 ≈ 1.0%
  情景    FOMC日：暂缓加仓、持核心、降size
```

## Discipline it encodes
- **Buy the zone, not the print** — the buy band sits *below* spot (pullback); it never chases the green candle.
- **Scale out** — ⅓ / ⅓ / runner beats all-or-nothing at one target.
- **Invalidation first** — every plan has a `< X close` stop; size is derived from the stop distance.
- **Event-aware** — the scenario line auto-folds the FOMC/CPI/OPEX gate (calendar in `tools/sim/decide.py`).

See also [[learned-strategy]], [[portfolio-desk]], [[intraday-email]], [[risk]].
