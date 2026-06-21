#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

mkdir -p .pids

echo "==> Starting Redis nodes"
if docker info >/dev/null 2>&1; then
  docker compose up -d
  echo "    Using Docker Compose (redis-0/1/2)"
else
  echo "    Docker unavailable; trying local redis-server instances"
  chmod +x scripts/start_redis_local.sh
  scripts/start_redis_local.sh || echo "    WARNING: Could not start Redis. Cache will be disabled."
fi

echo "==> Waiting for Redis"
sleep 2

if [ ! -d ".venv" ]; then
  echo "==> Creating Python virtual environment"
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

if [ ! -d "frontend/node_modules" ]; then
  echo "==> Installing frontend dependencies"
  (cd frontend && npm install)
fi

echo "==> Ingesting dataset if needed"
.venv/bin/python backend/scripts/ingest.py

if [ -f ".pids/backend.pid" ] && kill -0 "$(cat .pids/backend.pid)" 2>/dev/null; then
  echo "==> Restarting backend (pick up Redis connections)"
  kill "$(cat .pids/backend.pid)" 2>/dev/null || true
  rm -f .pids/backend.pid
fi

if [ ! -f ".pids/backend.pid" ] || ! kill -0 "$(cat .pids/backend.pid)" 2>/dev/null; then
  echo "==> Starting backend on http://localhost:8000"
  .venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > .pids/backend.log 2>&1 &
  echo $! > .pids/backend.pid
fi

if [ ! -f ".pids/frontend.pid" ] || ! kill -0 "$(cat .pids/frontend.pid)" 2>/dev/null; then
  echo "==> Starting frontend on http://localhost:5173"
  (cd frontend && npm run dev -- --host 127.0.0.1 --port 5173) > ../.pids/frontend.log 2>&1 &
  echo $! > .pids/frontend.pid
fi

echo
echo "Typeahead system is starting (allow ~45s for trie build on first backend start)."
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo "  Test guide: docs/HOW-TO-TEST.md"
echo
echo "Verify cache: curl -s http://localhost:8000/health | python3 -m json.tool"
echo
echo "Logs:"
echo "  tail -f .pids/backend.log"
echo "  tail -f .pids/frontend.log"
