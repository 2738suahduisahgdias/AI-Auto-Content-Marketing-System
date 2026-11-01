#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="$ROOT/vendor/openclaw/bin/openclaw"
ENV_FILE="$ROOT/data/wechat-inbox.env"
export OPENCLAW_STATE_DIR="$ROOT/data/openclaw"
export OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18790}"
mkdir -p "$OPENCLAW_STATE_DIR"

require_cli() {
  if [[ ! -x "$CLI" ]]; then
    echo "OpenClaw 尚未安装：$CLI"
    exit 1
  fi
}

load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
  fi
}

case "${1:-status}" in
  init)
    if [[ ! -f "$ENV_FILE" ]]; then
      TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
      GATEWAY_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
      umask 077
      printf 'CONTENT_AGENT_WECHAT_TOKEN=%s\nCONTENT_AGENT_WECHAT_SENDER_ID=\nOPENCLAW_GATEWAY_TOKEN=%s\n' "$TOKEN" "$GATEWAY_TOKEN" > "$ENV_FILE"
    fi
    echo "本机微信入库配置已准备：$ENV_FILE"
    echo "下一步：扫码后执行 bash scripts/wechat-openclaw.sh sender <本人微信ID>"
    ;;
  sender)
    if [[ $# -ne 2 || -z "$2" ]]; then
      echo "用法：bash scripts/wechat-openclaw.sh sender <本人微信ID>"
      exit 1
    fi
    [[ -f "$ENV_FILE" ]] || "$0" init
    ENV_FILE="$ENV_FILE" SENDER_ID="$2" python3 - <<'PY'
import os
from pathlib import Path
path = Path(os.environ["ENV_FILE"])
lines = path.read_text().splitlines()
lines = [line for line in lines if not line.startswith("CONTENT_AGENT_WECHAT_SENDER_ID=")]
lines.append("CONTENT_AGENT_WECHAT_SENDER_ID=" + os.environ["SENDER_ID"])
path.write_text("\n".join(lines) + "\n")
PY
    chmod 600 "$ENV_FILE"
    echo "本人微信发送者已保存，不会显示该 ID。重启本地服务和 Gateway 后生效。"
    ;;
  plugin)
    require_cli
    load_env
    "$CLI" plugins install "@tencent-weixin/openclaw-weixin@2.4.10"
    "$CLI" plugins enable openclaw-weixin
    "$CLI" gateway restart
    ;;
  login)
    require_cli
    load_env
    "$CLI" channels login --channel openclaw-weixin
    ;;
  gateway)
    require_cli
    load_env
    exec "$CLI" gateway
    ;;
  status)
    require_cli
    "$CLI" --version
    "$CLI" plugins list
    "$CLI" channels status --probe
    ;;
  *)
    echo "用法：bash scripts/wechat-openclaw.sh [init|sender <微信ID>|plugin|login|gateway|status]"
    exit 1
    ;;
esac
