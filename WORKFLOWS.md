# Hero workflows

Three copy-pasteable routines that show OpenTrading at its best. Each is **one or two
`ot` commands + one prompt to Claude** — run the commands, then paste the prompt (the
embedded `short-term-trader` skill does the reasoning). Educational only — not financial advice.

---

## 1. The morning read — "calls or puts today?"

Your pre-market brief in 30 seconds: macro tilt, sentiment, dealer gamma, news, your book.

```bash
ot                       # the fused data pack (macro + smart money + options + news + positions)
```

> **Ask Claude:** *"Here's my morning data pack — give me the regime call and whether I lean
> calls or puts on QQQ today. Macro first, then the one level that matters."*

**You get:** a RISK-ON / RISK-OFF / MIXED call, the key tension (e.g. *gap-up on weak
breadth*), and a directional lean with the invalidation level — not a data dump.

**Go deeper (parallel desks):**

```bash
ot report --deep         # splits the pack into 5 independent analyst desks + a synthesis pass
```

Hand the manifest to Claude (or a multi-agent runner): each desk reasons over **only its
slice** (macro / smart-money / options / tape / news) — fewer tokens, more focus — then the
**synthesis** pass fuses them into one regime call and a per-position plan.

---

## 2. "Is it safe to size up?" — the event gate

Never size blind into a known print. This is Step 0 before any add.

```bash
ot catalysts             # FOMC / CPI / PCE / NFP / OPEX + an explicit gate verdict
ot earnings --watchlist  # per-name earnings (财报) for the names in your watchlist
```

> **Ask Claude:** *"Given the catalyst gate and my earnings calendar, is it safe to add to
> NVDA today, or do I wait? If wait, until when?"*

**You get:** a ✅ clear / ⚠️ hold verdict that names the event and date. A great setup into a
HIGH-impact print becomes *"smaller size, or wait"* — not a blind buy. The macro gate is
blind to single-stock earnings, so `ot earnings` covers the 财报 half.

---

## 3. "Grade my book" — portfolio review

A bull/bear desk over your actual positions, with concrete share calls.

```bash
ot watch                 # live quotes for every name in watchlist.json
ot                       # the regime + gamma context to grade against
```

> **Ask Claude:** *"Grade my book one name at a time — add / hold / trim / hedge — with the
> reason and a stop for each. Flag my biggest concentration and factor risk."*

**You get:** a per-position call with a stop and a sizing note, plus the dominant risk in the
book (e.g. *single-factor BTC beta*) — the portfolio-review workflow with concentration limits.

---

> Your positions live only in git-ignored `watchlist.json` — nothing here leaves your machine.
> See the [README](README.md) for setup. **Educational only — not financial advice.**
