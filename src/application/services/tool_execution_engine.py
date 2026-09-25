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

from src.application.ports.data_source_resolver import DataSourceResolverPort
from src.application.services.data_source_marker import (
    inject_data_sources,
    parse_data_source_markers,
)
from src.application.services.retry_helpers import RetryPolicy, _call_with_retry
from src.domain.entities.tool import Tool
from src.domain.entities.tool_execution import (
    TERMINAL_STATES,
    ToolExecution,
    ToolExecutionState,
)
from src.domain.exceptions import (
    BusinessRuleViolationError,
    DataSourceError,
    ToolExecutionFailedError,
    ToolExecutionRetryExhaustedError,
    ToolExecutionTimeoutError,
    ValidationError,
)
from src.domain.ports.llm_client import LLMClientPort
from src.domain.ports.sandbox_executor import SandboxExecutor
from src.domain.ports.tool_execution_repository import ToolExecutionRepositoryPort
from src.domain.value_objects.data_source import DataSourceMeta
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
        # Story 4.1b：数据源解析器（默认 None 零行为变化；set_data_source_resolver 后注入，
        # 保护 Story 4.4 AC-7.4 BDD 对 __init__ 参数数量的断言）
        self._data_source_resolver: DataSourceResolverPort | None = None

    def set_data_source_resolver(self, resolver: DataSourceResolverPort | None) -> None:
        """后注入数据源解析器（Story 4.1b）

        Args:
            resolver: DataSourceResolverPort 实现或 None（None 撤销注入，恢复 4.4 既有行为）

        Note:
            采用 setter 后注入而非 __init__ 参数，避免破坏 Story 4.4 AC-7.4 对
            构造函数签名的 BDD 断言（两 Story 并行合入 main 的兼容约束）。
        """
        self._data_source_resolver = resolver

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
            await self._sandbox.start_container(session_id, tenant_id=context.tenant_id)
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
            # Story 4.1b：宿主机侧解析 $DATA_SOURCE 标记并注入采集数据（沙箱无网络不变量）
            code, data_source_metas = await self._resolve_data_sources(code, context, execution)
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
            evidence = self._build_evidence(execution, tool, tool_call, data_sources=data_source_metas)

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
        except (BusinessRuleViolationError, ValidationError, DataSourceError) as exc:
            # Story 4.1b：数据采集相关的领域异常不包装直传（调用方/策略/数据语义错误，
            # 区别于执行失败 ToolExecutionFailedError）
            if execution.state not in TERMINAL_STATES:
                execution.transition_to(ToolExecutionState.FAILED)
                execution.completed_at = datetime.now(UTC)
                execution.failure_reason = str(exc)
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

    # ===== 数据源采集（Story 4.1b）=====

    async def _resolve_data_sources(
        self,
        code: str,
        context: ExecutionContext,
        execution: ToolExecution,
    ) -> tuple[str, tuple[DataSourceMeta, ...]]:
        """Execute 阶段前置：解析 $DATA_SOURCE 标记 → 白名单校验 → 并发采集 → preamble 注入

        沙箱 network_mode="none" 为领域不变量（ContainerSpec），外部数据采集必须在
        宿主机侧完成并以 Python 字面量前言内联注入。

        Args:
            code: Code 阶段产出的沙箱代码
            context: 执行上下文（extensions["tool_metadata"] 携带白名单依据）
            execution: ToolExecution 聚合根（事件 aggregate_id 关联）

        Returns:
            (注入后的代码, DataSourceMeta 溯源元数据元组)

        Raises:
            BusinessRuleViolationError: 标记存在但无 tool_metadata（无白名单依据），
                或数据源未在白名单声明（EXCEPTION_207）
            ValidationError: 标记语法错误（EXCEPTION_201）
            DataSourceError: 全部数据源采集失败（412/413/411 等不包装直传）
        """
        if self._data_source_resolver is None:
            return code, ()

        markers = parse_data_source_markers(code)
        if not markers:
            return code, ()

        metadata = (context.extensions or {}).get("tool_metadata")
        if metadata is None:
            raise BusinessRuleViolationError(
                message="代码含 $DATA_SOURCE 标记但执行上下文缺少 tool_metadata（无白名单依据）",
                context={"stage": "resolve_data_sources", "marker_count": len(markers)},
            )

        results = await self._data_source_resolver.fetch_many(
            metadata,
            markers,
            tenant_id=context.tenant_id,
            execution_id=execution.execution_id,
        )
        metas = tuple(
            DataSourceMeta(
                source_name=r.source_name,
                source_timestamp=r.source_timestamp,
                freshness_score=r.freshness.score(datetime.now(UTC)),
                confidence=r.confidence,
            )
            for r in results
        )
        return inject_data_sources(code, results), metas

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
        """Validate 阶段:调用 LLMClientPort.structured_generate 产出 validation

        P0-D 修复:从 context.extensions["schema_last_violations"] 读取上轮 violations,
        由 ToolOutputValidator 装饰器在重试前注入,实现"重试 prompt 携带 violations"反馈
        """
        last_violations = (context.extensions or {}).get("schema_last_violations", ())
        prompt = self._build_validate_prompt(tool, result, observation, last_violations)
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
        data_sources: tuple[DataSourceMeta, ...] = (),
    ) -> EvidencePackage:
        """组装 EvidencePackage（9 字段统一 + Story 4.1b 数据源溯源元数据）"""
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
            data_sources=data_sources,
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
        last_violations: tuple = (),
    ) -> str:
        """构建 Validate 阶段 prompt

        P0-D 修复:可选 last_violations 参数(由 ToolOutputValidator 装饰器注入),
        实现"重试 prompt 携带上轮 violations"反馈,LLM 可基于 violations 自纠。
        """
        base = f"验证工具 {tool.name} 输出: result={result}, observation={observation}"
        if last_violations:
            violations_text = "\n".join(f"- path={v.path}, expected={v.expected}, message={v.message}" for v in last_violations)
            return f"{base}\n\n上轮 Schema 校验失败,请按以下 violations 自纠输出:\n{violations_text}"
        return base


__all__ = ["ToolExecutionEngine"]
