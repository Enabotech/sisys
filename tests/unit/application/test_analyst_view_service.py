"""Story 6-9 - 分析师视图服务单元测试（三段编排 + derive_stage_status 派生矩阵 + 段级容错）.

Mock 形态（故事 Task 2 循环 A 钦定）：三依赖全 AsyncMock(spec=Protocol)（三端口
Protocol 全在册——组合根 interface 注册面，无需具体类 spec）+ `_make_*` 工厂。

覆盖面：
    - 循环 A 三段聚合（工具箱投影白名单+分类分组保序/进度 state_data 解析+六阶段
      派生+单时间锚/溯源三层有效计数+jump_ready 计数+哨兵透传）；
    - 循环 B derive_stage_status 规则矩阵（三状态×timeline 形态 ≥10 格全枚举——
      含 synthesis 优先序边界格/重复条目去重格/值域外脏值格）；
    - 循环 C 段级容错（三源×抛异常→段 degraded+其余正常+build_degraded）+
      traceability 双分支格（R1-F5）+ 空 plan 幂等读 + state_data 畸形守卫
      （逐键处置复刻 6-8 :169-188——R1-F6/R2 补遗）。

Run with:
    poetry run pytest tests/unit/application/test_analyst_view_service.py -v
"""

from __future__ import annotations

import uuid as uuid_module
from typing import Any
from unittest import mock

from src.application.ports.analyst_view import (
    BLM_SIX_PHASES,
    PhaseStatus,
    ToolboxSection,
)
from src.application.ports.skill_loader import ToolMetadata
from src.application.ports.skill_selector import SkillSelectorPort
from src.application.ports.traceability_tree import (
    ChunkNode,
    DocumentNode,
    StageNode,
    TraceabilityTree,
    TraceabilityTreePort,
)
from src.application.services.analyst_view_service import (
    AnalystViewService,
    derive_stage_status,
)
from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.exceptions import SkillNotFoundError
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol

# ===================================================================
# Mock 工厂（三依赖 AsyncMock spec=Protocol——Task 2 循环 A 钦定形态）
# ===================================================================


def _make_tool_metadata(
    slug: str = "pestel-analysis",
    category: str = "environment_analysis",
    status: str = "active",
) -> ToolMetadata:
    """L1 元数据 fixture（必填五字段+默认其余——18 字段面完整构造）."""
    return ToolMetadata(
        tool_name=f"工具-{slug}",
        slug=slug,
        category=category,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        description=f"{slug} 的一句话功能描述",
        status=status,
    )


def _make_skill_selector(
    *,
    skills: tuple[ToolMetadata, ...] | None = None,
    error: Exception | None = None,
) -> mock.AsyncMock:
    """工具箱 selector Mock（spec=SkillSelectorPort——ACTIVE 清单返回序契约）."""
    selector = mock.AsyncMock(spec=SkillSelectorPort)
    if error is not None:
        selector.list_active_skills.side_effect = error
    else:
        selector.list_active_skills.return_value = skills if skills is not None else ()
    return selector


def _make_snapshot_repo(
    *,
    load_return: Any = None,
    load_side_effect: Any = None,
) -> mock.AsyncMock:
    """快照仓储 Mock（spec=SnapshotRepositoryProtocol）."""
    repo = mock.AsyncMock(spec=SnapshotRepositoryProtocol)
    if load_side_effect is not None:
        repo.load.side_effect = load_side_effect
    else:
        repo.load.return_value = load_return
    return repo


def _make_document(
    document_id: str,
    *,
    page: int | None = 3,
    object_key: str | None = "raw-documents/acceptance/doc.pdf",
    jump_ready: bool = True,
) -> DocumentNode:
    """文档层节点 fixture（jump_ready 派生布尔由服务侧预置——计数观测面）."""
    return DocumentNode(
        document_id=document_id,
        filename=f"文档-{document_id[:8]}.pdf",
        version=1,
        page=page,
        object_key=object_key,
        jump_ready=jump_ready,
    )


