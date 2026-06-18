#!/usr/bin/env bash
# roster_mailer.sh — daily multi-user roster emails.
#
# For EVERY roster (watchlist.json + watchlist.<id>.json, excluding the example),
# build one personalized pre-market email — 7-day news + per-name range execution
# plans + an engine-constructed strategy — written by `claude -p` in the roster's
# language and delivered to its recipient. Markets: US (Yahoo) and China A-share /
# HK (Yahoo .SS/.SZ/.HK, via the symbols normalizer). No tools in the claude call,
# so an unattended launchd run never hangs on a prompt; if claude is unavailable it
# falls back to emailing the raw data pack (same template).
#
# Env:
#   OT_EMAIL_RENDER_ONLY=1   render the HTML, do NOT send (safe testing)
#   OT_ROSTER_ONLY=<id|own>  process only this roster ('own' = watchlist.json)
#   OT_ROSTER_MARKET=US|CN   only US rosters, or only CN (A-share/HK) rosters (split schedules)
#   OT_EMAIL_MODEL=sonnet    pin a model for the claude synthesis
#
# Educational only — not financial advice.
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OT="$ROOT/bin/ot"
MODEL_ARG=()
[ -n "${OT_EMAIL_MODEL:-}" ] && MODEL_ARG=(--model "$OT_EMAIL_MODEL")

# Shared context (fetched once, reused for every roster).
"$OT" news store --quiet >/dev/null 2>&1 || true
NEWS7="$("$OT" news digest --days 7 2>/dev/null | head -90 || true)"
MACRO="$("$OT" macro 2>/dev/null || true)"
SMART="$("$OT" smart 2>/dev/null || true)"
DATESTR="$(date '+%A %b %d, %Y')"

shopt -s nullglob
for ROSTER in "$ROOT/watchlist.json" "$ROOT"/watchlist.*.json; do
  base="$(basename "$ROSTER")"
  [ "$base" = "watchlist.example.json" ] && continue
  [ -f "$ROSTER" ] || continue

  # meta: rid \t recipient \t lang \t owner \t "code:MARKET;code:MARKET;..."
  META="$(OT_NO_UV=1 python3 - "$ROSTER" <<'PY' 2>/dev/null || true
import json, os, sys
d = json.load(open(sys.argv[1]))
fn = os.path.basename(sys.argv[1])
rid = fn[len("watchlist."):-len(".json")] if fn != "watchlist.json" else "own"
recip = d.get("recipient") or os.environ.get("OT_EMAIL_TO", "")
lang = d.get("lang") or "en"
owner = d.get("owner") or "You"
specs = ";".join(f"{p['ticker']}:{(p.get('market') or 'US').upper()}"
                 for p in d.get("positions", []) if p.get("ticker"))
print("\t".join([rid, recip, lang, owner, specs]))
PY
)"
  [ -z "$META" ] && continue
  IFS=$'\t' read -r RID RECIP RLANG OWNER SPECS <<<"$META"
  [ -n "${OT_ROSTER_ONLY:-}" ] && [ "$RID" != "$OT_ROSTER_ONLY" ] && continue
  # market group: CN if any A-share/HK holding, else US (lets a split schedule target each)
  GROUP="US"; case ";$SPECS;" in *":A;"*|*":HK;"*) GROUP="CN" ;; esac
  if [ -n "${OT_ROSTER_MARKET:-}" ]; then
    case "$OT_ROSTER_MARKET" in
      US|us) [ "$GROUP" = "US" ] || continue ;;
      CN|cn|A|HK|"A,HK"|"a,hk") [ "$GROUP" = "CN" ] || continue ;;
    esac
  fi
  if [ -z "$RECIP" ]; then echo "[roster] $base: no recipient — skipped" >&2; continue; fi
  echo "[roster] $OWNER <$RECIP> lang=$RLANG group=$GROUP ($base)" >&2

  # Engine-constructed strategy + per-name range plans.
  if [ "$RID" = "own" ]; then STRAT="$("$OT" strategy 2>/dev/null || true)"
  else STRAT="$("$OT" strategy --roster "$RID" 2>/dev/null || true)"; fi
  PLANS=""; USTICK=""
  IFS=';' read -ra ARR <<<"$SPECS"
  for s in "${ARR[@]}"; do
    [ -z "$s" ] && continue
    code="${s%%:*}"; mkt="${s##*:}"
    PLANS+="--- $code ($mkt) ---
$("$OT" decide "$code" --market "$mkt" 2>/dev/null | grep -E 'price |>> |Buy zone|Sell zone|Buy-if|Trim|Cover|Stop/|Scenario' || true)
"
    [ "$mkt" = "US" ] && USTICK="$USTICK $code"
  done
  OPTS=""
  [ -n "$USTICK" ] && OPTS="$("$OT" options SPY $USTICK --dte 7 2>/dev/null || true)"

  DATA="### OWNER: $OWNER
