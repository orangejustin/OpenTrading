#!/usr/bin/env python3
"""
privacy_audit.py — `ot privacy-audit`: the pre-push privacy gate (P1-3).

Codifies the manual ritual that guards this PUBLIC repo:

  1. BRANCH GUARD — you are not about to push `main` (main advances only
     through merged PRs; a bare `git push` from main is the classic slip).
  2. TRACKED-FILE GUARD — `.env`, `watchlist.json` / `watchlist.<id>.json`
     (only `*.example` allowed), and anything under `data/` must never be
     tracked by git.
  3. CONTENT GUARD — the outgoing diff (vs origin/main) is grepped for
     secret-shaped and personal-shaped strings: API keys, SMTP creds,
     private e-mail addresses, account/P&L context words.

Personal patterns stay OUT of the public repo: put one regex per line in
`~/.opentrading-private/audit-patterns.txt` and they are added to the scan
(the file itself is never read into any output — only match locations).

    ot privacy-audit                 # audit branch + tracked files + diff
    ot privacy-audit --push          # strict mode: exit 1 on ANY finding (hook)
    ot privacy-audit --install-hook  # install as .git/hooks/pre-push

Educational only — and the reason your positions stay yours.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_PATTERNS = Path.home() / ".opentrading-private/audit-patterns.txt"

FORBIDDEN_TRACKED = [
    re.compile(r"^\.env$"),
    re.compile(r"^watchlist(\.[\w-]+)?\.json$"),   # watchlist.json / watchlist.<id>.json
    re.compile(r"^data/"),
]
ALLOWED_EXCEPTIONS = [re.compile(r"\.example(\.|$)"), re.compile(r"(^|/)\.gitkeep$")]

# secret/personal-shaped content in the OUTGOING diff (added lines only)
CONTENT_PATTERNS = [
    ("openrouter key", re.compile(r"sk-or-v1-[0-9a-f]{16,}")),
    ("google api key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("generic api key assign", re.compile(r"(API_KEY|APIKEY|SECRET|TOKEN)\s*=\s*['\"][^'\"]{12,}", re.I)),
    ("smtp credential", re.compile(r"SMTP_(PASS|PASSWORD|USER)\s*=\s*\S{4,}", re.I)),
    # gmail-style 16-char app password (4×4). Anchored to a credential context or
    # a quoted value so ordinary prose ("tool docs live next") doesn't trip it.
    ("app password (gmail-style)",
     re.compile(r"""(?:pass\w*|pwd|smtp|app[- ]?password)\W{0,6}[a-z]{4} [a-z]{4} [a-z]{4} [a-z]{4}\b"""
                r"""|["'][a-z]{4} [a-z]{4} [a-z]{4} [a-z]{4}["']""", re.I)),
    ("personal email", re.compile(r"\b[\w.+-]+@(outlook|qq|gmail|163)\.com\b", re.I)),
    # A P&L *figure* — a P&L/tax term within ~25 chars of an actual number/currency.
    # Descriptive mentions ("not your P&L", "1099 form", "不是你的盈亏") carry no
    # adjacent figure and are allowed; a real leak ("realized loss -$4,200") is caught.
    ("P&L figure", re.compile(
        r"(?:realized (?:gain|loss|p&l)|1099|盈亏|持仓成本)[^\n]{0,12}?[$¥€£]?\s?\d[\d,]{1,}"
        r"|[$¥€£]\s?\d[\d,]{1,}[^\n]{0,12}?(?:realized (?:gain|loss|p&l)|盈亏|持仓成本)", re.I)),
]


def _git(*args) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True, cwd=str(ROOT))
    return out.stdout.strip()


def _load_private_patterns():
    pats = []
    try:
        if PRIVATE_PATTERNS.exists():
            for ln in PRIVATE_PATTERNS.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    try:
                        pats.append(("private pattern", re.compile(ln, re.I)))
                    except re.error:
                        pass
    except Exception:  # noqa: BLE001
        pass
    return pats


def audit(push_mode: bool) -> dict:
    findings = []

    branch = _git("branch", "--show-current")
    if branch == "main":
        findings.append({"check": "branch", "severity": "block" if push_mode else "warn",
                         "detail": "you are ON main — branch first; main advances only via PRs"})

    tracked = _git("ls-files").splitlines()
    for f in tracked:
        if any(a.search(f) for a in ALLOWED_EXCEPTIONS):
            continue
        if any(p.search(f) for p in FORBIDDEN_TRACKED):
            findings.append({"check": "tracked-file", "severity": "block",
                             "detail": f"{f} is TRACKED — untrack it (git rm --cached) now"})

    # outgoing diff vs origin/main: only ADDED lines, excluding this tool itself
    base = _git("merge-base", "HEAD", "origin/main") or "origin/main"
    diff = _git("diff", f"{base}...HEAD", "--unified=0") + "\n" + _git("diff", "--cached", "--unified=0")
    pats = CONTENT_PATTERNS + _load_private_patterns()
    cur_file = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur_file = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if cur_file.startswith("tools/audit/"):
            continue  # this file names the patterns it hunts
        for name, rx in pats:
            if rx.search(line):
                findings.append({"check": "content", "severity": "block",
                                 "detail": f"{cur_file}: {name} in an added line"})
                break

    blocks = [f for f in findings if f["severity"] == "block"]
    return {"branch": branch, "findings": findings,
            "ok": not blocks and not (push_mode and findings)}


HOOK = """#!/bin/sh
# OpenTrading pre-push privacy gate (installed by `ot privacy-audit --install-hook`)
exec python3 "$(git rev-parse --show-toplevel)/tools/audit/privacy_audit.py" --push
"""


def main(argv=None):
    p = argparse.ArgumentParser(prog="ot privacy-audit",
                                description="Pre-push privacy gate for the public repo.")
    p.add_argument("--push", action="store_true", help="strict: exit 1 on any finding")
    p.add_argument("--install-hook", action="store_true", help="install as .git/hooks/pre-push")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)

    if a.install_hook:
        hook = ROOT / ".git/hooks/pre-push"
        hook.write_text(HOOK, encoding="utf-8")
        hook.chmod(0o755)
        print(f"installed {hook} — every push now runs the gate")
        return 0

    r = audit(a.push)
    if a.format == "json":
        print(json.dumps(r, indent=2))
    else:
        print(f"ot privacy-audit — branch: {r['branch']}")
        if not r["findings"]:
            print("✓ clean: not on main · no forbidden tracked files · no "
                  "secret/personal-shaped lines in the outgoing diff")
        for f in r["findings"]:
            mark = "✗" if f["severity"] == "block" else "⚠"
            print(f"{mark} [{f['check']}] {f['detail']}")
        if not r["ok"]:
            print("\nBLOCKED — fix the ✗ lines before pushing.")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
