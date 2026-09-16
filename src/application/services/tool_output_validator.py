"""应用层工具出参 Schema 验证装饰器模块

定义 ToolOutputValidator(应用层服务),包裹 ToolExecutionEngine,
在 Engine 返回 ToolResult 后做 Schema 校验,失败触发重试。

设计依据:Story 4.3 AC-3 / AC-7
- 纯 Decorator 外包(不修改 Engine 源码,保留 4.1a 向后兼容性)
- 重试通过抽离的 _call_with_retry 共享工具函数(避免 Engine 私有 _retry_call 访问)
- P0-D 修复:重试前将 last_violations 写入 context.extensions,Engine._validate_stage
  读取并注入 prompt(LLM 自纠反馈循环)
- P0-B 修复:重试耗尽时直接 raise ToolResultValidationError(让 _call_with_retry 的
  ToolExecutionRetryExhaustedError 仅作为内部诊断信息,装饰器对外契约仍是 ToolResultValidationError)
- P0-F 修复:INPUT/OUTPUT 共享 execution_id(从 context.extensions["schema_execution_id"] 取)
- P0-H 修复:发布事件前截断 violations(条数 + path 深度 + 总字节数)
- P0-I 修复:事件发布使用 fire-and-forget 异步任务,不阻塞主流程
"""

from __future__ import annotations

import logging
import uuid

