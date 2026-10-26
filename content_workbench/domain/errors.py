import uuid


class DomainError(Exception):
    def __init__(self, code, message, status=400, field=None, action=None, item=None, retryable=False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.field = field
        self.action = action
        self.item = item
        self.retryable = retryable
        self.trace_id = "trace_" + uuid.uuid4().hex[:16]

    def as_dict(self):
        return {"error": {"code": self.code, "message": self.message, "field": self.field,
                          "action": self.action, "item": self.item, "retryable": self.retryable,
                          "trace_id": self.trace_id}}
