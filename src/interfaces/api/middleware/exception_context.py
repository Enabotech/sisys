"""SISYS 接口层请求上下文注入中间件模块

为每个请求注入唯一追踪 ID，便于日志和异常追踪

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class ExceptionContextMiddleware(BaseHTTPMiddleware):
    """为每个请求注入唯一追踪 ID."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
