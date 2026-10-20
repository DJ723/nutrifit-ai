#!/bin/bash
# NutriFit AI 一键启动脚本（macOS）—— 单端口生产模式
# 后端 :8008 同时托管前端页面，手机连同一 WiFi 即可访问
# 双击运行即可
#
# 两条重要经验（改脚本前请先读）：
# 1) macOS 自带 bash 3.2，字符串里 "$VAR" 后若紧跟全角字符，会把多字节字节
#    吞进变量名导致 unbound variable。因此统一用 ${VAR}，且不用 emoji。
# 2) 用双重 fork + setsid 启动守护进程，而不是 nohup &：
#    这样进程直接挂到系统 init 下，关掉本窗口也绝不会被带走。

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="${ROOT}/backend"
DIST="${ROOT}/frontend/dist"
PORT=8008
LOG=/tmp/nutrifit_backend.log

echo "================================================"
echo "  NutriFit AI 启动中"
echo "================================================"

# --- 检查虚拟环境 ---
if [ ! -x "${BACKEND}/.venv/bin/python" ]; then
  echo "[X] 缺少 Python 虚拟环境：${BACKEND}/.venv"
  echo "    请先执行："
  echo "    cd \"${BACKEND}\" && python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-min.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
  read -n 1 -s -r -p "按任意键关闭..."
  exit 1
fi

# --- 检查前端构建产物 ---
if [ ! -f "${DIST}/index.html" ]; then
  echo "[!] 未找到前端构建产物（frontend/dist），本次只提供接口。"
  echo "    如需页面，请执行：cd \"${ROOT}/frontend\" && npm run build"
  echo ""
fi

# --- 接管已有实例 ---
if lsof -nP -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[i] 检测到端口 ${PORT} 已有实例，正在接管 ..."
  pkill -f "uvicorn app.main:app" 2>/dev/null
  sleep 2
fi

# --- 启动守护进程（双重 fork + setsid，脱离当前终端会话）---
echo ">> 启动服务 ..."
"${BACKEND}/.venv/bin/python" - "${BACKEND}" "${PORT}" "${LOG}" <<'PY'
import os, sys

backend, port, log_path = sys.argv[1], sys.argv[2], sys.argv[3]

# 第一次 fork：父进程立刻退出，让调用方（bash）继续往下走
if os.fork() > 0:
    sys.exit(0)
os.setsid()           # 脱离控制终端
# 第二次 fork：确保不会被重新获得终端
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

# --- 等待就绪 ---
echo ".. 等待就绪 ..."
OK=""
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/" 2>/dev/null)
  if [ "${code}" = "200" ]; then OK=1; break; fi
  sleep 1
done

# --- 获取局域网 IP ---
LANIP=""
for dev in en0 en1 en2; do
  ip=$(ipconfig getifaddr ${dev} 2>/dev/null)
  if [ -n "${ip}" ]; then LANIP="${ip}"; break; fi
done
if [ -z "${LANIP}" ]; then
  LANIP=$(ipconfig getifaddr bridge0 2>/dev/null)
fi

echo ""
if [ -n "${OK}" ]; then
  echo "[OK] 启动成功（守护进程，关掉本窗口不受影响）"
else
  echo "[X] 启动失败，日志末尾："
  tail -20 "${LOG}" 2>/dev/null
  read -n 1 -s -r -p "按任意键关闭..."
  exit 1
fi

echo ""
echo "  电脑访问:  http://127.0.0.1:${PORT}"
if [ -n "${LANIP}" ]; then
  echo "  手机访问:  http://${LANIP}:${PORT}"
  echo "             手机需连同一 WiFi，浏览器可添加到主屏幕"
else
  echo "  手机访问:  未检测到局域网 IP，请确认已连 WiFi"
fi
echo "  接口文档:  http://127.0.0.1:${PORT}/docs"
echo ""
echo "  日志: ${LOG}"
echo "  停止: 双击「停止服务.command」"
echo ""

if [ -n "${LANIP}" ]; then
  open "http://${LANIP}:${PORT}" 2>/dev/null
else
  open "http://127.0.0.1:${PORT}" 2>/dev/null
fi

echo "本窗口可以关闭。"
