from contextvars import ContextVar, Token

_headers_token = ContextVar("DJANGO_CLOUD_TASKS_HEADERS_TOKEN", default={})


def set_current_headers(value: dict) -> Token[dict]:
    return _headers_token.set(value)


def get_current_headers() -> dict:
    return _headers_token.get()


def reset_current_headers(ctx_token: Token[dict] | None = None):
    if ctx_token:
        _headers_token.reset(ctx_token)
    else:
        _headers_token.set({})
