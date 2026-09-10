"""应用层工具链编排器模块

实现 ToolChainOrchestrator（应用层编排器），按拓扑顺序调度 DAG 节点。
负责 6 步流程：DAG 校验 → 拓扑排序 → 波次构建 → 并行执行 → 变量插值 → 状态更新。

设计依据：
- Story 4.2 AC-5：Kahn 算法 + asyncio.TaskGroup 并行 + 3 种失败策略
- 复用 R1 端口：ToolExecutionServicePort（4.1a）+ ToolRegistryServicePort（4.1）
- 算法复杂度：O(V+E) 一次性预计算 + 入度表 + 拓扑排序

3 失败策略语义边界（节点级覆盖 DAG 级）：
- FAIL_FAST：首个节点失败立即取消同波 + 终止整链
- CONTINUE_ON_ERROR：节点失败标记，继续后续节点（无跳过）
- SKIP_DOWNSTREAM：节点失败时三态传播（skip/not_skip/pending）标记下游为 SKIPPED

变量插值：stdlib string.Template 自定义 delimiter="${" + idpattern=r"[a-zA-Z_][a-zA-Z0-9_.]*"
三层错误处理：
- Layer 1: 路径语法非法（缺 output 段）→ EntityBusinessRuleError
- Layer 2: 节点未声明上游 → safe_substitute 保留原文本
- Layer 3: 声明了上游但未完成 → EntityBusinessRuleError
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
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
    EntityStateTransitionError,
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

    idpattern 限制：变量名必须为字母数字下划线 + 点号路径，**且必须以 `}` 结尾**
    以兼容 stdlib string.Template 对 `${name}` 形式的语义：
    stdlib 默认 pattern 只匹配 `${name`（不含 `}`），导致 `${name}` 替换后残留字面 `}`。
    把 `}` 加入 idpattern 后整个 `${name}` 整体被 pattern 匹配，安全替换。

    业界参考：
    - stdlib string.Template（PEP 292）
    - Apache Airflow templated_fields 用 Jinja2 类似处理
    """

    delimiter = "${"
    idpattern = r"[a-zA-Z_][a-zA-Z0-9_.]*}"


