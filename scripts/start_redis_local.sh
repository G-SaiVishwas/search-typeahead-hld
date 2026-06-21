#!/usr/bin/env bash
# Start three standalone Redis instances on ports 6379, 6380, 6381 (no Docker).
set -euo pipefail

if ! command -v redis-server >/dev/null 2>&1; then
  echo "redis-server not found. Install with: brew install redis"
  exit 1
fi

start_one() {
  local port="$1"
  if redis-cli -p "$port" ping >/dev/null 2>&1; then
    echo "Redis already running on port $port"
    return
  fi
  redis-server --port "$port" --save "" --appendonly no --daemonize yes
  echo "Started redis-server on port $port"
}

start_one 6379
start_one 6380
start_one 6381

echo "All local Redis nodes ready."
