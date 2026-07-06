---
title: The daily email
sidebar_position: 4
---

# The daily email

OpenTrading can send a **position-aware pre-market brief** on a schedule — a
styled, Outlook-safe HTML email built from the same tools the dashboard uses.

![Sample daily email](/img/email-sample.png)

## What's in it

- a regime banner (macro × tape × smart money)
- your positions table, $-weighted
- sections for macro, smart money, options / dealer gamma, 24h news, concentration
- the desk's **Top-3** for the day (from `ot rank`), each graded with a
  buy-now / wait-for-price action

## One-off preview

Render it to a file without sending:

```bash
OT_EMAIL_RENDER_ONLY=1 OT_EMAIL_HTML_OUT=/tmp/brief.html \
  bash tools/brief/daily_email_claude.sh
open /tmp/brief.html
```

## Sending

Email goes out over SMTP using credentials in your git-ignored `.env`. Gmail is
the simplest — you'll need a 16-character **app password** (Google account →
2-Step Verification → App passwords). Set these four keys in `.env` (start from
`.env.example`):

| Key | Value |
|---|---|
| `OT_SMTP_PROVIDER` | `gmail` |
| `OT_SMTP_USER` | your Gmail address |
| `OT_SMTP_APP_PASSWORD` | the 16-character app password |
| `OT_EMAIL_TO` | where the brief is delivered |

## Scheduling

On macOS, install a `launchd` job:

```bash
ot schedule email 6 0        # every weekday at 06:00 local time
ot schedule email uninstall  # remove it
```

For **multiple rosters** (e.g. a US book and an A-share / HK book on different
schedules and languages), OpenTrading ships a roster mailer that fans out over
every `watchlist*.json`, emailing each to its own `recipient` in its own `lang`:

```bash
ot schedule roster us        # US rosters, weekday pre-market
ot schedule roster cn        # A/HK rosters, aligned to China pre-market
```

:::note Language rule
Each email is single-language: an English book gets English, a Chinese roster
gets 中文 — never mixed in one message.
:::
