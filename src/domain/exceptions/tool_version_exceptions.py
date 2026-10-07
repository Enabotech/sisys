"""领域层工具版本异常模块（Story 4-6 — 灰度发布与回滚）

tool_version 子域（430-439）首批 4 个异常：
- EXCEPTION_430 ToolVersionNotFoundError (404)——版本不存在
  （精确查找空 / rollback 显式目标无记录 / 有记录但无活跃版本可路由）
- EXCEPTION_431 ToolVersionAlreadyExistsError (409)——(tool_id, version) 重复注册
- EXCEPTION_432 ToolVersionTrafficWeightError (400)——权重非法（<=0 或 >100）、
  canary_only 版本 PENDING 直接全量、无 STABLE 请求灰度、并存冲突族
  （活跃 CANARY 并存 / 单 STABLE·单 CANARY 不变量并发破坏）
- EXCEPTION_433 ToolVersionRollbackError (409)——无可回滚稳定历史 / 目标非可回滚态

434-439 暂不分配，保持空段预留（后续协调）。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
)


class ToolVersionNotFoundError(NotFoundError):
    """工具版本不存在（EXCEPTION_430，HTTP 404）。

    触发场景：精确版本查找落空 / rollback 显式目标无记录 /
    有版本记录但无活跃版本可路由。

    Attributes:
        code: 错误码 EXCEPTION_430
        message: 默认消息
    """

    code = "EXCEPTION_430"
    message = "Tool version not found"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        version: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """以领域上下文构造异常。

        Args:
            message: 自定义消息（默认类消息）
            tool_id: 所属工具 ID
            version: 版本号
            cause: 根因异常
        """
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if version is not None:
            context["version"] = version
        super().__init__(message=message, cause=cause, context=context)


class ToolVersionAlreadyExistsError(ConflictError):
    """工具版本重复注册（EXCEPTION_431，HTTP 409）。

    触发场景：相同 (tool_id, version) 再次注册（仓储唯一约束 + PG UNIQUE
    索引双重保证；并发注册的 IntegrityError 经仓储转换为本异常）。

    Attributes:
        code: 错误码 EXCEPTION_431
        message: 默认消息
    """

    code = "EXCEPTION_431"
    message = "Tool version already exists"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        version: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """以领域上下文构造异常。

        Args:
            message: 自定义消息
            tool_id: 所属工具 ID
            version: 版本号
            cause: 根因异常（并发场景的 IntegrityError）
        """
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if version is not None:
            context["version"] = version
        super().__init__(message=message, cause=cause, context=context)


class ToolVersionTrafficWeightError(ValidationError):
    """工具版本流量权重/发布约束冲突（EXCEPTION_432，HTTP 400）。

    触发场景（权重 + 并存冲突族）：
    - 发布权重非法（<=0 或 >100——发布参数域 (0,100]）
    - canary_only 版本 PENDING 状态直接全量（promote 转正放行）
    - 无 STABLE 版本时请求灰度（灰度必是二元流量分配）
    - 活跃 CANARY 并存冲突（对其他版本发起灰度）
    - 单 STABLE/单 CANARY 不变量并发破坏（partial unique index 冲突经
      仓储转换 / InMemory save 守卫）

    Attributes:
        code: 错误码 EXCEPTION_432
        message: 默认消息
    """

    code = "EXCEPTION_432"
    message = "Tool version traffic weight or rollout constraint violated"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        version: str | None = None,
        traffic_weight: int | None = None,
        conflict_reason: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """以领域上下文构造异常。

        Args:
            message: 自定义消息
            tool_id: 所属工具 ID
            version: 版本号
            traffic_weight: 非法权重值（权重类场景）
            conflict_reason: 并存冲突原因（冲突族场景）
            cause: 根因异常（并发场景的 IntegrityError）
        """
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if version is not None:
            context["version"] = version
        if traffic_weight is not None:
            context["traffic_weight"] = traffic_weight
        if conflict_reason is not None:
            context["conflict_reason"] = conflict_reason
        super().__init__(message=message, cause=cause, context=context)


class ToolVersionRollbackError(InvalidStateError):
    """工具版本回滚状态冲突（EXCEPTION_433，HTTP 409）。

    触发场景：无当前 STABLE 或无可回滚稳定历史 / 显式目标非"曾稳定"版本
    （非 DEPRECATED 或 last_stable_at 为空）。

    Attributes:
        code: 错误码 EXCEPTION_433
        message: 默认消息
    """

    code = "EXCEPTION_433"
    message = "Tool version rollback not allowed"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        target_version: str | None = None,
        reason: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """以领域上下文构造异常。

        Args:
            message: 自定义消息
            tool_id: 所属工具 ID
            target_version: 显式回滚目标（可选）
            reason: 不可回滚原因（no_stable_history / not_stable_before 等）
            cause: 根因异常
        """
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if target_version is not None:
            context["target_version"] = target_version
        if reason is not None:
            context["reason"] = reason
        super().__init__(message=message, cause=cause, context=context)


__all__ = [
    "ToolVersionAlreadyExistsError",
    "ToolVersionNotFoundError",
    "ToolVersionRollbackError",
    "ToolVersionTrafficWeightError",
]
