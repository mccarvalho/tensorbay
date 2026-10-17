"""Middleware that assigns/propagates a correlation ID per request."""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from neocloud.core.logging import correlation_id_ctx

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        token = correlation_id_ctx.set(cid)
        request.state.correlation_id = cid
        try:
            response = await call_next(request)
        finally:
            correlation_id_ctx.reset(token)
        response.headers[CORRELATION_HEADER] = cid
        return response
