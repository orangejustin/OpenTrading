#!/usr/bin/env python3
"""
send_email.py — deliver an OpenTrading brief/report by email (stdlib-only SMTP).

The transport for the daily push. Reads the message body from stdin (or --body-file),
an optional HTML alternative from --html-file, and the SMTP credentials from the
environment / a git-ignored .env file — so no secret ever touches the command line,
your shell history, or git.

Config (env vars; put them in a git-ignored .env at the repo root):
    OT_SMTP_PROVIDER   gmail | outlook | icloud | yahoo   (preset host/port/security)
    OT_SMTP_HOST       overrides the provider preset (e.g. smtp.gmail.com)
    OT_SMTP_PORT       default 587
    OT_SMTP_SECURITY   starttls (default) | ssl | none
    OT_SMTP_USER       the login (usually the full sending address)
    OT_SMTP_PASS       an APP PASSWORD (never your normal password)
    OT_EMAIL_FROM      defaults to OT_SMTP_USER
    OT_EMAIL_TO        default recipient(s), comma-separated

Examples:
    echo "hello" | python3 send_email.py --subject "test"
    ot report | python3 send_email.py --subject "Morning read" --to me@example.com
    python3 send_email.py --dry-run --subject x --to me@example.com < body.txt

Educational only — not financial advice.
"""
import argparse
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

# provider -> (host, port, security)
PRESETS = {
    "gmail":   ("smtp.gmail.com", 587, "starttls"),
    "outlook": ("smtp-mail.outlook.com", 587, "starttls"),
    "office365": ("smtp.office365.com", 587, "starttls"),
    "icloud":  ("smtp.mail.me.com", 587, "starttls"),
    "yahoo":   ("smtp.mail.yahoo.com", 465, "ssl"),
    # Resend: transactional SMTP. Username is always the literal "resend";
    # the password is your API key (re_...). No 2FA setup required.
    "resend":  ("smtp.resend.com", 465, "ssl"),
}


def load_env_file(path):
    """Minimal .env loader: KEY=VALUE lines, # comments, optional quotes.
    Does not override variables already set in the real environment."""
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except OSError:
        pass


def make_ssl_context():
    """Build a verifying SSL context that actually finds root CAs on macOS.

    The python.org framework build ships with an empty cert dir unless the user
    ran "Install Certificates.command", so ssl.create_default_context() can fail
    with CERTIFICATE_VERIFY_FAILED. Resolve a CA bundle explicitly: certifi if
    importable, else a known system bundle. This keeps the tool dependency-free
    (works without certifi) while staying secure (verification stays ON)."""
    cafile = os.environ.get("SSL_CERT_FILE")
    if not cafile:
        try:
            import certifi  # noqa
            cafile = certifi.where()
        except Exception:
            for cand in ("/etc/ssl/cert.pem",
                         "/opt/homebrew/etc/ca-certificates/cert.pem",
                         "/usr/local/etc/ca-certificates/cert.pem",
                         "/opt/homebrew/etc/openssl@3/cert.pem"):
                if os.path.exists(cand):
                    cafile = cand
                    break
    if cafile and os.path.exists(cafile):
        return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()  # last resort: OpenSSL defaults


def split_addrs(value):
    if not value:
        return []
    parts = []
    for chunk in value.replace(";", ",").split(","):
        c = chunk.strip()
        if c:
            parts.append(c)
    return parts


def resolve_config(args):
    provider = (args.provider or os.environ.get("OT_SMTP_PROVIDER") or "").lower()
    host = args.host or os.environ.get("OT_SMTP_HOST")
    port = args.port or os.environ.get("OT_SMTP_PORT")
    security = (args.security or os.environ.get("OT_SMTP_SECURITY") or "").lower()

    if provider in PRESETS:
        p_host, p_port, p_sec = PRESETS[provider]
        host = host or p_host
        port = port or p_port
        security = security or p_sec

    port = int(port) if port else 587
    security = security or "starttls"

    user = args.user or os.environ.get("OT_SMTP_USER")
    # Resend's SMTP login is always the literal string "resend".
    if provider == "resend" and not user:
        user = "resend"
    password = os.environ.get("OT_SMTP_PASS")  # never via CLI (history leak)
    sender = args.sender or os.environ.get("OT_EMAIL_FROM") or user
    to = split_addrs(args.to) or split_addrs(os.environ.get("OT_EMAIL_TO"))

    return {
        "provider": provider, "host": host, "port": port, "security": security,
        "user": user, "password": password, "sender": sender, "to": to,
    }


