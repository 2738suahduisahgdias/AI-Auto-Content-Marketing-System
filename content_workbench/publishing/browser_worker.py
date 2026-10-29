import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    sync_playwright = None
from content_workbench.topics.browser_worker import open_context
from content_workbench.publishing.coverage import unsupported_payload_field

ROOT = Path(__file__).resolve().parents[2]
URLS = {
    "douyin": "https://creator.douyin.com/creator-micro/content/upload",
    "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish?source=official",
    "wechat_channels": "https://channels.weixin.qq.com/platform/post/list",
    "wechat_official_account": "https://mp.weixin.qq.com/",
}


def first(page, selectors, timeout=0):
    deadline = time.monotonic() + timeout / 1000
    while True:
        for selector in selectors:
            locator = page.locator(selector)
            for index in range(locator.count()):
                candidate = locator.nth(index)
                try:
                    if "input[type=file]" in selector or candidate.is_visible():
                        return candidate
                except Exception:
                    continue
        if time.monotonic() >= deadline:
            return None
        page.wait_for_timeout(250)


def value_of(locator):
    try:
        return locator.input_value()
    except Exception:
        try:
            return locator.inner_text()
        except Exception:
            return ""


def fill(locator, text):
    locator.click()
    try:
        locator.fill(text)
    except Exception:
        locator.press("ControlOrMeta+a")
        locator.type(text)
    return value_of(locator)


def click_visible(locator, timeout=0):
    deadline = time.monotonic() + timeout / 1000
    while True:
        for index in range(locator.count()):
            candidate = locator.nth(index)
            if not candidate.is_visible() or not candidate.is_enabled():
                continue
            try:
                candidate.click()
                return True
            except Exception:
                try:
                    candidate.locator("xpath=..").click()
                    return True
                except Exception:
                    continue
        if time.monotonic() >= deadline:
            return False
        locator.page.wait_for_timeout(250)


def visible_text(page, text, timeout=0):
    deadline = time.monotonic() + timeout / 1000
    while True:
        for frame in page.frames:
            locator = frame.get_by_text(text, exact=True)
            for index in range(locator.count()):
                candidate = locator.nth(index)
                try:
                    if candidate.is_visible():
                        return candidate
                except Exception:
                    continue
        if time.monotonic() >= deadline:
            return None
        page.wait_for_timeout(250)


def click_text(page, text, timeout=0):
    deadline = time.monotonic() + timeout / 1000
    while True:
        for frame in page.frames:
            if click_visible(frame.get_by_text(text, exact=True)):
                return True
        if time.monotonic() >= deadline:
            return False
        page.wait_for_timeout(250)


def xhs_action_control(page, action, timeout=0):
    deadline = time.monotonic() + timeout / 1000
    while True:
        for frame in page.frames:
            controls = frame.locator("xhs-publish-btn")
            for index in range(controls.count()):
                candidate = controls.nth(index)
                try:
                    if (candidate.get_attribute("submit-text") == action
                            and candidate.get_attribute("submit-disabled") != "true"
                            and candidate.get_attribute("submit-loading") != "true"
                            and candidate.is_visible() and candidate.is_enabled()):
                        return candidate
                except Exception:
                    continue
            controls = frame.get_by_text(action, exact=True)
            for index in range(controls.count()):
                candidate = controls.nth(index)
                try:
                    if candidate.is_visible() and candidate.is_enabled():
                        return candidate
                except Exception:
                    continue
        if time.monotonic() >= deadline:
            return None
        page.wait_for_timeout(250)


def click_xhs_control(control):
    if not control:
        return False
    try:
        box = control.bounding_box()
        if not box:
            return False
        has_draft = control.get_attribute("is-save-draft") == "true"
        control.click(position={"x": box["width"] * (0.6 if has_draft else 0.5), "y": box["height"] / 2})
        return True
    except Exception:
        return False


def click_xhs_action(page, action, timeout=0):
    return click_xhs_control(xhs_action_control(page, action, timeout))


def xhs_publish_control(page, timeout=0):
    return xhs_action_control(page, "发布", timeout)