from src.application.ports.schema_validator import SchemaValidatorPort
from src.application.ports.tool_execution_engine import ToolExecutionEnginePort
from src.application.services.retry_helpers import RetryPolicy, _call_with_retry
from src.application.services.schema_event_helpers import (
    EVENT_MAX_PATH_DEPTH_DEFAULT,
    EVENT_MAX_TOTAL_BYTES_DEFAULT,
    EVENT_MAX_VIOLATIONS_DEFAULT,
    extract_schema_execution_id,
    publish_schema_event_async,
    truncate_violations_for_event,
)
from src.domain.entities.tool import Tool
from src.domain.events.tool_schema_events import ToolSchemaValidationFailed
from src.domain.exceptions import (
    ToolExecutionRetryExhaustedError,
    ToolResultValidationError,
)
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
    - 重试时通过 context.extensions["schema_last_violations"] 注入上轮 violations,
      Engine._validate_stage 读取后拼入 LLM prompt(LLM 自纠反馈)
    - 重试耗尽 → 设置 ToolResult.status = FAILED + ToolResult.retry_count 填充
      + 抛 ToolResultValidationError (EXCEPTION_389)
    - 每次重试失败都通过 event_publisher 发布 ToolSchemaValidationFailed (OUTPUT),
      仅最后一次 is_final=True
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
            ToolResultValidationError: 重试耗尽后抛出(EXCEPTION_389,符合 AC-3 契约)
        """
        retry_policy = self._retry_policy or getattr(self._wrapped, "_retry", RetryPolicy())
        if retry_policy is None:
            retry_policy = RetryPolicy()
        retry_count = 0
        last_violations: tuple = ()
        # P0-F:与 INPUT 装饰器共享 execution_id,4.7 订阅者可按 execution_id 关联
        execution_id = extract_schema_execution_id(context) or uuid.uuid4()
        # 通过 with_extension 工厂方法透传(ExecutionContext frozen 不可变)

        # Round 2 P0-1:装饰器重试期间临时禁用 Engine 内部重试,防止 81x LLM 调用放大
        # 默认 Engine._retry.max_attempts=3,装饰器再重试 3 次 = 27x;
        # 加 litellm tenacity 默认 3 次 = 81x LLM 调用,触发 max_total_duration_sec 超时
        # 修复:装饰器重试期间把 Engine 临时改为 max_attempts=1,只重试 Validate 阶段
        # 而非整个 5 阶段,完成后恢复原值
        original_wrapped_retry = getattr(self._wrapped, "_retry", None)
        retry_policy_for_engine = RetryPolicy(
            max_attempts=1,
            backoff_strategy=retry_policy.backoff_strategy,
            initial_delay_sec=retry_policy.initial_delay_sec,
            max_delay_sec=retry_policy.max_delay_sec,
            max_total_duration_sec=retry_policy.max_total_duration_sec,
            retryable_exceptions=retry_policy.retryable_exceptions,
        )
        if hasattr(self._wrapped, "_retry"):
            self._wrapped._retry = retry_policy_for_engine  # type: ignore[attr-defined]

        async def execute_with_retry() -> ToolResult:
            """单次执行 + 校验 + 失败时通过异常触发 _call_with_retry 重试"""
            nonlocal retry_count, last_violations
            retry_count += 1
            # P0-D:重试时把上一轮 violations 注入 context,Engine._validate_stage 读出后拼入 prompt
            current_context = context
            if last_violations:
                current_context = context.with_extension(
                    "schema_last_violations",
                    last_violations,
                )
            result = await self._wrapped.execute(
                tool_id=tool_id,
                tool=tool,
                tool_call=tool_call,
                context=current_context,
            )
            validation = self._schema_validator.validate_output(tool, result.output)
            if validation.is_valid:
                return result
            last_violations = validation.violations

            # 发布 OUTPUT 阶段事件(每次重试失败都发布,仅最后一次 is_final=True)
            if self._event_publisher is not None:
                # P0-H:截断 violations 防止 DoS
                truncated = truncate_violations_for_event(
                    violations=validation.violations,
                    max_violations=EVENT_MAX_VIOLATIONS_DEFAULT,
                    max_path_depth=EVENT_MAX_PATH_DEPTH_DEFAULT,
                    max_total_bytes=EVENT_MAX_TOTAL_BYTES_DEFAULT,
                )
                event = ToolSchemaValidationFailed(
                    execution_id=execution_id,  # P0-F:与 INPUT 共享同一 execution_id
                    tool_id=tool_id,
                    tenant_id=context.tenant_id,
                    validation_phase="OUTPUT",
                    schema_violations=[v.to_dict() for v in truncated.violations],
                    retry_attempt=retry_count,
                    failed_at=validation.validated_at,
                    schema_version=tool.version,
                    is_final=retry_count >= retry_policy.max_attempts,
                )
                # P0-I:fire-and-forget 异步发布,不阻塞重试主循环
                publish_schema_event_async(
                    self._event_publisher,
                    event,
                    logger,
                    op_name="tool_output_validator",
                )
            # 触发重试(抛 ToolResultValidationError 让 _call_with_retry 捕获)
            raise ToolResultValidationError(
                message="Tool output schema validation failed",
                tool_id=str(tool_id),
                execution_id=str(execution_id),  # P0-F:与事件 payload 共享 execution_id
                reason=f"retry {retry_count}",
                schema_violations=[v.to_dict() for v in validation.violations],
            )

        # 重试主循环:每次执行 + 校验 + 失败时 _call_with_retry 重试
        # ToolResultValidationError 不在 RetryPolicy 默认 retryable_exceptions 内,
        # 故此处显式构造专用 retry_policy 让 ToolResultValidationError 可重试
        # Round 3 P0-1 修复:retryable_exceptions 联合 ToolExecutionRetryExhaustedError,
        # 让 Engine 内部 LLM 瞬时错误(LLMAPIError 等)耗尽后抛 ToolExecutionRetryExhaustedError
        # 也能被外层装饰器捕获并重试,避免 LLM 瞬时错误无法恢复
        retry_policy_for_validation = RetryPolicy(
            max_attempts=retry_policy.max_attempts,
            backoff_strategy=retry_policy.backoff_strategy,
            initial_delay_sec=retry_policy.initial_delay_sec,
            max_delay_sec=retry_policy.max_delay_sec,
            max_total_duration_sec=retry_policy.max_total_duration_sec,
            retryable_exceptions=(
                ToolResultValidationError,
                ToolExecutionRetryExhaustedError,
            ),
        )

        try:
            return await _call_with_retry(
                execute_with_retry,
                retry_policy_for_validation,
                execution_id=str(execution_id),
                tool_id=tool_id,
                op_name="tool_output_validator",
            )
        except ToolExecutionRetryExhaustedError as retry_exc:
            # Round 2 P0-1:重试耗尽时,先恢复 Engine 原始 _retry,避免污染 Engine 后续使用
            if hasattr(self._wrapped, "_retry") and original_wrapped_retry is not None:
                self._wrapped._retry = original_wrapped_retry  # type: ignore[attr-defined]
            # P0-B 修复:_call_with_retry 在重试耗尽时抛 ToolExecutionRetryExhaustedError,
            # 但 AC-3 + AC-7 契约明确要求装饰器对外抛 ToolResultValidationError(EXCEPTION_389),
            # 4.7 Validation Feedback 订阅契约按 ToolResultValidationError 类型做处理。
            # 转换异常类型,保留 last_violations 信息
            raise ToolResultValidationError(
                message="Tool output schema validation exhausted retries",
                tool_id=str(tool_id),
                execution_id=str(execution_id),
                reason=f"retries exhausted: {retry_count}; cause: {retry_exc.cause}",
                schema_violations=[v.to_dict() for v in last_violations],
            ) from retry_exc
        finally:
            # Round 2 P0-1:无论成功或失败,恢复 Engine 原始 _retry(防御性编程)
            if hasattr(self._wrapped, "_retry") and original_wrapped_retry is not None:
                self._wrapped._retry = original_wrapped_retry  # type: ignore[attr-defined]


__all__ = ["ToolOutputValidator"]
