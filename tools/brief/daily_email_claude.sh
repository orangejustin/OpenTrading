#!/usr/bin/env bash
# daily_email_claude.sh — the autonomous, Claude-written morning email.
#
# Architecture (robust for an unattended launchd job):
#   1. bash gathers live data deterministically from the OpenTrading CLIs
#      (macro + smart-money + 24h news + quotes + options/GEX + BTC), position-aware.
#   2. `claude -p` reasons over that data and writes the analysis as an HTML
#      fragment — with NO tools, so there are no permission prompts to hang a run.
#   3. wrap_html.py renders it into a styled, Outlook-safe HTML brief (+ a plain-text
#      alternative); send_email.py delivers the multipart message via SMTP (.env creds).
# If Claude is unavailable or returns nothing, it falls back to emailing the raw
# data pack (same template) so you still get *something*.
#
# Env: OT_EMAIL_MODEL=sonnet  pin a model · OT_EMAIL_RENDER_ONLY=1  render HTML, don't send
#      OT_EMAIL_HTML_OUT=path keep the rendered HTML at a fixed path (else a temp file)
#      OT_EMAIL_LANG=zh       write the brief in Simplified Chinese (中文)
#
#   ./daily_email_claude.sh                 # gather -> synthesize -> email (uses OT_EMAIL_TO)
#   ./daily_email_claude.sh you@example.com # override recipient
#   OT_EMAIL_MODEL=sonnet ./daily_email_claude.sh   # pin a cheaper model
#
# Educational only — not financial advice.
set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OT="$ROOT/bin/ot"
TO_ARG=()
[ -n "${1:-}" ] && TO_ARG=(--to "$1")
MODEL_ARG=()
[ -n "${OT_EMAIL_MODEL:-}" ] && MODEL_ARG=(--model "$OT_EMAIL_MODEL")

# Language: OT_EMAIL_LANG=zh -> Claude writes the brief in Simplified Chinese (HTML tags stay English).
LANG_INSTR=""
case "${OT_EMAIL_LANG:-en}" in
  zh|cn|chinese|zh-CN|zh_CN) LANG_INSTR="IMPORTANT: Write the ENTIRE brief in fluent, native Simplified Chinese (简体中文) — all prose, headings and analysis. Keep tickers, company names, prices, percentages and level numbers in their original form, and keep the HTML tags and class names exactly as specified (in English)." ;;
esac

# Positions for the prompt (read from watchlist.json; fall back to a literal list).
POS="$(OT_NO_UV=1 python3 - "$ROOT/watchlist.json" <<'PY' 2>/dev/null || true
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(", ".join(f"{p.get('shares','?')} {p['ticker']}" for p in d.get("positions", [])))
except Exception:
    pass
PY
)"
[ -z "$POS" ] && POS="300 MSTR, 80 SPCX, 400 ORCL, 100 HOOD"
# Bare ticker list for quote/options calls.
TICKERS="$(printf '%s' "$POS" | sed -E 's/[0-9]+ //g; s/,//g')"

echo "[daily-email] gathering data for: $POS" >&2

# Accrue the news archive so `ot news digest --days N` builds real multi-day history.
"$OT" news store --quiet >/dev/null 2>&1 || true

# --- 1. Gather (best-effort; each tool is allowed to fail without killing the run) ---
DATA="$(
  echo "### YOUR POSITIONS — live quotes"; "$OT" watch 2>/dev/null || true
  echo; echo "### VIX"; "$OT" quote '^VIX' 2>/dev/null || true
  echo; echo "### MACRO (rates / liquidity -> scored bias)"; "$OT" macro 2>/dev/null || true
  echo; echo "### SMART MONEY (Fear&Greed, BTC funding — contrarian)"; "$OT" smart 2>/dev/null || true
  echo; echo "### OPTIONS / DEALER GAMMA (GEX, walls)"; "$OT" options SPY $TICKERS --dte 7 2>/dev/null || true
  echo; echo "### NEWS — FinancialJuice, last 24h"; "$OT" news --minutes 1440 2>/dev/null | head -70 || true
  echo; echo "### BTC spot"; curl -sS --max-time 15 "https://api.coinbase.com/v2/prices/BTC-USD/spot" 2>/dev/null || true
)"

DATESTR="$(date '+%A %b %d, %Y')"
SUBJECT="OpenTrading — Pre-Market Read · $(date '+%a %b %d')"
[ -n "$LANG_INSTR" ] && SUBJECT="$SUBJECT · 中文"

# --- 2. Synthesize with Claude (no tools; data in -> HTML fragment out) ---
read -r -d '' PROMPT <<PROMPT || true
You are OpenTrading, a macro-first, risk-first short-term trading analyst. Today is $DATESTR.
Below is live pre-market data from the OpenTrading CLIs for this portfolio: $POS.

