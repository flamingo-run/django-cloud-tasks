class GoogleCredentialsException(Exception):
    def __init__(self):
        message = "GCP_JSON or GCP_B64 env variable not set properly"
        super().__init__(message)


class TaskNotFound(Exception):
    def __init__(self, name: str):
        message = f"Task {name} not registered."
        super().__init__(message)


class DiscardTaskException(Exception):
    default_http_status_code: int = 202
    default_http_status_reason: str | None = None  # only needed for custom HTTP status codes

    def __init__(self, *args, http_status_code: int | None = None, http_status_reason: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.http_status_code = http_status_code or self.default_http_status_code
        self.http_status_reason = http_status_reason or self.default_http_status_reason
