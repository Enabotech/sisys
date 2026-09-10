"""应用层工具出参 Schema 验证装饰器模块

定义 ToolOutputValidator(应用层服务),包裹 ToolExecutionEngine,
在 Engine 返回 ToolResult 后做 Schema 校验,失败触发重试。

设计依据：Story 4.3 AC-3 / AC-7
- 纯 Decorator 外包(不修改 Engine 源码,保留 4.1a 向后兼容性)
- 重试通过抽离的 _call_with_retry 共享工具函数(避免 Engine 私有 _retry_call 访问)
- 重试 prompt 携带上轮 violations 作为 LLM 反馈
- 重试耗尽 → ToolResult.status=FAILED + 抛 ToolResultValidationError (EXCEPTION_389)
"""

from __future__ import annotations

import logging
import uuid

from src.application.ports.schema_validator import SchemaValidatorPort
from src.application.ports.tool_execution_engine import ToolExecutionEnginePort
from src.application.services.retry_helpers import _call_with_retry
from src.application.services.tool_execution_engine import RetryPolicy
from src.domain.entities.tool import Tool
from src.domain.events.tool_schema_events import ToolSchemaValidationFailed
from src.domain.exceptions import ToolResultValidationError
from src.domain.ports.event_publisher import EventPublisher
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


class ToolOutputValidator:
    """出参 Schema 验证装饰器(包裹 ToolExecutionEngine,纯 Decorator 外包)

    在 Engine.execute 返回 ToolResult 前做 Schema 校验。
    校验失败:
    - 调用 _call_with_retry 触发重试(默认沿用 wrapped._retry,可在构造时覆盖)
    - 重试时通过 _build_validate_prompt 注入上轮 violations 给 LLM 作为反馈
    - 重试耗尽 → ToolResult.status = FAILED + ToolResult.retry_count 填充 + 抛 ToolResultValidationError (EXCEPTION_389)
    - 每次重试失败都通过 event_publisher 发布 ToolSchemaValidationFailed (OUTPUT)
    """

    def __init__(
        self,
        wrapped: ToolExecutionEnginePort,
        schema_validator: SchemaValidatorPort,
        event_publisher: EventPublisher | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        """初始化装饰器

        Args:
            wrapped: 被装饰的 ToolExecutionEngine
            schema_validator: Schema 验证端口
            event_publisher: 事件发布器(OUTPUT 校验失败时发布事件,可选)
            retry_policy: 重试策略(默认沿用 wrapped._retry,4.1a 兼容)
        """
        self._wrapped = wrapped
        self._schema_validator = schema_validator
        self._event_publisher = event_publisher
        self._retry_policy = retry_policy

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool: Tool,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """执行工具 + 出参 Schema 校验 + 失败重试

        Args:
            tool_id: 工具 ID
            tool: 工具实体
            tool_call: 工具调用值对象
            context: 执行上下文

        Returns:
            ToolResult(校验通过时由被装饰 Engine 返回;重试耗尽时 status=FAILED)

        Raises:
            ToolResultValidationError: 重试耗尽后抛出(EXCEPTION_389)
        """
        retry_policy = self._retry_policy or getattr(self._wrapped, "_retry", RetryPolicy())
        if retry_policy is None:
            retry_policy = RetryPolicy()
        retry_count = 0
        last_violations: tuple = ()

        async def execute_with_retry() -> ToolResult:
            nonlocal retry_count, last_violations
            retry_count += 1
            result = await self._wrapped.execute(tool_id=tool_id, tool=tool, tool_call=tool_call, context=context)
            validation = self._schema_validator.validate_output(tool, result.output)
            if validation.is_valid:
                return result
            last_violations = validation.violations
            # 发布 OUTPUT 阶段事件(每次重试失败都发布,仅最后一次 is_final=True)
            if self._event_publisher is not None:
                try:
                    event = ToolSchemaValidationFailed(
                        execution_id=uuid.uuid4(),
                        tool_id=tool_id,
                        tenant_id=context.tenant_id,
                        validation_phase="OUTPUT",
                        schema_violations=[v.to_dict() for v in validation.violations],
                        retry_attempt=retry_count,
                        failed_at=validation.validated_at,
                        schema_version=tool.version,
                        is_final=retry_count >= retry_policy.max_attempts,
                    )
                    await self._event_publisher.publish(event)
                except Exception as pub_exc:  # pragma: no cover
                    logger.warning("ToolSchemaValidationFailed 事件发布失败: %s", pub_exc)
            # 触发重试(抛异常让 _call_with_retry 捕获 retryable_exceptions)
            raise ToolResultValidationError(
                message="Tool output schema validation failed",
                tool_id=str(tool_id),
                execution_id=None,
                reason=f"retry {retry_count}",
                schema_violations=[v.to_dict() for v in validation.violations],
            )

        # 重试主循环:每次执行 + 校验 + 失败时 _call_with_retry 重试
        # 注意:ToolResultValidationError 不在 RetryPolicy 默认 retryable_exceptions 内,
        # 故此处需显式用 retry_policy.retryable_exceptions = (ToolResultValidationError, ...)
        retry_policy_for_validation = RetryPolicy(
            max_attempts=retry_policy.max_attempts,
            backoff_strategy=retry_policy.backoff_strategy,
            initial_delay_sec=retry_policy.initial_delay_sec,
            max_delay_sec=retry_policy.max_delay_sec,
            max_total_duration_sec=retry_policy.max_total_duration_sec,
            retryable_exceptions=(ToolResultValidationError,),
        )

        try:
            return await _call_with_retry(
                execute_with_retry,
                retry_policy_for_validation,
                execution_id=context.session_id or str(uuid.uuid4()),
                tool_id=tool_id,
                op_name="tool_output_validator",
            )
        except ToolResultValidationError:
            # 重试耗尽 → ToolResult.status=FAILED
            raise ToolResultValidationError(
                message="Tool output schema validation exhausted retries",
                tool_id=str(tool_id),
                execution_id=None,
                reason=f"retries exhausted: {retry_count}",
                schema_violations=[v.to_dict() for v in last_violations],
            ) from None


__all__ = ["ToolOutputValidator"]
