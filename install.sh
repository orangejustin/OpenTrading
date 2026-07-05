#!/usr/bin/env bash
# install.sh — put the `ot` command on your PATH and health-check OpenTrading.
#
#   bash install.sh                  # symlink bin/ot -> a PATH dir, then run doctor
#   bash install.sh --doctor         # just the health check (no changes)
#   bash install.sh --with-forecast  # ALSO set up the opt-in TimesFM module
#                                    # (~2 GB torch venv — the keyless core
#                                    # never needs this; `ot forecast` only)
#
# OpenTrading is stdlib-only Python 3.9+. There is nothing to compile and no
# API keys; this script only wires the CLI onto your PATH (optionally installs
# `certifi` for TLS) so you can type `ot` from anywhere.
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
OT="$ROOT/bin/ot"
chmod +x "$OT" 2>/dev/null || true

if [ "${1:-}" = "--doctor" ] || [ "${1:-}" = "doctor" ]; then
  exec "$OT" doctor
fi

# Opt-in power module: TimesFM quantile forecasts in an ISOLATED venv, so the
# heavy torch stack can never leak into (or break) the keyless core.
if [ "${1:-}" = "--with-forecast" ]; then
  PY=python3
  if ! $PY -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
    echo "❌ TimesFM needs Python 3.10+ (core stays 3.9+). Install a newer python3 first." >&2
    exit 1
  fi
  echo "• creating .venv-forecast (isolated — the keyless core does not use it)…"
  $PY -m venv "$ROOT/.venv-forecast"
  echo "• installing timesfm[torch] (~2 GB — one time)…"
  "$ROOT/.venv-forecast/bin/pip" install --quiet --upgrade pip
  "$ROOT/.venv-forecast/bin/pip" install --quiet "timesfm[torch]" certifi
  echo "✅ TimesFM ready:  ot forecast NVDA   (first run downloads the checkpoint)"
  exit 0
fi

# 1) Python check
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 not found. Install Python 3.9+ (e.g. 'brew install python')." >&2
  exit 1
fi

# 2) certifi is optional (tools fall back to curl) — best-effort, never fatal.
if ! python3 -c "import certifi" >/dev/null 2>&1; then
  echo "• installing optional 'certifi' for TLS (falls back to curl if this fails)…"
  python3 -m pip install --user --quiet certifi >/dev/null 2>&1 || \
    echo "  (skipped — curl fallback will be used)"
fi

# 3) Put `ot` on PATH: symlink into the first writable standard bin dir.
linked=""
for d in /usr/local/bin "$HOME/.local/bin"; do
  if [ -d "$d" ] && [ -w "$d" ]; then
    ln -sf "$OT" "$d/ot" && linked="$d/ot" && break
  fi
done
if [ -z "$linked" ] && mkdir -p "$HOME/.local/bin" 2>/dev/null && [ -w "$HOME/.local/bin" ]; then
  ln -sf "$OT" "$HOME/.local/bin/ot" && linked="$HOME/.local/bin/ot"
fi

echo
if [ -n "$linked" ]; then
  echo "✅ linked  $linked  ->  bin/ot"
  case ":$PATH:" in
    *":$(dirname "$linked"):"*) : ;;
    *) echo "⚠️  $(dirname "$linked") is not on your PATH. Add it:"
       echo "     echo 'export PATH=\"$(dirname "$linked"):\$PATH\"' >> ~/.zshrc && source ~/.zshrc" ;;
  esac
else
  echo "⚠️  Couldn't symlink into a PATH dir. Either add bin/ to PATH:"
  echo "     echo 'export PATH=\"$ROOT/bin:\$PATH\"' >> ~/.zshrc && source ~/.zshrc"
  echo "   or just run it in place:  $ROOT/bin/ot"
fi

echo
"$OT" doctor || true
echo
echo "Try it:   ot            # the morning market report"
echo "          ot news --ticker MSTR"
echo "          ot help"
