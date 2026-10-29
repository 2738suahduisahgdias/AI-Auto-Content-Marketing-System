import json
import re
import time

from content_workbench.accounts.platform_worker import fill_channels_titles, labeled_metrics
from content_workbench.publishing.webbridge_worker import Bridge

LOGIN_URLS = {
    "xiaohongshu_login": "https://creator.xiaohongshu.com/",
    "douyin_publish_login": "https://creator.douyin.com/creator-micro/content/upload",
    "channels_login": "https://channels.weixin.qq.com/login.html",
    "official_login": "https://mp.weixin.qq.com/",
}


def text(snapshot):
    return json.dumps(snapshot.get("tree", []), ensure_ascii=False)


def verified(snapshot, action):
    url = snapshot.get("url", "")
    body = text(snapshot)
    if action == "xiaohongshu_login":
        return "login" not in url and "扫码登录" not in body
    if action == "douyin_publish_login":
        return "login" not in url and "短信验证" not in body and "扫码登录" not in body
    if action == "channels_login":
        return "login" not in url and "登录视频号助手" not in body
    if action == "official_login":
        return bool(re.search(r"[?&]token=\d+", url)) or ("使用账号登录" not in body and "扫码登录" not in body)
    return False


def body(bridge):
    return bridge.evaluate("""() => {
      const bodies=Array.from(document.querySelectorAll('body')).map(e=>e.innerText||'');
      return bodies.sort((a,b)=>b.length-a.length)[0]||'';
    }""") or ""


def xhs_notes(bridge):
    bridge.goto("https://creator.xiaohongshu.com/new/note-manager")
    time.sleep(5)
    if "login" in bridge.snapshot().get("url", ""):
        return {"status": "login_required"}
    cards = bridge.evaluate("""() => Array.from(document.querySelectorAll('.note-card')).map(card => ({
      title: card.querySelector('.note-card__title')?.innerText.trim() || '',
      text: card.innerText,
      impression: card.getAttribute('data-impression') || '',
      cover: card.querySelector('.note-card__media')?.style.backgroundImage || ''
    }))""")
    items = []
    for card in cards:
        if not card.get("title"):
            continue
        try:
            impression = json.loads(card["impression"])
            note_id = impression.get("noteTarget", {}).get("value", {}).get("noteId", "")
        except (TypeError, json.JSONDecodeError):
            note_id = ""
        published_at = re.search(r"20\d{2}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?", card["text"])
        items.append({"title": card["title"], "canonical_url": "https://www.xiaohongshu.com/explore/" + note_id if note_id else "https://creator.xiaohongshu.com/new/note-manager",
                      "platform_item_id": note_id or None,
                      "metadata": {"title": card["title"], "cover_url": card["cover"], "visible_text": card["text"][:2000],
                                   "visible_metrics": re.findall(r"\d+(?:\.\d+)?[万wW]?", card["text"]),
                                   "published_at": published_at.group(0) if published_at else None}})
    return {"status": "ok", "profile": {}, "items": items}


def douyin_account(bridge):
    bridge.goto("https://www.douyin.com/user/self")
    time.sleep(3)
    current = body(bridge)
    if "login" in bridge.snapshot().get("url", "") or "登录后查看" in current:
        return {"status": "login_required"}
    bridge.evaluate("() => { window.scrollTo(0, 2200); return true; }")
    time.sleep(3)
    current = body(bridge)
    def match(pattern):
        found = re.search(pattern, current)
        return found.group(1) if found else None
    profile = {"account_name": match(r"抖音号：([^\n]+)"), "fans": match(r"粉丝\s*(\d+(?:\.\d+)?[万wW]?)"),
               "likes": match(r"获赞\s*(\d+(?:\.\d+)?[万wW]?)"), "works_count": match(r"作品\s*(\d+)")}
    items = bridge.evaluate("""() => {
      const result=[];const seen=new Set();
      for(const a of document.querySelectorAll('a[href*="/video/"]:has(img),a[href*="/note/"]:has(img)')){
        const href=a.href;if(seen.has(href))continue;
        const box=(a.innerText||a.closest('li')?.innerText||'').trim();
        const lines=box.split('\\n').map(x=>x.trim()).filter(Boolean);
        const title=lines.filter(x=>x.length>1&&!/^\\d+(\\.\\d+)?[万wW]?$/.test(x)).sort((a,b)=>b.length-a.length)[0]||'未读取标题';
        const match=href.match(/(?:video|note)\\/([0-9A-Za-z_-]+)/);
        const like_count=lines.find(x=>/^\\d+(\\.\\d+)?[万wW]?$/.test(x))||'';
        const cover_url=a.querySelector('img')?.src||'';
        seen.add(href);result.push({title,canonical_url:href,platform_item_id:match?match[1]:null,metadata:{title,visible_text:box.slice(0,1000),cover_url,like_count}});
        if(result.length>=20)break;
      }
      return result;
    }""")
    return {"status": "ok", "profile": profile, "items": items}


