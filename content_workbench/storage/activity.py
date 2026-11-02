"""One gate for local writes and desktop workspace transitions."""
import threading
from contextlib import contextmanager
from content_workbench.domain.errors import DomainError

class ActivityGate:
    def __init__(self):
        self.lock = threading.RLock()
        self.active = 0
        self.switching = False

    @contextmanager
    def operation(self):
        with self.lock:
            if self.switching:
                raise DomainError('WORKSPACE_SWITCHING', '工作区正在切换，请等待新页面打开后重试', 409)
            self.active += 1
        try:
            yield
        finally:
            with self.lock: self.active -= 1

    def switch(self, prepare):
        with self.lock:
            if self.switching or self.active:
                raise DomainError('WORKSPACE_BUSY', '仍有生成、渲染、上传或保存操作进行中，请完成后再切换', 409)
            result = prepare()
            self.switching = True
            return result

ACTIVITY = ActivityGate()
