"""Operator-only local issuer. Never bundle this directory into a customer app."""
import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from content_workbench.licensing.protocol import PRODUCT, canonical, encode, openssl, read_request, timestamp

class Issuer:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.key = self.root/'signing-key.encrypted.pem'
        self.lock = threading.RLock()
        self.db = self.root/'customers.sqlite3'
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS licenses(id TEXT PRIMARY KEY, record TEXT NOT NULL)')
        os.chmod(self.db, 0o600)

    def public(self, password):
        return openssl(['pkey', '-in', str(self.key), '-passin', 'stdin', '-pubout'], (password+'\n').encode()).decode()

    def initialize(self, password, backup=None):
        if not isinstance(password, str) or len(password) < 12 or '\n' in password:
            raise ValueError('私钥密码至少 12 个字符，不能含换行；请离线妥善保管')
        with self.lock:
            if self.key.exists():
                raise ValueError('已有签名私钥，不能覆盖')
            with tempfile.TemporaryDirectory(dir=self.root) as tmp:
                key = Path(tmp)/'key.pem'
                if backup is not None:
                    if not isinstance(backup, str) or len(backup) > 16000 or not backup.startswith('-----BEGIN ENCRYPTED PRIVATE KEY-----'):
                        raise ValueError('只接受加密 PEM 私钥备份')
                    key.write_text(backup)
                else:
                    openssl(['genpkey', '-algorithm', 'ED25519', '-aes-256-cbc', '-pass', 'stdin', '-out', str(key)], (password+'\n').encode())
                public = openssl(['pkey', '-in', str(key), '-passin', 'stdin', '-pubout'], (password+'\n').encode()).decode()
                # Verify restored key really is Ed25519 using a signing roundtrip.
                (Path(tmp)/'data').write_bytes(b'key-check')
                sig = openssl(['pkeyutl', '-sign', '-rawin', '-inkey', str(key), '-passin', 'stdin', '-in', str(Path(tmp)/'data')], (password+'\n').encode())
                if len(sig) != 64:
                    raise ValueError('备份不是 Ed25519 密钥')
                os.chmod(key, 0o600)
                os.replace(key, self.key)
                (self.root/'public-keys.json').write_text(json.dumps({self.key_id(public): public}))
            return self.status()

    @staticmethod
    def key_id(public):
        return hashlib.sha256(public.encode()).hexdigest()[:16]

    def records(self):
        with sqlite3.connect(self.db) as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT record FROM licenses ORDER BY rowid DESC')]

    def status(self):
        return {'initialized': self.key.exists(), 'records': self.records(), 'root': str(self.root),
                'publicKeys': json.loads((self.root/'public-keys.json').read_text()) if (self.root/'public-keys.json').exists() else {}}

    def issue(self, body):
        with self.lock:
            installation = read_request(body.get('requestCode', ''))
            for name in ('name', 'wechat', 'notes', 'kind', 'parentId', 'password'):
                if not isinstance(body.get(name, ''), str) or len(body.get(name, '')) > 4000:
                    raise ValueError('客户字段格式或长度无效')
            if not body.get('name', '').strip():
                raise ValueError('请输入客户称呼')
            parent = body.get('parentId', '')
            records = {record['licenseId']: record for record in self.records()}
            if body.get('kind') in ('续期', '换机补发') and not parent:
                raise ValueError('续期或换机补发请选择原授权记录')
            if parent and parent not in records:
                raise ValueError('续期或补发的原授权不存在')
            days = body.get('days')
            if days is not None and (type(days) is not int or not 1 <= days <= 3650):
                raise ValueError('期限应为 1–3650 天，或选择长期')
            password = body.get('password', '')
            public = self.public(password)
            now = datetime.now(timezone.utc)
            expiry = (now + timedelta(days=days)).isoformat() if days else None
            payload = {'schemaVersion': 1, 'licenseId': uuid.uuid4().hex, 'productId': PRODUCT,
                       'installationId': installation, 'issuedAt': now.isoformat(), 'expiresAt': expiry,
                       'features': ['workbench'], 'keyId': self.key_id(public)}
            with tempfile.TemporaryDirectory(dir=self.root) as tmp:
                data = Path(tmp)/'payload'
                data.write_bytes(canonical(payload))
                signature = openssl(['pkeyutl', '-sign', '-rawin', '-inkey', str(self.key), '-passin', 'stdin', '-in', str(data)], (password+'\n').encode())
            token = 'YXLIC1.' + encode(canonical(payload)) + '.' + encode(signature)
            record = {**payload, 'customerId': records[parent]['customerId'] if parent else uuid.uuid4().hex,
                      'name': body['name'].strip(), 'wechat': body.get('wechat', ''), 'notes': body.get('notes', ''),
                      'kind': body.get('kind', '正式'), 'parentId': parent, 'status': '已发码',
                      'requestCode': body['requestCode'], 'token': token}
            with sqlite3.connect(self.db) as conn:
                conn.execute('INSERT INTO licenses VALUES (?,?)', (record['licenseId'], json.dumps(record, ensure_ascii=False)))
            return record

    def update_customer(self, body):
        with self.lock, sqlite3.connect(self.db) as conn:
            row = conn.execute('SELECT record FROM licenses WHERE id=?', (body.get('licenseId'),)).fetchone()
            if not row:
                raise ValueError('授权记录不存在')
            record = json.loads(row[0])
            for key in ('name', 'wechat', 'notes'):
                value = body.get(key)
                if not isinstance(value, str) or len(value) > 4000 or (key == 'name' and not value.strip()):
                    raise ValueError('客户字段格式无效')
                record[key] = value
            conn.execute('UPDATE licenses SET record=? WHERE id=?', (json.dumps(record, ensure_ascii=False), record['licenseId']))
            return record

    def restore_records(self, records):
        if not isinstance(records, list) or len(records) > 10000:
            raise ValueError('客户备份格式无效')
        for record in records:
            if not isinstance(record, dict) or any(not isinstance(record.get(k), str) for k in ('licenseId','customerId','name','wechat','notes','token','requestCode','issuedAt')):
                raise ValueError('客户备份记录缺少必要字段')
            read_request(record['requestCode'])
            timestamp(record['issuedAt'])
        with self.lock, sqlite3.connect(self.db) as conn:
            for record in records:
                record = {**record, 'status': '已发码'}
                conn.execute('INSERT OR IGNORE INTO licenses VALUES (?,?)', (record['licenseId'], json.dumps(record, ensure_ascii=False)))
        return self.status()

