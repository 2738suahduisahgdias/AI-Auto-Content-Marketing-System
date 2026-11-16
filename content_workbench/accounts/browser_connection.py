"""Dedicated Chrome lifecycle; clients can select actions but never supply commands."""

import threading
from contextlib import nullcontext
from pathlib import Path
from typing import Optional

from content_workbench.accounts.dedicated_browser import (
    ensure_started,
    status as browser_status,
    stop,
)
from content_workbench.domain.errors import DomainError

_lock = threading.Lock()


def status() -> dict:
    return browser_status()


def control(action: Optional[str], db_path: Optional[Path] = None) -> dict:
    if action not in {"start", "stop", "restart"}:
        raise DomainError("BROWSER_ACTION_INVALID", "不支持的浏览器操作", 422)
    if not _lock.acquire(blocking=False):
        raise DomainError(
            "BROWSER_SERVICE_BUSY", "浏览器操作正在进行，请稍后重新检测", 409
        )
    from content_workbench.storage.db import connect, immediate

    try:
        with (
            connect(db_path) if db_path else nullcontext() as conn,
            immediate(conn) if conn else nullcontext(),
        ):
            if conn and action in {"stop", "restart"}:
                busy = conn.execute(
                    "SELECT 1 FROM wb_jobs WHERE resource_key='browser' "
                    "AND status IN ('queued','leased','running','retry_wait','cancel_requested') LIMIT 1"
                ).fetchone()
                if busy:
                    raise DomainError(
                        "BROWSER_TASK_ACTIVE",
                        "浏览器任务尚未结束，请等待完成或在任务页取消后再操作",
                        409,
                    )
            if action == "start":
                ensure_started()
            elif action == "stop":
                return {**stop(), **status()}
            else:
                stop()
                ensure_started()
            return status()
    finally:
        _lock.release()
