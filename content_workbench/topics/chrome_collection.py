"""Reuse the existing Chrome bridge and the original Douyin DOM parsers."""
import json
import time
from content_workbench.domain.errors import DomainError
from content_workbench.publishing.webbridge_worker import Bridge
from content_workbench.topics.browser_worker import HOT_URL, PROFILE_URL, public_items, visible_videos

class ReadPage:
    def __init__(self, bridge): self.bridge = bridge
    def evaluate(self, script, argument=None):
        return self.bridge.evaluate('(' + script + ')(' + json.dumps(argument, ensure_ascii=False) + ')')

def collect(action, collection=None, url=None):
    bridge = Bridge(session='yingxu-douyin-research')
    try:
        bridge.goto(HOT_URL if action == 'hot' else url if action == 'details' else PROFILE_URL)
        page = ReadPage(bridge)
        text = json.dumps(bridge.snapshot(), ensure_ascii=False)
        if action != 'hot' and ('扫码登录' in text or '登录后查看' in text):
            raise DomainError('LOGIN_REQUIRED', '请在已打开的 Chrome 中登录抖音后重试', 409, 'browser', '完成扫码后重新同步')
        if action == 'login':
            if '收藏夹' not in text:
                raise DomainError('LOGIN_REQUIRED', '尚未确认抖音个人收藏夹，请完成登录后重试', 409)
            return {'status': 'ok', 'login_verified': True}
        if action == 'hot':
            items = public_items(page, 20)
            if not items:
                raise DomainError('HOT_STRUCTURE_CHANGED', '未读取到抖音热榜，不使用空列表覆盖旧数据', 409)
            for index, item in enumerate(items, 1):
                item['rank'] = index
                item['metadata']['rank'] = index
            return {'status': 'ok', 'items': items}
        if action == 'favorites':
            if collection:
                bridge.wait_for_text(collection, timeout=45)
            clicked = bool(collection) and bridge.click_text(collection)
            if collection and not clicked:
                # Static text in collection cards may have no accessibility ref.
                clicked = bridge.evaluate("(() => {const title=" + json.dumps(collection) + ";const nodes=[...document.querySelectorAll('main *,[role=tabpanel] *,#user_detail_element *,[id=\"user_detail_element\"] *,li *,div')];const target=nodes.find(e=>(e.innerText||'').trim()===title && ![...e.children].some(c=>(c.innerText||'').trim()===title));if(!target)return false;target.click();return true})()") is True
            if not clicked:
                raise DomainError('COLLECTION_NOT_FOUND', '未找到收藏夹：' + str(collection), 409, 'collection', '核对个人收藏夹名称')
            time.sleep(3)
            items = {}
            quiet = 0
            for _ in range(15):
                before = len(items)
                for item in visible_videos(page): items[item['canonical_url']] = item
                quiet = quiet + 1 if before == len(items) else 0
                if quiet >= 3 or len(items) >= 100: break
                bridge.evaluate("() => {const candidates=[document.scrollingElement,...document.querySelectorAll('main,section,div')].filter(e=>e&&e.scrollHeight>e.clientHeight+100);for(const e of candidates)e.scrollTop+=1500;return true}")
                time.sleep(1)
            if not items and not any(word in json.dumps(bridge.snapshot(), ensure_ascii=False) for word in ('暂无作品', '还没有收藏', '暂无收藏')):
                raise DomainError('COLLECTION_INCOMPLETE', '收藏夹未读取到作品，保留旧快照', 409)
            return {'status': 'ok', 'items': list(items.values())}
        if action == 'details':
            details = page.evaluate("() => {const a=[...document.querySelectorAll('a[href*=\"/user/\"]')].find(a=>(a.innerText||'').trim() && a.innerText.trim()!=='我的');const cover=document.querySelector('meta[property=\"og:image\"]')?.content||document.querySelector('video[poster]')?.poster||'';return {author_name:a?a.innerText.trim():'',author_url:a?a.href:'',...(cover?{cover_url:cover}:{})}}")
            return {'status': 'ok', 'details': details or {}}
        raise DomainError('BROWSER_ACTION_INVALID', '未支持的采集操作', 422)
    except DomainError: raise
    except Exception as error:
        raise DomainError('BROWSER_SYNC_FAILED', str(error)[:500], 409, 'browser', '检查 Chrome 连接后手动重试')
