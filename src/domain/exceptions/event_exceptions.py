"""领域层 事件异常模块

定义事件存储与事件发布相关异常
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import ConflictError
from src.domain.exceptions.system_exceptions import MessageBusError


class EventPublishError(MessageBusError):
    """事件发布失败异常

    继承 MessageBusError（EXCEPTION_104，SystemException）。
    用于 Outbox/RabbitMQ 事件发布失败场景。
    """

    code = "EXCEPTION_104"
    message = "Event publish failed"

    def __init__(
        self,
        event_type: str | None = None,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
    ) -> None:
        self.event_type = event_type
        if message is None:
            message = f"Event publish failed: {event_type}"
        ctx: dict = {"event_type": event_type}
        if context:
            ctx.update(context)
        super().__init__(message=message, cause=cause, context=ctx)


class VersionError(ConflictError):
    """乐观锁冲突异常"""

    code = "EXCEPTION_251"
    message = "Version conflict"


__all__ = [
    "EventPublishError",
    "VersionError",
]