def channels_account(bridge):
    bridge.goto("https://channels.weixin.qq.com/platform/post/list")
    time.sleep(5)
    current = body(bridge)
    if "login" in bridge.snapshot().get("url", "") or "登录视频号助手" in current:
        return {"status": "login_required"}
    cards = bridge.evaluate("""() => Array.from(document.querySelectorAll('.post-feed-item')).map(card => ({
      text: card.innerText,
      cover: card.querySelector('img')?.src || '',
      counts: Array.from(card.querySelectorAll('.post-data .data-item .count')).map(e=>e.innerText)
    }))""")
    items = []
    for card in cards:
        lines = [line.strip() for line in card["text"].split("\n") if line.strip()]
        values = card.get("counts") or []
        keys = ["views", "likes", "comments", "shares", "favorites"]
        items.append({"title": "未读取标题", "canonical_url": "https://channels.weixin.qq.com/platform/post/list",
                      "metadata": {"title": "未读取标题", "visible_text": card["text"][:2000], "cover_url": card["cover"],
                                   "published_at": next((line for line in lines if re.match(r"20\d{2}年", line)), None)},
                      "metrics": {key: values[index] if index < len(values) else None for index, key in enumerate(keys)}})
    return {"status": "ok", "profile": labeled_metrics(current, "wechat_channels"), "items": fill_channels_titles(items, current)}


def official_account(bridge):
    bridge.goto("https://mp.weixin.qq.com/")
    time.sleep(5)
    current = body(bridge)
    if "使用账号登录" in current or "扫码登录" in current:
        return {"status": "login_required"}
    query = re.search(r"[?&]token=(\d+)", bridge.snapshot().get("url", ""))
    if query:
        bridge.goto("https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_list&action=list&token=" + query.group(1))
        time.sleep(4)
        current = body(bridge)
    items = bridge.evaluate("""() => {
      const result=[];const seen=new Set();
      for(const a of document.querySelectorAll('a[href]')){
        const href=a.href;const text=(a.innerText||a.closest('tr')?.innerText||a.closest('li')?.innerText||'').trim();
        if(!text||seen.has(href)||!/appmsg|__biz/.test(href))continue;
        const lines=text.split('\\n').map(x=>x.trim()).filter(Boolean);
        const title=lines.filter(x=>x.length>1&&!/^[\\d.,]+[万wW]?$/.test(x)).sort((a,b)=>b.length-a.length)[0];
        if(!title)continue;
        seen.add(href);result.push({title,canonical_url:href,metadata:{title,visible_text:text.slice(0,2000),cover_url:a.querySelector('img')?.src||''}});
        if(result.length>=50)break;
      }
      return result;
    }""")
    for item in items:
        published_at = re.search(r"20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}", item["metadata"].get("visible_text", ""))
        item["metadata"]["published_at"] = published_at.group(0) if published_at else None
        item["metrics"] = labeled_metrics(item["metadata"].get("visible_text", ""), "wechat_official_account")
    return {"status": "ok", "profile": labeled_metrics(current, "wechat_official_account"), "items": items}


def run(action):
    bridge = Bridge()
    try:
        if action in LOGIN_URLS:
            bridge.goto(LOGIN_URLS[action])
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                snapshot = bridge.snapshot()
                if verified(snapshot, action):
                    return {"status": "ok", "login_verified": True, "next_action": "自动同步全部账号并刷新数据"}
                time.sleep(3)
            return {"status": "login_required", "error": "3 分钟内未完成登录", "action": "请重新发起登录，在现有浏览器中完成扫码或验证"}
        collectors = {"xhs_notes": xhs_notes, "douyin_account": douyin_account,
                      "channels_account": channels_account, "official_account": official_account}
        if action not in collectors:
            raise ValueError("不支持的账号采集动作：" + action)
        return collectors[action](bridge)
    except Exception as error:
        return {"status": "error", "error": str(error)[:500], "action": "检查现有浏览器连接后手动重试，不会自动新建浏览器或重复拉取"}