class ToolChainOrchestrator:
    """DAG 工具链编排器（应用层服务，组合 ToolExecutionService + ToolRegistryService）

    6 步执行流程：
    1. ToolChainDagValidator.validate(dag) — 前置校验
    2. Kahn 算法生成拓扑序
    3. 切分为多个 execution wave
    4. 每波 asyncio.TaskGroup 并行执行（首个失败取消兄弟）
    5. 节点 arguments_template 通过 string.Template 变量插值
    6. ToolChainRun 状态机迁移 + 性能指标计算（含 critical_path 真实算法）
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
        # 异步构建 slug 索引（asyncio.to_thread 包装同步 list_all_tools，保留 4.1a 同步契约）
        slug_index = await self._build_slug_index_async()

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

        for wave in waves:
            wave_results = await self._execute_wave(
                dag=dag,
                wave=wave,
                completed_node_results=completed_node_results,
                parameters=parameters,
                context=context,
                failed_nodes=failed_nodes,
                node_runs=node_runs,
                slug_index=slug_index,
            )
            for node_id, result in wave_results.items():
                if isinstance(result, ToolResult):
                    completed_node_results[node_id] = result

            # FAIL_FAST 检查：首个失败立即抛出（TaskGroup 已取消兄弟）
            if dag.failure_strategy == FailureStrategy.FAIL_FAST and failed_nodes:
                failed_node_id = failed_nodes[0]
                # 终止态提交（一次性写入 state + completed_at，保留 frozen 语义）
                completed_at = datetime.now(UTC)
                try:
                    run = replace(run, state=ToolChainRunState.FAILED, completed_at=completed_at)
                except EntityStateTransitionError as transition_err:
                    logger.warning("ToolChainRun %s 状态机冲突: %s", run.chain_run_id, transition_err)
                # 提取原始异常（从 wave_results 或 node_runs 拿错误码）
                original_exc = None
                original_code = "WRAPPED_ORCHESTRATOR"
                original_stage = "ORCHESTRATION"
                # node_runs 中若节点 FAILED 状态有 error 字符串，可尝试解码
                node_run = node_runs.get(failed_node_id)
                if node_run and node_run.error:
                    original_exc = RuntimeError(node_run.error)
                # cause 仅在 original_exc 是 Exception 子类时传递（避免 BaseException 误传）
                cause_exc = original_exc if isinstance(original_exc, Exception) else None
                raise ToolChainExecutionFailedError(
                    message=f"工具链 FAIL_FAST 终止于节点 '{failed_node_id}'",
                    chain_run_id=str(run.chain_run_id),
                    chain_id=str(dag.chain_id),
                    failed_node_id=failed_node_id,
                    original_error_code=original_code,
                    original_stage=original_stage,
                    cause=cause_exc,
                )

        # 6. 终态判定 + 性能指标（含 critical_path 真实算法）
        completed_at = datetime.now(UTC)
        wall_clock_sec = (completed_at - run.started_at).total_seconds()

        # 计算串行总耗时（用于 Amdahl 加速比）
        total_work_sec = 0.0
        for nr in node_runs.values():
            if nr.completed_at and nr.started_at:
                total_work_sec += (nr.completed_at - nr.started_at).total_seconds()
        parallel_speedup_ratio = total_work_sec / wall_clock_sec if wall_clock_sec > 0 else 1.0

        # 关键路径（最长路径节点耗时求和，O(V+E) DP）
        node_durations: dict[str, float] = {
            nid: (nr.completed_at - nr.started_at).total_seconds()
            for nid, nr in node_runs.items()
            if nr.completed_at and nr.started_at
        }
        critical_path_sec = self._compute_critical_path(dag, waves, node_durations)

        # 终态提交（一次性 replace）
        terminal_state = ToolChainRunState.COMPLETED_WITH_ERRORS if failed_nodes else ToolChainRunState.COMPLETED
        run = replace(
            run,
            state=terminal_state,
            completed_at=completed_at,
            node_runs=dict(node_runs),
            failed_nodes=tuple(failed_nodes),
            total_duration_sec=wall_clock_sec,
            critical_path_sec=critical_path_sec,
            parallel_speedup_ratio=parallel_speedup_ratio,
            cost_audit=CostAudit(
                parallel_speedup_ratio=parallel_speedup_ratio,
                wall_clock_sec=wall_clock_sec,
                critical_path_sec=critical_path_sec,
            ).to_dict(),
        )
        return run

    # ============================================================================
    # 静态方法（纯函数）— 可被测试和外部使用
    # ============================================================================

    @staticmethod
    def _build_execution_waves(dag: ToolChainDag) -> list[list[str]]:
        """构建执行波次（BFS 拓扑分层）

        算法：使用 Kahn 算法生成拓扑序，按节点入度分层切分为波次。

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

        # 防御性环检测：若 processed 未覆盖所有节点，说明存在环
        # （正常流程由 ToolChainDagValidator 预先保证无环；此处仅作为单元测试独立调用的护栏）
        all_node_ids = {n.node_id for n in dag.nodes}
        if processed != all_node_ids:
            from src.domain.exceptions import ToolChainCycleDetectedError

            raise ToolChainCycleDetectedError(
                message=f"DAG 含环，无法拓扑排序：未处理节点 {sorted(all_node_ids - processed)}",
                chain_id=str(dag.chain_id),
                cycle_path=sorted(all_node_ids - processed),
            )

        return waves

    @staticmethod
    def _interpolate_arguments(
        node: ToolChainNode,
        upstream_results: dict[str, ToolResult],
    ) -> dict[str, Any]:
        """变量插值（${upstream.output.field} 解析）

        使用 stdlib string.Template 自定义 delimiter="${" + idpattern=r"[a-zA-Z_][a-zA-Z0-9_.]*"

        三层错误处理：
        - Layer 1 (路径语法): `${a.x}` 缺 output 段 → EntityBusinessRuleError
        - Layer 2 (节点未声明): `${c.output.x}` 但 c 不在 depends_on → safe_substitute 保留原文本
        - Layer 3 (上游未完成): 声明了上游但尚未完成 → EntityBusinessRuleError

        Args:
            node: 目标节点
            upstream_results: 上游节点结果字典（node_id → ToolResult）

        Returns:
            插值后的参数字典

        Raises:
            EntityBusinessRuleError: 路径语法非法或上游未完成
        """
        declared_upstreams: set[str] = set(node.depends_on)
        interpolated: dict[str, Any] = {}
        for key, raw_value in node.arguments_template.items():
            if not isinstance(raw_value, str):
                interpolated[key] = raw_value
                continue
            tmpl = _PathTemplate(raw_value)
            # 收集所有合法占位符的 path_parts（剥离末尾 `}`）和原 mapping value
            # 同时计算最终值（保留原类型）
            resolved: dict[str, Any] = {}  # ph (含 `}`) -> 解析值（原类型）或 None
            for match in tmpl.pattern.finditer(tmpl.template):
                ph = match.group("named") or match.group("braced")
                if ph is None:
                    continue
                parts = ph.split(".")
                # Layer 1：路径语法必须为 ${node.output.field}
                if len(parts) < 3 or parts[1] != "output":
                    raise EntityBusinessRuleError(
                        message=(
                            f"节点 '{node.node_id}' 的参数 '{key}' 引用非法语法 '${{{ph}}}'：必须为 ${{node.output.field}} 形式"
                        ),
                        context={
                            "entity": "ToolChainNode",
                            "node_id": node.node_id,
                            "parameter": key,
                            "placeholder": ph,
                        },
                    )
                upstream_node_id = parts[0]
                # Layer 2：节点未声明此上游 → safe_substitute 保留原文本
                if upstream_node_id not in declared_upstreams:
                    continue
                # Layer 3：节点声明了上游，但上游未完成
                if upstream_node_id not in upstream_results:
                    raise EntityBusinessRuleError(
                        message=f"节点 '{node.node_id}' 引用了未完成的上游节点 '{upstream_node_id}'",
                        context={
                            "entity": "ToolChainNode",
                            "node_id": node.node_id,
                            "missing_upstream": upstream_node_id,
                            "parameter": key,
                        },
                    )
                # 路径解析（剥离末尾 `}`）
                path_parts = ph.rstrip("}").split(".")
                upstream_result = upstream_results[upstream_node_id]
                current: Any = upstream_result.output
                for segment in path_parts[2:]:  # 跳过 "output"
                    if current is None:
                        break
                    if isinstance(current, dict):
                        current = current.get(segment)
                    else:
                        current = getattr(current, segment, None)
                # None 表示无法解析 → safe_substitute 保留原文本
                resolved[ph] = current
            # 替换策略：若模板整体是单一占位符且 resolved 有值 → 保留原类型返回
            # 否则使用 stdlib safe_substitute 文本拼接（统一 str 类型）
            matches = list(tmpl.pattern.finditer(tmpl.template))
            if len(matches) == 1 and matches[0].start() == 0 and matches[0].end() == len(tmpl.template):
                ph = matches[0].group("named") or matches[0].group("braced")
                val = resolved.get(ph)
                if val is not None:
                    interpolated[key] = val  # 保留原类型
                    continue
            # 通用路径：str mapping + safe_substitute
            mapping: dict[str, str] = {}
            for ph, val in resolved.items():
                mapping[ph] = str(val) if val is not None else "${" + ph + "}"
            interpolated[key] = tmpl.safe_substitute(mapping)
        return interpolated

    @staticmethod
    def _compute_critical_path(
        dag: ToolChainDag,
        waves: list[list[str]],
        node_durations: dict[str, float],
    ) -> float:
        """计算关键路径长度（最长路径上各节点耗时求和）

        算法：反向 DP（O(V+E)）
        - 初始化：dp[nid] = node_durations[nid]（每个节点自身耗时）
        - 递推（反向波次）：dp[nid] = duration[nid] + max(dp[c] for c in children)
        - 结果：max(dp[r] for r in roots) 其中 roots 是无下游的节点

        关键路径语义：理论最大加速比上限（完美并行情况下的串行耗时）

        Args:
            dag: DAG 聚合根
            waves: 波次列表（自顶向下）
            node_durations: 节点耗时字典（node_id → 秒）

        Returns:
            关键路径秒数（0.0 if 无节点）
        """
        if not waves or not node_durations:
            return 0.0
        dp: dict[str, float] = {nid: node_durations.get(nid, 0.0) for nid in node_durations}
        for wave in reversed(waves):
            for nid in wave:
                if nid not in dp:
                    continue
                children = dag._reverse_adj.get(nid, ())
                # 仅考虑 children 中有 duration 记录的（未执行的 SKIPPED 节点不计）
                child_durations = [dp[c] for c in children if c in dp]
                if child_durations:
                    dp[nid] = node_durations.get(nid, 0.0) + max(child_durations)
        # roots: 无下游的节点（叶子）
        all_nodes_with_children: set[str] = set()
        for nid in dp:
            for child in dag._reverse_adj.get(nid, ()):
                all_nodes_with_children.add(child)
        roots = [nid for nid in dp if nid not in all_nodes_with_children]
        return max((dp[r] for r in roots), default=0.0)

    # ============================================================================
    # 私有辅助方法
    # ============================================================================

    async def _build_slug_index_async(self) -> dict[str, uuid.UUID]:
        """构建 slug → tool_id 索引（异步化，保留 4.1a 同步契约）

        使用 asyncio.to_thread 包装同步 list_all_tools() 调用，
        避免在 async 上下文阻塞事件循环。

        Returns:
            slug → tool_id 字典
        """
        tools = await asyncio.to_thread(self._registry_service.list_all_tools)
        return {tool.slug: tool.tool_id for tool in tools if tool.slug}

    def _compute_skip_set(
        self,
        dag: ToolChainDag,
        failed_nodes: list[str],
    ) -> set[str]:
        """三态传播计算 SKIP 集合（尊重节点级 skip_on_upstream_failure 标志）

        算法：BFS 三态传播（skip / not_skip / pending）
        - 父节点 skip + 本节点 skip_on_upstream_failure=True → 本节点 skip
        - 父节点 skip + 本节点 skip_on_upstream_failure=False → 本节点 not_skip（仍要执行）
        - 父节点 not_skip → 本节点状态由自身 skip_on_upstream_failure 决定

        修复要点：原实现无条件把所有 failed_id 的下游加入 skip set，
        导致 B 节点即使 skip_on_upstream_failure=False 也会被标记 SKIPPED。
        本实现正确实现 AC-1 节点级 flag 覆盖语义。

        Args:
            dag: DAG 聚合根
            failed_nodes: 失败节点列表

        Returns:
            应跳过的节点集合 = skip_set - not_skip_set 抵消后的最终集合
        """
        skip_set: set[str] = set()
        not_skip_set: set[str] = set()
        queue: deque[tuple[str, str]] = deque((f, "skip") for f in failed_nodes)
        while queue:
            node_id, state = queue.popleft()
            for child in dag._reverse_adj.get(node_id, ()):
                child_node = dag.nodes_by_id(child)
                if not child_node.skip_on_upstream_failure:
                    # 节点明确"上游失败也要执行" → 标记 not_skip + 继续传播
                    if child not in not_skip_set:
                        not_skip_set.add(child)
                        queue.append((child, "not_skip"))
                elif state == "skip":
                    # 父节点被跳过 + 本节点也接受跳过 → 加入 skip_set
                    if child not in skip_set:
                        skip_set.add(child)
                        queue.append((child, "skip"))
                # else: 父 not_skip，本接受 skip → 既不加入 skip 也不传播
        return skip_set - not_skip_set

    async def _execute_wave(
        self,
        dag: ToolChainDag,
        wave: list[str],
        completed_node_results: dict[str, ToolResult],
        parameters: dict[str, Any],
        context: ExecutionContext,
        failed_nodes: list[str],
        node_runs: dict[str, NodeRunStatus],
        slug_index: dict[str, uuid.UUID],
    ) -> dict[str, ToolResult | None]:
        """执行单波节点（asyncio.TaskGroup + Semaphore 并发控制 + effective_strategy）

        Args:
            dag: 工具链 DAG
            wave: 当前波次节点 ID 列表
            completed_node_results: 已完成节点结果
            parameters: 调用方参数
            context: 执行上下文
            failed_nodes: 失败节点列表（in-place 累积）
            node_runs: 节点运行状态字典（in-place 累积）
            slug_index: tool_slug → tool_id 字典

        Returns:
            本波节点结果字典（node_id → ToolResult | None for SKIPPED）
        """
        # 节点级 effective_strategy（None 时降级到 dag 级）
        effective_strategies: dict[str, FailureStrategy] = {
            nid: dag.nodes_by_id(nid).failure_strategy or dag.failure_strategy for nid in wave
        }

        # 三态传播计算应跳过的节点集合（任一节点 effective 为 SKIP_DOWNSTREAM 时启用）
        downstream_to_skip: set[str] = set()
        if any(effective_strategies[nid] == FailureStrategy.SKIP_DOWNSTREAM for nid in wave):
            downstream_to_skip = self._compute_skip_set(dag, failed_nodes)

        semaphore = asyncio.Semaphore(dag.max_concurrency)
        results: dict[str, ToolResult | None] = {}

        async def execute_node(node_id: str) -> None:
            effective_strategy = effective_strategies[node_id]
            try:
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

                    node = dag.nodes_by_id(node_id)
                    # 检查：是否有依赖上游失败（仅 SKIP_DOWNSTREAM 检查节点 flag）
                    upstream_failed = any(dep in failed_nodes for dep in node.depends_on)
                    if (
                        effective_strategy == FailureStrategy.SKIP_DOWNSTREAM
                        and upstream_failed
                        and node.skip_on_upstream_failure
                    ):
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

                    tool_id = slug_index.get(node.tool_slug)
                    if tool_id is None:
                        raise ToolNotFoundError(slug=node.tool_slug)
                    tool_call = ToolCall(
                        tool_id=tool_id,
                        arguments={**interpolated, **parameters},
                        tenant_id=context.tenant_id,
                    )
                    result = await self._execution_service.execute(tool_id, tool_call, context)
                    completed_at = datetime.now(UTC)
                    result = replace(
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
            except asyncio.CancelledError:
                # 兄弟节点失败触发 TaskGroup 取消时回写 FAILED 状态
                if node_id not in node_runs or node_runs[node_id].state == "RUNNING":
                    node_runs[node_id] = NodeRunStatus(
                        node_id=node_id,
                        state="FAILED",
                        started_at=datetime.now(UTC),
                        completed_at=datetime.now(UTC),
                        error="执行被取消（兄弟节点失败触发 TaskGroup）",
                        tool_result=None,
                    )
                raise
            except Exception as e:
                # 通用异常捕获（ToolExecutionFailedError 等业务异常也走这里）
                # 标记失败并回写 NodeRunStatus
                node_runs[node_id] = NodeRunStatus(
                    node_id=node_id,
                    state="FAILED",
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                    error=f"{type(e).__name__}: {e}",
                    tool_result=None,
                )
                failed_nodes.append(node_id)
                # FAIL_FAST 策略：重新抛出触发 TaskGroup 取消兄弟
                if effective_strategy == FailureStrategy.FAIL_FAST:
                    raise
                # 其他策略：记录失败但不抛出，让 TaskGroup 正常完成
                results[node_id] = None

        try:
            async with asyncio.TaskGroup() as tg:
                for nid in wave:
                    tg.create_task(execute_node(nid))
        except* BaseException as eg:
            # TaskGroup 收到首个异常时取消兄弟任务，包装为 ExceptionGroup
            first_exc = eg.exceptions[0] if eg.exceptions else None
            if first_exc is None:
                raise
            # 标记首个失败节点（从 failed_nodes 推断，因 execute_node 的 except Exception 已加入）
            failed_node_id = failed_nodes[-1] if failed_nodes else None
            # 若任一节点 effective_strategy 为 FAIL_FAST → 立即包装为 ToolChainExecutionFailedError
            if failed_node_id is not None and any(effective_strategies[nid] == FailureStrategy.FAIL_FAST for nid in wave):
                # cause 仅在 first_exc 是 Exception 子类时传递（避免 BaseException 误传）
                cause_exc = first_exc if isinstance(first_exc, Exception) else None
                raise ToolChainExecutionFailedError(
                    message=f"工具链 FAIL_FAST 终止于节点 '{failed_node_id}'",
                    chain_run_id="",  # 由 execute_chain 补全
                    chain_id="",
                    failed_node_id=failed_node_id,
                    original_error_code="WRAPPED_ORCHESTRATOR",
                    original_stage="ORCHESTRATION",
                    cause=cause_exc,
                ) from first_exc
            # 其他策略透传原始异常
            raise first_exc

        return results


__all__ = ["ToolChainOrchestrator"]