def validate_channels_video(path):
    source = Path(path)
    if source.suffix.lower() != ".mp4" or not source.is_file():
        return "视频号仅支持已存在的 MP4 文件"
    if source.stat().st_size > 20 * 1024 ** 3:
        return "视频号视频不能超过 20GB"
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name:format=duration", "-of", "json", str(source)],
            capture_output=True, text=True, timeout=30,
        )
        metadata = json.loads(result.stdout or "{}") if result.returncode == 0 else {}
        video = (metadata.get("streams") or [{}])[0]
        duration = float(metadata.get("format", {}).get("duration", 0))
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
        return "无法读取视频编码或时长，未上传视频号"
    if video.get("codec_name") != "h264":
        return "视频号视频必须使用 H264 编码"
    if not 0 < duration <= 8 * 3600:
        return "视频号视频时长必须在 8 小时以内"
    return None


def field_error(platform, field, message):
    return {"status": "error", "field": field, "error": message}


def evidence(page, target_id, mode, fields, extra=None):
    directory = ROOT / "data/publishing-evidence"
    directory.mkdir(parents=True, exist_ok=True)
    name = "{}_{}_{}.png".format(target_id or "connection", mode, datetime.now().strftime("%Y%m%dT%H%M%S"))
    path = directory / name
    try:
        page.screenshot(path=str(path), full_page=False)
    except Exception:
        pass
    result = {"status": "preview_ready", "fields_verified": sorted(fields), "screenshot": str(path.relative_to(ROOT)), "auto_published": False}
    if extra:
        result.update(extra)
    return result


def verify_douyin(page, data):
    page.goto(URLS["douyin"], wait_until="domcontentloaded", timeout=60000)
    if not click_text(page, "内容管理", 15000):
        return field_error("douyin", "verification", "未找到内容管理入口，无法核验发布结果")
    title = data["payload"]["title"]
    if visible_text(page, title, 20000):
        return evidence(page, data["target_id"], "published", {"published"}, {
            "status": "published", "published_evidence": "抖音内容管理列表存在标题：" + title, "url": page.url})
    return evidence(page, data["target_id"], "not_found", set(), {
        "status": "not_found", "error": "抖音内容管理中未找到该标题，保持待核对，禁止自动重发"})


def prepare_douyin(page, data, mode):
    source, payload = data["source"], data["payload"]
    unsupported = unsupported_payload_field("douyin", "video", payload, {"title", "description", "tags"})
    if unsupported:
        return unsupported
    page.goto(URLS["douyin"], wait_until="domcontentloaded", timeout=60000)
    upload = first(page, ["input[type=file]"], 15000)
    if not upload:
        return {"status": "login_required", "error": "未检测到视频上传控件，请登录抖音创作者后台"}
    upload.set_input_files(source["absolute_video_path"])
    deadline = time.monotonic() + 180
    while True:
        page_text = page.locator("body").inner_text()
        if "取消上传" not in page_text and "上传过程中请不要删除" not in page_text:
            break
        if time.monotonic() >= deadline:
            return field_error("douyin", "video_path", "视频上传尚未完成，请检查网络后重试，不要提前发布")
        page.wait_for_timeout(1000)
    page.wait_for_timeout(3000)
    title = first(page, ['input[placeholder*="标题"]', 'textarea[placeholder*="标题"]', 'input[placeholder*="作品"]'])
    description = first(page, ['textarea[placeholder*="描述"]', 'textarea[placeholder*="简介"]', 'div[contenteditable="true"]', 'textarea'])
    if not description:
        return field_error("douyin", "description", "视频已选择，但未找到简介编辑区；请检查上传是否完成或页面是否变化")
    description_text = payload["description"] + ("\n" + payload["tags"] if payload.get("tags") else "")
    fields = set()
    if title:
        fill(title, payload["title"])
        fields.add("title")
        fill(description, description_text)
        fields.add("description")
    else:
        combined = payload["title"] + "\n" + description_text
        fill(description, combined)
        fields.update(("title", "description", "combined_caption"))
    if payload.get("tags"):
        fields.add("tags")
    readback = value_of(description)
    if payload["description"][:30] not in readback or (payload.get("tags") and payload["tags"] not in readback):
        return field_error("douyin", "description", "简介或话题文本写入后读回不一致")
    if mode == "execute":
        return click_publish(page, "douyin", data["target_id"], payload["title"])
    return evidence(page, data["target_id"], mode, fields, {"title": payload["title"]})


