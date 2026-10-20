#!/bin/bash
# 重启 NutriFit AI 后端（改完 config.yaml 后用这个）
# 采用双重 fork + setsid 守护进程方式，关掉窗口不受影响
# 注意：统一使用 ${VAR} 花括号、不使用 emoji（macOS bash 3.2 的解析限制）

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="${ROOT}/backend"
PORT=8008
LOG=/tmp/nutrifit_backend.log

echo "停止旧后端 ..."
pkill -f "uvicorn app.main:app" 2>/dev/null
sleep 2

if [ ! -x "${BACKEND}/.venv/bin/python" ]; then
  echo "[X] 缺少虚拟环境：${BACKEND}/.venv"
  read -n 1 -s -r -p "按任意键关闭..."
  exit 1
fi

echo "启动新后端 ..."
"${BACKEND}/.venv/bin/python" - "${BACKEND}" "${PORT}" "${LOG}" <<'PY'
import os, sys

backend, port, log_path = sys.argv[1], sys.argv[2], sys.argv[3]

if os.fork() > 0:
    sys.exit(0)
os.setsid()
if os.fork() > 0:
    sys.exit(0)

os.chdir(backend)

fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
devnull = os.open("/dev/null", os.O_RDONLY)
os.dup2(devnull, 0)
os.dup2(fd, 1)
os.dup2(fd, 2)

os.execv(".venv/bin/uvicorn",
         ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port])
PY

CODE=""
for i in $(seq 1 30); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/docs" 2>/dev/null)
  if [ "${CODE}" = "200" ]; then break; fi
  sleep 1
done

LANIP=""
for dev in en0 en1 en2; do
  ip=$(ipconfig getifaddr ${dev} 2>/dev/null)
  if [ -n "${ip}" ]; then LANIP="${ip}"; break; fi
done

echo ""
if [ "${CODE}" = "200" ]; then
  echo "[OK] 后端已重启：http://127.0.0.1:${PORT}/docs"
  if [ -n "${LANIP}" ]; then
    echo "     手机访问：http://${LANIP}:${PORT}"
  fi
  echo ""
  echo "当前模型配置："
  curl -s "http://127.0.0.1:${PORT}/api/config/public" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('  Base URL  :', d['base_url'])
print('  对话模型  :', d['chat_model'])
print('  视觉模型  :', d['vision_model'])
print('  API Key   :', '已配置' if d['has_api_key'] else '未配置')
" 2>/dev/null
  echo ""
  echo "请到浏览器按 Cmd+R 刷新页面，设置页才会显示最新状态"
else
  echo "[X] 启动失败，最后 15 行日志："
  tail -15 "${LOG}"
fi

echo ""
read -n 1 -s -r -p "按任意键关闭窗口..."