Write a position-aware PRE-MARKET BRIEF as a clean HTML FRAGMENT (no <html>/<head>/<body>, no
markdown, no code fences — output HTML only). Use only: <p>, <h2>, <table>/<thead>/<tbody>/<tr>/<th>/<td>,
<ul>/<li>, <strong>, <span>. Structure it EXACTLY in this order:

1. <p class="regime"><strong>REGIME:</strong> risk-on / risk-off / mixed — one sentence naming the single
   biggest driver right now, with its key number.</p>
2. A positions table ordered by DOLLAR exposure (shares x last price), highest first. Columns:
   Ticker, Shares, Last, \$ Exposure, Weight %, Driver, Today's read. Compute \$ Exposure and Weight % from
   the live quotes in the data (weights sum to ~100%). Keep "Today's read" to 8 words max. Mark a clearly
   up/down move with <span class="up"> or <span class="down">.
3. <h2>Macro</h2><p>...</p> — rates & liquidity into a directional bias; cite the real SOFR / 2s10s /
   TGA / RRP numbers and what they imply.
4. <h2>Smart money</h2><p>...</p> — CNN + crypto Fear&Greed and BTC funding; the contrarian read with the
   actual readings.
5. <h2>Options &amp; dealer gamma (EV)</h2><p>...</p> — SPY and the position names: the GEX sign and the
   gamma walls/levels. Positive GEX = vol-suppressing / pins toward the wall; negative = trend-amplifying.
   Name the levels.
6. <h2>News — last 24h</h2><ul>...</ul> — the 3-5 headlines most relevant to THIS book; each <li> =
   headline + the implication for the position(s) it touches.
7. <h2>Concentration &amp; correlation</h2><p>...</p> — name the dominant factor and quantify it (e.g.
   "BTC beta via MSTR+HOOD = NN% of book"); flag the main single-factor risk.
8. <h2>Watch today</h2><ul>...</ul> — 4-5 specific, actionable items with levels, times, or catalysts.
9. <p class="disclaimer">Educational only — not financial advice.</p>

Rules: every claim cites a real number from the data and states the "so what" — no filler, no hedging
boilerplate. Reason rigorously: connect macro -> book -> action. ~400-550 words.
$LANG_INSTR

DATA:
$DATA
PROMPT

BODY=""
if command -v claude >/dev/null 2>&1; then
  echo "[daily-email] synthesizing with claude${OT_EMAIL_MODEL:+ ($OT_EMAIL_MODEL)}..." >&2
  BODY="$(printf '%s' "$PROMPT" | claude -p --output-format text "${MODEL_ARG[@]}" 2>/dev/null || true)"
fi

# --- 3. Render a styled HTML email (+ plain-text alternative). Falls back to the
#        raw data pack — still wrapped in the template — if Claude gave nothing. ---
HTML_OUT="${OT_EMAIL_HTML_OUT:-/tmp/ot_email_$$.html}"
if [ -n "$(printf '%s' "$BODY" | tr -d '[:space:]')" ]; then
  TEXT="$(printf '%s' "$BODY" | OT_NO_UV=1 python3 "$ROOT/tools/brief/wrap_html.py" \
            --out "$HTML_OUT" --date "$DATESTR")"
else
  echo "[daily-email] claude unavailable -> emailing raw data pack" >&2
  TEXT="$(printf '%s' "$DATA" | OT_NO_UV=1 python3 "$ROOT/tools/brief/wrap_html.py" --raw \
            --note "Claude synthesis was unavailable this run — raw OpenTrading data below." \
            --out "$HTML_OUT" --date "$DATESTR")"
  SUBJECT="$SUBJECT (data pack)"
fi

# Render-only mode (OT_EMAIL_RENDER_ONLY=1): write the HTML, skip the send. For testing.
if [ -n "${OT_EMAIL_RENDER_ONLY:-}" ]; then
  echo "[daily-email] render-only: HTML at $HTML_OUT ($(wc -c <"$HTML_OUT" | tr -d ' ') bytes); not sent." >&2
  exit 0
fi

# --- 4. Email: plain-text body + HTML alternative (multipart/alternative) ---
printf '%s' "$TEXT" | OT_NO_UV=1 python3 "$ROOT/tools/email/send_email.py" \
  --subject "$SUBJECT" --html-file "$HTML_OUT" "${TO_ARG[@]}"
rc=$?
[ -z "${OT_EMAIL_HTML_OUT:-}" ] && rm -f "$HTML_OUT"
exit $rc
