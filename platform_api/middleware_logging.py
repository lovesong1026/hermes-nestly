"""Request-scoped logging context (request_id + optional user_id)."""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_request_id_var: ContextVar[Optional[str]] = ContextVar(
    "platform_request_id", default=None
)
_user_id_var: ContextVar[Optional[str]] = ContextVar(
    "platform_user_id", default=None
)

logger = logging.getLogger("hermes.platform.access")


def get_request_id() -> Optional[str]:
    return _request_id_var.get()


def get_request_user_id() -> Optional[str]:
    return _user_id_var.get()


def set_request_user_id(user_id: Optional[str]) -> None:
    """Bind authenticated user into log context (called from deps)."""
    _user_id_var.set(user_id)


class RequestIdFilter(logging.Filter):
    """Inject request_id / user_id into LogRecord extras for formatters."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"  # type: ignore[attr-defined]
        record.user_id = get_request_user_id() or "-"  # type: ignore[attr-defined]
        return True


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Generate/propagate X-Request-ID and emit a structured access line."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = (request.headers.get("x-request-id") or "").strip()
        request_id = incoming or uuid.uuid4().hex
        token_rid = _request_id_var.set(request_id)
        token_uid = _user_id_var.set(None)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logger.info(
                "method=%s path=%s status=%s duration_ms=%.1f request_id=%s user_id=%s",
                request.method,
                request.url.path,
                status_code,
                elapsed_ms,
                request_id,
                get_request_user_id() or "-",
            )
            _request_id_var.reset(token_rid)
            _user_id_var.reset(token_uid)


def install_request_logging() -> None:
    """Attach RequestIdFilter to platform loggers (idempotent)."""
    filt = RequestIdFilter()
    root = logging.getLogger("hermes.platform")
    if not any(isinstance(f, RequestIdFilter) for f in root.filters):
        root.addFilter(filt)