def build_message(cfg, subject, body, html):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["sender"]
    msg["To"] = ", ".join(cfg["to"])
    msg["Date"] = formatdate(localtime=True)
    try:
        domain = (cfg["sender"] or "opentrading").split("@")[-1]
        msg["Message-ID"] = make_msgid(domain=domain)
    except Exception:
        pass
    msg.set_content(body or "(empty)")
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def main():
    p = argparse.ArgumentParser(description="Send an OpenTrading brief by email (SMTP).")
    p.add_argument("--subject", default="OpenTrading", help="Email subject line.")
    p.add_argument("--to", help="Recipient(s), comma-separated. Defaults to OT_EMAIL_TO.")
    p.add_argument("--from", dest="sender", help="From address. Defaults to OT_EMAIL_FROM/OT_SMTP_USER.")
    p.add_argument("--body-file", help="Read the plain-text body from this file (default: stdin).")
    p.add_argument("--html-file", help="Optional HTML alternative body.")
    p.add_argument("--provider", help="gmail | outlook | office365 | icloud | yahoo")
    p.add_argument("--host", help="SMTP host (overrides provider preset).")
    p.add_argument("--port", help="SMTP port.")
    p.add_argument("--security", help="starttls | ssl | none")
    p.add_argument("--user", help="SMTP login (overrides OT_SMTP_USER).")
    p.add_argument("--env-file", help="Path to a .env file to load (default: repo .env).")
    p.add_argument("--dry-run", action="store_true", help="Validate + print the plan; do not connect.")
    a = p.parse_args()

    # Load .env: explicit path, else the repo root (two dirs up from this file).
    default_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    load_env_file(a.env_file or default_env)

    cfg = resolve_config(a)

    # Body
    if a.body_file:
        with open(a.body_file, "r", encoding="utf-8") as fh:
            body = fh.read()
    elif not sys.stdin.isatty():
        body = sys.stdin.read()
    else:
        body = ""
    html = None
    if a.html_file:
        with open(a.html_file, "r", encoding="utf-8") as fh:
            html = fh.read()

    # Validate
    missing = []
    if not cfg["host"]:
        missing.append("host (set OT_SMTP_PROVIDER or OT_SMTP_HOST)")
    if not cfg["user"]:
        missing.append("OT_SMTP_USER")
    if not cfg["password"] and not a.dry_run:
        missing.append("OT_SMTP_PASS (app password)")
    if not cfg["to"]:
        missing.append("recipient (--to or OT_EMAIL_TO)")
    if missing:
        print("send_email: missing config -> " + "; ".join(missing), file=sys.stderr)
        print("  Put credentials in a git-ignored .env at the repo root. See tools/email/README.md.",
              file=sys.stderr)
        return 2

    msg = build_message(cfg, a.subject, body, html)

    plan = (f"  host     {cfg['host']}:{cfg['port']} ({cfg['security']})\n"
            f"  user     {cfg['user']}\n"
            f"  from     {cfg['sender']}\n"
            f"  to       {', '.join(cfg['to'])}\n"
            f"  subject  {a.subject}\n"
            f"  body     {len(body)} chars" + (f" + {len(html)} chars html" if html else ""))
    if a.dry_run:
        print("send_email DRY RUN — would send:\n" + plan)
        return 0

    ctx = make_ssl_context()
    try:
        if cfg["security"] == "ssl":
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx, timeout=30)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=30)
        with server:
            server.ehlo()
            if cfg["security"] == "starttls":
                server.starttls(context=ctx)
                server.ehlo()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        print(f"send_email: auth failed ({e.smtp_code}). Use an APP PASSWORD, not your normal "
              f"password, and confirm SMTP is enabled for the account.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"send_email: failed -> {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print("[email] sent:\n" + plan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
