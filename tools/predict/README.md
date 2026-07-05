# predict — crowd forecasts for the macro gate

`ot poly` pulls the macro-relevant **Polymarket** prediction markets (public
Gamma API, **no key**) and distills a gate view — the crowd's *priced*
probabilities for the questions the Step-0 event gate asks:

```
ot poly                 # gate view + top macro markets by 24h volume
ot poly --tags fed      # one tag slug only (fed / economy / inflation / ...)
ot poly --json          # machine-readable (consumed by `ot debate`)
```

Gate view keys: `P(Fed holds, next FOMC)` · `P(25bp cut, next FOMC)` ·
`P(Fed HIKE this year)` · `P(zero cuts this year)` · `P(recession)`.

**Read:** odds are a *forecast input*, not a signal — they tell you what the
crowd is braced for, so a print that lands inside the priced consensus is a
non-event and one that lands outside it is the trade. `ot debate` folds these
odds into its evidence pack automatically.

Stdlib + optional certifi, curl fallback — same reliability envelope as every
other tool. Educational only — not financial advice.
