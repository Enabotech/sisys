"""应用层工具链运行用例模块

实现 RunToolChainUseCase（应用层用例），编排：
1. 通过 chain_name 查询 ToolChainDag
2. 通过 SkillLoaderPort 加载节点 Skill（按 tool_slug）
3. 委托 ToolChainService.execute_chain 执行
4. 发布 ToolChainExecuted 事件（双通道：realtime + reliable）

设计依据：Story 4.2 AC-7
- 复用 4.1a SkillLoaderPort 7 方法（节点级加载）
- 异常链路通过 EventBusPort 发布
- 依赖通过端口注入
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from src.application.ports.skill_loader import SkillLoaderPort, ToolMetadata
from src.application.ports.tool_chain_service import ToolChainServicePort
from src.domain.entities.tool_chain import ToolChainDag
from src.domain.entities.tool_chain_run import ToolChainRun
from src.domain.events.tool_chain_events import ToolChainExecuted
from src.domain.exceptions import ToolChainNotFoundError
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.tool_chain_repository import ToolChainRepositoryPort
from src.domain.value_objects.tool_execution import ExecutionContext

logger = logging.getLogger(__name__)


class RunToolChainUseCase:
    """运行工具链用例

    编排流程：
    1. chain_name 查询 ToolChainDag（Repository.list_by_name 或 list_by_query）
    2. 加载 Skill（SkillLoaderPort.load_sop，按 tool_slug，Story 4.1c L2 白名单接线）
    3. 委托 ToolChainService.execute_chain 执行
    4. 发布 ToolChainExecuted 事件（双通道）

    Attributes:
        _repository: 工具链仓储
        _service: 工具链服务
        _skill_loader: Skill 加载器
        _event_publisher: 事件发布器
    """

    def __init__(
        self,
        repository: ToolChainRepositoryPort,
        service: ToolChainServicePort,
        skill_loader: SkillLoaderPort,
        event_publisher: EventPublisher,
    ) -> None:
        """初始化用例

        Args:
            repository: 工具链仓储端口
            service: 工具链服务端口
            skill_loader: Skill 加载器端口
            event_publisher: 事件发布器端口
        """
        self._repository = repository
        self._service = service
        self._skill_loader = skill_loader
        self._event_publisher = event_publisher

    async def execute(
        self,
        chain_name: str,
        parameters: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolChainRun:
        """执行工具链用例

        Args:
            chain_name: 工具链名称（精确匹配）
            parameters: 调用方参数
            context: 执行上下文

        Returns:
            ToolChainRun 运行时实例

        Raises:
            ToolChainNotFoundError: chain_name 不存在（EXCEPTION_394，toolchain 子域）
            ToolChainExecutionFailedError: FAIL_FAST 触发
        """
        # 1. 通过 chain_name 查询 ToolChainDag
        dag = await self._find_dag_by_name(chain_name, context.tenant_id)
        if dag is None:
            raise ToolChainNotFoundError(chain_name=chain_name)

        # 2. 节点级 Skill L2 SOP 预加载（frontmatter 含 data_sources 白名单）
        # Story 4.1c 接线：load_metadata(L1, data_sources 恒为空) → load_sop(L2, 含白名单)。
        # 容错对齐 strategic_analysis 先例：单个 Skill SOP 加载失败不阻断链路，
        # 全部失败时 extensions 不含 tool_metadata 键（含标记时 Engine 按 4.1b 语义抛 207，
        # 安全失败方向正确）。
        slugs = list(dict.fromkeys(node.tool_slug for node in dag.nodes if node.tool_slug))
        skill_metadata: dict[str, ToolMetadata] = {}
        if slugs:
            results = await asyncio.gather(
                *(self._load_sop_tolerantly(slug) for slug in slugs),
            )
            for slug, result in zip(slugs, results):
                if result is not None:
                    skill_metadata[slug] = result

        logger.info("Loaded %d skill metadata for chain '%s'", len(skill_metadata), chain_name)

        # 3. 注入链路共享单 ToolMetadata（白名单依据）后委托 ToolChainService.execute_chain
        # Story 4.1c D7：链路全程共用声明序首节点（dag.nodes[0]）metadata（非字典），
        # 节点级 metadata 切换属 Story 4.2。
        node_metadata = skill_metadata.get(dag.nodes[0].tool_slug) if dag.nodes else None
        exec_context = context.with_extension("tool_metadata", node_metadata) if node_metadata is not None else context
        run = await self._service.execute_chain(chain_id=dag.chain_id, parameters=parameters, context=exec_context)

        # 4. 发布 ToolChainExecuted 事件（双通道：realtime + reliable）
        await self._publish_tool_chain_executed(run, dag)

        return run

    async def _load_sop_tolerantly(self, slug: str) -> ToolMetadata | None:
        """容错加载 Skill L2 SOP frontmatter（Story 4.1c）

        单个 Skill SOP 加载失败不阻断工具链执行（对齐 StrategicAnalysisUseCase
        容错先例）；失败返回 None，由调用方决定 extensions 注入语义。

        Args:
            slug: Skill slug

        Returns:
            ToolMetadata（含 data_sources 白名单）；加载失败返回 None
        """
        try:
            skill_doc = await self._skill_loader.load_sop(slug)
            return skill_doc.frontmatter
        except Exception as exc:
            logger.warning("技能 SOP 加载失败（不阻断工具链执行）: slug=%s exc=%s", slug, exc)
            return None

    async def _find_dag_by_name(self, chain_name: str, tenant_id: uuid.UUID) -> ToolChainDag | None:
        """通过 chain_name + tenant_id 查找 ToolChainDag"""
        from src.domain.ports.tool_chain_repository import ToolChainDagQuery

        results = await self._repository.list_by_query(ToolChainDagQuery(name=chain_name, tenant_id=tenant_id, limit=1))
        if results:
            return results[0]
        return None

    async def _publish_tool_chain_executed(self, run: ToolChainRun, dag: ToolChainDag) -> None:
        """发布 ToolChainExecuted 事件（双通道投递）"""
        event = ToolChainExecuted(
            chain_run_id=run.chain_run_id,
            chain_id=run.chain_id,
            tenant_id=run.tenant_id,
            execution_result={
                "node_runs": {
                    nid: {
                        "state": nr.state,
                        "started_at": nr.started_at.isoformat() if nr.started_at else None,
                        "completed_at": nr.completed_at.isoformat() if nr.completed_at else None,
                        "error": nr.error,
                    }
                    for nid, nr in run.node_runs.items()
                },
                "failed_nodes": list(run.failed_nodes),
                "total_duration_sec": run.total_duration_sec,
                "critical_path_sec": run.critical_path_sec,
                "parallel_speedup_ratio": run.parallel_speedup_ratio,
            },
            cost_audit=run.cost_audit,
            failure_strategy=run.failure_strategy,
        )
        try:
            await self._event_publisher.publish(event)
            logger.info(
                "Published ToolChainExecuted event for chain_run_id=%s",
                run.chain_run_id,
            )
        except Exception as e:
            # 事件发布失败不阻塞业务结果
            logger.error("Failed to publish ToolChainExecuted event: %s", e, exc_info=True)


__all__ = ["RunToolChainUseCase"]
