import argparse
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION = "publishing-live"


class Bridge:
    def __init__(self, endpoint="http://127.0.0.1:10086/command"):
        self.endpoint = endpoint

    def call(self, action, args=None):
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps({"action": action, "args": args or {}, "session": SESSION}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
        if not result.get("ok"):
            error = result.get("error", {})
            raise RuntimeError(error.get("message") or "Chrome 未执行 " + action)
        return result.get("data", {})

    def cdp(self, method, params=None):
        return self.call("cdp", {"method": method, "params": params or {}})

    def evaluate(self, expression):
        result = self.cdp("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"].get("text", "页面脚本执行失败"))
        return result.get("result", {}).get("value")

    def snapshot(self):
        return self.call("snapshot")

    def wait_for_text(self, text, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if text in json.dumps(self.snapshot().get("tree", []), ensure_ascii=False):
                return True
            time.sleep(0.5)
        return False

    def goto(self, url):
        try:
            self.call("find_tab", {"url": url})
            current = self.snapshot().get("url", "")
            if current == url or current.startswith(url):
                return
        except RuntimeError:
            pass
        try:
            self.call("navigate", {"url": url, "newTab": True, "group_title": "发布预览验证"})
        except RuntimeError as error:
            if "timeout" not in str(error).lower():
                raise
            self.call("find_tab", {"url": url})
            current = self.snapshot().get("url", "")
            if not (current == url or current.startswith(url)):
                raise
        time.sleep(3)

    def click_text(self, text, prefix=False):
        tree = self.snapshot().get("tree", [])

        def walk(nodes):
            for node in nodes:
                name = node.get("name", "")
                if (name.startswith(text) if prefix else name == text) and node.get("ref"):
                    return node["ref"]
                found = walk(node.get("children", []))
                if found:
                    return found
            return None

        ref = walk(tree)
        if not ref:
            return False
        self.call("click", {"selector": ref})
        return True

    def click_last_text(self, text):
        refs = []

        def walk(nodes):
            for node in nodes:
                if node.get("name") == text and node.get("ref"):
                    refs.append(node["ref"])
                walk(node.get("children", []))

        walk(self.snapshot().get("tree", []))
        if not refs:
            return False
        self.call("click", {"selector": refs[-1]})
        return True

    def screenshot(self, target_id, status):
        path = ROOT / "data/publishing-evidence" / "{}-{}.png".format(target_id, status)
        result = self.call("screenshot", {"path": str(path)})
        return result.get("path")

    def result(self, target_id, status, fields=None, extra=None):
        value = {"status": status, "fields_verified": sorted(fields or []),
                 "screenshot": self.screenshot(target_id, status)}
        value.update(extra or {})
        return value

    def error(self, platform, field, message, action):
        return {"status": "error", "field": field, "error": message,
                "message": platform + "：" + message, "action": action}


def set_channels_value(bridge, backend_id, value, rich=False):
    remote = bridge.cdp("DOM.resolveNode", {"backendNodeId": backend_id})
    object_id = remote["object"]["objectId"]
    if rich:
        function = """function(){let e=this.querySelector('.input-editor');if(!e)return '';
            e.innerText=%s;e.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:e.innerText}));return e.innerText}""" % json.dumps(value, ensure_ascii=False)
    else:
        function = """function(){let s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            s.call(this,%s);this.dispatchEvent(new Event('input',{bubbles:true}));
            this.dispatchEvent(new Event('change',{bubbles:true}));return this.value}""" % json.dumps(value, ensure_ascii=False)
    return bridge.cdp("Runtime.callFunctionOn", {"objectId": object_id, "functionDeclaration": function,
                                                   "returnByValue": True}).get("result", {}).get("value", "")


def media_duration(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                            capture_output=True, text=True, timeout=30, check=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def channels_video_duration(bridge):
    document = bridge.cdp("DOM.getDocument", {"depth": -1, "pierce": True})["root"]
    videos = []

    def walk(node):
        if node.get("localName") == "video":
            videos.append(node["backendNodeId"])
        for key in ("children", "shadowRoots"):
            for child in node.get(key, []):
                walk(child)

    walk(document)
    if not videos:
        return None
    remote = bridge.cdp("DOM.resolveNode", {"backendNodeId": videos[0]})
    result = bridge.cdp("Runtime.callFunctionOn", {"objectId": remote["object"]["objectId"],
                                                    "functionDeclaration": "function(){return this.duration}",
                                                    "returnByValue": True})
    value = result.get("result", {}).get("value")
    return float(value) if isinstance(value, (int, float)) else None


def channels_form_nodes(bridge):
    nodes = bridge.cdp("Accessibility.getFullAXTree")["nodes"]
    title = next((n for n in nodes if "填写短标题" in n.get("name", {}).get("value", "")), None)
    description = next((n for n in nodes if n.get("name", {}).get("value") == "视频描述"), None)
    return title, description, nodes


def prepare_channels(bridge, data, mode):
    source, payload = data["source"], data["payload"]
    bridge.goto("https://channels.weixin.qq.com/platform/post/create")
    snapshot = bridge.snapshot()
    text = json.dumps(snapshot.get("tree", []), ensure_ascii=False)
    if "扫码登录" in text or "微信登录" in text:
        return {"status": "login_required", "error": "视频号需要登录", "action": "在保留的 Chrome 标签页扫码后重试"}
    if "封面预览" not in text:
        try:
            bridge.call("upload", {"selector": "input[type=file][accept*=video]",
                                   "files": [source["absolute_video_path"]]})
        except RuntimeError:
            pass
        time.sleep(8)
        snapshot = bridge.snapshot()
        text = json.dumps(snapshot.get("tree", []), ensure_ascii=False)
    if "封面预览" not in text:
        bridge.click_text("上传时长8小时内，大小不超过20GB，建议分辨率720p及以上，码率10Mbps以内，格式为MP4/H.264格式")
        return bridge.result(data["target_id"], "manual_required", extra={
            "field": "video_path", "error": "视频号拒绝了程序文件注入，已打开系统文件选择窗口",
            "action": "选择 {}；上传出现封面预览后，回到系统重试本平台预览".format(source["absolute_video_path"])})
    expected_duration = media_duration(source["absolute_video_path"])
    actual_duration = channels_video_duration(bridge)
    if actual_duration is None or abs(actual_duration - expected_duration) > 1:
        return bridge.result(data["target_id"], "manual_required", extra={
            "field": "video_path", "error": "页面已有视频与本次审核成片不一致，禁止发布旧内容",
            "actual_duration": actual_duration, "expected_duration": expected_duration,
            "action": "在视频号发布页删除当前视频，选择 {}；确认时长约 {:.1f} 秒后重试".format(source["absolute_video_path"], expected_duration)})
    title, description, nodes = channels_form_nodes(bridge)
    if not title or not description:
        return bridge.error("视频号", "description", "视频已上传，但标题或描述控件尚未加载", "等待页面加载完成后重试，不要重复选择文件")
    node_map = {n["nodeId"]: n for n in nodes}
    label = node_map.get(description.get("parentId"), {})
    parent = label.get("parentId")
    while parent and "backendDOMNodeId" not in node_map.get(parent, {}):
        parent = node_map.get(parent, {}).get("parentId")
    short_title = payload.get("short_title") or payload["title"]
    if set_channels_value(bridge, title["backendDOMNodeId"], short_title) != short_title:
        return bridge.error("视频号", "title", "短标题写入后读回不一致", "检查短标题后重试")
    if not parent or payload["description"][:30] not in set_channels_value(
            bridge, node_map[parent]["backendDOMNodeId"], payload["description"], True):
        return bridge.error("视频号", "description", "描述写入后读回不一致", "检查视频描述后重试")
    fields = {"video", "short_title", "description"}
    if mode == "execute":
        return execute_bridge(bridge, "wechat_channels", data["target_id"], "发表")
    return bridge.result(data["target_id"], "preview_ready", fields, {"title": short_title, "transport": "webbridge"})


def fill(bridge, selector, value):
    bridge.call("fill", {"selector": selector, "value": value})


def open_official_cover(bridge):
    if "选择图片" in json.dumps(bridge.snapshot().get("tree", []), ensure_ascii=False):
        return True
    bridge.cdp("Page.bringToFront")
    point = bridge.evaluate("""(()=>{let e=document.querySelector('.js_cover_btn_area');if(!e)return null;
        e.scrollIntoView({block:'center'});let r=e.getBoundingClientRect();
        return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2})})()""")
    if point:
        position = json.loads(point)
        for event_type in ("mousePressed", "mouseReleased"):
            bridge.cdp("Input.dispatchMouseEvent", {"type": event_type, "x": position["x"], "y": position["y"],
                                                    "button": "left", "clickCount": 1})
    bridge.evaluate("""(()=>{let e=Array.from(document.querySelectorAll('a')).find(e=>e.textContent.trim()==='从图片库选择');if(!e)return false;e.click();return true})()""")
    return bridge.wait_for_text("选择图片")


def select_official_cover(bridge, filename):
    script = """(()=>{let name=%s;let e=Array.from(document.querySelectorAll('strong')).find(e=>e.textContent.trim()===name);
        if(!e)return 'missing-image';e.parentElement.click();
        let b=Array.from(document.querySelectorAll('button')).find(b=>b.innerText.trim()==='下一步'&&b.getBoundingClientRect().width>0&&!b.disabled);
        if(!b)return 'missing-next';b.scrollIntoView({block:'center'});let r=b.getBoundingClientRect();
        return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2})})()""" % json.dumps(filename, ensure_ascii=False)
    result = bridge.evaluate(script)
    if result in ("missing-image", "missing-next"):
        return result
    position = json.loads(result)
    bridge.cdp("Page.bringToFront")
    for event_type in ("mousePressed", "mouseReleased"):
        bridge.cdp("Input.dispatchMouseEvent", {"type": event_type, "x": position["x"], "y": position["y"],
                                                "button": "left", "clickCount": 1})
    return "editing" if bridge.wait_for_text("编辑封面") else "not-editing"


def official_editor_matches(bridge, payload):
    if "appmsg_edit" not in bridge.snapshot().get("url", ""):
        return False
    try:
        readback = json.loads(bridge.evaluate("""JSON.stringify({title:document.querySelector('.title-editor__input .ProseMirror').innerText,
            body:document.querySelector('.rich_media_content .ProseMirror').innerText,
            author:document.querySelector('#author').value,summary:document.querySelector('#js_description').value})"""))
        cover_html = bridge.evaluate("document.querySelector('.js_cover_btn_area').parentElement.parentElement.outerHTML")
    except (RuntimeError, KeyError, TypeError, json.JSONDecodeError):
        return False
    return all(re.sub(r"\s+", "", payload.get(key, "")) == re.sub(r"\s+", "", readback[key])
               for key in ("title", "body", "author", "summary")) and "mmbiz.qpic.cn" in cover_html


def prepare_official_account(bridge, data, mode):
    payload = data["payload"]
    fields = {"title", "author", "summary", "body", "cover"}
    if official_editor_matches(bridge, payload):
        if mode == "execute":
            return execute_bridge(bridge, "wechat_official_account", data["target_id"], "发表")
        return bridge.result(data["target_id"], "preview_ready", fields,
                             {"title": payload["title"], "body_length": len(payload["body"]), "transport": "webbridge"})
    bridge.goto("https://mp.weixin.qq.com/")
    page = bridge.snapshot()
    if "使用账号登录" in json.dumps(page.get("tree", []), ensure_ascii=False):
        return {"status": "login_required", "error": "公众号需要登录", "action": "在保留的 Chrome 标签页扫码后重试"}
    current = urllib.parse.urlparse(page["url"])
    token = urllib.parse.parse_qs(current.query).get("token", [""])[0]
    if not token:
        return {"status": "login_required", "error": "公众号登录状态无效", "action": "重新扫码登录"}
    query = urllib.parse.urlencode({"t": "media/appmsg_edit_v2", "action": "edit", "isNew": "1",
                                    "type": "77", "createType": "0", "token": token, "lang": "zh_CN"})
    bridge.goto("https://mp.weixin.qq.com/cgi-bin/appmsg?" + query)
    fill(bridge, "#author", payload.get("author", ""))
    fill(bridge, "#js_description", payload.get("summary", ""))
    fill(bridge, ".rich_media_content .ProseMirror", payload["body"])
    fill(bridge, ".title-editor__input .ProseMirror", payload["title"])
    if not open_official_cover(bridge):
        return bridge.error("公众号", "cover_asset_id", "封面图片库没有打开", "关闭遮挡弹窗后重试，不要直接发表")
    try:
        bridge.call("upload", {"selector": "input[type=file][accept*=bmp]", "files": [payload["cover_path"]]})
    except RuntimeError as error:
        if not bridge.wait_for_text(Path(payload["cover_path"]).name):
            return bridge.error("公众号", "cover_asset_id", "封面上传失败：" + str(error), "检查本地文件权限和图片库后重试")
    time.sleep(4)
    bridge.click_text("最近使用", prefix=True)
    if not bridge.wait_for_text(Path(payload["cover_path"]).name):
        return bridge.error("公众号", "cover_asset_id", "图片库中尚未出现本次封面文件", "等待封面上传完成后重试，不要选择其他图片")
    selected = select_official_cover(bridge, Path(payload["cover_path"]).name)
    if selected != "editing":
        return bridge.error("公众号", "cover_asset_id", "选择本次封面后未进入裁剪：" + selected, "核对文件名和可见的下一步按钮后重试")
    time.sleep(2)
    if not bridge.click_text("确认"):
        return bridge.error("公众号", "cover_asset_id", "未找到封面裁剪确认按钮", "检查裁剪比例后重试")
    time.sleep(4)
    text = json.dumps(bridge.snapshot().get("tree", []), ensure_ascii=False)
    if "系统繁忙" in text or "重新裁剪封面" in text:
        return bridge.error("公众号", "cover_asset_id", "平台拒绝保存封面裁剪", "使用至少 900×383 的 PNG/JPEG 正常封面后重试")
    readback = json.loads(bridge.evaluate("""JSON.stringify({title:document.querySelector('.title-editor__input .ProseMirror').innerText,
        body:document.querySelector('.rich_media_content .ProseMirror').innerText,
        author:document.querySelector('#author').value,summary:document.querySelector('#js_description').value})"""))
    for key in ("title", "body", "author", "summary"):
        if payload.get(key) and re.sub(r"\s+", "", payload[key]) != re.sub(r"\s+", "", readback[key]):
            return bridge.error("公众号", key, key + " 写入后读回不一致", "检查对应字段后重试")
    cover_html = bridge.evaluate("document.querySelector('.js_cover_btn_area').parentElement.parentElement.outerHTML")
    if "mmbiz.qpic.cn" not in cover_html and "background-image" not in cover_html:
        return bridge.error("公众号", "cover_asset_id", "封面裁剪结束后未读到已选封面", "重新选择正常尺寸封面，不要继续公开")
    fields = {"title", "author", "summary", "body", "cover"}
    if mode == "execute":
        return execute_bridge(bridge, "wechat_official_account", data["target_id"], "发表")
    return bridge.result(data["target_id"], "preview_ready", fields,
                         {"title": payload["title"], "body_length": len(payload["body"]), "transport": "webbridge"})


def execute_bridge(bridge, platform, target_id, label):
    if not bridge.click_text(label):
        return bridge.error(platform, "publish_button", "未找到最终发表按钮，未执行发表", "检查平台预览是否仍就绪")
    time.sleep(1)
    for _ in range(3):
        confirmed = False
        for confirmation in ("直接发表", "确认发表", "确认发布", "继续发布", "继续发表", "确定"):
            if bridge.click_text(confirmation):
                confirmed = True
                break
        if not confirmed and platform == "wechat_official_account":
            confirmed = bridge.click_last_text("发表")
        if not confirmed:
            break
        time.sleep(1)
    time.sleep(5)
    page = bridge.snapshot()
    text = json.dumps(page.get("tree", []), ensure_ascii=False)
    if "发布成功" in text or "发表成功" in text or "提交成功" in text or "/platform/post/list" in page.get("url", ""):
        return bridge.result(target_id, "published", {"published"}, {"published_evidence": "平台显示发布成功或已跳转到视频管理列表", "url": page.get("url")})
    return bridge.result(target_id, "unknown_remote", extra={
        "error": "已执行最终点击，但没有读到明确成功证据", "action": "到平台后台核对，禁止直接重试"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("prepare", "execute"), required=True)
    parser.add_argument("--platform", choices=("wechat_channels", "wechat_official_account"), required=True)
    parser.add_argument("--payload-file", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    bridge = Bridge()
    try:
        if args.platform == "wechat_channels":
            result = prepare_channels(bridge, data, args.action)
        else:
            result = prepare_official_account(bridge, data, args.action)
    except Exception as error:
        message = str(error)[:800]
        action = "先关闭 Chrome 中未完成的文件选择窗口，再检查 WebBridge 和登录状态后重试" if "page load timeout" in message else "确认 Chrome、Kimi WebBridge 和平台登录状态后重试"
        result = {"status": "error", "error": message, "action": action}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
