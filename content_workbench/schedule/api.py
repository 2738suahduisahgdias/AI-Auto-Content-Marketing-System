import re
import threading

from content_workbench.domain.errors import DomainError


class ScheduleAPI:
    def __init__(self, app, service):
        self.app = app
        self.service = service

    def handle(self, handler, method, path, body):
        body = body or {}
        if method == "GET" and path == "/api/schedule/bootstrap":
            return self.app.response(handler, {"schedules": self.service.list_schedules(), "csrf_token": self.app.csrf(self.app.cookie(handler))})
        if method == "POST" and path == "/api/schedule":
            schedule = self.service.create_schedule(body.get("batches"), body.get("first_run_at"),
                int(body.get("interval_minutes", 30)), int(body.get("daily_limit", 20)), "local_user", handler.headers.get("Idempotency-Key"))
            return self.app.response(handler, schedule, 201)
        match = re.fullmatch(r"/api/schedule/([^/]+)", path)
        if method == "GET" and match:
            return self.app.response(handler, self.service.get_schedule(match.group(1)))
        if method == "PUT" and match:
            return self.app.response(handler, self.service.update_schedule(match.group(1), body.get("first_run_at"),
                body.get("interval_minutes"), body.get("daily_limit"), body.get("status")))
        match = re.fullmatch(r"/api/schedule/([^/]+)/cancel", path)
        if method == "POST" and match:
            return self.app.response(handler, self.service.cancel_schedule(match.group(1)))
        if method == "POST" and path == "/api/schedule/dispatch":
            return self.app.response(handler, {"jobs": self.service.due_jobs()})
        raise DomainError("SCHEDULE_API_NOT_FOUND", "发布调度接口不存在", 404)


class ScheduleDispatcher:
    def __init__(self, service, interval=15):
        self.service = service
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, name="publish-schedule-dispatcher", daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop_event.is_set():
            try:
                self.service.due_jobs()
            except Exception as error:
                print("publish schedule error:", repr(error), flush=True)
            self.stop_event.wait(self.interval)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(2)
