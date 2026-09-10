"""应用层工具入参 Schema 验证装饰器模块

定义 ToolInputValidator(应用层服务),包裹 ToolExecutionService,
在委托前对 arguments 做 JSON Schema 校验。

设计依据：Story 4.3 AC-3 / AC-7
- 包裹 ToolExecutionService(Service 层做入参校验,通过注入 tool_registry 解决 Tool 元数据获取)
- 两种策略:strict(默认,抛 ToolInputSchemaValidationError)/ lenient(记录 warning 继续执行)
- 通过 EventPublisher 在 INPUT 校验失败时发布 ToolSchemaValidationFailed 事件
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from src.application.ports.schema_validator import SchemaValidatorPort
from src.application.ports.tool_execution_service import ToolExecutionServicePort
from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.domain.events.tool_schema_events import ToolSchemaValidationFailed
from src.domain.exceptions import ToolInputSchemaValidationError
from src.domain.ports.event_publisher import EventPublisher
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


class ToolInputValidator:
    """入参 Schema 验证装饰器(包裹 ToolExecutionService)

    在委托前对 ToolCall.arguments 做 JSON Schema 校验。
    校验失败策略:
    - strict(默认):抛 ToolInputSchemaValidationError(EXCEPTION_395),不进 Engine
    - lenient:记录 warnings 继续执行(用于 MVP/调试)
    """

    def __init__(
        self,
        wrapped: ToolExecutionServicePort,
        schema_validator: SchemaValidatorPort,
        tool_registry: ToolRegistryServicePort,
        event_publisher: EventPublisher | None = None,
        failure_policy: Literal["strict", "lenient"] = "strict",
    ) -> None:
        """初始化装饰器

        Args:
            wrapped: 被装饰的 ToolExecutionService
            schema_validator: Schema 验证端口(jsonschema 委托)
            tool_registry: 工具注册服务(用于解析 Tool 元数据)
            event_publisher: 事件发布器(INPUT 校验失败时发布事件,可选)
            failure_policy: 失败策略(strict / lenient)
        """
        self._wrapped = wrapped
        self._schema_validator = schema_validator
        self._tool_registry = tool_registry
        self._event_publisher = event_publisher
        self._failure_policy = failure_policy

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """执行工具(在委托前对 arguments 做 Schema 校验)

        Args:
            tool_id: 工具 ID
            tool_call: 工具调用值对象
            context: 执行上下文

        Returns:
            ToolResult(校验通过时由被装饰 Service 返回)

        Raises:
            ToolInputSchemaValidationError: strict 模式下入参校验失败
        """
        tool = self._tool_registry.get_tool(tool_id=tool_id)
        result = self._schema_validator.validate_arguments(tool, tool_call.arguments)
        if result.is_valid:
            return await self._wrapped.execute(tool_id=tool_id, tool_call=tool_call, context=context)

        # 校验失败:发布事件 + 按策略处理
        if self._event_publisher is not None:
            try:
                event = ToolSchemaValidationFailed(
                    execution_id=uuid.uuid4(),
                    tool_id=tool_id,
                    tenant_id=context.tenant_id,
                    validation_phase="INPUT",
                    schema_violations=[v.to_dict() for v in result.violations],
                    retry_attempt=1,
                    failed_at=result.validated_at,
                    schema_version=tool.version,
                    is_final=True,  # INPUT 不重试,直接终止
                )
                await self._event_publisher.publish(event)
            except Exception as pub_exc:  # pragma: no cover
                logger.warning("ToolSchemaValidationFailed 事件发布失败: %s", pub_exc)

        if self._failure_policy == "strict":
            raise ToolInputSchemaValidationError(
                message="Tool arguments schema validation failed",
                tool_id=str(tool_id),
                execution_id=None,
                tool_call_id=None,
                violations=[v.to_dict() for v in result.violations],
            )
        logger.warning(
            "ToolInputValidator[lenient] 入参校验失败仍继续执行: tool_id=%s violations=%d",
            tool_id,
            len(result.violations),
        )
        return await self._wrapped.execute(tool_id=tool_id, tool_call=tool_call, context=context)


__all__ = ["ToolInputValidator"]