### 7-DAY NEWS DIGEST (FinancialJuice)
$NEWS7
### MACRO (rates / liquidity)
$MACRO
### SMART MONEY (Fear&Greed, BTC funding)
$SMART
### ENGINE-CONSTRUCTED STRATEGY (ot strategy)
$STRAT
### PER-NAME RANGE PLANS (ot decide — local currency)
$PLANS
### OPTIONS / DEALER GAMMA (US names only)
$OPTS"

  LANG_FLAG="en"; LANG_INSTR=""
  case "$RLANG" in
    zh|cn|zh-CN|zh_CN|chinese) LANG_FLAG="zh"
      LANG_INSTR="IMPORTANT: write the ENTIRE email in fluent native Simplified Chinese (简体中文); keep tickers/codes/numbers and the HTML tags/class names exactly as-is." ;;
  esac

  read -r -d '' PROMPT <<PROMPT || true
You are OpenTrading, a macro-first, risk-first analyst. Today is $DATESTR. Write a DAILY
PRE-MARKET email for $OWNER's portfolio as a clean HTML FRAGMENT (no <html>/<head>/<body>,
no markdown, no code fences — HTML only). Use only: <p>, <h2>, <ul>/<li>, <strong>,
<span class="up">, <span class="down">, <p class="regime">, <p class="disclaimer">. Order:

1. <p class="regime"><strong>...</strong> one-sentence regime naming the single biggest driver + its number.</p>
2. <h2>News (7d)</h2><ul> 4-6 of the 7-day headlines MOST relevant to THESE holdings; each li = headline + implication for the name(s) it touches.</ul>
3. <h2>Holdings</h2><ul> per held name: the range execution plan FROM THE DATA — buy/建仓 zone, trim/止盈, stop/止损 — plus a one-line read. The user trades ZONES, not single points; mark up/down with span.</ul>
4. <h2>Strategy</h2><p> summarize the engine-constructed allocation (top weights + cash); flag extended names to wait on.</p>
5. <h2>Risk</h2><ul> 3 discipline points tied to today's data.</ul>
6. <p class="disclaimer">Educational only — not financial advice.</p>

Rules: every claim cites a real number from the data; state the "so what"; no filler. Prices are
in each name's local currency (¥ A-share, HK\$ HK, \$ US) — keep them as shown. ~450-650 words.
$LANG_INSTR

DATA:
$DATA
PROMPT

  BODY=""
  if command -v claude >/dev/null 2>&1; then
    echo "[roster] $OWNER: synthesizing with claude${OT_EMAIL_MODEL:+ ($OT_EMAIL_MODEL)}..." >&2
    BODY="$(printf '%s' "$PROMPT" | claude -p --output-format text "${MODEL_ARG[@]}" 2>/dev/null || true)"
  fi

  HTML="/tmp/ot_roster_${RID}_$$.html"
  HDR="$([ "$LANG_FLAG" = zh ] && echo "盘前策略" || echo "Pre-Market Read")"
  if [ -n "$(printf '%s' "$BODY" | tr -d '[:space:]')" ]; then
    TEXT="$(printf '%s' "$BODY" | OT_NO_UV=1 python3 "$ROOT/tools/brief/wrap_html.py" \
              --out "$HTML" --lang "$LANG_FLAG" --header "$HDR" --date "$DATESTR · $OWNER")"
  else
    echo "[roster] $OWNER: claude unavailable -> raw data pack" >&2
    TEXT="$(printf '%s' "$DATA" | OT_NO_UV=1 python3 "$ROOT/tools/brief/wrap_html.py" --raw \
              --note "Raw OpenTrading data (claude synthesis unavailable)" \
              --out "$HTML" --lang "$LANG_FLAG" --header "$HDR" --date "$DATESTR · $OWNER")"
  fi

  if [ "$LANG_FLAG" = zh ]; then SUBJ="OpenTrading 盘前策略与资讯（中文）· $(date '+%m/%d')"
  else SUBJ="OpenTrading — Pre-Market Read · $(date '+%a %b %d')"; fi

  if [ -n "${OT_EMAIL_RENDER_ONLY:-}" ]; then
    echo "[roster] $OWNER: render-only -> $HTML ($(wc -c <"$HTML" | tr -d ' ') bytes), not sent." >&2
    continue
  fi
  printf '%s' "$TEXT" | OT_NO_UV=1 python3 "$ROOT/tools/email/send_email.py" \
    --subject "$SUBJ" --to "$RECIP" --html-file "$HTML" || echo "[roster] $OWNER: send failed" >&2
  rm -f "$HTML"
done
