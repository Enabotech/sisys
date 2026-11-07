"""分析师视图服务（Story 6-9）——三段聚合编排 + derive_stage_status 阶段派生.

读侧聚合 CQRS 投影（R2 应用层具体端口组合注入三既有基础端口——R1~R4 设计规则落点）：
    - toolbox 段：skill_selector.list_active_skills()（ACTIVE 纯过滤+slug 清单稳定序）
      → ToolSummary 五键投影白名单 + 分类分组计数（selector 返回序去重序——禁字母序重排）；
    - progress 段：snapshot_repository.load(latest 快照) 直读 state_data 七键
      （步级计数 int 直读口径）+ 六阶段全景派生（timeline step 集合判别——前两阶段
      实数据+后四阶段恒 not_started 规划态）；
    - traceability 段：traceability_tree_service.build_trace_tree(depth=4) 全树
      → 三层有效计数（结论层恒单根节点不计入统计面——R1-F1）+ jump_ready 计数
      + degraded_stages 上卷 + 树顶层哨兵透传。

段级独立容错（6-8 段级降级哲学直系+两层哨兵分立）：三源各自 try 包裹——单源异常
仅该段 degraded=True（计数/清单降默认值），其余段照常聚合，视图整体不抛（AC-5）；
顶层哨兵 build_degraded = 任一段 degraded（段级）；树顶层哨兵 tree_build_degraded
独立透传（「本段拿不到」vs「树内拿不到」语义正交——R1-F5 双分支）。

服务无状态（SINGLETON 并发共享——AC-7 并发约束；禁持每次调用的可变实例态）。

性能口径注记（OD-7——trace_tree 全树成本随归档量增长）：三读串行中 build_trace_tree
最重（query_archive PG 归档查+get_point/find Qdrant 点查）——MVP 量级远小于门限；
万行级归档时该段成为热点，分组统计端口/物化视图立项锚 Epic 7/21。

端口版本：(v1.0.0)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from src.application.ports.analyst_view import (
    BLM_SIX_PHASES,
    PHASE_STEP_DOMAINS,
    AnalystView,
    AnalystViewPort,
    PhaseProgress,
    PhaseStatus,
    ProgressSection,
    ToolboxSection,
    ToolCategorySummary,
    ToolSummary,
    TraceabilitySection,
)
from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
from src.application.ports.skill_selector import SkillSelectorPort
from src.application.ports.traceability_tree import TraceabilityTreePort
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.value_objects.blm_phases import BLM_TOTAL_STEPS

logger = logging.getLogger(__name__)

#: 市场洞察六子步骤裸值域（in_progress 判别值域——ports 值域单源派生）
_MARKET_INSIGHT_SUB_VALUES: frozenset[str] = PHASE_STEP_DOMAINS["market_insight"] - frozenset({"market_insight_synthesis"})

#: timeline step 实值全集（performance_gap+六子+synthesis——值域外脏值过滤面）
_TIMELINE_STEP_DOMAIN: frozenset[str] = PHASE_STEP_DOMAINS["performance_gap"] | PHASE_STEP_DOMAINS["market_insight"]


def derive_stage_status(stage_steps: set[str]) -> PhaseStatus:
    """按 timeline step 集合判别阶段状态（确定性纯函数——AC-3 规则表逐字）.

    规则表（Task 0.2 冻结）：
        - 阶段1（performance_gap）：含 performance_gap 条目 → completed；否则 not_started；
        - 阶段2（market_insight）：含 market_insight_synthesis → completed（synthesis
          优先序——与子步骤并存时 completed 优先）；含任一六子裸值 → in_progress；
          否则 not_started；
        - 阶段3~6：恒 not_started（step_total==0 规划态——V1 归 Epic 10-1，注记归
          CLI 呈现不进 status 值域）。

    单集合参数可判别三规则的依据：三阶段值域两两不相交（{performance_gap}/六子+
    synthesis 七值/∅——AC-3 注记），调用方按阶段值域过滤后传入。

    Args:
        stage_steps: 该阶段归属的 timeline step 值集合（服务层按阶段值域过滤后传入——
            集合去重口径与 step_completed 计数同源，R1-F3）.

    Returns:
        PhaseStatus 三值进度态（completed/in_progress/not_started）.
    """
    if stage_steps & PHASE_STEP_DOMAINS["performance_gap"]:
        return PhaseStatus.COMPLETED
    if "market_insight_synthesis" in stage_steps:
        return PhaseStatus.COMPLETED
    if stage_steps & _MARKET_INSIGHT_SUB_VALUES:
        return PhaseStatus.IN_PROGRESS
    return PhaseStatus.NOT_STARTED


class AnalystViewService(AnalystViewPort):
    """分析师视图聚合服务（三段编排——段级容错+空 plan 幂等读）.

    三依赖注入（OD-11）：skill_selector（SINGLETON）/snapshot_repository（SCOPED）/
    traceability_tree_service（SINGLETON）三既有注册名——两 SINGLETON+一 SCOPED 混态的
    SINGLETON 捕获声明（6-8 OD-11 同款注记：CLI 一次性进程+测试双清下无故障面；
    未来 7-2 长驻 REST 面改 SCOPED 触发器注记）。
    """

    def __init__(
        self,
        *,
        skill_selector: SkillSelectorPort,
        snapshot_repository: SnapshotRepositoryProtocol,
        traceability_tree_service: TraceabilityTreePort,
    ) -> None:
        """三依赖 keyword-only 构造（服务无状态——SINGLETON 并发共享安全）."""
        self._skill_selector = skill_selector
        self._snapshot_repository = snapshot_repository
        self._traceability_tree_service = traceability_tree_service

    async def build_analyst_view(self, *, plan_id: str) -> AnalystView:
        """按 plan_id 构建三段聚合视图（段级独立容错——单源异常不炸整体）.

        Args:
            plan_id: 规划任务标识（UUID 字符串——畸形守卫归用例层 242，服务不守卫）.

        Returns:
            AnalystView 六键冻结视图（空 plan 幂等读返回空态视图不抛——AC-5）.
        """
        # 单时间锚派生（6-8 R1-F2 直系）：入口取一次 now——generated_at 是顶层唯一
        # 每次调用新生成键（并发对照排除集单键——OD-6 联动；段内不透传树 generated_at）
        now = datetime.now(UTC)
        toolbox = await self._build_toolbox_section()
        progress = await self._build_progress_section(plan_id)
        traceability = await self._build_traceability_section(plan_id)
        build_degraded = toolbox.degraded or progress.degraded or traceability.degraded
        return AnalystView(
            plan_id=plan_id,
            generated_at=now.isoformat(),
            build_degraded=build_degraded,
            toolbox=toolbox,
            progress=progress,
            traceability=traceability,
        )

    async def _build_toolbox_section(self) -> ToolboxSection:
        """专业工具箱段（ACTIVE 清单投影白名单+分类分组保序——与 plan 正交）.

        Returns:
            ToolboxSection（selector 异常降 degraded=True 空清单——SkillNotFoundError
            fail-loud「缺档案是资产缺陷」语义在聚合面收敛为段降级+warning，OD-3）.
        """
        try:
            skills = await self._skill_selector.list_active_skills()
            # 投影白名单五键（slug/tool_name/category/description/status——ToolMetadata
            # 18 字段面防扩散，OD-4；白名单单源=ports ToolSummary 字段定义，禁第二源镜像）
            tools = tuple(
                ToolSummary(
                    slug=metadata.slug,
                    tool_name=metadata.tool_name,
                    category=metadata.category,
                    description=metadata.description,
                    status=metadata.status,
                )
                for metadata in skills
            )
            # 分类分组：selector 返回序去重序（dict 保插入序——禁字母序重排，OD-10）
            category_counts: dict[str, int] = {}
            for tool in tools:
                category_counts[tool.category] = category_counts.get(tool.category, 0) + 1
            categories = tuple(
                ToolCategorySummary(category=category, tool_count=count) for category, count in category_counts.items()
            )
            return ToolboxSection(degraded=False, total_tools=len(tools), tools=tools, categories=categories)
        except Exception as error:  # 段级容错：单源异常仅本段降级（键恒在纪律）
            logger.warning("分析师视图工具箱段降级: error=%s: %s", type(error).__name__, error)
            return ToolboxSection(degraded=True)

    async def _build_progress_section(self, plan_id: str) -> ProgressSection:
        """BLM 进度段（latest 快照直读+六阶段派生——畸形降级不抛）.

        逐键处置复刻 6-8 executive_view_service :169-188（R1-F6/R2 补遗）：
        completed_steps 必备缺→段降级 / total_steps `.get` 默认 BLM_TOTAL_STEPS 且
        ≤0 显式段降级（除零守卫）/ timeline、degraded_steps 缺→空列表 / phase、
        current_step `.get` 缺→None（空态同形，不触发段降级）——「宽容-严格」三分界：
        缺键且有单源常量→默认 / 值现且可强转→采用 / 值现且不可用→降级。

        Args:
            plan_id: 规划任务标识.

        Returns:
            ProgressSection（快照缺席降空态默认值含六阶段框架；解析异常/畸形键降
            degraded=True——六阶段框架恒在，静态清单不依赖快照）.
        """
        try:
            snapshot = await self._snapshot_repository.load(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}")
            if snapshot is None:
                return ProgressSection()  # 空态默认值（R3-F2：计数全 0+六阶段 not_started 框架）
            state_data = snapshot.state_data if isinstance(snapshot.state_data, dict) else {}
            completed_steps = int(state_data["completed_steps"])
            total_steps = int(state_data.get("total_steps", BLM_TOTAL_STEPS))
            if total_steps <= 0:
                # 显式早退降级（除零形态守卫——R1-F6）：与缺键/类型错两形态一致留
                # warning 痕迹禁静默降级（6-8 R1-F1 修复形态直系）
                logger.warning(
                    "分析师视图进度段降级: plan_id=%s error=ValueError: total_steps=%s 非正数（除零形态）",
                    plan_id,
                    total_steps,
                )
                return ProgressSection(degraded=True)
            degraded_steps = state_data.get("degraded_steps") or []
            timeline = state_data.get("timeline") or []
            # timeline step 值集合（一次构造——status 派生与 step_completed 计数共用
            # 同一集合，禁二次遍历计数，R1-F3；条目形态守卫+str 过滤+值域过滤防脏值）
            step_values: set[str] = {
                step for entry in timeline if isinstance(entry, dict) for step in [entry.get("step")] if isinstance(step, str)
            } & _TIMELINE_STEP_DOMAIN
            return ProgressSection(
                available=True,
                phase=state_data.get("phase"),
                current_step=state_data.get("current_step"),
                completed_steps=completed_steps,
                total_steps=total_steps,
                progress_percent=int(completed_steps / total_steps * 100),
                degraded_step_count=len(degraded_steps),
                stages=self._derive_stages(step_values),
            )
        except Exception as error:  # 段级容错：读侧脏数据守卫+单源异常隔离（6-8 同款降级哲学）
            logger.warning("分析师视图进度段降级: plan_id=%s error=%s: %s", plan_id, type(error).__name__, error)
            return ProgressSection(degraded=True)

    async def _build_traceability_section(self, plan_id: str) -> TraceabilitySection:
        """溯源摘要段（depth=4 全树统计+jump_ready 计数+哨兵透传——树构建零触碰）.

        两层哨兵分立（R1-F5）：本方法异常→段 degraded=True+tree_build_degraded=False
        （段降级默认值）；树服务正常返回 build_degraded=True 的降级树→仅
        tree_build_degraded 透传+段不降级（6-7 服务内降级形态 :186-192）。

        Args:
            plan_id: 规划任务标识.

        Returns:
            TraceabilitySection（空树幂等 available=False+五计数 0 不抛——「没有数据」
            非「拿不到数据」两层分立语义）.
        """
        try:
            tree = await self._traceability_tree_service.build_trace_tree(plan_id=plan_id, depth=4)
            stage_nodes = tree.root.children  # 分析层（结论层恒单根节点不计入统计面——R1-F1）
            chunk_nodes = [chunk for stage in stage_nodes for chunk in stage.children]  # 实例计数（跨 stage 重复引用按实例计）
            document_nodes = [document for chunk in chunk_nodes for document in chunk.children]  # 同文档多 chunk 嵌套重复计
            stage_count = len(stage_nodes)
            return TraceabilitySection(
                available=stage_count > 0,
                degraded=False,
                stage_count=stage_count,
                chunk_count=len(chunk_nodes),
                document_count=len(document_nodes),
                jump_ready_count=sum(1 for document in document_nodes if document.jump_ready),
                degraded_stage_count=len(tree.degraded_stages),
                tree_build_degraded=tree.build_degraded,  # 树顶层哨兵透传零变形
            )
        except Exception as error:  # 段级容错：本段编排异常（树服务抛异常面）
            logger.warning("分析师视图溯源摘要段降级: plan_id=%s error=%s: %s", plan_id, type(error).__name__, error)
            return TraceabilitySection(degraded=True)

    def _derive_stages(self, step_values: set[str]) -> tuple[PhaseProgress, ...]:
        """六阶段全景派生（静态清单循环+值域过滤——空 plan 框架恒在同路径）.

        Args:
            step_values: timeline step 值全集（值域过滤后——脏值剔除）.

        Returns:
            六元组 PhaseProgress（step_completed 与 status 同源派生自同一 stage_steps
            集合基数——去重口径计数天然有界于阶段值域基数，R1-F3）.
        """
        stages: list[PhaseProgress] = []
        for phase_key, phase_name in BLM_SIX_PHASES:
            domain = PHASE_STEP_DOMAINS[phase_key]
            stage_steps = step_values & domain
            stages.append(
                PhaseProgress(
                    phase_key=phase_key,
                    phase_name=phase_name,
                    status=derive_stage_status(stage_steps),
                    step_completed=len(stage_steps),
                    step_total=len(domain),
                )
            )
        return tuple(stages)
