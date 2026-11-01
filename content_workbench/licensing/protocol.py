"""Ed25519 verification through OpenSSL 3+; no custom cryptography."""
import base64
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from content_workbench.domain.errors import DomainError

PRODUCT = 'liuliang-yingxu'

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')

def decode(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('invalid encoding')
    return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)

def openssl(args, password=None):
    binary = shutil.which('openssl')
    if not binary:
        raise DomainError('CRYPTO_UNAVAILABLE', '需要安装支持 Ed25519 的 OpenSSL 3+，然后重试', 503)
    result = subprocess.run([binary, *args], input=password, capture_output=True, timeout=15)
    if result.returncode:
        raise ValueError('密码、签名或 OpenSSL 能力校验失败')
    return result.stdout

def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('日期格式无效')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('日期缺少时区')
    return parsed

def request_code(installation):
    return 'YXREQ1.' + encode(canonical({'productId': PRODUCT, 'installationId': installation}))

def read_request(code):
    try:
        if len(code) > 1024 or not code.startswith('YXREQ1.'):
            raise ValueError()
        value = json.loads(decode(code[7:]))
        if value['productId'] != PRODUCT or not re.fullmatch(r'[a-f0-9]{32}', value['installationId']):
            raise ValueError()
        return value['installationId']
    except (ValueError, TypeError, KeyError):
        raise DomainError('INVALID_REQUEST', '申请码格式无效，请复制客户界面的完整申请码')

def verify(token, keys, installation, now=None):
    try:
        if not isinstance(token, str) or len(token) > 16000:
            raise ValueError()
        version, payload, signature = token.strip().split('.')
        if version != 'YXLIC1':
            raise DomainError('LICENSE_VERSION', '不支持此授权格式，请更新客户端')
        raw = decode(payload)
        data = json.loads(raw)
        if not isinstance(data, dict) or canonical(data) != raw:
            raise ValueError()
        if data.get('schemaVersion') != 1:
            raise DomainError('LICENSE_VERSION', '不支持此授权版本，请更新客户端')
        for field in ('licenseId', 'productId', 'installationId', 'issuedAt', 'keyId'):
            if not isinstance(data.get(field), str) or not 1 <= len(data[field]) <= 200:
                raise ValueError()
        if not isinstance(data.get('features'), list) or data['features'] != ['workbench']:
            raise ValueError()
        key = keys.get(data['keyId'])
        if not isinstance(key, str):
            raise DomainError('LICENSE_KEY', '客户端没有此签发公钥，请联系刘洋更新公钥配置')
        sig = decode(signature)
        if len(sig) != 64:
            raise ValueError()
        with tempfile.TemporaryDirectory(prefix='yx-verify-') as tmp:
            folder = Path(tmp)
            (folder/'public.pem').write_text(key)
            (folder/'payload').write_bytes(raw)
            (folder/'signature').write_bytes(sig)
            try:
                openssl(['pkeyutl', '-verify', '-pubin', '-inkey', str(folder/'public.pem'), '-rawin', '-in', str(folder/'payload'), '-sigfile', str(folder/'signature')])
            except ValueError:
                raise DomainError('LICENSE_SIGNATURE', '授权签名无效，内容可能被修改，请重新导入')
        if data['productId'] != PRODUCT:
            raise DomainError('LICENSE_PRODUCT', '此授权不属于刘量映序工作台')
        if data['installationId'] != installation:
            raise DomainError('LICENSE_DEVICE', '此授权属于另一台安装，请发送本机申请码重新发码')
        now = now or datetime.now(timezone.utc)
        issued = timestamp(data['issuedAt'])
        expiry = timestamp(data['expiresAt']) if data.get('expiresAt') is not None else None
        if expiry and expiry <= issued:
            raise ValueError()
        if issued > now:
            raise DomainError('LICENSE_CLOCK', '本机时间早于授权签发时间，请检查系统时间')
        if expiry and expiry <= now:
            raise DomainError('LICENSE_EXPIRED', '授权已到期，可以查看已有成果；继续制作请联系续期', 403)
        return data
    except DomainError:
        raise
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise DomainError('LICENSE_INVALID', '授权码内容无效，请复制完整授权码或重新导入文件')
