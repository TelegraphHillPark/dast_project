import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.uuid7 import uuid7

logger = logging.getLogger("dast.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Присваивает каждому запросу UUIDv7 Request-ID и логирует метрики."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid7()
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "%s %s %s %.1fms rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response