def serve(root, port):
    issuer = Issuer(root)
    sessions = {}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log customer records, codes or passwords.
        def send(self, body, status=200, content_type='application/json', cookie=None):
            raw = body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type+'; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.end_headers()
            self.wfile.write(raw)
        def guard(self, write=False):
            from http.cookies import SimpleCookie
            if self.headers.get('Host') != f'127.0.0.1:{port}':
                raise ValueError('仅允许本机地址')
            if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{port}'):
                raise ValueError('拒绝跨站请求')
            cookie = SimpleCookie(self.headers.get('Cookie', '')).get('yx_issuer')
            session = cookie.value if cookie else ''
            if session not in sessions or (write and not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), sessions[session])):
                raise ValueError('本地会话失效，请刷新管理页')
            return sessions[session]
        def do_GET(self):
            try:
                if self.path == '/':
                    if self.headers.get('Host') != f'127.0.0.1:{port}':
                        raise ValueError('仅允许本机地址')
                    session = secrets.token_urlsafe(32)
                    sessions[session] = secrets.token_urlsafe(32)
                    return self.send(Path(__file__).with_name('issuer.html').read_text(), content_type='text/html', cookie=f'yx_issuer={session}; HttpOnly; SameSite=Strict; Path=/')
                csrf = self.guard()
                if self.path == '/api/status':
                    return self.send({**issuer.status(), 'csrf': csrf})
                if self.path == '/api/key-backup':
                    return self.send({'encryptedPem': issuer.key.read_text()})
                self.send({'error': '页面不存在'}, 404)
            except Exception as error:
                self.send({'error': str(error)}, 400)
        def do_POST(self):
            try:
                self.guard(True)
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 5_000_000:
                    raise ValueError('请求大小无效')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('请求格式无效')
                if self.path == '/api/initialize':
                    return self.send(issuer.initialize(body.get('password'), body.get('backup')))
                if self.path == '/api/issue':
                    return self.send(issuer.issue(body))
                if self.path == '/api/customer':
                    return self.send(issuer.update_customer(body))
                if self.path == '/api/restore':
                    return self.send(issuer.restore_records(body.get('records')))
                self.send({'error': '接口不存在'}, 404)
            except Exception as error:
                self.send({'error': str(error)}, 400)
    print(f'授权管理端 http://127.0.0.1:{port} （只在本机运行）', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, help='独立于客户目录的经营者私密目录')
    parser.add_argument('--port', type=int, default=8848)
    args = parser.parse_args()
    serve(args.root, args.port)
