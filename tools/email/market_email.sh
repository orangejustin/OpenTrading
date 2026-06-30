#!/usr/bin/env bash
# market_email.sh — send OpenTrading's POSITION-FREE daily market brief by email.
#
# The cloud / CI path for the daily email. Builds a market-only data pack
# (macro + news + smart money + options + a PUBLIC watch list) and emails it.
# It carries NO positions, shares, P&L, cash, or alpha ideas — so it is safe to
# run from a PUBLIC GitHub Actions repo. Keyless: stdlib + curl fallback; the
# reasoning is the deterministic report.py fusion (no LLM, no API key).
#
#   STOCK_LIST="SPY,QQQ,^VIX,GLD,TLT" tools/email/market_email.sh
#   tools/email/market_email.sh --dry-run                  # validate, do not send
#   OT_EMAIL_LANG=zh tools/email/market_email.sh --to a@b.com --subject "…"
#
# Config (env — from a git-ignored .env locally, or GitHub Secrets/Variables in CI):
#   OT_SMTP_* / OT_EMAIL_TO   SMTP transport (see send_email.py)
#   STOCK_LIST                comma-separated PUBLIC tickers (default: broad macro set)
#   OT_EMAIL_LANG             en | zh  (header/footer chrome; default en)
#
# It NEVER reads or writes your real watchlist.json: it builds an ephemeral
# position-free list in a temp file and points OT_WATCHLIST at it.
#
# Educational only — not financial advice.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# ---- arg parse (passes unknown flags through to send_email.py) --------------
DRY=""
SUBJECT=""
TO_ARGS=()
PASS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY="--dry-run"; shift ;;
    --subject) SUBJECT="${2:-}"; shift 2 ;;
    --to)      TO_ARGS=(--to "${2:-}"); shift 2 ;;
    *)         PASS+=("$1"); shift ;;
  esac
done

# ---- temp files (real watchlist.json is never touched) ---------------------
WL=""; TXT=""
cleanup() { rm -f "$WL" "$TXT" 2>/dev/null || true; }
trap cleanup EXIT

# ---- position-free watchlist from STOCK_LIST (no shares / P&L / cash) -------
LIST="${STOCK_LIST:-SPY,QQQ,DIA,IWM,^VIX,GLD,SLV,TLT,BTC-USD}"
WL="$(mktemp 2>/dev/null || mktemp -t ot_market_wl)"
python3 - "$LIST" > "$WL" <<'PY'
import json, sys
syms = [s.strip() for s in sys.argv[1].split(",") if s.strip()]
# Tickers go in positions[] (that is what q.py --watchlist reads) but with NO
# shares / cost / cash — a public quote list, nothing private.
print(json.dumps({
    "_comment": "EPHEMERAL position-free market watchlist (CI). No real holdings.",
    "owner": "OpenTrading market brief",
    "lang": "en",
    "positions": [{"ticker": s, "market": "US"} for s in syms],
    "watch": [],
    "alpha": [],
}))
PY
export OT_WATCHLIST="$WL"

# ---- build + style + send --------------------------------------------------
LANG_OPT="${OT_EMAIL_LANG:-en}"
DATE_STR="$(date '+%a %b %d, %Y')"
[ -z "$SUBJECT" ] && SUBJECT="OpenTrading — Daily Market Read · $(date '+%a %b %d')"

mkdir -p "$ROOT/data/reports"
HTML="$ROOT/data/reports/market-$(date '+%Y%m%d').html"   # persisted (git-ignored) for the CI artifact
TXT="$(mktemp 2>/dev/null || mktemp -t ot_market_txt)"

# report.py (deterministic, keyless markdown) -> wrap_html --raw (branded chrome
# + <pre>) writes the full HTML to --out and prints the plain-text alt on stdout.
python3 "$ROOT/tools/report/report.py" \
  | python3 "$ROOT/tools/brief/wrap_html.py" \
       --out "$HTML" --date "$DATE_STR" --lang "$LANG_OPT" \
       --header "Daily Market Read" --raw \
       --note "Market brief — macro · news · smart money · options (position-free)" \
  > "$TXT"

echo "[market_email] built $HTML ($(wc -c < "$HTML" | tr -d ' ') bytes) for: $LIST"

python3 "$ROOT/tools/email/send_email.py" \
  --subject "$SUBJECT" \
  ${TO_ARGS[@]+"${TO_ARGS[@]}"} \
  --html-file "$HTML" --body-file "$TXT" \
  ${DRY:+$DRY} ${PASS[@]+"${PASS[@]}"}
