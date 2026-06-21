#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ -f ".pids/backend.pid" ]; then
  kill "$(cat .pids/backend.pid)" 2>/dev/null || true
  rm -f .pids/backend.pid
fi

if [ -f ".pids/frontend.pid" ]; then
  kill "$(cat .pids/frontend.pid)" 2>/dev/null || true
  rm -f .pids/frontend.pid
fi

pkill -f "uvicorn backend.app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true

docker compose down 2>/dev/null || true

echo "Stopped local typeahead services."
