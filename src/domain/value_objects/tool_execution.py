"""领域层工具执行值对象模块

定义 ToolExecution 相关的不可变值对象：
- ToolCall: 工具调用（arguments + tenant_id）
- ExecutionContext: 执行上下文（tenant_id/user_id/session_id/trace_id/timeout_sec）
- ToolResultStatus: 工具结果状态枚举（4 值）
- ToolResult: 工具执行结果（含 output + evidence_package + validation_violations + retry_count）
- EvidencePackage: 证据包（9 字段统一）

设计依据：Story 4.1a AC-3 + Story 4.3 AC-4 扩展
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Mapping

from src.domain.exceptions import (
    EntityValidationError,
    EvidenceValidationFailedError,
)
from src.domain.services.schema_validator import SchemaViolation


class ToolResultStatus(str, Enum):
    """工具结果状态枚举 — 4 值边界

    - success: 执行成功且产出完整
    - failed: 执行失败（沙箱/LLM/校验失败，已重试 3 次）
    - invalid: 输入参数不符合 Tool.input_schema（DDL 校验失败，不进入重试）
    - insufficient_data: 输入数据不充分（可重试）
    """

    SUCCESS = "success"
    FAILED = "failed"
    INVALID = "invalid"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class ToolCall:
    """工具调用值对象（frozen dataclass）

    Attributes:
        tool_id: 工具唯一标识
        arguments: 调用参数（符合 Tool.input_schema）
        tenant_id: 多租户隔离
    """

    tool_id: uuid.UUID
    arguments: dict[str, Any] = field(default_factory=dict)
    tenant_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ExecutionContext:
    """执行上下文值对象(Query Object 模式,CLAUDE.md §4)

    Attributes:
        tenant_id: 多租户隔离
        user_id: 用户唯一标识
        session_id: 会话唯一标识(用于沙箱 session)
        trace_id: 链路追踪 ID
        timeout_sec: 超时秒数(默认 60.0)
        extensions: 扩展上下文(Story 4.3 装饰器透传 execution_id 用;frozen dict 模式)
    """

    tenant_id: uuid.UUID
    user_id: uuid.UUID | None = None
    session_id: str = ""
    trace_id: str = ""
    timeout_sec: float = 60.0
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """构造时校验不变量"""
        if not isinstance(self.tenant_id, uuid.UUID):
            raise EntityValidationError(
                message="tenant_id must be a valid UUID",
                context={"entity": "ExecutionContext", "field": "tenant_id"},
            )
        if self.timeout_sec <= 0:
            raise EntityValidationError(
                message="timeout_sec 必须 > 0",
                context={"entity": "ExecutionContext", "field": "timeout_sec"},
            )

    def with_extension(self, key: str, value: Any) -> "ExecutionContext":
        """返回带扩展项的新实例(frozen 值对象不可变,工厂方法)

        Story 4.3 装饰器(SchemaValidator)用于透传 schema_execution_id 等元数据,
        避免直接修改 frozen 实例。

        Args:
            key: 扩展项键
            value: 扩展项值

        Returns:
            新的 ExecutionContext 实例
        """
        new_extensions: dict[str, Any] = dict(self.extensions)
        new_extensions[key] = value
        return ExecutionContext(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
            trace_id=self.trace_id,
            timeout_sec=self.timeout_sec,
            extensions=new_extensions,
        )


@dataclass(frozen=True)
class EvidencePackage:
    """证据包值对象（9 字段统一）

    字段说明：
    - input_hash: 输入参数哈希
    - rule_version: 业务规则版本
    - plan: Think 阶段产物
    - code: Code 阶段产物
    - result: Execute 阶段产物
    - observation: Observe 阶段产物
    - validation: Validate 阶段产物(Story 4.3 扩展:接受 str | dict 存储 violations)
    - confidence: 置信度 ∈ [0.0, 1.0]
    - citations: 引用列表
    """

    input_hash: str = ""
    rule_version: str = ""
    plan: str = ""
    code: str = ""
    result: str = ""
    observation: str = ""
    validation: str | dict = ""
    confidence: float = 0.0
    citations: list[str] = field(default_factory=list)

    def validate_complete(self) -> bool:
        """完整性校验（必填字段缺失抛 EvidenceValidationFailedError）

        Returns:
            所有必填字段非空时返回 True

        Raises:
            EvidenceValidationFailedError: 必填字段缺失
        """
        missing = []
        if not self.input_hash:
            missing.append("input_hash")
        if not self.rule_version:
            missing.append("rule_version")
        if not self.plan:
            missing.append("plan")
        if not self.code:
            missing.append("code")
        if not self.result:
            missing.append("result")
        if not self.observation:
            missing.append("observation")
        # validation 可为 str (向后兼容) 或 dict (Story 4.3 结构化)
        if isinstance(self.validation, str):
            if not self.validation:
                missing.append("validation")
        elif isinstance(self.validation, dict):
            if "passed" not in self.validation:
                missing.append("validation.passed")
        else:
            missing.append("validation")
        if missing:
            raise EvidenceValidationFailedError(
                message=f"EvidencePackage 必填字段缺失: {missing}",
                missing_fields=missing,
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise EvidenceValidationFailedError(
                message="confidence 必须 ∈ [0.0, 1.0]",
                missing_fields=["confidence"],
            )
        return True


@dataclass(frozen=True)
class ToolResult:
    """工具执行结果值对象（frozen dataclass,Story 4.3 扩展 8 字段）

    Attributes:
        tool_id: 工具唯一标识
        status: 结果状态
        output: 输出字典
        evidence_package: 证据包(向后兼容默认 None)
        started_at: 启动时间
        completed_at: 完成时间
        validation_violations: Schema 验证违规列表(Story 4.3 新增)
        retry_count: 重试次数(Story 4.3 新增,供下游区分原始/重试结果)
    """

    tool_id: uuid.UUID
    status: ToolResultStatus
    output: dict[str, Any] = field(default_factory=dict)
    evidence_package: EvidencePackage | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    validation_violations: tuple[SchemaViolation, ...] = ()
    retry_count: int = 0

    def __post_init__(self) -> None:
        """构造时校验不变量(向后兼容 4.1a:不强制 INVALID 状态必填 violations/output)"""
        if not isinstance(self.tool_id, uuid.UUID):
            raise EntityValidationError(
                message="tool_id must be a valid UUID",
                context={"entity": "ToolResult", "field": "tool_id"},
            )
        if not isinstance(self.status, ToolResultStatus):
            raise EntityValidationError(
                message="status 必须为 ToolResultStatus 枚举值",
                context={"entity": "ToolResult", "field": "status"},
            )
        if self.completed_at < self.started_at:
            raise EntityValidationError(
                message="completed_at 不能早于 started_at",
                context={"entity": "ToolResult"},
            )

    def validate_complete(self) -> bool:
        """完整性校验（success 状态必须有 evidence_package）

        Raises:
            EvidenceValidationFailedError: evidence_package 缺失或无效
        """
        if self.status == ToolResultStatus.SUCCESS:
            if self.evidence_package is None:
                raise EvidenceValidationFailedError(
                    message="ToolResult.status=success 必须包含 evidence_package",
                    missing_fields=["evidence_package"],
                )
            self.evidence_package.validate_complete()
        return True


__all__ = [
    "ToolCall",
    "ExecutionContext",
    "ToolResultStatus",
    "ToolResult",
    "EvidencePackage",
    "SchemaViolation",
]
