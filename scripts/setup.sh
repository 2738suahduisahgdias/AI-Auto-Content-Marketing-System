#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_ONLY="${1:-}"
cd "$ROOT"

missing=0
for command_name in python3 node npm ffmpeg ffprobe; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "缺少核心依赖：$command_name（请先安装并加入 PATH）"
    missing=1
  fi
done
if [[ ! -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]] && ! command -v google-chrome >/dev/null 2>&1 && ! command -v chromium >/dev/null 2>&1; then
  echo "未检测到 Chrome：平台采集和扫码登录需要本机 Chrome"
  missing=1
fi
if [[ "$missing" -ne 0 ]]; then
  echo "依赖说明：https://github.com/2738suahduisahgdias/AI-Auto-Content-Marketing-System#本地启动"
  exit 1
fi

check_webbridge() {
  python3 - <<'PY'
import json
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:10086/status", timeout=3) as response:
        status = json.load(response)
except Exception:
    print("WebBridge 未连接：平台采集和微信发布前，请先安装并启动它。")
    print("安装：https://www.kimi.com/zh-cn/features/webbridge")
    print("启动：~/.kimi-webbridge/bin/kimi-webbridge start")
else:
    print("WebBridge 服务：{}；Chrome 扩展：{}".format(
        "已运行" if status.get("running") else "未运行",
        "已连接" if status.get("extension_connected") else "未连接",
    ))
    if not status.get("extension_connected"):
        print("请在 Chrome 安装并启用 Kimi WebBridge 扩展，再重新检查。")
PY
}

if [[ "$CHECK_ONLY" == "--check" ]]; then
  echo "核心命令检查通过；Python $(python3 --version)，Node $(node --version)，FFmpeg $(ffmpeg -version | head -n 1)"
  check_webbridge
  exit 0
fi

if [[ ! -x "$ROOT/.venv-topics/bin/python" ]]; then
  python3 -m venv "$ROOT/.venv-topics"
fi
"$ROOT/.venv-topics/bin/python" -m pip install --disable-pip-version-check -r "$ROOT/requirements-topics.txt"
(
  cd "$ROOT/webapp"
  npm ci
  npm run build
)
(
  cd "$ROOT/remotion-app"
  npm ci
)
if [[ ! -f "$ROOT/data/seed.json" ]]; then
  cp "$ROOT/data/seed.example.json" "$ROOT/data/seed.json"
fi

check_webbridge
echo "安装完成。启动：bash scripts/start.sh"
echo "访问：http://127.0.0.1:8765/"
