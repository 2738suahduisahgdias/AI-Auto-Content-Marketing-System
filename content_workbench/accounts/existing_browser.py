import json
import re
import time

from content_workbench.accounts.exports import number
from content_workbench.accounts.platform_worker import fill_channels_titles, labeled_metrics
from content_workbench.publishing.webbridge_worker import Bridge

LOGIN_URLS = {
    "xiaohongshu_login": "https://creator.xiaohongshu.com/",
    "xhs_personal_login": "https://www.xiaohongshu.com/explore",
    "douyin_publish_login": "https://creator.douyin.com/creator-micro/content/upload",
    "channels_login": "https://channels.weixin.qq.com/login.html",
    "official_login": "https://mp.weixin.qq.com/",
}


def text(snapshot):
    return json.dumps(snapshot.get("tree", []), ensure_ascii=False)


def verified(snapshot, action):
    url = snapshot.get("url", "")
    body = text(snapshot)
    if action in ("xiaohongshu_login", "xhs_personal_login"):
        return "login" not in url and "扫码登录" not in body and "电脑设备登录超限" not in body
    if action == "douyin_publish_login":
        return "login" not in url and "短信验证" not in body and "扫码登录" not in body
    if action == "channels_login":
        return "login" not in url and "登录视频号助手" not in body
    if action == "official_login":
        return bool(re.search(r"[?&]token=\d+", url)) or ("使用账号登录" not in body and "扫码登录" not in body)
    return False


def body(bridge):
    return bridge.evaluate("""() => {
      const texts=[];function walk(root){
        if(root.body)texts.push(root.body.innerText||'');
        for(const element of root.querySelectorAll('*'))if(element.shadowRoot)walk(element.shadowRoot);
      }walk(document);return texts.sort((a,b)=>b.length-a.length)[0]||'';
    }""") or ""


def click_dom_text(bridge, text):
    script = """(()=>{const wanted=%s;const all=[];function walk(root){
      for(const element of root.querySelectorAll('*')){all.push(element);if(element.shadowRoot)walk(element.shadowRoot)}
    }walk(document);const element=all.find(e=>{if(e.childElementCount!==0||(e.innerText||'').trim()!==wanted)return false;const rect=e.getBoundingClientRect();return rect.width>0&&rect.height>0});
    if(!element)return false;element.click();return true})()""" % json.dumps(text, ensure_ascii=False)
    return bool(bridge.evaluate(script))


