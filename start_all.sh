#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "[start] 启动后端: http://127.0.0.1:8000"
uv run uvicorn api:app --reload --port 8000 &
BACKEND_PID=$!

echo "[start] 启动前端: http://127.0.0.1:5173"
(
  cd frontend
  npm run dev
) &
FRONTEND_PID=$!

cleanup() {
  echo
  echo "[stop] 正在停止前后端..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  echo "[stop] 已全部退出"
}

trap cleanup INT TERM EXIT

# 兼容 macOS 自带 bash(3.2)：不用 wait -n，改为轮询任一子进程是否退出
EXIT_CODE=0
while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID" 2>/dev/null || EXIT_CODE=$?
    break
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID" 2>/dev/null || EXIT_CODE=$?
    break
  fi
  sleep 1
done

if [ "$EXIT_CODE" -ne 0 ]; then
  echo "[warn] 有子进程异常退出，退出码: $EXIT_CODE"
fi

exit "$EXIT_CODE"