def _make_chunk(chunk_id: str, documents: tuple[DocumentNode, ...] = ()) -> ChunkNode:
    """切片层节点 fixture."""
    return ChunkNode(
        chunk_id=chunk_id,
        content_excerpt=f"切片内容（{chunk_id}）",
        page_start=3,
        page_end=4,
        status="resolved",
        children=documents,
    )


def _make_stage_node(stage: str, chunks: tuple[ChunkNode, ...] = ()) -> StageNode:
    """分析层节点 fixture（synthesis 行不产生 StageNode——6-7 语义）."""
    return StageNode(
        stage=stage,
        display_name=f"阶段-{stage}",
        summary=f"摘要（{stage}）",
        degraded=False,
        degrade_reason="",
        tools_used=("tool-a",),
        reflection_excerpt="反思摘录",
        evidence_count=1,
        children=chunks,
    )


def _make_tree(
    plan_id: str,
    *,
    stages: tuple[StageNode, ...] = (),
    build_degraded: bool = False,
    degraded_stages: tuple[str, ...] = (),
) -> TraceabilityTree:
    """溯源树 fixture（root 即唯一 ConclusionNode——结论层恒单根节点不计入统计面）."""
    from src.application.ports.traceability_tree import ConclusionNode

    root = ConclusionNode(
        plan_id=plan_id,
        title="BLM 战略规划溯源",
        summary="综合结论联展",
        stage_count=len(stages),
        children=stages,
    )
    return TraceabilityTree(
        plan_id=plan_id,
        root=root,
        adopted_archives=len(stages),
        total_archives=len(stages),
        degraded_stages=degraded_stages,
        build_degraded=build_degraded,
        generated_at="2026-11-07T10:00:00+00:00",
    )


def _make_tree_service(
    *,
    tree: TraceabilityTree | None = None,
    error: Exception | None = None,
) -> mock.AsyncMock:
    """溯源树服务 Mock（spec=TraceabilityTreePort）."""
    service = mock.AsyncMock(spec=TraceabilityTreePort)
    if error is not None:
        service.build_trace_tree.side_effect = error
    else:
        service.build_trace_tree.return_value = tree if tree is not None else _make_tree("tree-plan")
    return service


def _make_service(
    *,
    skill_selector: mock.AsyncMock | None = None,
    snapshot_repo: mock.AsyncMock | None = None,
    tree_service: mock.AsyncMock | None = None,
) -> AnalystViewService:
    """三依赖注入服务构造（keyword-only——ExecutiveViewService 同风格）."""
    return AnalystViewService(
        skill_selector=skill_selector or _make_skill_selector(),
        snapshot_repository=snapshot_repo or _make_snapshot_repo(),
        traceability_tree_service=tree_service or _make_tree_service(),
    )


def _make_latest_snapshot(
    plan_id: str,
    *,
    completed: int = 3,
    total: int = 8,
    timeline_steps: tuple[str, ...] = ("performance_gap", "trend"),
    degraded_steps: list[str] | None = None,
) -> CheckpointSnapshot:
    """latest 快照 fixture（state_data 七键——timeline step 裸值三形态 R1-F4）."""
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX

    timeline = [
        {"step": step, "completed_at": "2026-11-07T10:00:00+00:00", "degraded": step in (degraded_steps or [])}
        for step in timeline_steps
    ]
    return CheckpointSnapshot(
        session_id=f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}",
        state_data={
            "plan_id": plan_id,
            "phase": "market_insight",
            "current_step": timeline_steps[-1] if timeline_steps else None,
            "completed_steps": completed,
            "total_steps": total,
            "degraded_steps": degraded_steps or [],
            "timeline": timeline,
        },
    )


# ===================================================================
# 循环 A：三段聚合编排
# ===================================================================


