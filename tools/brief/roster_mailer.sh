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

  # meta: rid \t recipient \t lang \t owner \t positions-specs \t watch-specs
  #   specs = "code:MARKET;code:MARKET;..."  (positions);  wspecs = the 'watch' apex universe.
  META="$(OT_NO_UV=1 python3 - "$ROSTER" <<'PY' 2>/dev/null || true
import json, os, sys
d = json.load(open(sys.argv[1]))
fn = os.path.basename(sys.argv[1])
rid = fn[len("watchlist."):-len(".json")] if fn != "watchlist.json" else "own"
recip = d.get("recipient") or os.environ.get("OT_EMAIL_TO", "")
lang = d.get("lang") or "en"
owner = d.get("owner") or "You"
specs = ";".join(f"{p['ticker']}:{(p.get('market') or 'US').upper()}:{p.get('name') or p['ticker']}"
                 for p in d.get("positions", []) if p.get("ticker"))
# alpha / new-name ideas: the curated 'alpha' list (preferred), else 'watch' apex theme candidates.
_alpha = d.get("alpha") or [w for w in d.get("watch", []) if w.get("kind") == "apex"]
wspecs = ";".join(f"{a['ticker']}:{(a.get('market') or 'US').upper()}:{a.get('name') or a['ticker']}"
                  for a in _alpha if a.get("ticker"))
print("\t".join([rid, recip, lang, owner, specs, wspecs]))
PY
)"
  [ -z "$META" ] && continue
  IFS=$'\t' read -r RID RECIP RLANG OWNER SPECS WSPECS <<<"$META"
  [ -n "${OT_ROSTER_ONLY:-}" ] && [ "$RID" != "$OT_ROSTER_ONLY" ] && continue
  # market group: CN if any A-share/HK holding, else US (lets a split schedule target each)
  GROUP="US"; case ";$SPECS;" in *":A:"*|*":HK:"*) GROUP="CN" ;; esac
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
  GREP='price |>> |Buy zone|Sell zone|Buy-if|Trim|Cover|Stop/|Scenario|grade'
  PLANS=""; USTICK=""
  IFS=';' read -ra ARR <<<"$SPECS"
  for s in "${ARR[@]}"; do
    [ -z "$s" ] && continue
    code="${s%%:*}"; rest="${s#*:}"; mkt="${rest%%:*}"; name="${rest#*:}"; [ "$name" = "$mkt" ] && name=""
    PLANS+="--- $code ${name:+$name }($mkt) ---
$("$OT" decide "$code" --market "$mkt" 2>/dev/null | grep -E "$GREP" || true)
"
    [ "$mkt" = "US" ] && USTICK="$USTICK $code"
  done
  # Alpha / new-name ideas — the watch universe (apex theme candidates), same range engine.
  ALPHA=""
  IFS=';' read -ra WARR <<<"$WSPECS"
  for s in "${WARR[@]}"; do
    [ -z "$s" ] && continue
    code="${s%%:*}"; rest="${s#*:}"; mkt="${rest%%:*}"; name="${rest#*:}"; [ "$name" = "$mkt" ] && name=""
    ALPHA+="--- $code ${name:+$name }($mkt) ---
$("$OT" decide "$code" --market "$mkt" 2>/dev/null | grep -E "$GREP" || true)
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
### ALPHA / NEW-NAME IDEAS (ot decide — watch universe)
$ALPHA
### OPTIONS / DEALER GAMMA (US names only)
$OPTS"

  LANG_FLAG="en"; LANG_INSTR=""
  case "$RLANG" in
    zh|cn|zh-CN|zh_CN|chinese) LANG_FLAG="zh"
      LANG_INSTR="IMPORTANT: write the ENTIRE email in fluent native Simplified Chinese (简体中文); keep tickers/codes/numbers and the HTML tag/class NAMES exactly as-is — but the VISIBLE TEXT inside every badge MUST be Chinese, not English. Map action badges (keep the class, translate the label): <span class=\"buy\">买入</span>, <span class=\"trim\">减仓</span>, <span class=\"hold\">持有</span>, <span class=\"watch\">观察</span>, <span class=\"avoid\">回避</span>; bull/bear labels: <span class=\"bull\">看多</span>, <span class=\"bear\">看空</span>. Grade badges stay A/B/C/D. NEVER emit an English word like hold/trim/buy/watch/avoid/Bull/Bear as visible text in a Chinese email." ;;
  esac

  read -r -d '' PROMPT <<PROMPT || true
