# Email delivery (`send_email.py`) — the daily push to your inbox

Delivers an OpenTrading report/brief by email over plain **SMTP** — stdlib only
(`smtplib` + `ssl` + `email.message`), no third-party packages, no API keys.

```bash
ot email                       # report.py -> your inbox (subject auto-dated)
ot email --to me@example.com   # override recipient
ot email --subject "AM read"   # override subject
ot email --dry-run             # show exactly what would be sent; do NOT connect
```

`ot email` pipes the **full position-aware report** (`tools/report/report.py`) into
`send_email.py`. To email any other text, pipe it yourself:

```bash
echo "hello" | python3 tools/email/send_email.py --subject hi --to me@example.com
```

## One-time setup (2 minutes)

Credentials live in a **git-ignored `.env`** at the repo root — never on the command
line, never committed. The password is read only from `.env`/the environment.

```bash
cp .env.example .env      # then edit .env
ot email --dry-run        # confirms host/user/to resolve (no send)
ot email                  # the real send
```

### Provider quick-reference

| Provider | `OT_SMTP_PROVIDER` | Host (auto) | Password = |
|----------|--------------------|-------------|------------|
| **Resend** (no 2FA) | `resend` | smtp.resend.com:465 | an **API key** (`re_…`) from resend.com/api-keys. User is always `resend`. Free tier sends from `onboarding@resend.dev` to your own account email. |
| Gmail | `gmail` | smtp.gmail.com:587 | app password — myaccount.google.com → Security → 2-Step → **App passwords** |
| Outlook.com | `outlook` | smtp-mail.outlook.com:587 | app password — needs two-step ON first (account.microsoft.com → 双重验证 → 管理). Basic-auth SMTP may be disabled on some accounts. |
| Microsoft 365 (work) | `office365` | smtp.office365.com:587 | app password — tenant may disable SMTP AUTH; ask IT |
| iCloud | `icloud` | smtp.mail.me.com:587 | app-specific password — appleid.apple.com → Sign-In & Security |

### Resend (the no-2FA path)
1. Sign up at **resend.com** with the email you want the report delivered to (e.g. `zechengli@outlook.com`).
2. Create an API key at **resend.com/api-keys** (starts with `re_`).
3. Paste it into `.env` as `OT_SMTP_PASS`. Leave `OT_SMTP_USER=resend` and `OT_EMAIL_FROM=onboarding@resend.dev`.
4. `ot email`. On the free tier the only allowed recipient is your Resend account email — which is the point here (you're emailing yourself). To send from your own domain / to anyone, verify a domain in Resend and change `OT_EMAIL_FROM`.

> **Always use an _app password_, not your normal password.** Normal passwords fail
> SMTP auth when 2FA is on, and putting a real password in a file is a bad idea.

### Why an app password and not OAuth?
SMTP with an app password is the most portable, dependency-free way to send mail from
a stdlib script and from a headless scheduler. The Claude Gmail *connector* can only
create drafts (no send), so it can't power an automated 6am push — this can.

## Schedule it (daily at 6am ET)

Once `.env` works, wire the daily job:

```bash
ot schedule email            # installs a launchd job that runs `ot email`
ot schedule email uninstall
```

> ⚠️ **macOS TCC:** a `launchd` job **cannot read a repo under `~/Desktop`,
> `~/Documents`, or `~/Downloads`.** If OpenTrading lives there, either move it
> (e.g. `~/OpenTrading`) or grant the runner **Full Disk Access**. See
> `tools/brief/README.md` for the full caveat.

## Security notes
- `.env` is in `.gitignore`; `send_email.py` never echoes the password.
- The password is accepted **only** via env/`.env`, never as a CLI flag (shell history).
- TLS is on by default (STARTTLS on 587, implicit SSL on 465) with cert verification.

Educational only — not financial advice.
