"""领域层工具链 DAG 校验器模块

定义 ToolChainDagValidator（领域层纯函数服务），对 DAG 拓扑合法性校验。

设计依据：
- Story 4.2 AC-2：3 项校验规则（节点唯一 / 依赖存在 / 无环）
- 业界参考：Apache Airflow 用 Kahn + 单独 nx.find_cycle() 报路径
- stdlib graphlib.TopologicalSorter（Python 3.9+）提供零依赖 Kahn BFS 实现
- 环路径提取：graphlib.CycleError.args[1] 仅返回参与环的节点集合（frozenset），
  不含路径顺序，故使用单点 DFS 从 CycleError 提供的环节点集合中提取路径

校验顺序（**顺序敏感**，前项失败立即抛错）：
1. 节点唯一性（ToolChainDuplicateNodeError）
2. 依赖节点存在性（ToolChainNodeNotFoundError）
3. 无环检测（ToolChainCycleDetectedError，自依赖作为长度为 1 的环被统一捕获）

算法复杂度：O(V + E)
"""

from __future__ import annotations

import logging
from graphlib import CycleError, TopologicalSorter

from src.domain.entities.tool_chain import ToolChainDag
from src.domain.exceptions import (
    ToolChainCycleDetectedError,
    ToolChainDuplicateNodeError,
    ToolChainNodeNotFoundError,
)

logger = logging.getLogger(__name__)


class ToolChainDagValidator:
    """DAG 校验器（领域层纯函数服务，**无状态、无依赖**）

    使用 stdlib graphlib.TopologicalSorter（Kahn 算法 BFS）做拓扑排序 + 环检测；
    自依赖作为长度为 1 的环被统一捕获；环路径提取通过 DFS 调用
    （graphlib.CycleError 仅返回节点集合，不含路径）。
    """

    @staticmethod
    def validate(dag: ToolChainDag) -> None:
        """校验 DAG 合法性（无环 + 节点唯一 + 依赖存在）

        Args:
            dag: 待校验的 DAG 聚合根

        Raises:
            ToolChainDuplicateNodeError: 节点重复
            ToolChainNodeNotFoundError: 依赖节点不存在
            ToolChainCycleDetectedError: 循环依赖（含自依赖）
        """
        # === Step 1: 节点唯一性校验 ===
        seen: set[str] = set()
        for node in dag.nodes:
            if node.node_id in seen:
                raise ToolChainDuplicateNodeError(
                    message=f"DAG 节点 node_id='{node.node_id}' 重复",
                    chain_id=str(dag.chain_id),
                    duplicate_node_id=node.node_id,
                )
            seen.add(node.node_id)

        # === Step 2: 依赖节点存在性校验 ===
        node_ids = {n.node_id for n in dag.nodes}
        missing_to_referrers: dict[str, list[str]] = {}
        for node in dag.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    missing_to_referrers.setdefault(dep, []).append(node.node_id)
        if missing_to_referrers:
            # 取第一个缺失节点作为主键（context 字段要求单一 missing_node_id）
            missing_node_id, referrers = next(iter(missing_to_referrers.items()))
            raise ToolChainNodeNotFoundError(
                message=f"DAG 边引用了不存在的节点 '{missing_node_id}'",
                chain_id=str(dag.chain_id),
                missing_node_id=missing_node_id,
                referenced_by_node_ids=referrers,
            )

        # === Step 3: 无环检测（Kahn 算法 BFS） ===
        graph: dict[str, list[str]] = {}
        # TopologicalSorter 要求所有节点都作为 key 出现，即使没有出边
        for node in dag.nodes:
            graph[node.node_id] = list(node.depends_on)
        try:
            sorter = TopologicalSorter(graph)
            # prepare() 内部做 Kahn 算法 BFS；如有环则抛 CycleError
            sorter.prepare()
            # 不强制 static_order()，仅触发 prepare() 检测环
        except CycleError as e:
            # CycleError.args = (msg, frozenset[node_ids in cycle])
            # 仅返回环上节点集合，不含路径；需 DFS 提取环路径
            cycle_nodes: frozenset[str] = e.args[1]  # type: ignore[assignment]
            cycle_path = ToolChainDagValidator._extract_cycle_path(dag, cycle_nodes)
            raise ToolChainCycleDetectedError(
                message=f"DAG 包含循环依赖，环路径: {' -> '.join(cycle_path)}",
                chain_id=str(dag.chain_id),
                cycle_path=cycle_path,
            ) from e

    @staticmethod
    def _extract_cycle_path(dag: ToolChainDag, cycle_nodes: frozenset[str]) -> list[str]:
        """从环上节点集合中提取环路径（DFS）

        Args:
            dag: DAG 聚合根
            cycle_nodes: CycleError 提供的环上节点集合（frozenset）

        Returns:
            环路径列表（如 ["b", "c", "d", "b"]），保证起始节点在 cycle_nodes 中
        """
        if not cycle_nodes:
            return []
        # 构造邻接表：depends_on 表（n 依赖 → n 是其下游的反向）
        # Kahn 检测环的方向基于 depends_on（入度方向），故环也在 depends_on 边中
        # 我们需要从 cycle_nodes 中的某个节点出发，沿 depends_on 边 DFS 找到回路
        reverse_adj = dag._reverse_adj  # 复用预计算的反向邻接表

        # 任选 cycle_nodes 中一个起点，找到该节点的下游中也在环内的节点
        # 从该下游出发继续 DFS，最终回到起点
        for start in cycle_nodes:
            path = ToolChainDagValidator._dfs_find_cycle(start, start, reverse_adj, cycle_nodes, set())
            if path is not None:
                return path
        # 兜底：若 DFS 失败，返回 sorted 列表
        return sorted(cycle_nodes)

    @staticmethod
    def _dfs_find_cycle(
        start: str,
        current: str,
        reverse_adj: dict[str, tuple[str, ...]],
        cycle_nodes: frozenset[str],
        visited: set[str],
    ) -> list[str] | None:
        """DFS 搜索环路径

        Args:
            start: 环起始节点
            current: 当前访问节点
            reverse_adj: 反向邻接表（current → 其下游节点列表）
            cycle_nodes: 环上节点集合（剪枝用）
            visited: 当前 DFS 路径上的节点集合

        Returns:
            环路径列表（start → ... → start），未找到返回 None
        """
        visited = visited | {current}
        neighbors = reverse_adj.get(current, ())
        for next_node in neighbors:
            if next_node not in cycle_nodes:
                continue
            if next_node == start:
                # 回到起点，环路径完成
                return [current, start]
            if next_node in visited:
                # 进入已访问节点（环路径上的节点），跳过避免死循环
                continue
            sub_path = ToolChainDagValidator._dfs_find_cycle(start, next_node, reverse_adj, cycle_nodes, visited)
            if sub_path is not None:
                return [current] + sub_path
        return None


__all__ = ["ToolChainDagValidator"]
