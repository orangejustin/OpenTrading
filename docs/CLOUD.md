# Cloud & tooling — the cross-device plan (design, not yet built)

Two forward-looking directions that need accounts/keys, so they live **outside** the
keyless core as opt-in tiers. Nothing here changes the default install.

---

## 1. Cross-device access (Cloudflare + Supabase)

**Goal:** view the desk from a phone; let ≤5 trusted people reach it — without breaking the
rule that *your positions and heavy compute stay on your machine*.

The naïve "port `server.py` to the edge" fails: the Workers runtime can't run the Python
`ot` tools (quant fit, TimesFM, `codex`/`claude` subprocesses). So the privacy-preserving
shape is a **home-agent → mirror → thin reader**, not a lift-and-shift:

```
  YOUR COMPUTER (the backend, already built)
    Claude Code / Codex + `ot` compute everything locally
        │  push snapshots (rank, debate verdicts, macro, cones) — NEVER raw P&L
        ▼
  Supabase  — Postgres (computed reads) · Auth (≤5-user email allowlist) · RLS
              (positions private per user) · Realtime (push to phone)
        ▲                                   ▲
        │ read-only                         │ auth
  Cloudflare Workers (API)  ───────────►  Cloudflare Pages (the existing index.html,
    thin: serve from Supabase, no compute      already a static SPA — just point
    beyond keyless quote passthrough)          /api/* at the Worker)
```

**Why this shape**
- `tools/web/index.html` is already a dependency-free static SPA → deploys to **Pages**
  almost as-is; only the `/api/*` base URL changes.
- The **home agent** keeps all heavy compute + LLM keys local (the ethos holds); it writes
  *results*, not secrets, to Supabase. A tiny `ot push` would do the mirroring.
- **Supabase Auth + Row-Level Security** is the "<5 people" model: an email allowlist, each
  person sees only what a policy permits. This is the one deliberate change from
  "never leaves localhost" — positions would live in Supabase behind auth+RLS, opt-in only,
  and still never in the public repo. Hard tax and realized-profit figures stay off it entirely.
- **Workers** stay thin: serve cached reads from Supabase, optionally proxy the keyless
  quote endpoints (Yahoo/CBOE) at the edge for freshness. No model calls in the cloud.

**MVP milestones** (each shippable alone)
1. `ot push` — write the current overview/rank/debate snapshots to Supabase (service key in
   `.env`, git-ignored).
2. Pages deploy of `index.html` with an `OT_API_BASE` switch (local server ↔ Worker).
3. Worker read API over Supabase + Supabase Auth allowlist.
4. Realtime: the home agent's morning run pushes; phones update live.

**Open decisions (owner):** which reads are safe to mirror (default: everything except raw
position sizes / P&L); whether the ≤5 users are read-only or can trigger a debate (a
triggered debate would need a home-agent job queue, not a Worker).

---

## 2. Dependency & docs tooling (Firecrawl)

As the surface grows (TimesFM, `ib_async`, MCP servers, pinned versions), the skill and the
agent benefit from **current** vendor docs rather than training-cutoff memory.
[Firecrawl](https://docs.firecrawl.dev/introduction) turns a docs site into LLM-ready
markdown in one call.

**Proposed opt-in dev tool** — `ot docs fetch <url>` → snapshot into a git-ignored
`docs/vendor/<host>/…​.md` cache the skill can load on demand (e.g. the live `ib_async`
or TimesFM API surface before writing against it).

- **Keyless-core caveat:** Firecrawl needs an API key → strictly a **developer tooling**
  module, never a runtime dependency. Gate it like the LLM engines: absent key → the
  feature is simply unavailable, the core is untouched.
- **Fallback:** the existing `WebFetch`-style single-page grab covers one-off lookups; use
  Firecrawl when a whole docs tree needs mirroring or the pages are JS-heavy.

Both tiers keep the same contract as every optional module: **the plain install stays
zero-key, zero-step; nothing in the core depends on either.**

Educational only — not financial advice.
