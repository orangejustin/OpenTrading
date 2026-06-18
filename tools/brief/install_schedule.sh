#!/usr/bin/env bash
# Install (or remove) an OpenTrading daily launchd schedule on macOS.
#
#   ./install_schedule.sh                  # notify job: weekdays 05:30 local (08:30 ET)
#   ./install_schedule.sh 6 0              # notify job: weekdays 06:00 local
#   ./install_schedule.sh uninstall        # remove the notify job
#
#   ./install_schedule.sh email            # EMAIL job: weekdays 03:00 local (= 06:00 ET on PT)
#   ./install_schedule.sh email 3 0        # EMAIL job at a specific local time
#   ./install_schedule.sh email uninstall  # remove the email job
#
#   ./install_schedule.sh roster           # MULTI-USER: ALL rosters, one slot (05:00 local)
#   ./install_schedule.sh roster us        # US rosters only (05:00 local)
#   ./install_schedule.sh roster cn 16 0   # A-share/HK rosters only (16:00 local = ~07:00 China)
#   ./install_schedule.sh roster us uninstall   # remove a group's job
#
# notify job -> report.py --notify --save  (writes data/reports/<date>.md + macOS banner)
# email  job -> bin/ot email               (emails the report via SMTP; creds in .env)
# launchd runs missed calendar jobs on next wake.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# --- mode: "email" as first arg switches to the email job ----------------------
MODE="notify"
case "${1:-}" in email) MODE="email"; shift ;; roster) MODE="roster"; shift ;; esac
ROSTER_GROUP=""
if [ "$MODE" = "roster" ]; then
  case "${1:-}" in us|US) ROSTER_GROUP="US"; shift ;; cn|CN) ROSTER_GROUP="CN"; shift ;; esac
fi

if [ "$MODE" = "email" ]; then
  LABEL="com.opentrading.dailyemail"
  DEF_HOUR=8; DEF_MIN=30         # 08:30 local (Seattle/PT) — in the inbox before a 9am wake
elif [ "$MODE" = "roster" ]; then
  if [ "$ROSTER_GROUP" = "US" ]; then
    LABEL="com.opentrading.rostermail.us"; DEF_HOUR=5; DEF_MIN=0    # US pre-market
  elif [ "$ROSTER_GROUP" = "CN" ]; then
    LABEL="com.opentrading.rostermail.cn"; DEF_HOUR=16; DEF_MIN=0   # 16:00 PT = ~07:00 China, A/HK pre-open
  else
    LABEL="com.opentrading.rostermail"; DEF_HOUR=5; DEF_MIN=0       # all rosters, one slot
  fi
else
  LABEL="com.opentrading.dailybrief"
  DEF_HOUR=5; DEF_MIN=30         # 05:30 PT == 08:30 ET
fi
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${1:-}" = "uninstall" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Removed $LABEL"
  exit 0
fi

HOUR="${1:-$DEF_HOUR}"; MIN="${2:-$DEF_MIN}"   # local wall-clock
LOG="$ROOT/data/briefs/_launchd.log"
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/data/briefs"

# Runner: prefer uv (absolute path — launchd has a minimal PATH). uv runs a
# standalone CPython, which avoids the python.org framework "Python.app" startup
# hang under launchd. Fall back to Apple's /usr/bin/python3 when uv is absent.
UV="$(command -v uv || true)"
if [ -n "$UV" ] && [ -z "${OT_NO_UV:-}" ]; then
  RUNNER_DESC="uv run --no-project (standalone CPython)"
  RUNNER_PATH="$(dirname "$UV"):$HOME/.local/bin:"
else
  RUNNER_DESC="python3"
  RUNNER_PATH=""
fi

if [ "$MODE" = "email" ] || [ "$MODE" = "roster" ]; then
  # Claude-written email(s): gather data -> claude -p synthesizes -> SMTP.
  # launchd has a minimal PATH, so add the dirs holding claude/uv/node/python3.
  for b in claude uv node python3; do
    d="$(dirname "$(command -v "$b" 2>/dev/null)" 2>/dev/null)"
    [ -n "$d" ] && case ":$RUNNER_PATH:" in *":$d:"*) ;; *) RUNNER_PATH="${RUNNER_PATH}${d}:" ;; esac
  done
  if [ "$MODE" = "roster" ]; then
    PROG_ARGS="<string>/bin/bash</string><string>$ROOT/tools/brief/roster_mailer.sh</string>"
    JOB_DESC="roster_mailer.sh  (every roster: 7d news + strategy -> claude -p -> SMTP)"
  else
    PROG_ARGS="<string>/bin/bash</string><string>$ROOT/tools/brief/daily_email_claude.sh</string>"
    JOB_DESC="daily_email_claude.sh  (gather -> claude -p -> SMTP)"
  fi
  RUNNER_DESC="claude -p (headless) + SMTP"
else
  SCRIPT="$ROOT/tools/report/report.py"
  if [ -n "$UV" ] && [ -z "${OT_NO_UV:-}" ]; then
    PROG_ARGS="<string>$UV</string><string>run</string><string>--no-project</string><string>$SCRIPT</string><string>--notify</string><string>--save</string>"
  else
    if [ -x /usr/bin/python3 ]; then PY="/usr/bin/python3"; else PY="$(command -v python3)"; fi
    RUNNER_DESC="$PY"
    PROG_ARGS="<string>$PY</string><string>$SCRIPT</string><string>--notify</string><string>--save</string>"
  fi
  JOB_DESC="$SCRIPT --notify --save"
fi

intervals=""
for wd in 1 2 3 4 5; do
  intervals+="    <dict><key>Weekday</key><integer>$wd</integer><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MIN</integer></dict>
"
done
ENV_EXTRA=""
[ -n "$ROSTER_GROUP" ] && ENV_EXTRA="<key>OT_ROSTER_MARKET</key><string>$ROSTER_GROUP</string>"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>$PROG_ARGS</array>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>${RUNNER_PATH}/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>${ENV_EXTRA}</dict>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>StartCalendarInterval</key>
  <array>
$intervals  </array>
</dict>
</plist>
PLIST

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"
echo "Installed $LABEL"
echo "  schedule : Mon-Fri ${HOUR}:$(printf '%02d' "$MIN") local"
echo "  job      : $JOB_DESC"
echo "  runner   : $RUNNER_DESC"
echo "  log      : $LOG"
if [ "$MODE" != "notify" ]; then
  echo "  note     : needs a configured .env (see tools/email/README.md)"
  [ "$MODE" = "roster" ] && echo "  rosters  : watchlist.json + watchlist.<id>.json -> each its own recipient/lang; supersedes the single-user job (remove it: ./install_schedule.sh email uninstall)"
fi
echo "  TCC      : launchd cannot read ~/Desktop|~/Documents|~/Downloads — move the"
echo "             repo out of those, or grant the runner Full Disk Access."
RM="${MODE/notify/}"; [ "$MODE" = roster ] && [ -n "$ROSTER_GROUP" ] && RM="roster $(printf %s "$ROSTER_GROUP" | tr 'A-Z' 'a-z')"
echo "  remove   : ./install_schedule.sh $RM uninstall"
