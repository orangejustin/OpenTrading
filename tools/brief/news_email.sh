#!/usr/bin/env bash
# news_email.sh — email a FinancialJuice NEWS DIGEST over ANY user-chosen timeframe.
#
# The live RSS feed only retains ~40 headlines, so a multi-day digest is built by merging
# the stored archive (data/news-log/) with a live fetch — see `ot news digest`. This script
# stores the current tape first (so the archive keeps growing), gathers the digest for the
# requested window, lets `claude -p` summarize it into a styled HTML brief, and emails it.
# Falls back to emailing the raw digest if claude returns nothing.
#
#   ./news_email.sh                       # default: last 7 days
#   ./news_email.sh --days 3              # any timeframe the digest accepts:
#   ./news_email.sh --minutes 1440        #   --days N | --minutes N | --since HH:MM | --window W
#   ./news_email.sh --window session
#   ./news_email.sh --to you@example.com --days 7
#   ./news_email.sh --lang zh --days 7    # write the email in Simplified Chinese (中文)
#
# Env: OT_EMAIL_MODEL=sonnet  pin a model · OT_EMAIL_RENDER_ONLY=1  render HTML, don't send
#      OT_EMAIL_HTML_OUT=path keep the rendered HTML at a fixed path (else a temp file)
#
# Educational only — not financial advice.
set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OT="$ROOT/bin/ot"
MODEL_ARG=()
[ -n "${OT_EMAIL_MODEL:-}" ] && MODEL_ARG=(--model "$OT_EMAIL_MODEL")

# Split `--to` (recipient) and `--lang` (output language) from the timeframe args;
# the rest are forwarded to `ot news digest`.
TO_ARG=(); TF=(); LANG_SEL="${OT_EMAIL_LANG:-en}"
while [ $# -gt 0 ]; do
  case "$1" in
    --to)   TO_ARG=(--to "${2:-}"); shift 2 ;;
    --lang) LANG_SEL="${2:-en}"; shift 2 ;;
    *)      TF+=("$1"); shift ;;
  esac
done
[ ${#TF[@]} -eq 0 ] && TF=(--days 7)
WINDOW_LABEL="$(printf '%s ' "${TF[@]}" | sed 's/ *$//')"

# zh/cn -> instruct Claude to write the whole email in Simplified Chinese.
LANG_INSTR=""
case "$LANG_SEL" in
  zh|cn|chinese|zh-CN|zh_CN) LANG_INSTR="IMPORTANT: Write the ENTIRE email in fluent, native Simplified Chinese (简体中文) — all prose, headings and analysis. Keep ticker symbols, company names, prices, percentages and level numbers in their original form." ;;
esac

echo "[news-email] window: $WINDOW_LABEL" >&2

# Keep the archive growing so future multi-day windows have real history.
"$OT" news store --quiet >/dev/null 2>&1 || true

# Gather the digest (archive + live, deduped). --limit 0 = no cap.
DIGEST="$("$OT" news digest "${TF[@]}" --limit 0 2>/dev/null || true)"

DATESTR="$(date '+%A %b %d, %Y')"
SUBJECT="OpenTrading — News Digest ($WINDOW_LABEL) · $(date '+%a %b %d')"
[ -n "$LANG_INSTR" ] && SUBJECT="$SUBJECT · 中文"

# Position context so the summary can flag your names (best-effort).
POS="$(OT_NO_UV=1 python3 - "$ROOT/watchlist.json" <<'PY' 2>/dev/null || true
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(", ".join(p["ticker"] for p in d.get("positions", [])))
except Exception:
    pass
PY
)"
[ -z "$POS" ] && POS="MSTR, SPCX, ORCL, HOOD"

read -r -d '' PROMPT <<PROMPT || true
You are OpenTrading, a macro-first markets analyst. Today is $DATESTR.
Below is a FinancialJuice news digest for the window: $WINDOW_LABEL. Summarize it into a
clean HTML FRAGMENT (no <html>/<head>/<body>, no markdown, no code fences — HTML only).
Use only: <p>, <h2>, <ul>/<li>, <strong>, <span class="up">, <span class="down">.

Structure:
1. <p class="regime"><strong>TAPE:</strong> one-sentence regime read of the period naming the single biggest driver and its key number.</p>
2. Group the news into 3-6 <h2> themes (Fed/Macro, Geopolitics, AI/Tech, Rates, Earnings, Crypto...). Under each, 2-4 <li> bullets — each a real headline distilled to "what happened + why it matters", citing the actual number.
3. <h2>Flags for the book</h2><ul>...</ul> — only headlines touching these positions: $POS. One <li> per affected name with the implication. If none, say so.
4. <p>Net read for risk assets over the window.</p>
5. <p class="disclaimer">Educational only — not financial advice.</p>

Rules: every bullet ties to a real item in the data; no filler; scannable.
$LANG_INSTR

NEWS DIGEST ($WINDOW_LABEL):
$DIGEST
PROMPT

BODY=""
if command -v claude >/dev/null 2>&1 && [ -n "$(printf '%s' "$DIGEST" | tr -d '[:space:]')" ]; then
  echo "[news-email] summarizing with claude${OT_EMAIL_MODEL:+ ($OT_EMAIL_MODEL)}..." >&2
  BODY="$(printf '%s' "$PROMPT" | claude -p --output-format text "${MODEL_ARG[@]}" 2>/dev/null || true)"
fi

HTML_OUT="${OT_EMAIL_HTML_OUT:-/tmp/ot_news_$$.html}"
if [ -n "$(printf '%s' "$BODY" | tr -d '[:space:]')" ]; then
  TEXT="$(printf '%s' "$BODY" | OT_NO_UV=1 PYTHONUTF8=1 python3 "$ROOT/tools/brief/wrap_html.py" \
            --out "$HTML_OUT" --date "News Digest · $WINDOW_LABEL · $DATESTR")"
else
  echo "[news-email] claude unavailable -> emailing the raw digest" >&2
  TEXT="$(printf '%s' "${DIGEST:-No headlines in window.}" | OT_NO_UV=1 PYTHONUTF8=1 python3 "$ROOT/tools/brief/wrap_html.py" --raw \
            --note "Raw FinancialJuice digest ($WINDOW_LABEL) — Claude summary unavailable this run." \
            --out "$HTML_OUT" --date "News Digest · $WINDOW_LABEL · $DATESTR")"
  SUBJECT="$SUBJECT (raw)"
fi

# Render-only mode (OT_EMAIL_RENDER_ONLY=1): write the HTML, skip the send. For testing.
if [ -n "${OT_EMAIL_RENDER_ONLY:-}" ]; then
  echo "[news-email] render-only: HTML at $HTML_OUT ($(wc -c <"$HTML_OUT" | tr -d ' ') bytes); not sent." >&2
  exit 0
fi

printf '%s' "$TEXT" | OT_NO_UV=1 PYTHONUTF8=1 python3 "$ROOT/tools/email/send_email.py" \
  --subject "$SUBJECT" --html-file "$HTML_OUT" "${TO_ARG[@]}"
rc=$?
[ -z "${OT_EMAIL_HTML_OUT:-}" ] && rm -f "$HTML_OUT"
exit $rc
