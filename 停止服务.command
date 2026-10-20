#!/bin/bash
# 停止 NutriFit AI 服务（后端 8008 与可选的开发服务器 5175）
# 注意：统一使用 ${VAR} 花括号、不使用 emoji（macOS bash 3.2 的解析限制）

echo "停止中 ..."
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "node_modules/.bin/vite" 2>/dev/null
pkill -f "NutriFit_AI_健康轻食营养顾问平台/frontend" 2>/dev/null
sleep 2

if lsof -nP -iTCP:8008 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[!] 8008 仍被占用："
  lsof -nP -iTCP:8008 -sTCP:LISTEN
else
  echo "[OK] 后端已停止，端口 8008"
fi

if lsof -nP -iTCP:5175 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[!] 5175 仍被占用："
  lsof -nP -iTCP:5175 -sTCP:LISTEN
else
  echo "[OK] 开发服务器已停止，端口 5175"
fi
