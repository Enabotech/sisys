"""应用层工具执行引擎模块

实现 ToolExecutionEngine，负责五阶段工作流（Think → Code → Execute → Observe → Validate）。
委托 ToolExecutionRepository 持久化，委托 SkillLoaderPort 加载 SOP。

设计依据：Story 4.1a AC-4
- 五阶段端口映射：Think/Code/Validate → LLMClientPort.structured_generate
                  Execute/Observe → SandboxExecutor.execute_code
- RetryPolicy frozen dataclass（指数退避，最多 3 次）
- 证据包双轨存储（L2_rdb 结构化 + L4_object 大文本）
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from src.application.services.retry_helpers import RetryPolicy, _call_with_retry
from src.domain.entities.tool import Tool
from src.domain.entities.tool_execution import (
    TERMINAL_STATES,
    ToolExecution,
    ToolExecutionState,
)
from src.domain.exceptions import (
    ToolExecutionFailedError,
    ToolExecutionRetryExhaustedError,
    ToolExecutionTimeoutError,
)
from src.domain.ports.llm_client import LLMClientPort
from src.domain.ports.sandbox_executor import SandboxExecutor
from src.domain.ports.tool_execution_repository import ToolExecutionRepositoryPort
from src.domain.value_objects.tool_execution import (
    EvidencePackage,
    ExecutionContext,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)

logger = logging.getLogger(__name__)


class ToolExecutionEngine:
    """工具执行引擎

    实现五阶段工作流（Think → Code → Execute → Observe → Validate），
    封装 RetryPolicy 重试逻辑、Session 生命周期管理、证据包组装。

    五阶段端口映射：
    | 阶段     | 端口方法                                         | 输入                      | 输出              |
    |----------|--------------------------------------------------|---------------------------|-------------------|
    | Think    | LLMClientPort.structured_generate                | SKILL.md + arguments      | plan: str         |
    | Code     | LLMClientPort.structured_generate                | plan + input_schema       | code: str         |
    | Execute  | SandboxExecutor.execute_code                     | session_id + code         | result: str       |
    | Observe  | SandboxExecutor.execute_code                     | result                    | observation: str  |
    | Validate | LLMClientPort.structured_generate                | result + observation      | validation: str   |
    """

    def __init__(
        self,
        llm_client: LLMClientPort,
        sandbox: SandboxExecutor,
        retry_policy: RetryPolicy | None = None,
        tool_execution_repository: ToolExecutionRepositoryPort | None = None,
    ) -> None:
        """初始化引擎

        Args:
            llm_client: LLM 客户端端口
            sandbox: 沙箱执行器端口
            retry_policy: 重试策略（默认使用 RetryPolicy 默认值）
            tool_execution_repository: ToolExecution 仓储端口（可选，注入后自动持久化）
        """
        self._llm = llm_client
        self._sandbox = sandbox
        self._retry = retry_policy or RetryPolicy()
        self._tool_execution_repository = tool_execution_repository

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool: Tool,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """执行五阶段工作流

        Args:
            tool_id: 工具唯一标识
            tool: 工具实体
            tool_call: 工具调用值对象
            context: 执行上下文

        Returns:
            ToolResult 执行结果

        Raises:
            ToolExecutionFailedError: 五阶段任一失败（不可重试）
            ToolExecutionRetryExhaustedError: 重试耗尽
            ToolExecutionTimeoutError: 超过 max_total_duration_sec
        """
        # 创建 ToolExecution 聚合根（IDLE 状态）
        execution = ToolExecution(
            execution_id=uuid.uuid4(),
            tenant_id=context.tenant_id,
            tool_id=tool_id,
            tool_version=tool.version,
            state=ToolExecutionState.IDLE,
            started_at=datetime.now(UTC),
        )
        start_time = time.monotonic()

        # 启动沙箱 session
        session_id = context.session_id or f"sess-{execution.execution_id}"
        try:
            await self._sandbox.start_container(session_id)
        except Exception as exc:
            logger.error("沙箱启动失败: %s", exc)
            execution.transition_to(ToolExecutionState.FAILED)
            execution.failure_reason = f"sandbox_start_failed: {exc}"
            raise ToolExecutionFailedError(
                execution_id=str(execution.execution_id),
                tool_id=str(tool_id),
                stage="SANDBOX_START",
                cause=exc,
            )

        try:
            # === Think 阶段 ===
            execution.transition_to(ToolExecutionState.PLANNING)
            plan = await self._think_stage(tool, tool_call, context)

            # === Code 阶段 ===
            code = await self._code_stage(plan, tool, context)
            execution.code = code

            # === Execute 阶段 ===
            execution.transition_to(ToolExecutionState.EXECUTING)
            result = await self._execute_stage(session_id, code, tool)
            execution.result = result

            # === Observe 阶段 ===
            observation = await self._observe_stage(session_id, result, tool)

            # === Validate 阶段 ===
            execution.transition_to(ToolExecutionState.VALIDATING)
            validation = await self._validate_stage(tool, result, observation, context)

            # 终止状态：COMPLETED
            execution.transition_to(ToolExecutionState.COMPLETED)
            execution.completed_at = datetime.now(UTC)
            execution.plan = plan
            execution.observation = observation
            execution.validation = validation

            elapsed = time.monotonic() - start_time
            if elapsed > self._retry.max_total_duration_sec:
                raise ToolExecutionTimeoutError(
                    execution_id=str(execution.execution_id),
                    tool_id=str(tool_id),
                    elapsed_sec=elapsed,
                )

            # 构造 EvidencePackage
            evidence = self._build_evidence(execution, tool, tool_call)

            tool_result = ToolResult(
                tool_id=tool_id,
                status=ToolResultStatus.SUCCESS,
                output={"plan": plan, "result": result},
                evidence_package=evidence,
                started_at=execution.started_at,
                completed_at=execution.completed_at,
            )

            # 持久化 ToolExecution（如果注入了仓储）
            if self._tool_execution_repository is not None:
                await self._tool_execution_repository.save(execution)

            return tool_result

        except ToolExecutionRetryExhaustedError:
            # 状态机守卫：仅在非终态时迁移到 FAILED
            if execution.state not in TERMINAL_STATES:
                execution.transition_to(ToolExecutionState.FAILED)
                execution.completed_at = datetime.now(UTC)
            raise
        except ToolExecutionTimeoutError:
            # 状态机守卫：仅在非终态时迁移到 FAILED（避免 COMPLETED → FAILED 非法迁移）
            if execution.state not in TERMINAL_STATES:
                execution.transition_to(ToolExecutionState.FAILED)
                execution.completed_at = datetime.now(UTC)
            raise
        except Exception as exc:
            # 状态机守卫：仅在非终态时迁移到 FAILED
            if execution.state not in TERMINAL_STATES:
                logger.exception("工具执行失败: tool_id=%s exc=%s", tool_id, exc)
                execution.transition_to(ToolExecutionState.FAILED)
                execution.completed_at = datetime.now(UTC)
                execution.failure_reason = str(exc)
            raise ToolExecutionFailedError(
                execution_id=str(execution.execution_id),
                tool_id=str(tool_id),
                stage="EXECUTION",
                cause=exc,
            )
        finally:
            # 清理沙箱
            try:
                await self._sandbox.stop_container(session_id)
            except Exception as cleanup_exc:
                logger.warning("沙箱清理失败: %s", cleanup_exc)

    # ===== 五阶段端口方法 =====

    async def _think_stage(
        self,
        tool: Tool,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> str:
        """Think 阶段：调用 LLMClientPort.structured_generate 产出 plan

        Args:
            tool: 工具实体
            tool_call: 工具调用值对象
            context: 执行上下文

        Returns:
            plan 字符串
        """
        prompt = self._build_think_prompt(tool, tool_call)
        response = await self._retry_call(
            lambda: self._llm.structured_generate(
                prompt=prompt,
                response_schema=str,
            ),
            execution_id=context.session_id,
            tool_id=tool.tool_id,
        )
        return str(response)

    async def _code_stage(
        self,
        plan: str,
        tool: Tool,
        context: ExecutionContext,
    ) -> str:
        """Code 阶段：调用 LLMClientPort.structured_generate 产出 code"""
        prompt = self._build_code_prompt(plan, tool)
        response = await self._retry_call(
            lambda: self._llm.structured_generate(
                prompt=prompt,
                response_schema=str,
            ),
            execution_id=context.session_id,
            tool_id=tool.tool_id,
        )
        return str(response)

    async def _execute_stage(self, session_id: str, code: str, tool: Tool) -> str:
        """Execute 阶段：调用 SandboxExecutor.execute_code 产出 result"""
        result = await self._retry_call(
            lambda: self._sandbox.execute_code(session_id, code),
            execution_id=session_id,
            tool_id=tool.tool_id,
        )
        return str(result.get("output", ""))

    async def _observe_stage(self, session_id: str, result: str, tool: Tool) -> str:
        """Observe 阶段：调用 SandboxExecutor.execute_code 产出 observation"""
        observation_code = self._build_observation_code(result)
        observation = await self._retry_call(
            lambda: self._sandbox.execute_code(session_id, observation_code),
            execution_id=session_id,
            tool_id=tool.tool_id,
        )
        return str(observation.get("output", ""))

    async def _validate_stage(
        self,
        tool: Tool,
        result: str,
        observation: str,
        context: ExecutionContext,
    ) -> str:
        """Validate 阶段：调用 LLMClientPort.structured_generate 产出 validation"""
        prompt = self._build_validate_prompt(tool, result, observation)
        response = await self._retry_call(
            lambda: self._llm.structured_generate(
                prompt=prompt,
                response_schema=str,
            )
        )
        return str(response)

    # ===== 重试机制 =====

    async def _retry_call(
        self,
        fn,
        execution_id: str | None = None,
        tool_id: uuid.UUID | None = None,
    ) -> Any:
        """带指数退避的重试调用(Story 4.3 重构为薄壳,委托 _call_with_retry)

        保留 4.1a 既有 API,内部委托给 retry_helpers._call_with_retry 共享工具函数。
        Engine 与 ToolOutputValidator 装饰器共享同一重试语义。

        Args:
            fn: 异步可调用对象
            execution_id: 当前执行标识(透传到 ToolExecutionRetryExhaustedError context)
            tool_id: 工具 ID(透传到异常 context)

        Returns:
            调用结果

        Raises:
            ToolExecutionRetryExhaustedError: 重试耗尽
        """
        return await _call_with_retry(
            fn,
            self._retry,
            on_failure_callback=None,
            execution_id=execution_id,
            tool_id=tool_id,
            op_name="tool_engine",
        )

    def _compute_backoff(self, attempt: int) -> float:
        """计算退避延迟(薄壳,委托给 retry_helpers._compute_backoff 保持 API 兼容)"""
        from src.application.services.retry_helpers import _compute_backoff

        return _compute_backoff(self._retry, attempt)

    # ===== 证据包组装 =====

    def _build_evidence(
        self,
        execution: ToolExecution,
        tool: Tool,
        tool_call: ToolCall,
    ) -> EvidencePackage:
        """组装 EvidencePackage（9 字段统一）"""
        args_str = json.dumps(tool_call.arguments, sort_keys=True, default=str)
        input_hash = hashlib.sha256(args_str.encode()).hexdigest()[:16]

        return EvidencePackage(
            input_hash=input_hash,
            rule_version=tool.rule_version or "default",
            plan=execution.plan or "",
            code=execution.code or "",
            result=execution.result or "",
            observation=execution.observation or "",
            validation=execution.validation or "",
            confidence=tool.reliability_score,
            citations=[],
        )

    # ===== Prompt 构建 =====

    def _build_think_prompt(self, tool: Tool, tool_call: ToolCall) -> str:
        return f"为工具 {tool.name} 规划执行步骤。参数: {tool_call.arguments}"

    def _build_code_prompt(self, plan: str, tool: Tool) -> str:
        return f"基于以下计划生成代码: {plan}"

    def _build_observation_code(self, result: str) -> str:
        return f"# Observe\nprint('{result[:100]}')"

    def _build_validate_prompt(
        self,
        tool: Tool,
        result: str,
        observation: str,
    ) -> str:
        return f"验证工具 {tool.name} 输出: result={result}, observation={observation}"


__all__ = ["ToolExecutionEngine"]
