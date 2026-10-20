#!/bin/bash
# NutriFit AI 开发模式：后端热重载 + 前端 Vite 开发服务器（改代码即时生效）
# 日常使用请双击「启动服务.command」（单端口，更快更稳）
#
# 注意：统一使用 ${VAR} 花括号、不使用 emoji（macOS bash 3.2 的解析限制）

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="${ROOT}/backend"
FRONTEND="${ROOT}/frontend"

# 定位 node
if ! command -v node >/dev/null 2>&1; then
  for dir in "${HOME}"/.workbuddy/binaries/node/versions/*/bin; do
    if [ -x "${dir}/node" ]; then
      PATH="${dir}:${PATH}"
      export PATH
    fi
  done
fi
if ! command -v node >/dev/null 2>&1; then
  echo "[X] 找不到 node，请先安装 Node.js 18+"
  read -n 1 -s -r -p "按任意键关闭..."
  exit 1
fi

echo "================================================"
echo "  NutriFit AI 开发模式"
echo "================================================"
echo "Node: $(node -v)"

if [ ! -x "${BACKEND}/.venv/bin/python" ]; then
  echo "[X] 缺少虚拟环境：${BACKEND}/.venv"
  read -n 1 -s -r -p "按任意键关闭..."
  exit 1
fi

if [ ! -d "${FRONTEND}/node_modules" ]; then
  echo "[X] 缺少前端依赖：${FRONTEND}/node_modules"
  echo "    请执行：cd \"${FRONTEND}\" && npm install"
  read -n 1 -s -r -p "按任意键关闭..."
  exit 1
fi

# 后端（热重载）
if lsof -nP -iTCP:8008 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[i] 后端已在运行，端口 8008"
else
  echo ">> 启动后端（--reload）..."
  ( cd "${BACKEND}" && nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8008 --reload \
      > /tmp/nutrifit_backend.log 2>&1 & )
fi

# 前端
if lsof -nP -iTCP:5175 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[i] 前端开发服务器已在运行，端口 5175"
else
  echo ">> 启动前端开发服务器 ..."
  ( cd "${FRONTEND}" && nohup npm run dev > /tmp/nutrifit_frontend.log 2>&1 & )
fi

echo ".. 等待就绪 ..."
BACK=""
FRONT=""
for i in $(seq 1 45); do
  BACK=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8008/docs" 2>/dev/null)
  FRONT=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5175" 2>/dev/null)
  if [ "${BACK}" = "200" ] && [ "${FRONT}" = "200" ]; then break; fi
  sleep 1
done

LANIP=""
for dev in en0 en1 en2; do
  ip=$(ipconfig getifaddr ${dev} 2>/dev/null)
  if [ -n "${ip}" ]; then LANIP="${ip}"; break; fi
done

echo ""
echo "  后端:  http://127.0.0.1:8008/docs   状态 ${BACK}"
echo "  前端:  http://127.0.0.1:5175        状态 ${FRONT}"
if [ -n "${LANIP}" ]; then
  echo "  手机:  http://${LANIP}:5175"
fi
echo ""
echo "  日志: /tmp/nutrifit_backend.log  /tmp/nutrifit_frontend.log"
echo "  注意: 开发模式占用两个端口，日常请用「启动服务.command」"
echo ""
echo "本窗口可以关闭，服务会继续在后台运行。"