class TestThreeSectionAggregation:
    """循环 A：三段聚合（Mock 三依赖——投影/解析/统计/单时间锚）."""

    async def test_toolbox_projection_and_categories(self) -> None:
        """工具箱段：投影白名单五键+分类分组保序（selector 返回序派生禁字母序重排）."""
        plan_id = str(uuid_module.uuid4())
        skills = (
            _make_tool_metadata(slug="pestel-analysis", category="environment_analysis"),
            _make_tool_metadata(slug="competitor-analysis", category="competitive_analysis"),
            _make_tool_metadata(slug="porters-five-forces", category="environment_analysis"),
        )
        service = _make_service(
            skill_selector=_make_skill_selector(skills=skills),
            snapshot_repo=_make_snapshot_repo(),
            tree_service=_make_tree_service(),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.toolbox.degraded is False
        assert view.toolbox.total_tools == 3
        assert tuple(tool.slug for tool in view.toolbox.tools) == (
            "pestel-analysis",
            "competitor-analysis",
            "porters-five-forces",
        )
        first = view.toolbox.tools[0]
        assert (first.slug, first.tool_name, first.category, first.description, first.status) == (
            "pestel-analysis",
            "工具-pestel-analysis",
            "environment_analysis",
            "pestel-analysis 的一句话功能描述",
            "active",
        )
        # 分组序=selector 返回序去重序（environment 先于 competitive 出现——禁字母序）
        assert [(category.category, category.tool_count) for category in view.toolbox.categories] == [
            ("environment_analysis", 2),
            ("competitive_analysis", 1),
        ]
        assert sum(category.tool_count for category in view.toolbox.categories) == view.toolbox.total_tools

    async def test_toolbox_projection_excludes_execution_fields(self) -> None:
        """投影白名单：input_schema 等执行面载荷禁入 ToolSummary（构造入参仅五键）."""
        plan_id = str(uuid_module.uuid4())
        skills = (_make_tool_metadata(),)
        service = _make_service(
            skill_selector=_make_skill_selector(skills=skills),
            snapshot_repo=_make_snapshot_repo(),
            tree_service=_make_tree_service(),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        from dataclasses import fields

        assert {f.name for f in fields(view.toolbox.tools[0])} == {"slug", "tool_name", "category", "description", "status"}
        assert not hasattr(view.toolbox.tools[0], "input_schema")

    async def test_progress_section_state_data_parsing(self) -> None:
        """进度段：state_data 七键直读+六阶段派生+单时间锚 generated_at."""
        plan_id = str(uuid_module.uuid4())
        snapshot = _make_latest_snapshot(
            plan_id,
            completed=3,
            timeline_steps=("performance_gap", "trend", "market_customer"),
            degraded_steps=["performance_gap"],
        )
        service = _make_service(
            skill_selector=_make_skill_selector(),
            snapshot_repo=_make_snapshot_repo(load_return=snapshot),
            tree_service=_make_tree_service(),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        progress = view.progress
        assert progress.available is True
        assert progress.degraded is False
        assert progress.phase == "market_insight"
        assert progress.current_step == "market_customer"
        assert progress.completed_steps == 3
        assert progress.total_steps == 8
        assert progress.progress_percent == 37  # int(3/8*100) 向下取整
        assert progress.degraded_step_count == 1
        assert [stage.status for stage in progress.stages] == [
            PhaseStatus.COMPLETED,
            PhaseStatus.IN_PROGRESS,
            PhaseStatus.NOT_STARTED,
            PhaseStatus.NOT_STARTED,
            PhaseStatus.NOT_STARTED,
            PhaseStatus.NOT_STARTED,
        ]
        assert progress.stages[1].step_completed == 2  # trend+market_customer 去重集合基数
        assert view.generated_at  # 单时间锚 ISO 字符串

    async def test_traceability_section_statistics(self) -> None:
        """溯源段：三层有效计数（chunk 实例跨 stage 重复计）+jump_ready 计数+哨兵透传."""
        plan_id = str(uuid_module.uuid4())
        shared_doc = _make_document("doc-shared")
        tree = _make_tree(
            plan_id,
            stages=(
                _make_stage_node("performance_gap", (_make_chunk("chunk-1", (_make_document("doc-1"),)),)),
                _make_stage_node(
                    "market_insight_trend",
                    (
                        _make_chunk("chunk-2", (shared_doc,)),
                        _make_chunk("chunk-3", (_make_document("doc-2", page=None, object_key=None, jump_ready=False),)),
                    ),
                ),
            ),
        )
        service = _make_service(
            skill_selector=_make_skill_selector(),
            snapshot_repo=_make_snapshot_repo(),
            tree_service=_make_tree_service(tree=tree),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        traceability = view.traceability
        assert traceability.available is True
        assert traceability.degraded is False
        assert traceability.stage_count == 2
        assert traceability.chunk_count == 3  # 实例计数（2 stage×3 chunk——判别计数面错接）
        assert traceability.document_count == 3
        assert traceability.jump_ready_count == 2  # True 2+False 1 混合判别
        assert traceability.degraded_stage_count == 0
        assert traceability.tree_build_degraded is False

    async def test_traceability_stage_count_with_degraded_stages(self) -> None:
        """溯源段：degraded_stages 上卷计数（len 透传——R2-F9 补全枚举）."""
        plan_id = str(uuid_module.uuid4())
        tree = _make_tree(
            plan_id,
            stages=(_make_stage_node("performance_gap"),),
            degraded_stages=("performance_gap",),
        )
        service = _make_service(
            skill_selector=_make_skill_selector(),
            snapshot_repo=_make_snapshot_repo(),
            tree_service=_make_tree_service(tree=tree),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.traceability.degraded_stage_count == 1
        assert view.traceability.tree_build_degraded is False

    async def test_top_level_build_degraded_or_semantics(self) -> None:
        """顶层哨兵：全正常 False（任一段 degraded 即 True 归循环 C 各格承载——正向对照腿）."""
        plan_id = str(uuid_module.uuid4())
        snapshot = _make_latest_snapshot(plan_id)
        service = _make_service(
            skill_selector=_make_skill_selector(skills=(_make_tool_metadata(),)),
            snapshot_repo=_make_snapshot_repo(load_return=snapshot),
            tree_service=_make_tree_service(tree=_make_tree(plan_id, stages=(_make_stage_node("performance_gap"),))),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.build_degraded is False
        assert view.plan_id == plan_id


# ===================================================================
# 循环 B：derive_stage_status 派生规则矩阵（三状态×timeline 形态 ≥10 格）
# ===================================================================


class TestDeriveStageStatusMatrix:
    """循环 B：阶段状态派生规则表（Task 0.2 冻结——确定性纯函数单集合判别）."""

    def test_stage1_with_performance_gap_completed(self) -> None:
        """格 1：阶段1 含 performance_gap → completed."""
        assert derive_stage_status({"performance_gap"}) is PhaseStatus.COMPLETED

    def test_stage1_without_performance_gap_not_started(self) -> None:
        """格 2：阶段1 空 → not_started."""
        assert derive_stage_status(set()) is PhaseStatus.NOT_STARTED

    def test_stage2_with_synthesis_completed(self) -> None:
        """格 3：阶段2 含 synthesis → completed（synthesis 优先序）."""
        assert derive_stage_status({"trend", "market_insight_synthesis"}) is PhaseStatus.COMPLETED

    def test_stage2_partial_substeps_in_progress(self) -> None:
        """格 4：阶段2 仅子步骤（部分 1-6）→ in_progress."""
        assert derive_stage_status({"trend"}) is PhaseStatus.IN_PROGRESS
        assert (
            derive_stage_status({"trend", "market_customer", "competition", "self", "opportunity", "opportunity_gap"})
            is PhaseStatus.IN_PROGRESS
        )

    def test_stage2_empty_not_started(self) -> None:
        """格 5：阶段2 空 → not_started."""
        assert derive_stage_status(set()) is PhaseStatus.NOT_STARTED

    def test_stage2_synthesis_without_subs_dirty_boundary(self) -> None:
        """格 6：synthesis-without-subs 脏形态边界格（synthesis 单独在 → completed——优先序边界）."""
        assert derive_stage_status({"market_insight_synthesis"}) is PhaseStatus.COMPLETED

    def test_later_four_phases_always_not_started(self) -> None:
        """格 7：阶段3~6 恒 not_started（step_total==0 规划态——空集合传入）."""
        assert derive_stage_status(set()) is PhaseStatus.NOT_STARTED

    def test_stage2_full_seven_steps_completed(self) -> None:
        """格 8：阶段2 全 7 值 → completed+step_completed 边界（全量格）."""
        stage_steps = {
            "trend",
            "market_customer",
            "competition",
            "self",
            "opportunity",
            "opportunity_gap",
            "market_insight_synthesis",
        }
        assert derive_stage_status(stage_steps) is PhaseStatus.COMPLETED
        assert len(stage_steps) == 7

    def test_duplicate_entries_deduplicated(self) -> None:
        """格 9：重复 timeline 条目去重（2×trend → 集合基数 1——R1-F3 判别格）."""
        step_values = {"trend", "trend"}  # set 字面量天然去重——服务层集合构造同口径
        assert derive_stage_status(step_values) is PhaseStatus.IN_PROGRESS
        assert len(step_values) == 1

    def test_out_of_domain_dirty_value_ignored(self) -> None:
        """格 10：值域外脏值（market_insight_trend 前缀形态）不触发阶段2——写侧裸值契约防御."""
        assert derive_stage_status({"market_insight_trend"}) is PhaseStatus.NOT_STARTED

    async def test_service_dedup_count_with_duplicate_timeline(self) -> None:
        """格 11：服务层重复 timeline 条目计数去重（step_completed==1 非条目数 2）."""
        plan_id = str(uuid_module.uuid4())
        snapshot = _make_latest_snapshot(
            plan_id,
            completed=1,
            timeline_steps=("performance_gap", "trend", "trend"),  # record_step 纯 append 无幂等防护——重复形态
        )
        service = _make_service(
            skill_selector=_make_skill_selector(),
            snapshot_repo=_make_snapshot_repo(load_return=snapshot),
            tree_service=_make_tree_service(),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.progress.stages[1].step_completed == 1  # 集合去重口径（R1-F3）
        assert view.progress.stages[1].status is PhaseStatus.IN_PROGRESS

    async def test_service_dirty_value_not_affecting_derivation(self) -> None:
        """格 12：值域外脏值不入派生（前缀形态 timeline → 六阶段全 not_started——「快照计数 vs 派生计数」分立注记）."""
        plan_id = str(uuid_module.uuid4())
        snapshot = _make_latest_snapshot(
            plan_id,
            completed=8,
            total=8,
            timeline_steps=(
                "market_insight_trend",
                "market_insight_strategy",
                "market_insight_risk",
            ),  # 6-8 _STEP_SEQUENCE 前缀形态脏值
        )
        service = _make_service(
            skill_selector=_make_skill_selector(),
            snapshot_repo=_make_snapshot_repo(load_return=snapshot),
            tree_service=_make_tree_service(),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.progress.completed_steps == 8  # 快照 int 直读口径
        assert all(stage.status is PhaseStatus.NOT_STARTED for stage in view.progress.stages)  # 派生口径独立

    async def test_stages_static_framework_key_sequence(self) -> None:
        """服务六阶段框架恒在：phase_key 六元组与 BLM_SIX_PHASES 精确一致（含空 plan）."""
        plan_id = str(uuid_module.uuid4())
        service = _make_service(
            skill_selector=_make_skill_selector(),
            snapshot_repo=_make_snapshot_repo(load_return=None),
            tree_service=_make_tree_service(),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert [stage.phase_key for stage in view.progress.stages] == [pair[0] for pair in BLM_SIX_PHASES]
        assert [stage.step_total for stage in view.progress.stages] == [1, 7, 0, 0, 0, 0]


# ===================================================================
# 循环 C：段级容错与畸形守卫
# ===================================================================


class TestSectionFaultTolerance:
    """循环 C：段级独立容错（单源异常仅该段 degraded，其余段照常，视图不抛——AC-5）."""

    async def test_selector_error_degrades_toolbox_only(self) -> None:
        """toolbox 源异常（SkillNotFoundError——fail-loud 资产缺陷语义收敛为段降级）→ 仅工具箱段降级."""
        plan_id = str(uuid_module.uuid4())
        service = _make_service(
            skill_selector=_make_skill_selector(error=SkillNotFoundError(slug="pestel-analysis")),
            snapshot_repo=_make_snapshot_repo(load_return=_make_latest_snapshot(plan_id)),
            tree_service=_make_tree_service(),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.toolbox.degraded is True
        assert view.toolbox.total_tools == 0
        assert view.toolbox.tools == ()
        assert view.progress.degraded is False
        assert view.traceability.degraded is False
        assert view.build_degraded is True

    async def test_snapshot_error_degrades_progress_only(self) -> None:
        """progress 源异常（快照读异常——RedisSnapshotStore 真实链路吞异常归 None，本格 AsyncMock 面可达）→ 仅进度段降级."""
        plan_id = str(uuid_module.uuid4())
        service = _make_service(
            skill_selector=_make_skill_selector(skills=(_make_tool_metadata(),)),
            snapshot_repo=_make_snapshot_repo(load_side_effect=RuntimeError("redis down")),
            tree_service=_make_tree_service(),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.progress.degraded is True
        assert view.progress.available is False
        assert len(view.progress.stages) == 6  # 六阶段框架恒在（静态清单不依赖快照）
        assert view.toolbox.degraded is False
        assert view.traceability.degraded is False
        assert view.build_degraded is True

    async def test_tree_error_degrades_traceability_only(self) -> None:
        """traceability 源异常 → 段降级+tree_build_degraded==False（段降级默认值——R1-F5 ②）."""
        plan_id = str(uuid_module.uuid4())
        service = _make_service(
            skill_selector=_make_skill_selector(skills=(_make_tool_metadata(),)),
            snapshot_repo=_make_snapshot_repo(load_return=_make_latest_snapshot(plan_id)),
            tree_service=_make_tree_service(error=Exception("qdrant unreachable")),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.traceability.degraded is True
        assert view.traceability.available is False
        assert view.traceability.tree_build_degraded is False  # 段降级默认值（非树顶层哨兵）
        assert view.toolbox.degraded is False
        assert view.progress.degraded is False
        assert view.build_degraded is True

    async def test_tree_build_degraded_flag_passthrough(self) -> None:
        """R1-F5 ①：正常返回 build_degraded=True 的树 → tree_build_degraded 透传+段不降级."""
        plan_id = str(uuid_module.uuid4())
        tree = _make_tree(plan_id, stages=(), build_degraded=True)  # 6-7 服务内降级形态（query_archive 异常被捕获返回降级空树）
        service = _make_service(
            skill_selector=_make_skill_selector(skills=(_make_tool_metadata(),)),
            snapshot_repo=_make_snapshot_repo(load_return=_make_latest_snapshot(plan_id)),
            tree_service=_make_tree_service(tree=tree),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.traceability.degraded is False  # 段编排无异常
        assert view.traceability.tree_build_degraded is True  # 树顶层哨兵透传零变形
        assert view.traceability.available is False  # 空树 stage_count==0
        assert view.build_degraded is False  # 树顶层哨兵不并入顶层 build_degraded（两层分立）

    async def test_all_sources_error_view_not_raised(self) -> None:
        """三源全异常 → 视图整体不抛+三段全降级+build_degraded."""
        plan_id = str(uuid_module.uuid4())
        service = _make_service(
            skill_selector=_make_skill_selector(error=SkillNotFoundError(slug="any")),
            snapshot_repo=_make_snapshot_repo(load_side_effect=RuntimeError("redis down")),
            tree_service=_make_tree_service(error=Exception("pg down")),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.build_degraded is True
        assert (view.toolbox.degraded, view.progress.degraded, view.traceability.degraded) == (True, True, True)

    async def test_empty_plan_idempotent_read(self) -> None:
        """空 plan 幂等读：6 键恒在+toolbox 完整+两段空态+build_degraded False+不抛."""
        plan_id = str(uuid_module.uuid4())
        skills = tuple(_make_tool_metadata(slug=f"tool-{index}") for index in range(3))
        service = _make_service(
            skill_selector=_make_skill_selector(skills=skills),
            snapshot_repo=_make_snapshot_repo(load_return=None),
            tree_service=_make_tree_service(tree=_make_tree(plan_id)),
        )
        view = await service.build_analyst_view(plan_id=plan_id)
        assert view.build_degraded is False
        assert view.toolbox.total_tools == 3  # 静态真源与 plan 正交
        assert view.progress.available is False
        assert view.progress.phase is None
        assert all(stage.status is PhaseStatus.NOT_STARTED for stage in view.progress.stages)
        assert view.traceability.available is False
        assert view.traceability.stage_count == 0


class TestStateDataMalformedGuards:
    """state_data 畸形守卫（逐键处置复刻 6-8 executive_view_service :169-188——R1-F6/R2 补遗）.

    「宽容-严格」三分界钦定：缺键且有单源常量→默认/值现且可强转→采用/值现且不可用→降级。
    """

    @staticmethod
    def _service_with_state(state_data: dict[str, Any]) -> AnalystViewService:
        snapshot = CheckpointSnapshot(session_id="blm-planning-x", state_data=state_data)
        return _make_service(
            skill_selector=_make_skill_selector(),
            snapshot_repo=_make_snapshot_repo(load_return=snapshot),
            tree_service=_make_tree_service(),
        )

    async def test_missing_completed_steps_degrades(self) -> None:
        """completed_steps 必备缺 → 段降级（available=False+六阶段框架恒在）."""
        service = self._service_with_state({"plan_id": "x", "total_steps": 8})
        view = await service.build_analyst_view(plan_id=str(uuid_module.uuid4()))
        assert view.progress.degraded is True
        assert view.progress.available is False
        assert len(view.progress.stages) == 6
        assert all(stage.status is PhaseStatus.NOT_STARTED for stage in view.progress.stages)

    async def test_missing_total_steps_defaults_to_eight(self) -> None:
        """total_steps 缺 → .get 默认 BLM_TOTAL_STEPS=8（宽容采用——单源常量默认）."""
        service = self._service_with_state({"plan_id": "x", "completed_steps": 4})
        view = await service.build_analyst_view(plan_id=str(uuid_module.uuid4()))
        assert view.progress.degraded is False
        assert view.progress.total_steps == 8
        assert view.progress.progress_percent == 50

    async def test_zero_total_steps_degrades(self) -> None:
        """total_steps ≤0 → 显式段降级（除零形态守卫——progress_percent 归 0，R1-F6）."""
        service = self._service_with_state({"plan_id": "x", "completed_steps": 2, "total_steps": 0})
        view = await service.build_analyst_view(plan_id=str(uuid_module.uuid4()))
        assert view.progress.degraded is True
        assert view.progress.progress_percent == 0

    async def test_missing_timeline_and_degraded_steps_default_empty(self) -> None:
        """timeline/degraded_steps 缺 → 空列表默认（宽容——六阶段全 not_started+degraded_step_count 0）."""
        service = self._service_with_state({"plan_id": "x", "completed_steps": 1, "total_steps": 8})
        view = await service.build_analyst_view(plan_id=str(uuid_module.uuid4()))
        assert view.progress.degraded is False
        assert view.progress.degraded_step_count == 0
        assert view.progress.stages[0].status is PhaseStatus.NOT_STARTED  # timeline 空 → 阶段1 无条目

    async def test_missing_phase_and_current_step_default_none(self) -> None:
        """phase/current_step 缺 → None（空态同形——6-8 :188 先例直系；不触发段降级）."""
        service = self._service_with_state({"plan_id": "x", "completed_steps": 1, "total_steps": 8})
        view = await service.build_analyst_view(plan_id=str(uuid_module.uuid4()))
        assert view.progress.degraded is False
        assert view.progress.phase is None
        assert view.progress.current_step is None
        assert view.progress.available is True

    async def test_non_int_completed_steps_string_coerced(self) -> None:
        """completed_steps 字符串数字 → int() 宽容采用（6-8 R3-F1 行为锁定同款）."""
        service = self._service_with_state({"plan_id": "x", "completed_steps": "3", "total_steps": 8})
        view = await service.build_analyst_view(plan_id=str(uuid_module.uuid4()))
        assert view.progress.degraded is False
        assert view.progress.completed_steps == 3

    async def test_non_numeric_completed_steps_degrades(self) -> None:
        """completed_steps 非数字字符串 → 段降级不抛（值现且不可强转→降级）."""
        service = self._service_with_state({"plan_id": "x", "completed_steps": "three", "total_steps": 8})
        view = await service.build_analyst_view(plan_id=str(uuid_module.uuid4()))
        assert view.progress.degraded is True
        assert view.progress.available is False

    async def test_non_dict_state_data_degrades(self) -> None:
        """state_data 非 dict → 段降级（isinstance 守卫→{}→缺必备键降级链路）.

        脏形态注入经 object.__setattr__（frozen 逃逸口——存储层反序列化损坏形态模拟，
        零类型抑制注释）。
        """
        snapshot = CheckpointSnapshot(session_id="blm-planning-x")
        object.__setattr__(snapshot, "state_data", "corrupted")
        service = _make_service(
            skill_selector=_make_skill_selector(),
            snapshot_repo=_make_snapshot_repo(load_return=snapshot),
            tree_service=_make_tree_service(),
        )
        view = await service.build_analyst_view(plan_id=str(uuid_module.uuid4()))
        assert view.progress.degraded is True


class TestServiceStatelessness:
    """服务无状态约束（SINGLETON 并发共享——AC-7；禁持每次调用的可变实例态）."""

    async def test_no_mutable_instance_state(self) -> None:
        """服务实例无跨调用可变态（除三依赖句柄外零实例属性增长）."""
        service = _make_service()
        before_attributes = set(vars(service).keys())
        await service.build_analyst_view(plan_id=str(uuid_module.uuid4()))
        await service.build_analyst_view(plan_id=str(uuid_module.uuid4()))
        assert set(vars(service).keys()) == before_attributes


class TestToolboxSectionReexport:
    """ToolboxSection 等类型从 ports 文件单源 re-export 验证（禁服务本地定义 VO）."""

    def test_service_module_no_local_vo_definitions(self) -> None:
        """服务模块零本地 VO/枚举定义（AST 层面归架构验证器承载——本测试锚行为面）."""
        import inspect

        from src.application.services import analyst_view_service

        source = inspect.getsource(analyst_view_service)
        assert "class ToolboxSection" not in source
        assert "class PhaseStatus" not in source
        assert ToolboxSection.__module__ == "src.application.ports.analyst_view"
