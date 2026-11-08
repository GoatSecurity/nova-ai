#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR"

echo "====================================================================="
echo "  NOVA -- Advanced Local AI Agent and Workstation (macOS / Linux)"
echo "====================================================================="

# 1. Locate Python 3.11+
PY_BIN=""
for cand in python3 python python3.13 python3.12 python3.11; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
      PY_BIN="$cand"
      break
    fi
  fi
done

if [ -z "$PY_BIN" ]; then
  echo "[ERROR] Python 3.11 or newer is required."
  exit 1
fi

# 2. Ensure virtual environment and dependencies
if [ ! -d ".venv" ]; then
  echo "[INFO] Creating Python virtual environment in .venv ..."
  "$PY_BIN" -m venv .venv
fi

VENV_PY="$SCRIPT_DIR/.venv/bin/python"
if ! "$VENV_PY" -c "import uvicorn, fastapi, bs4, yaml" >/dev/null 2>&1; then
  echo "[INFO] Installing dependencies from requirements.txt ..."
  "$VENV_PY" -m pip install --upgrade pip >/dev/null
  "$VENV_PY" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi

# 3. Check port 46815 availability
if "$VENV_PY" -c "import socket; s=socket.socket(); r=s.connect_ex(('127.0.0.1', 46815)); s.close(); raise SystemExit(0 if r==0 else 1)" 2>/dev/null; then
  echo "[ERROR] Port 46815 is already in use. Run ./stop.sh first."
  exit 1
fi

# 4. Open browser cleanly in background
(
  sleep 2
  if command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:46815" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:46815" >/dev/null 2>&1 || true
  fi
) &

echo "[INFO] Starting NOVA Workstation on http://127.0.0.1:46815 ..."
echo "[INFO] Press Ctrl+C to gracefully stop, or run ./stop.sh."

cleanup() {
  rm -f "$SCRIPT_DIR/.nova.pid"
}
trap cleanup EXIT

"$VENV_PY" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 46815 --log-level info &
SERVER_PID=$!
echo "$SERVER_PID" > "$SCRIPT_DIR/.nova.pid"
wait "$SERVER_PID"
