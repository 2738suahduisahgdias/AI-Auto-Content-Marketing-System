import json
import os
import threading
import uuid
from pathlib import Path
from content_workbench.domain.errors import DomainError
from .protocol import request_code, verify, timestamp

class LicenseService:
    def __init__(self, root, mode=None):
        self.root = Path(root)
        self.folder = self.root/'license'
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.mode = mode or os.environ.get('CONTENT_AGENT_LICENSE_MODE', 'legacy')
        self.state_path = self.folder/'state.json'
        if not self.state_path.exists():
            self.save({'installationId': uuid.uuid4().hex, 'onboarding': {'version': 1, 'steps': [], 'completed': False}})

    def read(self):
        try:
            return json.loads(self.state_path.read_text())
        except (ValueError, OSError):
            raise DomainError('LICENSE_STORAGE', '本地授权记录无法读取，请恢复授权备份，不会自动重置安装标识', 503)

    def save(self, state):
        temp = self.state_path.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as out:
            os.chmod(temp, 0o600)
            json.dump(state, out, ensure_ascii=False)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, self.state_path)

    def keys(self):
        path = self.folder/'public-keys.json'
        if not path.exists():
            return {}
        try:
            keys = json.loads(path.read_text())
            if not isinstance(keys, dict):
                raise ValueError()
            return keys
        except (ValueError, OSError):
            raise DomainError('LICENSE_KEYS', '签发公钥配置损坏，请联系经营者', 503)

    def status(self):
        with self.lock:
            state = self.read()
            result = {'mode': self.mode, 'status': 'unactivated', 'installationId': state['installationId'],
                      'requestCode': request_code(state['installationId']), 'onboarding': state['onboarding'],
                      'storageRoot': str(self.root), 'configured': bool(self.keys()), 'license': None}
            if state.get('token'):
                try:
                    result['license'] = verify(state['token'], self.keys(), state['installationId'])
                    result['status'] = 'valid'
                except DomainError as error:
                    result.update(status=error.code, message=error.message)
            return result

    def require_active(self):
        if self.mode == 'legacy':
            return
        status = self.status()
        if status['status'] != 'valid':
            raise DomainError('LICENSE_REQUIRED', status.get('message', '请先完成离线激活；已有项目和成果仍可查看'), 403)

    def activate(self, token):
        with self.lock:
            state = self.read()
            verified = verify(token, self.keys(), state['installationId'])
            # Failed import never replaces a working license. Older entitlements cannot downgrade it.
            if state.get('token'):
                try:
                    old = verify(state['token'], self.keys(), state['installationId'])
                except DomainError:
                    old = None
                if old and old['licenseId'] != verified['licenseId']:
                    if old.get('expiresAt') is None or (verified.get('expiresAt') and timestamp(verified['expiresAt']) < timestamp(old['expiresAt'])):
                        raise DomainError('LICENSE_DOWNGRADE', '此授权会缩短现有有效期，未覆盖当前授权')
            state['token'] = token.strip()
            self.save(state)
            return self.status()

    def onboarding(self, body):
        self.require_active()
        with self.lock:
            state = self.read()
            current = state['onboarding']
            step = body.get('step')
            if step not in ('storage', 'environment', 'capabilities', 'project', 'complete', 'restart'):
                raise DomainError('ONBOARDING_STEP', '未知引导步骤')
            if step == 'restart':
                current['completed'] = False
            elif step == 'complete':
                current['completed'] = True
            else:
                current['steps'] = list(dict.fromkeys([*current['steps'], step]))
            self.save(state)
            return self.status()
