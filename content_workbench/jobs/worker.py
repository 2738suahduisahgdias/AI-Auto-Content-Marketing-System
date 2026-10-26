import os
import signal
import subprocess
import threading
import time
import uuid

from content_workbench.domain.errors import DomainError
from .store import JobStore


class UnknownRemote(Exception):
    pass


class JobCancelled(Exception):
    pass


class ExecutionContext:
    def __init__(self, worker, job):
        self.worker = worker
        self.job = job
        self.store = worker.store
        self.job_id = job["id"]
        self.owner = worker.owner
        self.token = job["fencing_token"]
        self.processes = set()
        self.lock = threading.Lock()

    def progress(self, stage, progress=None):
        self.store.heartbeat(self.job_id, self.owner, self.token, stage, progress)

    def check_cancelled(self):
        current = self.store.get(self.job_id)
        if current["status"] == "cancel_requested":
            raise JobCancelled()

    def run_process(self, arguments, timeout=600, stage="running", cwd=None):
        self.progress(stage)
        process = subprocess.Popen(arguments, cwd=str(cwd or self.worker.root), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                   start_new_session=True)
        with self.lock:
            self.processes.add(process)
        started = time.monotonic()
        try:
            while True:
                try:
                    stdout, stderr = process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    self.check_cancelled()
                    if time.monotonic() - started > timeout:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.communicate()
                        raise DomainError("PROCESS_TIMEOUT", "执行超过 {} 秒".format(timeout), 504, "job", "检查任务日志后重试")
                    self.store.heartbeat(self.job_id, self.owner, self.token, stage)
            if len(stdout) + len(stderr) > 2 * 1024 * 1024:
                raise DomainError("PROCESS_OUTPUT_LIMIT", "外部命令输出超过限制", 502)
            if process.returncode:
                raise DomainError("PROCESS_FAILED", "外部命令失败：" + " ".join(stderr.strip().split())[:500], 502,
                                  "job", "查看失败阶段和命令错误，修正后重试", retryable=False)
            return stdout, stderr
        except JobCancelled:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
            raise
        finally:
            with self.lock:
                self.processes.discard(process)


class Worker:
    def __init__(self, db_path=None, executors=None, root=None, poll_interval=0.25):
        self.store = JobStore(db_path)
        self.executors = executors or {}
        self.owner = "worker_" + uuid.uuid4().hex[:16]
        self.root = root
        self.poll_interval = poll_interval
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run_forever, name="workbench-worker", daemon=True)
        self.thread.start()

    def stop(self, timeout=5):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout)

    def run_forever(self):
        while not self.stop_event.is_set():
            job = self.store.lease(self.owner)
            if not job:
                self.stop_event.wait(self.poll_interval)
                continue
            self.execute(job)

    def execute(self, job):
        context = ExecutionContext(self, job)
        try:
            executor = self.executors.get(job["kind"])
            if not executor:
                raise DomainError("EXECUTOR_NOT_FOUND", "没有任务执行器：" + job["kind"], 500)
            context.progress("running", 0.05)
            result = executor(job, context)
            self.store.assert_lease(job["id"], self.owner, job["fencing_token"])
            self.store.finish(job["id"], self.owner, job["fencing_token"], result=result)
        except JobCancelled:
            self.store.finish(job["id"], self.owner, job["fencing_token"], status="cancelled",
                              error={"code": "JOB_CANCELLED", "message": "任务已取消"})
        except UnknownRemote as error:
            self.store.finish(job["id"], self.owner, job["fencing_token"], status="unknown_remote",
                              error={"code": "UNKNOWN_REMOTE", "message": str(error), "retryable": False})
        except DomainError as error:
            if error.code == "FENCING_REJECTED":
                return
            status = "cancelled" if error.code == "JOB_CANCELLED" else "failed"
            self.store.finish(job["id"], self.owner, job["fencing_token"], status=status,
                              error={"code": error.code, "message": error.message, "field": error.field,
                                     "action": error.action, "trace_id": error.trace_id})
        except Exception as error:
            job_now = self.store.get(job["id"])
            status = "retry_wait" if job_now["attempt_count"] < job_now["max_attempts"] else "failed"
            self.store.finish(job["id"], self.owner, job["fencing_token"], status=status,
                              error={"code": "WORKER_ERROR", "message": str(error)[:1000], "retryable": status == "retry_wait"})
