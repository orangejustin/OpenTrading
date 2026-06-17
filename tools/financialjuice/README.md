# FinancialJuice CLI (`fj.py`)

Real-time financial news from [FinancialJuice](https://www.financialjuice.com/home)
via its **public RSS squawk feed** — no account, no browser automation.

Feed: `https://www.financialjuice.com/feed.ashx?xy=rss`

Stdlib-only (Python 3.9+). Uses `certifi` if installed; otherwise falls back to the
system `curl` for TLS (handles the common macOS "certificate verify failed" issue).

## Commands

```bash
ot news        [filters] [--format table|json|markdown]
ot news digest [filters] [--feeds ...]   # multi-day; merges the stored archive + live
ot news store  [filters] [--dir DIR] [--quiet]
```

`ot news` is the wrapper; the underlying script is
`python3 tools/financialjuice/fj.py {fetch,store}`. `store` writes a date-stamped
markdown log (`YYYY-MM-DD_HH-MM_financialjuice.md`) to `data/news-log/` by default.

## Filters

| Flag | Meaning |
|------|---------|
| `--window {premarket,open,today,afternoon,afterhours,session,all}` | Named intraday window (ET) |
| `--minutes N` | Only the last N minutes |
| `--days N` | Only the last N days (`digest` reads the archive for real history) |
| `--since HH:MM` \| `--since "YYYY-MM-DD HH:MM"` | Since a time (today ET, or explicit) |
| `--ticker SYM` | Only headlines relevant to a ticker (NVDA, AAPL, MSFT, GOOGL, AMZN, META, TSLA, SPY, QQQ, BTC, ETH; unknown symbols matched literally) |
| `--grep REGEX` | Case-insensitive regex over the headline |
| `--category CAT` | Fed / Macro / Earnings / Geopolitical / Crypto / Other |
| `--source NAMES` | Keep items whose source/headline matches any (e.g. `cnbc,yahoo`) |
| `--limit N` | Max headlines (default 40; `digest` 200, `0` = no cap) |

ET windows: `premarket` 04:00–09:30, `open` 09:30–10:30, `today` 09:30–now,
`afternoon` 13:00–16:00, `afterhours` 16:00–20:00, `session` 09:30–16:00, `all` = no
time filter.

## Network options

| Flag | Meaning |
|------|---------|
| `--cache-ttl N` | Reuse a cached feed for N seconds (default 60) to avoid the feed's rate limit |
| `--no-cache` | Always fetch fresh, ignore the cache |
| `--feed-url URL` | Override the RSS feed URL |
| `--file PATH` | Read RSS from a local file (offline / testing) |
| `--insecure` | Skip TLS verification (last resort) |

The cache lives in your system temp dir. On a failed live fetch, the tool falls back
to the last cached copy (with a note on stderr) so you still get something usable.

## Multi-source news (direct provider RSS)

The public FinancialJuice feed is **provider-agnostic** (one "FinancialJuice" author). For
per-provider coverage, aggregate direct RSS feeds with `--feeds` (each item is source-tagged,
merged newest-first, deduped):

| Source | What | Notes |
|--------|------|-------|
| `financialjuice` | the public squawk (default) | macro + global tape |
| `cnbc` | CNBC Top News / Markets / Earnings / Economy | US stocks |
| `yahoo` | Yahoo Finance **per-ticker** headlines | needs `--tickers AAPL,MSTR` |

```bash
ot news --feeds financialjuice,cnbc          # aggregate, newest-first, source-tagged
ot news --feeds cnbc --source cnbc           # CNBC only
ot news --feeds yahoo --tickers AAPL,MSTR    # position-relevant Yahoo headlines
ot news digest --days 7 --feeds financialjuice,cnbc
```

Set a default with `OT_NEWS_FEEDS=financialjuice,cnbc`. Reuters/Bloomberg dropped their free
RSS, so they're not included; `OT_FJ_FEED_URL` can point `financialjuice` at a personalized feed.

## Examples

```bash
# Pre-market brief as a table
ot news --window premarket

# Everything NVDA-related since the open, as JSON
ot news --since 9:30 --ticker NVDA --json

# Just Fed/central-bank headlines from the last 2 hours
ot news --minutes 120 --category Fed

# Archive the market-open hour to data/news-log/
ot news store --window open
```

## Notes

- Categories are keyword heuristics (whole-word matched). They're a convenience for
  scanning, not ground truth.
- The RSS feed carries the **text** squawk. The live **voice** squawk is a paid
  membership feature the feed does not include.
- For 0DTE decisions, treat headlines older than ~15 minutes as stale — always check
  the ET timestamp.