def wait_click_dom_text(bridge, title, timeout=20):
    """AX text can arrive before the collection card is mounted and clickable."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if click_dom_text(bridge, title):
            return True
        time.sleep(0.5)
    return False


def xhs_card_title(card):
    if card.get("title"):
        return card["title"]
    ignored = {"未通过", "已发布", "审核中", "仅自己可见", "查看修改建议"}
    lines = [line.strip() for line in card.get("text", "").split("\n") if line.strip()]
    candidates = [line for line in lines if line not in ignored and not re.fullmatch(r"[\d.,]+[万wW]?", line)
                  and not re.fullmatch(r"\d{2}:\d{2}", line) and not line.startswith("查看修改建议")
                  and not re.search(r"20\d{2}-\d{2}-\d{2}", line)]
    return max(candidates, key=len, default="")


def xhs_notes(bridge):
    bridge.goto("https://creator.xiaohongshu.com/new/note-manager")
    time.sleep(5)
    if "login" in bridge.snapshot().get("url", ""):
        return {"status": "login_required"}
    cards = bridge.evaluate("""() => Array.from(document.querySelectorAll('[data-impression]')).map(card => ({
      title: card.querySelector('.note-card__title')?.innerText.trim() || '',
      text: card.innerText,
      impression: card.getAttribute('data-impression') || '',
      cover: card.querySelector('.note-card__media')?.style.backgroundImage || card.querySelector('img')?.src || ''
    }))""") or []
    items = []
    for card in cards:
        try:
            impression = json.loads(card["impression"])
            note_id = impression.get("noteTarget", {}).get("value", {}).get("noteId", "")
        except (TypeError, json.JSONDecodeError):
            note_id = ""
        title = xhs_card_title(card)
        if not note_id or not title:
            continue
        published_at = re.search(r"20\d{2}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?", card["text"])
        items.append({"title": title, "canonical_url": "https://www.xiaohongshu.com/explore/" + note_id,
                      "platform_item_id": note_id,
                      "metadata": {"title": title, "cover_url": card["cover"], "visible_text": card["text"][:2000],
                                   "visible_metrics": re.findall(r"\d+(?:\.\d+)?[万wW]?", card["text"]),
                                   "published_at": published_at.group(0) if published_at else None}})
    return {"status": "ok", "profile": {"published_notes_count": len(items)}, "items": items}


def xhs_favorite_cards(bridge):
    return bridge.evaluate("""(() => {
      const result=[];const seen=new Set();
      for(const a of document.querySelectorAll('a[href*="/explore/"],a[href*="/search_result/"],a[href*="/board/"]')){
        const href=a.href;const match=href.match(/(?:explore|search_result)\\/([0-9a-zA-Z]+)/)||href.match(/board\\/[0-9a-zA-Z]+\\/([0-9a-zA-Z]+)/);
        if(!match||seen.has(match[1]))continue;
        const container=a.closest('section,li,article')||a;
        const text=(container.innerText||a.innerText||'').trim();
        const lines=text.split('\\n').map(x=>x.trim()).filter(Boolean);
        const image=a.querySelector('img')||container.querySelector('img');
        const title=(image?.alt||'').trim()||lines.filter(x=>x.length>1&&!/^\\d+(\\.\\d+)?[万wW]?$/.test(x)).sort((a,b)=>b.length-a.length)[0]||'';
        if(!title)continue;
        const like_count=lines.find(x=>/^\\d+(\\.\\d+)?[万wW]?$/.test(x))||null;
        seen.add(match[1]);result.push({title,canonical_url:'https://www.xiaohongshu.com/explore/'+match[1],platform_item_id:match[1],
          metadata:{title,visible_text:text.slice(0,1000),cover_url:image?.src||'',like_count,visible_metrics:like_count?[like_count]:[]}});
        if(result.length>=100)break;
      }
      return result;
    })()""") or []


def xhs_favorites(bridge, collections):
    bridge.goto("https://www.xiaohongshu.com/explore")
    time.sleep(3)
    current = body(bridge)
    if "login" in bridge.snapshot().get("url", "") or "扫码登录" in current or "电脑设备登录超限" in current or "手机号登录" in current:
        return {"status": "login_required", "error": "个人小红书需要重新登录", "action": "点击连接个人小红书，在现有浏览器完成扫码后重试"}
    profile_url = bridge.evaluate("""(() => {
      const link=Array.from(document.querySelectorAll('a[href*="/user/profile/"]')).find(a=>a.href);
      return link?link.href:'';
    })()""")
    if not profile_url:
        return {"status": "error", "error": "未找到个人主页入口，可能未登录或页面结构已变化", "action": "确认个人小红书已登录，并检查页面是否改版"}
    # 收藏 defaults to loose notes; collections live under the 专辑/board subtab.
    board_url = profile_url.split("?", 1)[0] + "?tab=fav&subTab=board"
    grouped = {}
    errors = []
    for source, title in collections.items():
        if not title:
            continue
        bridge.call("navigate", {"url": board_url})
        bridge.wait_for_text(title, timeout=15)
        bridge.evaluate("() => { window.scrollTo(0,0); return true; }")
        if not wait_click_dom_text(bridge, title):
            grouped[source] = []
            errors.append({"source": source, "code": "COLLECTION_NOT_FOUND", "message": "等待页面加载后仍未找到可点击的收藏夹：" + title,
                           "action": "先确认个人收藏页已加载并重试；名称确实不一致时再修改配置。旧数据不会因此删除"})
            continue
        time.sleep(2)
        collected = {}
        quiet = 0
        for _ in range(5):
            for item in xhs_favorite_cards(bridge):
                item["metadata"]["collection_name"] = title
                item["metadata"]["source_name"] = "个人小红书收藏夹"
                collected[item["canonical_url"]] = item
            previous = len(collected)
            bridge.evaluate("() => { window.scrollBy(0,1800); return true; }")
            time.sleep(1)
            for item in xhs_favorite_cards(bridge):
                item["metadata"]["collection_name"] = title
                item["metadata"]["source_name"] = "个人小红书收藏夹"
                collected[item["canonical_url"]] = item
            quiet = quiet + 1 if len(collected) == previous else 0
            if quiet >= 2:
                break
        grouped[source] = list(collected.values())
        if not grouped[source]:
            errors.append({"source": source, "code": "EMPTY_OR_STRUCTURE_CHANGED", "message": "收藏夹未读取到笔记：" + title,
                           "action": "确认收藏夹确实为空；不为空时检查页面结构，不重复刷新"})
    return {"status": "ok", "collections": grouped, "errors": errors}


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
    cards = bridge.evaluate("""() => {
      const cards=[];function walk(root){
        for(const card of root.querySelectorAll('.post-feed-item'))cards.push({
          text:card.innerText,title:card.querySelector('.post-title')?.innerText.trim()||'',
          cover:card.querySelector('img')?.src||'',
          counts:Array.from(card.querySelectorAll('.post-data .data-item .count')).map(e=>e.innerText)
        });
        for(const element of root.querySelectorAll('*'))if(element.shadowRoot)walk(element.shadowRoot);
      }walk(document);return cards;
    }""") or []
    items = []
    for card in cards:
        lines = [line.strip() for line in card["text"].split("\n") if line.strip()]
        values = card.get("counts") or []
        keys = ["views", "likes", "comments", "shares", "favorites"]
        title = card.get("title") or "未读取标题"
        items.append({"title": title, "canonical_url": "https://channels.weixin.qq.com/platform/post/list",
                      "metadata": {"title": title, "visible_text": card["text"][:2000], "cover_url": card["cover"],
                                   "published_at": next((line for line in lines if re.match(r"20\d{2}年", line)), None)},
                      "metrics": {key: values[index] if index < len(values) else None for index, key in enumerate(keys)}})
    totals = {key: sum(number(item["metrics"].get(key)) or 0 for item in items) for key in keys}
    return {"status": "ok", "profile": {**labeled_metrics(current, "wechat_channels"), **totals, "videos_count": len(items)},
            "items": fill_channels_titles(items, current)}


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
        item["metadata"]["record_scope"] = "asset"
    return {"status": "ok", "profile": {**labeled_metrics(current, "wechat_official_account"),
            "content_scope": "素材库/商品消息，非发表历史"}, "items": items}


def metric(text, label):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for index, line in enumerate(lines[:-1]):
        if line == label:
            value = number(lines[index + 1])
            if value is not None and "分钟" in lines[index + 1]:
                value = round(value * 60, 1)
            return value
    return None


def wait_for_metric(bridge, label, timeout=20):
    deadline = time.monotonic() + timeout
    while True:
        current = body(bridge)
        if metric(current, label) is not None:
            return current
        if time.monotonic() >= deadline:
            return current
        time.sleep(0.5)


def data_period(text):
    match = re.search(r"统计(?:周期|时间)[： ]?([^\n]+)", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"历史数据更新至([^\n，]+)", text)
    return match.group(1).strip() if match else None


def douyin_content_metrics(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    favorites = 0
    weighted = []
    for index, line in enumerate(lines):
        if line == "收藏" and index + 1 < len(lines):
            value = number(lines[index + 1])
            if value is not None:
                favorites += value
        if line == "完播率" and index + 1 < len(lines):
            rate = number(lines[index + 1])
            views = None
            for previous in range(index - 1, max(-1, index - 13), -1):
                if lines[previous] == "播放" and previous + 1 < index:
                    views = number(lines[previous + 1])
                    break
            if rate is not None and views:
                weighted.append((rate, views))
    total_weight = sum(weight for _, weight in weighted)
    completion = round(sum(rate * weight for rate, weight in weighted) / total_weight, 2) if total_weight else None
    return {"favorites": favorites, "completionRate": completion,
            "content_metrics_scope": "内容管理当前已加载作品"}


def douyin_analytics(bridge):
    bridge.goto("https://creator.douyin.com/creator-micro/data-center/operation")
    current = wait_for_metric(bridge, "播放量", 40)
    if "登录" in current and "数据总览" not in current:
        return {"status": "login_required"}
    if "数据总览" not in current:
        return {"status": "error", "error": "抖音数据中心尚未加载完成", "action": "打开数据中心/运营数据后重新读取，不自动重试"}
    profile = {
        "views": metric(current, "总播放量"), "likes": metric(current, "总点赞量"), "shares": metric(current, "总分享量"),
        "comments": metric(current, "总评论量"), "engagementRate": metric(current, "互动率"),
        "completionRate": metric(current, "完播率"), "fiveSecondCompletionRate": metric(current, "5秒完播率"),
        "twoSecondBounceRate": metric(current, "2秒跳出率"), "coverClickRate": metric(current, "封面点击率"),
        "avgConsumptionSeconds": metric(current, "平均播放时长"), "periodPublications": metric(current, "投稿量"),
        "fans": metric(current, "总粉丝量"), "newFollowers": metric(current, "粉丝净增"),
        "gainedFollowers": metric(current, "吸粉量"), "lostFollowers": metric(current, "脱粉量"),
        "returningFans": metric(current, "回访粉丝量"), "data_period": data_period(current),
        "analytics_source": "抖音数据中心/运营数据",
    }
    bridge.goto("https://creator.douyin.com/creator-micro/content/manage")
    bridge.wait_for_text("内容管理", 20)
    current = body(bridge)
    for _ in range(5):
        previous = current
        bridge.evaluate("() => { window.scrollTo(0, document.body.scrollHeight); return true; }")
        time.sleep(1.5)
        current = body(bridge)
        if current == previous:
            break
    profile.update(douyin_content_metrics(current))
    bridge.goto("https://creator.douyin.com/creator-micro/home")
    current = wait_for_metric(bridge, "主页访问量", 40)
    profile["profileVisits"] = metric(current, "主页访问量")
    profile["unavailable_fields"] = {"impressions": "当前账号运营页、内容管理和官方导出未提供独立曝光指标；播放量不冒充曝光"}
    return {"status": "ok", "profile": profile}


def xhs_analytics(bridge):
    bridge.goto("https://creator.xiaohongshu.com/statistics/account/v2")
    bridge.wait_for_text("账号诊断", 20)
    current = body(bridge)
    if "账号诊断" not in current:
        return {"status": "login_required"}
    profile = {"impressions": metric(current, "曝光数"), "views": metric(current, "观看数"),
               "coverClickRate": metric(current, "封面点击率"), "avgConsumptionSeconds": metric(current, "平均观看时长"),
               "totalConsumptionSeconds": metric(current, "观看总时长"), "completionRate": metric(current, "视频完播率"),
               "data_period": data_period(current), "analytics_source": "小红书数据看板/账号概览"}
    sections = [("互动数据", {"likes": "点赞数", "comments": "评论数", "favorites": "收藏数", "shares": "分享数"}),
                ("涨粉数据", {"newFollowers": "净涨粉", "gainedFollowers": "新增关注", "lostFollowers": "取消关注",
                              "profileVisits": "主页访客", "profileConversionRate": "主页转粉率"}),
                ("发布数据", {"periodPublications": "总发布", "videoPublications": "发布视频", "imagePublications": "发布图文"})]
    for section, mapping in sections:
        bridge.wait_for_text(section, 10)
        if not click_dom_text(bridge, section):
            return {"status": "error", "error": "数据看板缺少" + section, "action": "打开账号概览后重新读取，不自动重试"}
        bridge.wait_for_text(next(iter(mapping.values())), 10)
        current = body(bridge)
        for key, label in mapping.items():
            profile[key] = metric(current, label)
    profile["interactions"] = sum(profile.get(key) or 0 for key in ("likes", "comments", "favorites", "shares"))
    return {"status": "ok", "profile": profile}


def channels_analytics(bridge):
    bridge.goto("https://channels.weixin.qq.com/platform/post/list")
    if not click_dom_text(bridge, "数据中心"):
        return {"status": "error", "error": "未找到视频号数据中心入口", "action": "在视频号助手打开数据中心"}
    bridge.wait_for_text("视频数据", 10)
    if not bridge.click_text("视频数据"):
        return {"status": "error", "error": "未找到视频号视频数据入口", "action": "在数据中心选择视频数据"}
    current = wait_for_metric(bridge, "播放", 25)
    if "关键指标" not in current:
        return {"status": "login_required"}
    daily = []
    for line in current.split("\n"):
        match = re.match(r"^(20\d{2}/\d{2}/\d{2})\s+(.+)$", line.strip())
        if match:
            daily.append({"date": match.group(1), "values": match.group(2).split()})
    period_views = sum(number(row["values"][0]) or 0 for row in daily) if daily else None
    return {"status": "ok", "profile": {"views": metric(current, "播放"), "periodViews": period_views,
            "comments": metric(current, "评论"), "shares": metric(current, "分享"), "newFollowers": metric(current, "关注"),
            "data_period": data_period(current), "daily_history": daily,
            "analytics_source": "视频号数据中心/视频数据"}}


def official_analytics(bridge):
    bridge.goto("https://mp.weixin.qq.com/")
    time.sleep(4)
    current = body(bridge)
    if "使用账号登录" in current or "扫码登录" in current:
        return {"status": "login_required"}
    link = bridge.evaluate("""() => {
      const anchor=Array.from(document.querySelectorAll('a[href]')).find(a=>(a.innerText||'').trim()==='内容分析');
      return anchor?anchor.href:'';
    }""")
    if not link:
        return {"status": "error", "error": "未找到公众号内容分析入口", "action": "在公众号后台打开数据分析/内容分析"}
    bridge.goto(link)
    time.sleep(4)
    current = body(bridge)
    profile = {"readers": metric(current, "阅读(次)"), "views": metric(current, "阅读(次)"), "shares": metric(current, "分享(次)"),
               "completedReads": metric(current, "完成阅读(次)"), "data_period": data_period(current),
               "analytics_source": "公众号数据分析/内容分析"}
    query = re.search(r"[?&]token=(\d+)", bridge.snapshot().get("url", ""))
    if query:
        bridge.goto("https://mp.weixin.qq.com/misc/useranalysis?&token=" + query.group(1) + "&lang=zh_CN")
        time.sleep(4)
        current = body(bridge)
        for key, label in (("newFollowers", "新关注人数"), ("lostFollowers", "取消关注人数"),
                           ("netFollowers", "净增关注人数"), ("fans", "累积关注人数")):
            value = metric(current, label)
            if value is not None:
                profile[key] = value
    return {"status": "ok", "profile": profile}


def run(action, **kwargs):
    bridge = Bridge()
    try:
        if action in LOGIN_URLS:
            bridge.goto(LOGIN_URLS[action])
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                snapshot = bridge.snapshot()
                if verified(snapshot, action):
                    next_action = "同步个人小红书四个收藏夹" if action == "xhs_personal_login" else "自动同步全部账号并刷新数据"
                    return {"status": "ok", "login_verified": True, "next_action": next_action}
                time.sleep(3)
            return {"status": "login_required", "error": "3 分钟内未完成登录", "action": "请重新发起登录，在现有浏览器中完成扫码或验证"}
        if action == "xhs_favorites":
            return xhs_favorites(bridge, kwargs.get("collections") or {})
        collectors = {"xhs_notes": xhs_notes, "douyin_account": douyin_account,
                      "channels_account": channels_account, "official_account": official_account,
                      "douyin_analytics": douyin_analytics, "xhs_analytics": xhs_analytics,
                      "channels_analytics": channels_analytics, "official_analytics": official_analytics}
        if action not in collectors:
            raise ValueError("不支持的账号采集动作：" + action)
        return collectors[action](bridge)
    except Exception as error:
        return {"status": "error", "error": str(error)[:500], "action": "检查现有浏览器连接后手动重试，不会自动新建浏览器或重复拉取"}
