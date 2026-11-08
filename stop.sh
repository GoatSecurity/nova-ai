#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Stopping NOVA Workstation on port 46815..."

if [ -f "$SCRIPT_DIR/.nova.pid" ]; then
  PID="$(cat "$SCRIPT_DIR/.nova.pid" || true)"
  if [ -n "$PID" ] && kill -0 "$PID" >/dev/null 2>&1; then
    kill "$PID" >/dev/null 2>&1 || true
    sleep 1
    kill -9 "$PID" >/dev/null 2>&1 || true
  fi
  rm -f "$SCRIPT_DIR/.nova.pid"
fi

if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti:46815 || true)"
  if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs kill -9 >/dev/null 2>&1 || true
  fi
elif command -v fuser >/dev/null 2>&1; then
  fuser -k 46815/tcp >/dev/null 2>&1 || true
else
  pkill -f "uvicorn backend.app.main:app" >/dev/null 2>&1 || true
fi

echo "NOVA workstation stopped."