def xhs_editor(page):
    page.goto(URLS["xiaohongshu"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    if "login" in page.url:
        return None
    return page


def verify_xhs_video(page, data):
    if not xhs_editor(page):
        return {"status": "login_required", "error": "小红书创作者后台需要登录"}
    if not click_text(page, "笔记管理", 15000):
        return field_error("xiaohongshu", "verification", "未找到笔记管理入口，无法核验发布结果")
    title = data["payload"]["title"]
    if visible_text(page, title, 20000):
        return evidence(page, data["target_id"], "published", {"published"}, {
            "status": "published", "published_evidence": "笔记管理列表存在标题：" + title, "url": page.url})
    return evidence(page, data["target_id"], "not_found", set(), {
        "status": "not_found", "error": "笔记管理中未找到该标题，保持待核对，禁止自动重发"})


def prepare_xhs_video(page, data, mode):
    source, payload = data["source"], data["payload"]
    unsupported = unsupported_payload_field("xiaohongshu", "video", payload, {"title", "description", "tags"})
    if unsupported:
        return unsupported
    if not xhs_editor(page):
        return {"status": "login_required", "error": "小红书创作者后台需要登录"}
    upload = first(page, ["input[type=file]"], 15000)
    if not upload:
        return {"status": "login_required", "error": "未检测到小红书视频上传控件，请确认登录状态"}
    upload.set_input_files(source["absolute_video_path"])
    page.wait_for_timeout(7000)
    title = first(page, ['input[placeholder*="标题"]', 'textarea[placeholder*="标题"]'])
    body = first(page, ['div[contenteditable="true"]', 'textarea[placeholder*="正文"]', 'textarea[placeholder*="描述"]', 'textarea'])
    if not title:
        return field_error("xiaohongshu", "title", "视频上传后未找到标题输入框")
    if not body:
        return field_error("xiaohongshu", "description", "视频上传后未找到正文编辑区")
    description_text = payload["description"] + ("\n" + payload["tags"] if payload.get("tags") else "")
    fill(title, payload["title"])
    fill(body, description_text)
    if payload["title"] not in value_of(title) or payload["description"][:30] not in value_of(body) \
            or (payload.get("tags") and payload["tags"] not in value_of(body)):
        return field_error("xiaohongshu", "description", "标题、正文或话题文本读回不一致")
    if mode == "execute":
        return click_publish(page, "xiaohongshu", data["target_id"])
    fields = {"title", "description", "tags"} if payload.get("tags") else {"title", "description"}
    return evidence(page, data["target_id"], mode, fields, {"title": payload["title"]})


def prepare_xhs_article(page, data, mode):
    payload = data["payload"]
    unsupported = unsupported_payload_field("xiaohongshu", "article", payload, {"title", "body", "description", "tags", "template_name"})
    if unsupported:
        return unsupported
    if not xhs_editor(page):
        return {"status": "login_required", "error": "小红书创作者后台需要登录"}
    if not click_text(page, "写长文", 15000):
        return field_error("xiaohongshu", "long_article", "长文入口加载超时或被遮挡，请检查平台页面")
    if not click_text(page, "新的创作", 15000):
        return field_error("xiaohongshu", "long_article", "未找到新的创作按钮")
    title = first(page, ['input[placeholder="输入标题"]', 'textarea[placeholder="输入标题"]'], 15000)
    body = first(page, ['div[contenteditable="true"]', 'textarea'])
    if not title or not body:
        return field_error("xiaohongshu", "body", "未找到长文标题或正文编辑器")
    fill(title, payload["title"])
    fill(body, payload["body"])
    normalized_title = re.sub(r"\s+", "", payload["title"])
    actual_body = re.sub(r"\s+", "", value_of(body))
    if (normalized_title not in re.sub(r"\s+", "", value_of(title))
            or re.sub(r"\s+", "", payload["body"][:30]) not in actual_body
            or re.sub(r"\s+", "", payload["body"][-30:]) not in actual_body):
        return field_error("xiaohongshu", "body", "长文标题或正文读回不一致")
    fields = {"title", "body", "long_article"}
    if not click_xhs_action(page, "一键排版", 15000):
        return field_error("xiaohongshu", "layout", "未找到可用的一键排版控件，未进入发布设置")
    fields.add("layout")
    if not visible_text(page, "选择模板", 15000):
        return field_error("xiaohongshu", "layout", "一键排版后未出现模板选择")
    if not click_text(page, payload.get("template_name") or "理性现代", 5000):
        return field_error("xiaohongshu", "template_name", "指定长文模板未选择，无法进入下一步")
    fields.add("template_name")
    page.wait_for_timeout(1000)
    for _ in range(4):
        if xhs_publish_control(page):
            break
        if not click_xhs_action(page, "下一步", 5000) and not click_text(page, "下一步", 3000) and not click_xhs_action(page, "下一步设置"):
            break
        page.wait_for_timeout(2000)
    click_text(page, "我知道了", 3000)
    try:
        page.get_by_text(re.compile("笔记图片生成中")).wait_for(state="hidden", timeout=180000)
    except Exception:
        return field_error("xiaohongshu", "cover", "长文笔记图片仍在生成，请稍后重试，不要跳过图片检查")
    if not visible_text(page, "内容设置") or not xhs_publish_control(page, 30000):
        return field_error("xiaohongshu", "publish_settings", "尚未进入可发布设置页，未找到可用的发布宿主控件")
    description_text = payload.get("description", "") + ("\n" + payload["tags"] if payload.get("tags") else "")
    if description_text:
        publish_description = first(page, ['div[contenteditable="true"]', 'textarea[placeholder*="正文"]',
                                          'textarea[placeholder*="描述"]', 'textarea'])
        if not publish_description:
            return field_error("xiaohongshu", "description", "未找到长文发布设置中的独立描述字段")
        fill(publish_description, description_text)
        readback = value_of(publish_description)
        if (payload.get("description") and payload["description"][:30] not in readback) \
                or (payload.get("tags") and payload["tags"] not in readback):
            return field_error("xiaohongshu", "description", "长文发布描述或话题文本读回不一致")
        if payload.get("description"):
            fields.add("description")
        if payload.get("tags"):
            fields.add("tags")
    fields.update(("publish_settings", "publish_button"))
    if mode == "execute":
        return click_publish(page, "xiaohongshu", data["target_id"])
    return evidence(page, data["target_id"], mode, fields,
                    {"title": payload["title"], "body_length": len(payload["body"]), "settings_text": page.locator("body").inner_text()[-2500:]})


def topic_names(value):
    return [part.strip().lstrip("#") for part in re.split(r"[\s,，]+", value or "") if part.strip().lstrip("#")]


def prepare_wechat_channels(page, data, mode):
    source, payload = data["source"], data["payload"]
    unsupported = unsupported_payload_field("wechat_channels", "video", payload,
                                            {"short_title", "description", "tags", "scheduled_at", "original"})
    if unsupported:
        return unsupported
    invalid = validate_channels_video(source["absolute_video_path"])
    if invalid:
        return field_error("wechat_channels", "video_path", invalid)
    page.goto(URLS["wechat_channels"], wait_until="domcontentloaded", timeout=60000)
    upload = first(page, ['input[type=file][accept*="video"]', "input[type=file]"], 10000)
    if not upload:
        for label in ("发表动态", "发布视频", "上传视频"):
            if click_text(page, label, 3000):
                break
        upload = first(page, ['input[type=file][accept*="video"]', "input[type=file]"], 15000)
    if not upload:
        body_text = page.locator("body").inner_text()
        if "login" in page.url or "扫码登录" in body_text or "微信登录" in body_text:
            return {"status": "login_required", "error": "视频号助手需要登录，请在专用窗口扫码"}
        return field_error("wechat_channels", "video_path", "未找到视频号视频上传控件，未执行上传或发布")
    upload.set_input_files(source["absolute_video_path"])
    description = first(page, ['textarea[placeholder*="描述"]', 'textarea[placeholder*="简介"]',
                               'div[contenteditable="true"]', "textarea"], 180000)
    if not description:
        return field_error("wechat_channels", "description", "视频上传后未找到描述编辑区，可能仍在转码或页面已变化")
    fill(description, payload["description"])
    if payload["description"][:30] not in value_of(description):
        return field_error("wechat_channels", "description", "视频号描述写入后读回不一致")
    fields = {"description"}
    short_title = payload.get("short_title") or payload["title"]
    title = first(page, ['input[placeholder*="短标题"]', 'textarea[placeholder*="短标题"]',
                         'input[maxlength="16"]'], 10000)
    if not title:
        return field_error("wechat_channels", "short_title", "未找到视频号短标题字段")
    fill(title, short_title)
    if short_title not in value_of(title):
        return field_error("wechat_channels", "short_title", "视频号短标题写入后读回不一致")
    fields.add("short_title")
    topics = topic_names(payload.get("tags"))
    if topics:
        topic_input = first(page, ['input[placeholder*="话题"]', 'textarea[placeholder*="话题"]'])
        if not topic_input and click_text(page, "话题"):
            topic_input = first(page, ['input[placeholder*="话题"]', 'input[type="text"]'], 5000)
        if not topic_input:
            return field_error("wechat_channels", "tags", "未找到视频号话题输入控件，未将普通文本冒充话题")
        for topic in topics:
            fill(topic_input, topic)
            topic_input.press("Enter")
            page.wait_for_timeout(800)
        page_text = page.locator("body").inner_text()
        if any(topic not in page_text and topic not in value_of(description) for topic in topics):
            return field_error("wechat_channels", "tags", "视频号话题提交后读回不一致")
        fields.add("topics")
    scheduled = payload.get("scheduled_at") or payload.get("schedule_time")
    if scheduled:
        if not click_text(page, "定时发表") and not click_text(page, "定时发布"):
            return field_error("wechat_channels", "scheduled_at", "未找到视频号定时设置")
        schedule_input = first(page, ['input[type="datetime-local"]', 'input[placeholder*="时间"]',
                                      'input[placeholder*="日期"]'], 5000)
        if not schedule_input:
            return field_error("wechat_channels", "scheduled_at", "定时设置已打开，但未找到时间输入框")
        schedule_value = str(scheduled).replace(" ", "T")[:16]
        fill(schedule_input, schedule_value)
        if schedule_value not in value_of(schedule_input):
            return field_error("wechat_channels", "scheduled_at", "视频号定时时间读回不一致")
        fields.add("scheduled_at")
    if payload.get("original"):
        if not click_text(page, "原创声明") and not click_text(page, "原创"):
            return field_error("wechat_channels", "original", "未找到视频号原创声明控件")
        click_text(page, "确定", 3000)
        checked = first(page, ['label:has-text("原创") input[type="checkbox"]:checked',
                               'input[type="checkbox"][name*="original"]:checked'])
        if not checked and not visible_text(page, "已声明原创") and not visible_text(page, "已开启原创"):
            return field_error("wechat_channels", "original", "原创声明后未读到明确开启状态")
        fields.add("original")
    publish = visible_text(page, "发表", 30000) or visible_text(page, "发布")
    if not publish or not publish.is_enabled():
        return field_error("wechat_channels", "video_path", "视频尚未进入可发表状态，可能仍在上传或转码")
    fields.add("publish_button")
    if mode == "execute":
        return click_publish(page, "wechat_channels", data["target_id"])
    return evidence(page, data["target_id"], mode, fields,
                    {"title": short_title, "duration_limit_seconds": 28800, "size_limit_bytes": 20 * 1024 ** 3})


def wechat_cover_ready(control):
    current = control
    for _ in range(6):
        if not current:
            break
        try:
            images = current.locator("img")
            for index in range(images.count()):
                image = images.nth(index)
                if image.is_visible() and image.get_attribute("src"):
                    return True
            backgrounds = current.locator('[style*="background-image"]')
            if any(backgrounds.nth(index).is_visible() for index in range(backgrounds.count())):
                return True
            current = current.locator("xpath=..")
        except Exception:
            break
    return False


def prepare_wechat_article(page, data, mode):
    payload = data["payload"]
    unsupported = unsupported_payload_field("wechat_official_account", "article", payload,
                                            {"title", "author", "summary", "body", "cover_asset_id"})
    if unsupported:
        return unsupported
    for key, label, maximum in (("title", "标题", 64), ("author", "作者", 8), ("summary", "摘要", 120)):
        if len(str(payload.get(key, ""))) > maximum:
            return field_error("wechat_official_account", key, "{}不能超过{}字".format(label, maximum))
    if not payload.get("cover_path"):
        return field_error("wechat_official_account", "cover_asset_id", "公众号正文封面不能为空")
    page.goto(URLS["wechat_official_account"], wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    body_text = page.locator("body").inner_text()
    if "login" in page.url or ("使用账号登录" in body_text and "新的创作" not in body_text):
        return {"status": "login_required", "error": "公众号后台需要登录，请在专用窗口扫码"}
    if not click_text(page, "文章", 10000):
        return field_error("wechat_official_account", "body", "未找到公众号文章创作入口")
    title = first(page, ["#title", 'input[placeholder*="标题"]'], 20000)
    if not title:
        return field_error("wechat_official_account", "title", "未进入公众号文章编辑器，未找到标题")
    fill(title, payload["title"])
    if payload["title"] not in value_of(title):
        return field_error("wechat_official_account", "title", "公众号标题读回不一致")
    fields = {"title"}
    if payload.get("author"):
        author = first(page, ["#author", 'input[placeholder="请输入作者"]'], 5000)
        if not author:
            return field_error("wechat_official_account", "author", "未找到公众号作者字段")
        fill(author, payload["author"])
        if payload["author"] not in value_of(author):
            return field_error("wechat_official_account", "author", "公众号作者读回不一致")
        fields.add("author")
    if payload.get("summary"):
        summary = first(page, ["#digest", 'textarea[placeholder*="摘要会在"]'], 5000)
        if not summary:
            return field_error("wechat_official_account", "summary", "未找到公众号摘要字段")
        fill(summary, payload["summary"])
        if payload["summary"] not in value_of(summary):
            return field_error("wechat_official_account", "summary", "公众号摘要读回不一致")
        fields.add("summary")
    body = None
    for frame in page.frames:
        body = first(frame, ['body[contenteditable="true"]', 'div[contenteditable="true"]', "#ueditor_0"])
        if body:
            break
    if body is None:
        return field_error("wechat_official_account", "body", "未找到公众号可编辑正文区")
    fill(body, payload["body"])
    if payload["body"][:30] not in value_of(body):
        return field_error("wechat_official_account", "body", "公众号正文写入后读回不一致")
    fields.add("body")
    cover = visible_text(page, "拖拽或选择封面", 10000) or visible_text(page, "选择封面")
    if not cover or not click_visible(cover):
        return field_error("wechat_official_account", "cover_asset_id", "未找到公众号正文封面入口")
    upload = first(page, ["input[type=file]"], 10000)
    if not upload:
        return field_error("wechat_official_account", "cover_asset_id", "封面选择器已打开，但没有找到图片上传控件")
    upload.set_input_files(payload["cover_path"])
    page.wait_for_timeout(2500)
    for label in ("确定", "完成", "使用"):
        if click_text(page, label, 3000):
            break
    page.wait_for_timeout(1500)
    if not wechat_cover_ready(cover):
        return field_error("wechat_official_account", "cover_asset_id", "封面上传后未读到已选图片，未标记预览就绪")
    fields.add("cover")
    if mode == "execute":
        return click_publish(page, "wechat_official_account", data["target_id"])
    return evidence(page, data["target_id"], mode, fields,
                    {"title": payload["title"], "body_length": len(payload["body"])})


def authentication_required(page):
    text = page.locator("body").inner_text()
    return re.search(r"接收短信验证码|请输入验证码|获取验证码|扫码登录|安全验证|验证身份|微信验证", text)


def authentication_interrupted(page, platform, target_id):
    evidence_result = evidence(page, target_id, "login_required", set(), {
        "status": "login_required", "field": "verification",
        "error": "平台要求验证码、扫码或安全验证，尚未公开发布",
        "action": "在保留的后台页面完成验证；任务将等待 5 分钟，不要重复发布"})
    if platform != "douyin":
        return evidence_result
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        for label in ("发布成功", "发表成功", "提交成功"):
            success = visible_text(page, label)
            if success:
                return evidence(page, target_id, "published", {"published"}, {
                    "status": "published", "published_evidence": success.inner_text()[:300], "url": None})
        if not authentication_required(page):
            page.wait_for_timeout(5000)
            return evidence(page, target_id, "unknown", set(), {
                "status": "unknown_remote", "error": "验证页面已关闭，但未读到明确成功证据，请到后台核对"})
        page.wait_for_timeout(1000)
    return evidence_result


def click_publish(page, platform, target_id, title=None):
    if authentication_required(page):
        return authentication_interrupted(page, platform, target_id)
    click_visible(page.get_by_role("button", name="我知道了", exact=True), 3000)
    labels = ("发表",) if platform == "wechat_official_account" else ("发布", "发表")
    clicked = False
    if platform == "xiaohongshu":
        clicked = click_xhs_action(page, "发布")
    for label in labels if not clicked else ():
        buttons = page.get_by_text(label, exact=True)
        for index in range(buttons.count()):
            button = buttons.nth(index)
            try:
                if button.is_visible() and button.is_enabled():
                    button.click()
                    clicked = True
                    break
            except Exception:
                continue
        if clicked:
            break
    if not clicked:
        return field_error(platform, "publish_button", "没有找到可用的最终发表按钮，未执行发表")
    page.wait_for_timeout(2000)
    if authentication_required(page):
        return authentication_interrupted(page, platform, target_id)
    confirmations = page.get_by_role("button", name=re.compile("确定|确认发表|确认发布|继续发布"))
    for index in range(confirmations.count()):
        button = confirmations.nth(index)
        try:
            if button.is_visible() and button.is_enabled():
                button.click()
                break
        except Exception:
            continue
    page.wait_for_timeout(5000)
    if authentication_required(page):
        return authentication_interrupted(page, platform, target_id)
    for label in ("发布成功", "发表成功", "提交成功"):
        success = visible_text(page, label)
        if success:
            return evidence(page, target_id, "published", {"published"}, {"status": "published", "published_evidence": success.inner_text()[:300], "url": None})
    if platform == "douyin" and title and visible_text(page, title, 5000):
        return evidence(page, target_id, "published", {"published"}, {
            "status": "published", "published_evidence": "抖音内容管理列表存在标题：" + title, "url": page.url})
    return evidence(page, target_id, "unknown", set(), {"status": "unknown_remote", "error": "已执行点击，但未读到明确成功证据，请到平台后台核对"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("login", "prepare", "execute", "verify"), required=True)
    parser.add_argument("--platform", choices=tuple(URLS), required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--payload-file")
    args = parser.parse_args()
    if sync_playwright is None:
        raise RuntimeError("发布 worker 需要在 .venv-topics 隔离环境运行 Playwright")
    with sync_playwright() as playwright:
        context = open_context(playwright, Path(args.profile).resolve())
        try:
            page = context.pages[0] if context.pages else context.new_page()
            if args.action == "login":
                page.goto(URLS[args.platform], wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(300000)
                result = {"status": "browser_closed", "login_verified": False, "next_action": "返回发布中心重新生成预览"}
            else:
                data = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
                if args.action == "verify" and args.platform == "xiaohongshu":
                    result = verify_xhs_video(page, data)
                elif args.action == "verify" and args.platform == "douyin":
                    result = verify_douyin(page, data)
                elif args.platform == "douyin":
                    result = prepare_douyin(page, data, args.action)
                elif args.platform == "xiaohongshu" and data["source"]["kind"] == "video":
                    result = prepare_xhs_video(page, data, args.action)
                elif args.platform == "xiaohongshu":
                    result = prepare_xhs_article(page, data, args.action)
                elif args.platform == "wechat_official_account":
                    result = prepare_wechat_article(page, data, args.action)
                elif args.platform == "wechat_channels":
                    result = prepare_wechat_channels(page, data, args.action)
                else:
                    result = field_error(args.platform, "connector", "该平台没有可用连接器，未执行发布")
            if result.get("status") == "error":
                diagnostic = evidence(page, locals().get("data", {}).get("target_id"), "error", set())
                result["screenshot"] = diagnostic["screenshot"]
                result["page_text"] = page.locator("body").inner_text()[-2000:]
            print(json.dumps(result, ensure_ascii=False))
        except Exception as error:
            result = {"status": "error", "error": str(error)[:800]}
            try:
                diagnostic = evidence(page, locals().get("data", {}).get("target_id"), "error", set())
                result["screenshot"] = diagnostic["screenshot"]
                result["page_text"] = page.locator("body").inner_text()[-2000:]
            except Exception:
                pass
            print(json.dumps(result, ensure_ascii=False))
        finally:
            context.close()


if __name__ == "__main__":
    main()
