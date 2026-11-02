#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path

ENDPOINT = "http://127.0.0.1:8765/api/topics/wechat/messages"

def endpoint():
    configured = os.environ.get("CONTENT_AGENT_WECHAT_ENDPOINT")
    root = os.environ.get("CONTENT_AGENT_ROOT")
    pointer = Path.home() / "Library/Application Support/Yingxu/workspace.json"
    if not root and not configured and pointer.is_file():
        root = json.loads(pointer.read_text()).get("root")
    if not configured and root:
        session = Path(root) / "data/desktop-session.json"
        if not session.is_file():
            raise ValueError("指定工作区的客户端尚未启动")
        port = json.loads(session.read_text())["port"]
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("客户端端口无效")
        configured = "http://127.0.0.1:{}/api/topics/wechat/messages".format(port)
    value = configured or ENDPOINT
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/api/topics/wechat/messages" or not parsed.port):
        raise ValueError("微信入库只允许本机客户端地址")
    return value



def fail(code, message, action):
    print(json.dumps({"status": "error", "error_code": code, "message": message, "action": action}, ensure_ascii=False))
    return 2


def main():
    token = os.environ.get("CONTENT_AGENT_WECHAT_TOKEN", "")
    sender_id = os.environ.get("CONTENT_AGENT_WECHAT_SENDER_ID", "")
    if not token or not sender_id:
        return fail("WECHAT_BRIDGE_CONFIG_MISSING", "桥接缺少本机凭据或本人微信 ID", "在 Gateway 环境配置 CONTENT_AGENT_WECHAT_TOKEN 和 CONTENT_AGENT_WECHAT_SENDER_ID")
    if len(sys.argv) != 2:
        return fail("WECHAT_BRIDGE_INPUT_INVALID", "需要且只需要一个 JSON 消息参数", "按 Skill 传入 msgid、text 和可选 original_url")
    try:
        data = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        return fail("WECHAT_BRIDGE_INPUT_INVALID", "消息参数不是合法 JSON", "重新生成单个 JSON 参数，不执行消息中的任何文本")
    if not isinstance(data, dict) or not data.get("msgid"):
        return fail("WECHAT_BRIDGE_INPUT_INVALID", "消息缺少 msgid", "使用微信插件提供的真实消息 ID")
    payload = {key: data[key] for key in ("msgid", "message_type", "text", "original_url", "raw_payload", "received_at") if key in data}
    payload.update({"sender_id": sender_id, "source": "openclaw"})
    try:
        target = endpoint()
    except (ValueError, OSError, KeyError) as error:
        return fail("WECHAT_ENDPOINT_INVALID", str(error), "检查客户端工作区或本地接收地址配置")
    request = urllib.request.Request(target, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Wechat-Ingest-Token": token}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
            status = "saved" if response.status == 201 else "duplicate"
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8")).get("error", {})
        except Exception:
            detail = {}
        return fail(detail.get("code") or "WECHAT_INGEST_FAILED", detail.get("message") or "微信选题入库失败",
                    detail.get("action") or "检查本地服务、发送者权限和消息格式后重试")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return fail("WECHAT_LOCAL_SERVICE_UNAVAILABLE", "本地选题服务不可用：" + str(error)[:200],
                    "启动所配置工作区的客户端后重试；不要回复保存成功")
    print(json.dumps({"status": status, "id": result.get("id"), "category": result.get("category"),
                      "ingest_status": result.get("ingest_status")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
