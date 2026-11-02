"""Local Weixin transport. No legacy gateway, model tool calls or shell bridge."""
import base64
import json
import os
import secrets
import threading
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

BASE = 'https://ilinkai.weixin.qq.com'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('微信接口重定向未获允许')


def checked_base(value):
    p = urlsplit(value)
    if p.scheme != 'https' or not (p.hostname == 'ilinkai.weixin.qq.com' or (p.hostname or '').endswith('.ilinkai.weixin.qq.com')) or p.username or p.password or p.port not in (None, 443) or p.query or p.fragment or p.path not in ('', '/'):
        raise ValueError('微信服务地址无效')
    return value.rstrip('/')


def request(base, endpoint, body=None, token=''):
    headers = {'Content-Type':'application/json', 'iLink-App-Id':'bot',
               'iLink-App-ClientVersion':str(2 << 16 | 4 << 8 | 10),
               'AuthorizationType':'ilink_bot_token',
               'X-WECHAT-UIN':base64.b64encode(str(secrets.randbits(32)).encode()).decode()}
    if token: headers['Authorization'] = 'Bearer ' + token
    if body is not None:
        body = {**body, 'base_info':{'channel_version':'2.4.10','bot_agent':'Yingxu/0.1.1'}}
    req = Request(checked_base(base) + '/' + endpoint, data=None if body is None else json.dumps(body).encode(), headers=headers)
    with build_opener(NoRedirect()).open(req, timeout=35) as r:
        result = json.load(r)
    if result.get('ret',0) or result.get('errcode',0):
        raise ValueError('微信接口错误：' + str(result.get('errcode') or result.get('ret')))
    return result


class WechatClient:
    def __init__(self, root, inbox, transport=request):
        self.path = Path(root)/'config/wechat-client.json'
        self.inbox, self.request = inbox, transport
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.login = {}
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.error = ''

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        fd = os.open(tmp, os.O_CREAT|os.O_TRUNC|os.O_WRONLY, 0o600)
        with os.fdopen(fd,'w') as f: json.dump(self.state, f)
        os.replace(tmp,self.path)

    def status(self):
        return {'status': self.login.get('status') or ('connected' if self.state.get('token') else 'disconnected'),
                'error':self.error, 'received':self.state.get('received',0),
                'qrcode_url':self.login.get('qrcode_url',''), 'transport':'local_direct'}

    def begin_login(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError('请先断开当前微信连接')
            data = self.request(BASE, 'ilink/bot/get_bot_qrcode?bot_type=3', {'local_token_list':[]})
            self.login = {'qrcode':data['qrcode'],'qrcode_url':data['qrcode_img_content'],'status':'wait','base':BASE}
            self.error = ''
            return self.status()

    def poll_login(self, code=''):
        with self.lock:
            if not self.login: return self.status()
            query = {'qrcode':self.login['qrcode']}
            if code: query['verify_code'] = code
            data = self.request(self.login['base'], 'ilink/bot/get_qrcode_status?' + urlencode(query))
            status = data.get('status','wait')
            self.login['status'] = status
            if status == 'scaned_but_redirect':
                self.login['base'] = checked_base('https://' + data['redirect_host'])
            if status == 'confirmed':
                if not all(data.get(k) for k in ('bot_token','ilink_bot_id','ilink_user_id')):
                    raise ValueError('扫码返回缺少身份信息，未建立连接')
                self.state = {'token':data['bot_token'],'bot':data['ilink_bot_id'],'owner':data['ilink_user_id'],
                              'base':checked_base(data.get('baseurl') or BASE),'cursor':'','received':0}
                self.save(); self.login = {}; self.start()
            return self.status()

    def process(self, msg):
        if msg.get('from_user_id') != self.state.get('owner') or msg.get('group_id') or msg.get('message_type') != 1:
            return
        mid = str(msg.get('message_id') or '')
        if not mid: raise ValueError('消息没有平台 ID，未确认入库')
        text = '\n'.join(i.get('text_item',{}).get('text','') for i in msg.get('item_list',[]) if i.get('type') == 1).strip()
        # Media is kept as metadata; never claim a media file was downloaded.
        record, created = self.inbox.ingest({'msgid':'weixin:'+self.state['bot']+':'+mid,
            'sender_id':self.state['owner'],'source':'local_clawbot','message_type':'text' if text else 'unknown',
            'text':text,'raw_payload':{'items':msg.get('item_list',[])}})
        if not record.get('id') or record.get('ingest_status') != 'saved': raise ValueError('入库未确认')
        if msg.get('context_token'):
            self.request(self.state['base'],'ilink/bot/sendmessage',{'msg':{
                'from_user_id':'','to_user_id':self.state['owner'],'client_id':'yingxu-ack-'+mid,
                'message_type':2,'message_state':2,'context_token':msg['context_token'],
                'item_list':[{'type':1,'text_item':{'text':'已保存到待分类' if text else '已保存消息信息，附件尚未下载'}}]}},self.state['token'])
        if created: self.state['received'] = self.state.get('received',0)+1

    def run_once(self):
        data = self.request(self.state['base'],'ilink/bot/getupdates',{'get_updates_buf':self.state.get('cursor','')},self.state['token'])
        for msg in data.get('msgs',[]): self.process(msg)
        # Commit cursor only after all messages are persisted and replies succeed.
        self.state['cursor'] = data.get('get_updates_buf',self.state.get('cursor',''))
        self.save()
        self.error = ''

    def start(self):
        if not self.state.get('token') or (self.thread and self.thread.is_alive()): return
        self.stop_event.clear()
        def loop():
            while not self.stop_event.is_set():
                try: self.run_once()
                except Exception as e:
                    self.error = '微信接收暂未成功（'+type(e).__name__+'），将自动重试；保存进度未跳过。'
                    self.stop_event.wait(5)
        self.thread = threading.Thread(target=loop,daemon=True,name='yingxu-wechat')
        self.thread.start()

    def disconnect(self):
        with self.lock:
            self.stop_event.set()
            if self.thread:
                self.thread.join(timeout=40)
                if self.thread.is_alive():
                    raise ValueError('微信连接仍在结束，请稍后重试')
            self.thread = None
            self.state = {}
            self.login = {}
            self.error = ''
            self.save()
            return self.status()

    def stop(self):
        self.stop_event.set()
