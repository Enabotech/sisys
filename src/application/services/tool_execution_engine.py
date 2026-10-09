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
from src.application.services.schema_event_helpers import extract_schema_execution_id
from src.domain.entities.tool import Tool
from src.domain.entities.tool_execution import (
    TERMINAL_STATES,
    ToolExecution,
    ToolExecutionState,
)
from src.domain.exceptions import (
    BusinessRuleViolationError,
    ConfigurationError,
    DataSourceError,
    LLMAPIError,
    LLMResponseError,
    TimeoutError,
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
        # Story 4.7（决策 #16）：聚合 id 优先读链入口注入的 schema_execution_id
        # （经 extract_schema_execution_id 单点归一——非法值静默新铸，禁直读裸值：
        # 裸 UUID 构造在 try 块外抛 242）；无注入时兜底新铸——聚合 id / 382/389
        # context / 演进日志幂等键 / 两事件 id 全链同源
        execution = ToolExecution(
            execution_id=extract_schema_execution_id(context) or uuid.uuid4(),
            tenant_id=context.tenant_id,
            tool_id=tool_id,
            tool_version=tool.version,
            state=ToolExecutionState.IDLE,
            started_at=datetime.now(UTC),
        )
        start_time = time.monotonic()

        # 启动沙箱 session（R3-3 H1v2-①：先迁移 PLANNING 再启动——原 IDLE→FAILED
        # 直迁被状态矩阵拒绝（VALID_TRANSITIONS[IDLE]={PLANNING}）抛
        # EntityStateTransitionError(243) 掩盖 ToolExecutionFailedError，该分支为死代码）
        session_id = context.session_id or f"sess-{execution.execution_id}"
        execution.transition_to(ToolExecutionState.PLANNING)
        try:
            await self._sandbox.start_container(session_id, tenant_id=context.tenant_id)
        except Exception as exc:
            logger.error("沙箱启动失败: %s", exc)
            execution.transition_to(ToolExecutionState.FAILED)
            execution.completed_at = datetime.now(UTC)
            execution.failure_reason = f"sandbox_start_failed: {exc}"
            # 失败态可观测性（R3-3 H1v2：失败路径 best-effort 持久化——save 为
            # upsert，自吞噬异常防顶替在途的 ToolExecutionFailedError）
            await self._persist_execution(execution)
            raise ToolExecutionFailedError(
                execution_id=str(execution.execution_id),
                tool_id=str(tool_id),
                stage="SANDBOX_START",
                cause=exc,
            )

        try:
            # === Think 阶段 ===（PLANNING 迁移已提前至沙箱启动前——R3-3 H1v2-①）
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

        except ToolExecutionRetryExhaustedError as exc:
            # 状态机守卫：仅在非终态时迁移到 FAILED
            if execution.state not in TERMINAL_STATES:
                execution.transition_to(ToolExecutionState.FAILED)
                execution.completed_at = datetime.now(UTC)
                execution.failure_reason = str(exc)
            await self._persist_execution(execution)
            raise
        except ToolExecutionTimeoutError as exc:
            # 状态机守卫：仅在非终态时迁移到 FAILED（避免 COMPLETED → FAILED 非法迁移）；
            # failure_reason 无条件赋值（R3-3 H1v2-④：raise 点在 COMPLETED 迁移之后，
            # 守卫恒 False——「完成但超预算」也须记录原因并持久化 COMPLETED 态）
            if execution.state not in TERMINAL_STATES:
                execution.transition_to(ToolExecutionState.FAILED)
                execution.completed_at = datetime.now(UTC)
            execution.failure_reason = str(exc)
            await self._persist_execution(execution)
            raise
        except (BusinessRuleViolationError, ValidationError, DataSourceError, ConfigurationError, TimeoutError) as exc:
            # Story 4.1b：数据采集相关的领域异常不包装直传（调用方/策略/数据语义错误，
            # 区别于执行失败 ToolExecutionFailedError）。R2-P1-7 修复：补 ConfigurationError(101)
            # 与领域 TimeoutError(302)（非内置同名类——端口契约声明的传播异常；
            # 重试包装器使语义变化实际仅限 _resolve_data_sources 路径）
            if execution.state not in TERMINAL_STATES:
                execution.transition_to(ToolExecutionState.FAILED)
                execution.completed_at = datetime.now(UTC)
                execution.failure_reason = str(exc)
            await self._persist_execution(execution)
            raise
        except Exception as exc:
            # 状态机守卫：仅在非终态时迁移到 FAILED
            if execution.state not in TERMINAL_STATES:
                logger.exception("工具执行失败: tool_id=%s exc=%s", tool_id, exc)
                execution.transition_to(ToolExecutionState.FAILED)
                execution.completed_at = datetime.now(UTC)
                execution.failure_reason = str(exc)
            await self._persist_execution(execution)
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

    async def _persist_execution(self, execution: ToolExecution) -> None:
        """失败/超预算路径的 best-effort 持久化（R3-3 H1v2-③）

        修复「失败可观测性为零」：save 仅在成功路径（execute 主流程尾部）调用，
        6 处失败路径（沙箱启动/重试耗尽/超时/领域异常组/兜底）迁移 FAILED 后
        均不落库——`list_by_query(state=FAILED)` 永远空集，且 DataSourceFetchFailed
        事件（outbox）的 aggregate_id 指向不存在的聚合行，事件溯源断链。

        事务边界说明：save 为独立 upsert（无 outbox 事务关联）——HTTP 路径经
        SessionMiddleware commit 存活；后台 session_context 路径随异常回滚丢失
        （Story 4.7 已修复形态①：outbox save 无请求 session 时经注入的
        session_factory 走独立会话写入；形态②「业务 session 异常回滚连带丢失
        已 flush 事件」为遗留债，登记 deferred-work.md——会话策略重构超出范围）。

        异常语义：自吞噬（except Exception → warning）——本方法运行于 except
        分支内，抛出会顶替正在传播的原始领域/执行异常；CancelledError 属
        BaseException 不被捕获，取消语义安全。
        """
        if self._tool_execution_repository is None:
            return
        try:
            await self._tool_execution_repository.save(execution)
        except Exception as e:
            logger.warning("ToolExecution 失败态持久化失败（best-effort，不影响在途异常传播）: %s", type(e).__name__)

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
            ConfigurationError: 代码含标记但引擎未注入数据源解析器（EXCEPTION_101
                fail-fast——R3-2 G6：resolver 缺失时含标记代码原样进沙箱必然
                SyntaxError，被误包装为 ToolExecutionFailedError 掩盖装配缺失根因）
            DataSourceError: 全部数据源采集失败（412/413/411 等不包装直传）
        """
        # 标记解析前置（R3-2 G6）：干净代码（$ 仅在字符串/注释内 → 掩码 → markers=()）
        # 与 resolver 是否注入完全正交，保持 4.4 零行为变化；含未掩码标记 +
        # resolver 缺失（组合根未注册数据源端口等部署漂移）→ 101 fail-fast，
        # 而非沙箱 SyntaxError 误导排障方向
        markers = parse_data_source_markers(code)
        if not markers:
            return code, ()

        if self._data_source_resolver is None:
            raise ConfigurationError(
                message="代码含 $DATA_SOURCE 标记但引擎未注入数据源解析器（需 set_data_source_resolver 配置采集链路）",
                context={"stage": "resolve_data_sources", "marker_count": len(markers)},
            )

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
        # 溯源元数据仅收录成功源（过滤等长对齐元组的 None 失败位——失败信息由
        # DataSourceFetchFailed 事件承载）
        metas = tuple(
            DataSourceMeta(
                source_name=r.source_name,
                source_timestamp=r.source_timestamp,
                freshness_score=r.freshness.score(datetime.now(UTC)),
                confidence=r.confidence,
            )
            for r in results
            if r is not None
        )
        return inject_data_sources(code, markers, results), metas

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

        Story 4.7：读取 context.extensions["validation_feedback_hints"]（P0-D
        模式同款通道）——Think stage 消费 case_summaries（含负样本提示）与
        stderr 摘要（Subtask 0.12 per-stage 映射）。
        """
        hints = (context.extensions or {}).get("validation_feedback_hints")
        prompt = self._build_think_prompt(tool, tool_call, hints=hints)
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
        """Code 阶段：调用 LLMClientPort.structured_generate 产出 code

        Story 4.7：Code stage 是唯一代码产出作者——必消费 suggested_fix（优先
        采纳指令）+ prior_attempts（含前次方案摘要——R8-1）+ stderr_excerpt +
        禁止重复失败方案指令 + schema_violations（Subtask 0.12 per-stage 映射）。
        """
        hints = (context.extensions or {}).get("validation_feedback_hints")
        prompt = self._build_code_prompt(plan, tool, hints=hints)
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

    def _build_think_prompt(self, tool: Tool, tool_call: ToolCall, hints: dict | None = None) -> str:
        """构建 Think 阶段 prompt（Story 4.7：可选 hints——case_summaries + stderr 摘要）.

        前缀「为工具」保持稳定（Fake LLM 分派契约——BDD/test_tool_execution_engine_hints）。
        """
        base = f"为工具 {tool.name} 规划执行步骤。参数: {tool_call.arguments}"
        if not hints:
            return base
        sections = [base]
        stderr = str(hints.get("stderr_excerpt", "") or "")
        if stderr:
            sections.append(f"上次执行失败 STDERR 摘要：\n{stderr[:500]}")
        case_summaries = hints.get("case_summaries") or []
        if case_summaries:
            sections.append("历史案例参考：\n" + "\n".join(f"- {str(s)[:500]}" for s in case_summaries))
        return "\n\n".join(sections)

    def _build_code_prompt(self, plan: str, tool: Tool, hints: dict | None = None) -> str:
        """构建 Code 阶段 prompt（Story 4.7：可选 hints——修复反馈注入）.

        前缀「基于以下计划」保持稳定（Fake LLM 分派契约）。
        """
        base = f"基于以下计划生成代码: {plan}"
        if not hints:
            return base
        sections = [base]
        suggested_fix = str(hints.get("suggested_fix", "") or "")
        if suggested_fix:
            sections.append(f"修复顾问建议（优先采纳，仅做必要适配）：\n{suggested_fix[:2000]}")
        stderr = str(hints.get("stderr_excerpt", "") or "")
        if stderr:
            sections.append(f"上次执行失败 STDERR：\n{stderr[:500]}")
        violations = hints.get("schema_violations") or []
        if violations:
            lines = []
            for v in violations:
                if isinstance(v, dict):
                    lines.append(
                        f"- path={v.get('path', '')}, expected={v.get('expected', '')}, message={v.get('message', '')}"
                    )
                else:
                    lines.append(f"- {v}")
            sections.append("上轮 Schema 校验 violations：\n" + "\n".join(lines))
        prior_attempts = hints.get("prior_attempts") or []
        banned: list[str] = []
        if prior_attempts:
            lines = []
            for attempt in prior_attempts:
                no = attempt.get("attempt_no", "?")
                fix = str(attempt.get("suggested_fix_excerpt", "") or "")
                line = f"- attempt {no}（{attempt.get('detail', '')}）"
                if fix:
                    line += f"：已试方案 {fix[:500]}"
                    banned.append(f"attempt {no} 的方案（{fix[:500]}）")
                else:
                    line += "：未产出方案（生成失败）"
                lines.append(line)
            sections.append("此前增强尝试的失败记录：\n" + "\n".join(lines))
        if banned:
            sections.append("以下方案已失败，禁止重复：\n" + "\n".join(f"- {b}" for b in banned))
        return "\n\n".join(sections)

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


def build_tool_execution_engine(resolver: Any) -> ToolExecutionEngine:
    """从组合根 resolver 组装工具执行引擎（域自身组装知识——组合根零私有函数纪律）。

    原组合根私有函数 `_build_tool_execution_engine` 随「组合根禁止出现子模块子系统
    私有函数」约束下沉至本域模块（学习 registration.py R-REG 模式：组装逻辑归
    子模块域，组合根保持纯组合边界一行委托）。

    重试白名单收窄（随迁自组合根 Round 2 审查修订）：默认白名单含 ExecutionError
    会把沙箱确定性失败（313/316/317）错误重试 3 次，并与「超时即销毁」契约冲突；
    仅 LLM 瞬时故障（API/响应/领域超时）可重试。

    Args:
        resolver: 组合根 resolver（Any 注入——避免 application 层反向依赖组合根）

    Returns:
        组装完成的 ToolExecutionEngine（含数据源解析器后注入——Story 4.1b
        set_data_source_resolver 模式，__init__ 签名不变以保护 4.4 AC-7.4 断言）
    """
    engine = ToolExecutionEngine(
        llm_client=resolver.resolve("llm_client"),
        sandbox=resolver.resolve("sandbox_executor"),
        retry_policy=RetryPolicy(
            retryable_exceptions=(
                LLMAPIError,
                LLMResponseError,
                TimeoutError,
            )
        ),
        tool_execution_repository=resolver.resolve("tool_execution_repository"),
    )
    engine.set_data_source_resolver(resolver.resolve_optional("data_source_resolver"))
    return engine


__all__ = ["ToolExecutionEngine", "build_tool_execution_engine"]
