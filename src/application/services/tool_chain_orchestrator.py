"""应用层工具链编排器模块

实现 ToolChainOrchestrator（应用层编排器），按拓扑顺序调度 DAG 节点。
负责 6 步流程：DAG 校验 → 拓扑排序 → 波次构建 → 并行执行 → 变量插值 → 状态更新。

设计依据：
- Story 4.2 AC-5：Kahn 算法 + asyncio.gather 并行 + 3 种失败策略
- 复用 R1 端口：ToolExecutionServicePort（4.1a）+ ToolRegistryServicePort（4.1）
- 算法复杂度：O(V+E) 一次性预计算 + 入度表 + 拓扑排序

3 失败策略语义边界：
- FAIL_FAST：首个节点失败立即终止整链，抛 ToolChainExecutionFailedError
- CONTINUE_ON_ERROR：节点失败标记，继续后续节点（无跳过）
- SKIP_DOWNSTREAM：节点失败时 BFS _reverse_adj 标记所有下游为 SKIPPED

变量插值：stdlib string.Template 自定义 delimiter="${" + idpattern=r"[a-zA-Z_][a-zA-Z0-9_.]*"
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from string import Template
from typing import Any

from src.application.ports.tool_execution_service import ToolExecutionServicePort
from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.domain.entities.tool_chain import (
    FailureStrategy,
    ToolChainDag,
    ToolChainNode,
)
from src.domain.entities.tool_chain_run import (
    CostAudit,
    NodeRunStatus,
    ToolChainRun,
    ToolChainRunState,
)
from src.domain.exceptions import (
    EntityBusinessRuleError,
    ToolChainExecutionFailedError,
    ToolNotFoundError,
)
from src.domain.services.tool_chain_dag_validator import ToolChainDagValidator
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


# 自定义 delimiter 的 string.Template；限制合法变量名（属性路径 a-zA-Z0-9_+.）
class _PathTemplate(Template):
    """支持 `${upstream.output.field}` 语法的 string.Template

    idpattern 限制：变量名必须为字母数字下划线 + 点号路径
    """

    delimiter = "${"
    idpattern = r"[a-zA-Z_][a-zA-Z0-9_.]*"


# 占位符正则：匹配 ${...}
_PLACEHOLDER_PATTERN = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


class ToolChainOrchestrator:
    """DAG 工具链编排器（应用层服务，组合 ToolExecutionService + ToolRegistryService）

    6 步执行流程：
    1. ToolChainDagValidator.validate(dag) — 前置校验
    2. Kahn 算法生成拓扑序
    3. 切分为多个 execution wave
    4. 每波 asyncio.gather 并行执行
    5. 节点 arguments_template 通过 string.Template 变量插值
    6. ToolChainRun 状态机迁移 + 性能指标计算
    """

    def __init__(
        self,
        tool_execution_service: ToolExecutionServicePort,
        tool_registry_service: ToolRegistryServicePort,
    ) -> None:
        """初始化编排器

        Args:
            tool_execution_service: 工具执行服务（执行节点工具调用）
            tool_registry_service: 工具注册服务（按 slug 查 tool_id）
        """
        self._execution_service = tool_execution_service
        self._registry_service = tool_registry_service
        self._slug_index: dict[str, uuid.UUID] | None = None

    # ============================================================================
    # 公开方法
    # ============================================================================

    async def execute_chain(
        self,
        dag: ToolChainDag,
        parameters: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolChainRun:
        """执行工具链（顶层入口）

        Args:
            dag: 工具链 DAG 聚合根
            parameters: 调用方传入参数
            context: 执行上下文

        Returns:
            工具链运行时实例 ToolChainRun（终态）

        Raises:
            ToolChainCycleDetectedError / ToolChainDuplicateNodeError /
            ToolChainNodeNotFoundError: DAG 校验失败
            ToolChainExecutionFailedError: FAIL_FAST 策略下首个节点失败
        """
        # 重建 slug 索引（每次执行独立缓存）
        self._build_slug_index()

        # 1. DAG 校验
        ToolChainDagValidator.validate(dag)

        # 2-3. 拓扑排序 + 波次构建
        waves = self._build_execution_waves(dag)

        # 初始化 ToolChainRun
        run = ToolChainRun(
            chain_run_id=uuid.uuid4(),
            chain_id=dag.chain_id,
            tenant_id=dag.tenant_id,
            state=ToolChainRunState.PENDING,
            started_at=datetime.now(UTC),
            completed_at=None,
            failure_strategy=dag.failure_strategy,
        )
        run.transition_to(ToolChainRunState.RUNNING)

        # 4-5. 逐波次执行（并行 + 变量插值）
        completed_node_results: dict[str, ToolResult] = {}
        failed_nodes: list[str] = []
        node_runs: dict[str, NodeRunStatus] = {}
        total_work_sec = 0.0

        for wave in waves:
            wave_results = await self._execute_wave(
                dag=dag,
                wave=wave,
                completed_node_results=completed_node_results,
                parameters=parameters,
                context=context,
                failure_strategy=dag.failure_strategy,
                node_runs=node_runs,
                failed_nodes=failed_nodes,
            )
            for node_id, result in wave_results.items():
                if isinstance(result, ToolResult):
                    completed_node_results[node_id] = result
                    if result.completed_at and result.started_at:
                        total_work_sec += (result.completed_at - result.started_at).total_seconds()

            # FAIL_FAST 检查
            if dag.failure_strategy == FailureStrategy.FAIL_FAST and failed_nodes:
                failed_node_id = failed_nodes[0]
                try:
                    run.transition_to(ToolChainRunState.FAILED)
                except Exception:
                    logger.exception("Failed to transition to FAILED")
                raise ToolChainExecutionFailedError(
                    message=f"工具链 FAIL_FAST 终止于节点 '{failed_node_id}'",
                    chain_run_id=str(run.chain_run_id),
                    chain_id=str(dag.chain_id),
                    failed_node_id=failed_node_id,
                    original_error_code="RUNTIME_ERROR",
                    original_stage="EXECUTION",
                )

        # 6. 终态判定 + 性能指标
        completed_at = datetime.now(UTC)
        wall_clock_sec = (completed_at - run.started_at).total_seconds()
        parallel_speedup_ratio = total_work_sec / wall_clock_sec if wall_clock_sec > 0 else 1.0

        if failed_nodes:
            run.transition_to(ToolChainRunState.COMPLETED_WITH_ERRORS)
        else:
            run.transition_to(ToolChainRunState.COMPLETED)

        cost_audit = CostAudit(
            parallel_speedup_ratio=parallel_speedup_ratio,
            wall_clock_sec=wall_clock_sec,
            critical_path_sec=total_work_sec,
        ).to_dict()

        # frozen 聚合根 → 用 replace() 创建新实例
        run = replace(
            run,
            completed_at=completed_at,
            node_runs=dict(node_runs),
            failed_nodes=tuple(failed_nodes),
            total_duration_sec=wall_clock_sec,
            critical_path_sec=total_work_sec,
            parallel_speedup_ratio=parallel_speedup_ratio,
            cost_audit=cost_audit,
        )
        return run

    # ============================================================================
    # 静态方法（纯函数）— 可被测试和外部使用
    # ============================================================================

    @staticmethod
    def _build_execution_waves(dag: ToolChainDag) -> list[list[str]]:
        """构建执行波次（BFS 拓扑分层）

        算法：使用 graphlib.TopologicalSorter（Kahn 算法）生成拓扑序，
        然后按节点入度分层切分为波次。

        Args:
            dag: DAG 聚合根

        Returns:
            波次列表（外层顺序，内层同波可并行）

        Raises:
            ToolChainCycleDetectedError: DAG 含环
        """
        in_degree: dict[str, int] = {n.node_id: len(n.depends_on) for n in dag.nodes}
        waves: list[list[str]] = []
        processed: set[str] = set()

        current_wave: list[str] = [node_id for node_id, deg in in_degree.items() if deg == 0]

        while current_wave:
            waves.append(sorted(current_wave))
            processed.update(current_wave)
            next_wave: list[str] = []
            for node_id in current_wave:
                downstream = dag._reverse_adj.get(node_id, ())
                for down in downstream:
                    if down in processed:
                        continue
                    all_deps_processed = all(dep in processed for dep in dag.nodes_by_id(down).depends_on)
                    if all_deps_processed:
                        next_wave.append(down)
            current_wave = sorted(set(next_wave))

        all_node_ids = {n.node_id for n in dag.nodes}
        if processed != all_node_ids:
            missing = all_node_ids - processed
            from src.domain.exceptions import ToolChainCycleDetectedError

            raise ToolChainCycleDetectedError(
                message=f"DAG 含环，无法拓扑排序：未处理节点 {sorted(missing)}",
                chain_id=str(dag.chain_id),
                cycle_path=sorted(missing),
            )

        return waves

    @staticmethod
    def _interpolate_arguments(
        node: ToolChainNode,
        upstream_results: dict[str, ToolResult],
    ) -> dict[str, Any]:
        """变量插值（${upstream.output.field} 解析）

        使用 stdlib string.Template 自定义 delimiter="${" + idpattern=r"[a-zA-Z_][a-zA-Z0-9_.]*"

        两层错误处理：
        - Layer 1 (string.Template safe_substitute)：变量名拼写错误 / 未声明占位符
          → 保留原文本，不抛错
        - Layer 2 (Orchestrator 守卫)：变量引用的上游节点在 node.depends_on 中声明了，
          但尚未在 completed_node_ids 中 → 抛 EntityBusinessRuleError

        Args:
            node: 目标节点
            upstream_results: 上游节点结果字典（node_id → ToolResult）

        Returns:
            插值后的参数字典

        Raises:
            EntityBusinessRuleError: 引用了声明的上游但未完成
        """
        declared_upstreams: set[str] = set(node.depends_on)
        interpolated: dict[str, Any] = {}
        for key, raw_value in node.arguments_template.items():
            template_str = raw_value if isinstance(raw_value, str) else str(raw_value)
            placeholders = _PLACEHOLDER_PATTERN.findall(template_str)
            if not placeholders:
                # 无占位符 → 原值
                interpolated[key] = raw_value
                continue
            # 取第一个占位符解析（若多个占位符同 key，取第一个）
            ph = placeholders[0]
            parts = ph.split(".")
            if len(parts) < 3 or parts[1] != "output":
                raise EntityBusinessRuleError(
                    message=f"节点 '{node.node_id}' 的参数 '{key}' 引用非法语法 '{ph}'：必须为 ${{node.output.field}} 形式",
                    context={
                        "entity": "ToolChainNode",
                        "node_id": node.node_id,
                        "parameter": key,
                        "placeholder": ph,
                    },
                )
            upstream_node_id = parts[0]
            # Layer 2：变量引用的上游节点是声明的依赖，但未在已完成列表中
            if upstream_node_id in declared_upstreams and upstream_node_id not in upstream_results:
                raise EntityBusinessRuleError(
                    message=f"节点 '{node.node_id}' 引用了未完成的上游节点 '{upstream_node_id}'",
                    context={
                        "entity": "ToolChainNode",
                        "node_id": node.node_id,
                        "missing_upstream": upstream_node_id,
                        "parameter": key,
                    },
                )
            # Layer 1：变量未在声明依赖中 → safe_substitute 保留原文本
            if upstream_node_id not in upstream_results:
                interpolated[key] = raw_value
                continue
            # 路径解析：a.output.field.nested → output[field][nested]
            upstream_result = upstream_results[upstream_node_id]
            current: Any = upstream_result.output
            for segment in parts[2:]:  # 跳过 "output"
                if current is None:
                    break
                if isinstance(current, dict):
                    current = current.get(segment)
                else:
                    current = getattr(current, segment, None)
            if current is None:
                current = "${" + ph + "}"  # 保留原文本
            interpolated[key] = current
        return interpolated

    # ============================================================================
    # 私有辅助方法
    # ============================================================================

    def _build_slug_index(self) -> None:
        """构建 slug → tool_id 索引（缓存于执行器实例）"""
        tools = self._registry_service.list_all_tools()
        self._slug_index = {tool.slug: tool.tool_id for tool in tools if tool.slug}

    async def _execute_wave(
        self,
        dag: ToolChainDag,
        wave: list[str],
        completed_node_results: dict[str, ToolResult],
        parameters: dict[str, Any],
        context: ExecutionContext,
        failure_strategy: FailureStrategy,
        node_runs: dict[str, NodeRunStatus],
        failed_nodes: list[str],
    ) -> dict[str, ToolResult | None]:
        """执行单波节点（asyncio.gather + Semaphore 并发控制）

        Args:
            dag: 工具链 DAG
            wave: 当前波次节点 ID 列表
            completed_node_results: 已完成节点结果
            parameters: 调用方参数
            context: 执行上下文
            failure_strategy: 失败策略
            node_runs: 节点运行状态字典（in-place 累积）
            failed_nodes: 失败节点列表（in-place 累积）

        Returns:
            本波节点结果字典（node_id → ToolResult | None for SKIPPED）
        """
        # 计算下游被 skip 传播的节点
        downstream_to_skip: set[str] = set()
        if failure_strategy == FailureStrategy.SKIP_DOWNSTREAM:
            for failed_id in failed_nodes:
                downstream_to_skip.update(self._collect_downstream(dag, failed_id))

        semaphore = asyncio.Semaphore(dag.max_concurrency)
        results: dict[str, ToolResult | None] = {}

        async def execute_node(node_id: str) -> None:
            async with semaphore:
                # 检查：是否被下游 skip 传播命中
                if node_id in downstream_to_skip:
                    node_runs[node_id] = NodeRunStatus(
                        node_id=node_id,
                        state="SKIPPED",
                        started_at=datetime.now(UTC),
                        completed_at=datetime.now(UTC),
                        error="上游失败传播跳过",
                        tool_result=None,
                    )
                    results[node_id] = None
                    return

                # 检查：是否有依赖上游失败（仅 SKIP_DOWNSTREAM 策略检查）
                node = dag.nodes_by_id(node_id)
                upstream_failed = any(dep in failed_nodes for dep in node.depends_on)
                if failure_strategy == FailureStrategy.SKIP_DOWNSTREAM and upstream_failed and node.skip_on_upstream_failure:
                    node_runs[node_id] = NodeRunStatus(
                        node_id=node_id,
                        state="SKIPPED",
                        started_at=datetime.now(UTC),
                        completed_at=datetime.now(UTC),
                        error="上游失败跳过（依赖节点失败）",
                        tool_result=None,
                    )
                    results[node_id] = None
                    return

                # 变量插值
                try:
                    interpolated = self._interpolate_arguments(node, completed_node_results)
                except EntityBusinessRuleError as e:
                    started_at = datetime.now(UTC)
                    node_runs[node_id] = NodeRunStatus(
                        node_id=node_id,
                        state="FAILED",
                        started_at=started_at,
                        completed_at=datetime.now(UTC),
                        error=str(e),
                        tool_result=None,
                    )
                    failed_nodes.append(node_id)
                    results[node_id] = None
                    return

                # 调用工具
                started_at = datetime.now(UTC)
                node_runs[node_id] = NodeRunStatus(
                    node_id=node_id,
                    state="RUNNING",
                    started_at=started_at,
                )

                try:
                    if not self._slug_index:
                        raise ToolNotFoundError(slug=node.tool_slug)
                    tool_id = self._slug_index.get(node.tool_slug)
                    if tool_id is None:
                        raise ToolNotFoundError(slug=node.tool_slug)
                    tool_call = ToolCall(
                        tool_id=tool_id,
                        arguments={**interpolated, **parameters},
                        tenant_id=context.tenant_id,
                    )
                    # 用本地计时覆盖 ToolResult 默认时间戳（保持真实 wall-clock 累计）
                    from dataclasses import replace as dc_replace

                    result = await self._execution_service.execute(tool_id, tool_call, context)
                    completed_at = datetime.now(UTC)
                    result = dc_replace(
                        result,
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                    node_runs[node_id] = NodeRunStatus(
                        node_id=node_id,
                        state="COMPLETED" if result.status.value == "success" else "FAILED",
                        started_at=started_at,
                        completed_at=completed_at,
                        error=None,
                        tool_result=result.output,
                    )
                    if result.status.value != "success":
                        failed_nodes.append(node_id)
                    results[node_id] = result
                except Exception as e:
                    completed_at = datetime.now(UTC)
                    node_runs[node_id] = NodeRunStatus(
                        node_id=node_id,
                        state="FAILED",
                        started_at=started_at,
                        completed_at=completed_at,
                        error=f"{type(e).__name__}: {e}",
                        tool_result=None,
                    )
                    failed_nodes.append(node_id)
                    results[node_id] = None

        await asyncio.gather(
            *[execute_node(nid) for nid in wave],
            return_exceptions=False,
        )
        return results

    def _collect_downstream(self, dag: ToolChainDag, node_id: str) -> set[str]:
        """BFS 收集节点的所有下游节点（复用 _reverse_adj）

        Args:
            dag: DAG 聚合根
            node_id: 起始节点

        Returns:
            下游节点集合
        """
        downstream: set[str] = set()
        queue = [node_id]
        visited = {node_id}
        while queue:
            current = queue.pop(0)
            children = dag._reverse_adj.get(current, ())
            for child in children:
                if child not in visited:
                    visited.add(child)
                    downstream.add(child)
                    queue.append(child)
        return downstream


__all__ = ["ToolChainOrchestrator"]
