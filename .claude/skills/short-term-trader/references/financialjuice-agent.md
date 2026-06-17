# FinancialJuice News Agent

## Overview

FinancialJuice (https://www.financialjuice.com/home) is a professional real-time financial news squawk service. Its **public RSS feed is free and needs no login** — that is what this agent uses by default (a paid membership only adds the live *voice* squawk, which the RSS feed does not carry). This agent handles:

1. **Fetching news** for specific timeframes (NY time)
2. **Storing news by date** in a structured local log
3. **Summarizing** news into a clean brief
4. **Analyzing** news using trading skill context
5. **Making trade decisions** on specific stocks based on headlines

---

## How to Access FinancialJuice — the `fj` CLI

Use the bundled CLI. It reads the public RSS squawk feed
(`https://www.financialjuice.com/feed.ashx?xy=rss`), converts timestamps to ET,
tags categories, and caches for 60s to avoid rate limits. **No login, no Chrome.**

```bash
# Most recent headlines
ot news

# A specific intraday window (ET)
ot news --window premarket   # 04:00–09:30
ot news --window open        # 09:30–10:30

# Time-relative / custom
ot news --minutes 60
ot news --since 13:00

# Filter
ot news --ticker NVDA
ot news --category Fed
ot news --grep "cpi|inflation"

# JSON for further processing, or archive to data/news-log/
ot news --json
ot news store --window open
```

**Important**: the feed is real-time; use `--no-cache` if you need to force a fresh
pull within the 60s cache window. Note each headline's ET timestamp — for 0DTE
decisions, news older than ~15 minutes is stale.

*Fallback*: only for **member-gated** content the RSS feed omits (e.g. the live
voice squawk) drop to the Claude-in-Chrome MCP and have the user log in — never
handle their credentials.

---

## Timeframe Fetch Commands

When the user asks for news, these are the standard timeframe requests:

| Command | NY Time Window | `ot news` flag |
|---------|----------------|-------------|
| "morning news" / "pre-market" | 4:00 AM – 9:30 AM ET | `--window premarket` |
| "open news" / "market open" | 9:30 AM – 10:30 AM ET | `--window open` |
| "today so far" | Market open to now | `--window today` |
| "last hour" | Current time − 1 hour | `--minutes 60` |
| "afternoon news" | 1:00 PM – 4:00 PM ET | `--window afternoon` |
| "after hours" | 4:00 PM – 8:00 PM ET | `--window afterhours` |
| Custom (e.g., "since 2pm") | As requested | `--since 14:00` |
| News on a ticker | Any of the above + filter | `--ticker NVDA` |

---

## News Storage Format

`ot news store [filters]` writes the log for you to the
project-local `data/news-log/` directory (git-ignored). You rarely need to write
the file by hand — but the format it produces is below for reference.

File naming convention: `YYYY-MM-DD_HH-MM_financialjuice.md`
Example: `data/news-log/2026-03-29_09-30_financialjuice.md`

### Storage Template

```markdown
# FinancialJuice News Log
**Date**: YYYY-MM-DD
**Fetched at**: HH:MM ET
**Timeframe**: [e.g., Pre-market 4:00–9:30 AM ET]

---

## Headlines (newest first)

| Time (ET) | Headline | Category |
|-----------|----------|----------|
| 09:28 | [headline text] | [Fed / Macro / Earnings / Geopolitical / Sector] |
| 09:15 | [headline text] | [category] |
...

---

## Raw Count: [N] headlines in timeframe
```

---

## News Summary Format

When summarizing news, produce this format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEWS BRIEF — [TIMEFRAME] | [DATE] [TIME] ET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MACRO / FED
• [Key macro headline]
• [Fed commentary if any]

EARNINGS / CORPORATE
• [Any earnings reports or guidance]

GEOPOLITICAL / SECTOR
• [Any relevant geo or sector news]

TONE: [Dovish / Hawkish / Mixed / Risk-On / Risk-Off]
MARKET IMPACT: [Brief 1-sentence assessment]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## News Analysis Framework

After fetching and summarizing news, apply this analysis:

### Step 1: Classify Each Headline

| Headline Type | Typical Market Impact |
|---|---|
| Hot CPI / PPI / PCE | Bearish (hawkish repricing) |
| Cool CPI / PPI / PCE | Bullish (rate cut repricing) |
| Strong NFP / Jobs | Bearish (Fed keeps rates high) |
| Weak NFP / Jobs | Bullish (Fed has room to cut) |
| Fed hawkish speak | Bearish |
| Fed dovish speak / cut signal | Bullish |
| Earnings beat + guidance raise | Bullish for stock + sector |
| Earnings miss / guidance cut | Bearish for stock + sector |
| Geopolitical escalation | Bearish (risk-off, VIX up) |
| Geopolitical de-escalation | Bullish (risk-on) |
| China stimulus / risk | Mixed (AAPL, TSLA sensitive) |
| AI capex announcements | Bullish (NVDA, MSFT, GOOGL) |

### Step 2: Cross-Reference with Macro Dashboard

After classifying headlines, check against the macro dashboard scores:
- Does news **confirm** the macro bias? → Higher conviction trade
- Does news **contradict** the macro bias? → Reduce size, wait for clarity
- Is news **company-specific** with no macro overlap? → Isolated stock trade only

### Step 3: Stock-Specific Impact Assessment

When the user asks about a specific stock, produce this:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEWS IMPACT ANALYSIS — [TICKER]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RELEVANT HEADLINES:
• [Time] [Headline 1]
• [Time] [Headline 2]

DIRECT IMPACT: [High / Medium / Low / None]
DIRECTION: [Bullish / Bearish / Neutral]
WHY: [1–2 sentences connecting the news to the stock's fundamentals]

MACRO ALIGNMENT: [Aligned / Contradicts / Independent]

TRADE IMPLICATION:
  Bias: [Calls / Puts / No trade]
  Timeframe: [0DTE / weekly / skip]
  Key level: [price level to watch given this news]
  Risk: [what would invalidate this news-driven thesis]

CONFIDENCE: [High / Medium / Low]
Note: This is analysis only, not financial advice.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Trigger Phrases

This agent activates when the user says:
- "get me the news", "what's on the squawk", "FinancialJuice"
- "morning brief", "pre-market news", "open news"
- "what happened at [time]", "news since [time]"
- "any news on [ticker]", "what's moving [ticker]"
- "summarize today's news", "store the news"
- "what's the tape saying", "news flow"

---

## Important Notes

- **Never trade solely on news without checking macro dashboard first** — a single headline can be noise; the macro context determines whether it's signal.
- **Speed matters**: In intraday trading, news > 15 minutes old is stale for 0DTE decisions. Always note the headline timestamp.
- **Fade vs. follow**: Strong initial news-driven moves (first 5 min) often reverse. Wait for confirmation before entering in the direction of news.
- **Quiet tape = stay small**: If FinancialJuice is showing no major headlines, the market is trading on technicals alone → reduce directional conviction.