You are OpenTrading, a macro-first, risk-first analyst. Today is $DATESTR. Write a DAILY
PRE-MARKET DESK NOTE for $OWNER's portfolio as a clean HTML FRAGMENT (no <html>/<head>/<body>,
no markdown, no code fences — HTML only). TABLES for everything scannable. Use only these tags
and classes: <p>, <h2>, <ul>/<li>, <strong>, <em>, <table>/<tr>/<th>/<td>, <span class="up">,
<span class="down">, <td class="num"> (number cells, right-aligned), <td class="tk"> (ticker cell),
<span class="buy"|"trim"|"hold"|"watch"|"avoid"> (action badges), <span class="grade"> (A/B/C/D),
<p class="regime">, <p class="disclaimer">. Section order (this is the contract):

1. <p class="regime"><strong>...</strong></p> — one dark callout: the single biggest driver + its number + the read.
2. <h2>News &rarr; what it means</h2> — a 2-col <table> (Driver | Read for the book), 4-6 rows, each citing a real number.
3. <h2>Holdings — levels &amp; call</h2> — a <table>: columns Name | Last | Day | Call | Levels (buy · trim · stop) | Read.
   One row per HELD name: in the Name column use the DISPLAY NAME shown in the range-plan header (e.g. "300394 天孚通信" → show "天孚通信"), never the bare code alone; tk ticker cell, num Last/Day cells, an action badge in Call, the mechanical zones FROM THE DATA, a one-line read.
4. <h2>Alpha Watch</h2> (the 观望/watch recommendation; title in the EMAIL'S language, e.g. "今日观望 · Top 3" for zh / "Watchlist — Top 3" for en — never append a parenthetical in the other language) — the candidate pool may hold many names, but DO NOT give every candidate a row. RANK them and feature ONLY THE TOP 3 FOR TODAY (best grade / closest to buy zone / best fit for TODAY's regime) as <table> rows: Name (+theme sub-line) | Last | Day | <span class="grade">A/B/C/D</span> | Bull vs Bear | Action. For EACH of the 3: a one-line stress-test (one <span class="bull">Bull</span> line, one <span class="bear">Bear</span> line), a real letter grade, and an EXPLICIT action badge — either <span class="buy">买入 / Enter</span> when Last is AT/INSIDE its buy zone NOW, or <span class="watch">等待 / Wait</span> WITH THE EXACT buy-zone price to wait for (e.g. "等回调至 14.50–15.49"); never a vague watch with no number. Then ONE short <p> naming the remaining candidates as "也在候选池，今日不占优 / also watching, not today" — no rows for them. (Omit this section entirely if there is no candidate data.)
5. <h2>Strategy</h2> — a short <p>: the engine's top weights + cash; flag extended names to wait on.
6. <h2>The policy</h2> — a 2-col <table> (Principle | The rule): Selection &gt; timing · Ranges not points (never chase the green candle) · 0DTE QQQ done right · Risk governor · Apex lens · Event-aware. Tie one rule to today (name FOMC/CPI/OPEX if near).
7. <h2>Risk — today</h2> — a <ul> of 3 points tied to today's numbers.
8. <p class="disclaimer">Educational only — not financial advice.</p>

Rules: every claim cites a real number from the data; mark moves up/down with a span; state the "so what"; no filler.
Write every heading and word in ONE language only (the email's) — never mix Chinese and English. Separate a hold thesis
from a trade setup. The user trades ZONES, not single points. Prices are in each name's local currency (¥ A-share,
HK\$ HK, \$ US) — keep them as shown. ~500-650 words.
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
