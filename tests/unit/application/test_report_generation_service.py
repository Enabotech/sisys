"""ReportGenerationService 单元测试（Story 6-5a Task 2——双源聚合+降级+渲染编排+事件）。

Mock 形态：AsyncMock(spec=Port) 五依赖 + _make_trace_view 参数化工厂三态分派
（正常 dict / 降级信封两键 dict / 缺行 None——6-4 _make_material 形态移植）。

覆盖面：
- 循环 A：聚合分派（八 stage → 章节）/ payload JSON 解析三态 / 降级三态判定
  （信封态 reason 传导+兜底/锚叠加不计/缺行骨架）/ 490 全缺 / 快照附录 A
- 循环 B：L0/L2 持久化编排 / ReportGenerated 三键组装值级 / 发布失败两形态
  宽容 / 491 二元 layer 包装

Run with:
    poetry run pytest tests/unit/application/test_report_generation_service.py -v
"""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.ports.chain_of_thought_archive import ChainOfThoughtArchiveServicePort, ChainOfThoughtTraceView
from src.application.ports.report_generation import REPORT_FILE_MEMORY_TYPE
from src.application.services.report_generation_service import ReportGenerationService, _step_field_blocks
from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.entities.strategic_report import ReportType
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.exceptions import ReportGenerationError, ReportStorageError
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l0_storage import L0StoragePort
from src.domain.ports.report_repository import ReportRepositoryProtocol
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.value_objects.chain_of_thought import ChainOfThought


def _make_chain_vo(payload: dict | None) -> ChainOfThought:
    """构造 chain VO（final_answer = json.dumps(payload)——payload 三态载体）。

    Args:
        payload: 结构化产物 dict（信封态传 `_make_envelope_payload` 的两键 dict）。

    Returns:
        ChainOfThought VO 实例。
    """
    return ChainOfThought(
        input_summary="测试输入摘要",
        reflection="测试反思",
        tools_used=("工具一",),
        constraints_check="通过",
        final_answer=json.dumps(payload, ensure_ascii=False),
    )


def _make_gap_payload(degraded: bool = False) -> dict:
    """构造 gap 型 payload（asdict 六键——PerformanceGapArtifacts 同构）。

    Args:
        degraded: 降级锚。

    Returns:
        六键 payload dict。
    """
    return {
        "financial_gap": "财务差距结论（达成率 85%）",
        "operational_gap": "运营差距结论（交付周期延长 20%）",
        "root_causes": ["根因一：组织能力缺口", "根因二：流程效率不足"],
        "portfolio_health": "业务组合健康度：核心业务处于守住区间",
        "degraded": degraded,
        "degrade_reason": "检索降级（工具不可用）" if degraded else "",
    }


def _make_insight_payload(step: str) -> dict:
    """构造六子步骤正常 payload（summary/findings + 领域字段——按步分派要点）。

    Args:
        step: 步骤键（trend/market_customer/competition/self/opportunity/opportunity_gap）。

    Returns:
        该步类型化 Schema 的 model_dump 同构 dict。
    """
    base = {"summary": f"{step} 步骤摘要", "findings": [f"{step} 发现一", f"{step} 发现二"]}
    if step == "trend":
        return {
            **base,
            "pestel_political": "政策稳定",
            "pestel_economic": "温和增长",
            "pestel_social": "人口结构变化",
            "pestel_technological": "AI 成熟度爬升",
            "pestel_environmental": "双碳约束",
            "pestel_legal": "数据合规强化",
            "technology_roadmap": ["试点验证", "规模推广", "生态整合"],
            "scenario_plans": ["基准情景", "乐观情景"],
        }
    if step == "market_customer":
        return {
            **base,
            "customer_segments": ["大企业客户", "中小企业客户"],
            "demand_priority_matrix": ["价格敏感度高", "交付周期优先"],
            "value_proposition_map": ["痛点：决策效率低", "收益：规划周期缩短"],
        }
    if step == "competition":
        return {
            **base,
            "five_forces_supplier_power": "中等",
            "five_forces_buyer_power": "较强",
            "five_forces_new_entrants": "中等",
            "five_forces_substitutes": "较低",
            "five_forces_rivalry": "高",
            "competitor_radar": ["研发能力强", "渠道覆盖广", "品牌力弱"],
            "strategy_recommendations": ["强化差异化", "锁定核心客户"],
        }
    if step == "self":
        return {
            **base,
            "internal_capabilities": ["数据分析能力", "行业知识沉淀"],
            "vrio_assessment": ["有价值", "稀缺"],
            "resource_constraints": ["人才缺口", "预算约束"],
        }
    if step == "opportunity":
        return {
            **base,
            "opportunity_list": ["相邻市场渗透", "产品线延伸"],
            "priority_ranking": ["优先级一：相邻市场", "优先级二：产品延伸"],
            "growth_path": ["市场渗透路径", "市场开发路径"],
        }
    return {
        **base,
        "gap_quantification": ["收入差距 20%", "利润差距 15%"],
        "capability_match_matrix": ["研发匹配度高", "渠道匹配度低"],
        "closure_strategies": ["能力补强", "生态合作"],
    }


def _make_envelope_payload(reason: str | None = None) -> dict:
    """构造降级信封态 payload（键集 ⊆ {degraded, degrade_reason}——三态判定②）。

    Args:
        reason: 降级原因（None 时构造仅 degraded 键的最小信封）。

    Returns:
        信封态 payload dict。
    """
    if reason is None:
        return {"degraded": True}
    return {"degraded": True, "degrade_reason": reason}


def _make_synthesis_payload() -> dict:
    """构造 synthesis 型 payload（asdict 两键——conclusions + degraded_inputs）。

    Returns:
        两键 payload dict。
    """
    return {
        "conclusions": ["综合结论一：聚焦核心市场", "综合结论二：补强数据能力"],
        "degraded_inputs": ["market_insight_trend"],
    }


def _make_trace_view(
    stages_payload: dict[str, dict | None],
    *,
    degraded_stages: frozenset[str] = frozenset(),
) -> ChainOfThoughtTraceView:
    """构造聚合主源 TraceView（三态分派工厂——6-4 _make_material 形态移植）。

    CR2-F6：直接构造真实 ChainOfThoughtTraceView（四参 frozen dataclass，
    与原手搓替身属性逐一同名——替换零行为差；DTO 契约漂移从此单测即红，
    6-1/6-3/6-4「属性形态断裂族」在替身层堵口）。

    Args:
        stages_payload: stage → payload 三态映射（dict=正常/None=缺行）。
        degraded_stages: 行级 degraded 锚为 True 的 stage 集（锚叠加态）。

    Returns:
        真实 ChainOfThoughtTraceView DTO 实例。
    """
    records = []
    for stage, payload in stages_payload.items():
        if payload is None:
            continue
        records.append(
            {
                "stage": stage,
                "chain": _make_chain_vo(payload),
                "archive_id": f"archive-{stage}",
                "degraded": stage in degraded_stages,
                "blob_content": None,
            }
        )
    return ChainOfThoughtTraceView(
        plan_id="trace-plan",
        records=records,
        total=len(records),
        archived_count=len(records),
    )


def _make_snapshot(timeline: list[dict] | None) -> CheckpointSnapshot:
    """构造 latest 快照替身（timeline 条目六键——附录 A 数据源）。

    Args:
        timeline: 时间线条目列表（None 表示无 timeline 键）。

    Returns:
        CheckpointSnapshot 实例。
    """
    state_data: dict = {"plan_id": "plan-1", "phase": "market_insight"}
    if timeline is not None:
        state_data["timeline"] = timeline
    return CheckpointSnapshot(
        session_id="blm-planning-plan-1",
        stage_id="blm_planning",
        state_data=state_data,
        timestamp=datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc),
    )


def _make_timeline_entry(step: str, status: str = "completed", degraded: bool = False) -> dict:
    """构造 timeline 条目（六键——step/started_at/completed_at/status/summary_excerpt/degraded）。

    Args:
        step: 步骤值（三种形态：六子裸值/performance_gap/market_insight_synthesis
            ——写侧 record_step 实证值，CR1-F1）。
        status: 状态。
        degraded: 降级锚。

    Returns:
        条目 dict。
    """
    return {
        "step": step,
        "started_at": "2026-11-03T12:00:00+00:00",
        "completed_at": "2026-11-03T12:00:05+00:00",
        "status": status,
        "summary_excerpt": "步骤摘要",
        "degraded": degraded,
    }


def _full_stages_payload(
    *,
    gap_degraded: bool = False,
    step_override: dict[str, dict | None] | None = None,
) -> dict[str, dict | None]:
    """构造八 stage 全量 payload 映射（正常基线——step_override 覆盖指定步）。

    Args:
        gap_degraded: gap 步降级锚叠加形态。
        step_override: 覆盖映射（None 值=构造缺行；信封态直接传 `_make_envelope_payload` dict）。

    Returns:
        stage → payload 映射。
    """
    stages: dict[str, dict | None] = {
        "performance_gap": _make_gap_payload(degraded=gap_degraded),
        "market_insight_trend": _make_insight_payload("trend"),
        "market_insight_market_customer": _make_insight_payload("market_customer"),
        "market_insight_competition": _make_insight_payload("competition"),
        "market_insight_self": _make_insight_payload("self"),
        "market_insight_opportunity": _make_insight_payload("opportunity"),
        "market_insight_opportunity_gap": _make_insight_payload("opportunity_gap"),
        "market_insight_synthesis": _make_synthesis_payload(),
    }
    if step_override:
        stages.update(step_override)
    return stages


def _make_service(
    *,
    trace_view: object,
    snapshot: CheckpointSnapshot | None = None,
    l0_write_returns: bool = True,
    l0_side_effect: object | None = None,
    save_side_effect: object | None = None,
    publish_side_effect: object | None = None,
) -> tuple[ReportGenerationService, dict[str, AsyncMock]]:
    """构造被测服务（五依赖 AsyncMock——返回 mock 字典供断言）。

    Args:
        trace_view: chain 聚合主源替身。
        snapshot: latest 快照（None=缺失）。
        l0_write_returns: L0 write 返回值（False=端口契约面失败形态）。
        l0_side_effect: L0 write 异常注入（OSError 形态）。
        save_side_effect: L2 save 注入。
        publish_side_effect: 事件发布注入（失败 PublishResult/raise）。

    Returns:
        (服务实例, mock 依赖字典)。
    """
    chain = AsyncMock(spec=ChainOfThoughtArchiveServicePort)
    chain.query_chain_trace.return_value = trace_view
    snapshot_repo = AsyncMock(spec=SnapshotRepositoryProtocol)
    snapshot_repo.load.return_value = snapshot
    l0 = AsyncMock(spec=L0StoragePort)
    if l0_side_effect is not None:
        l0.write.side_effect = l0_side_effect
    else:
        l0.write.return_value = l0_write_returns
    report_repo = AsyncMock(spec=ReportRepositoryProtocol)
    if save_side_effect is not None:
        report_repo.save.side_effect = save_side_effect
    else:
        report_repo.save.side_effect = None
        report_repo.save.return_value = None
    publisher = AsyncMock(spec=EventPublisher)
    if publish_side_effect is not None:
        publisher.publish.side_effect = publish_side_effect
    else:
        publisher.publish.return_value = PublishResult(
            event_id=str(uuid.uuid4()), results=(ChannelResult("reliable", True, None),)
        )
    service = ReportGenerationService(
        chain_archive_service=chain,
        snapshot_repository=snapshot_repo,
        l0_storage=l0,
        report_repository=report_repo,
        event_publisher=publisher,
    )
    return service, {
        "chain": chain,
        "snapshot_repo": snapshot_repo,
        "l0": l0,
        "report_repo": report_repo,
        "publisher": publisher,
    }


def _failed_publish_result() -> PublishResult:
    """构造失败 PublishResult（event_id 必填首参——publish_result.py:30 形态）。"""
    return PublishResult(
        event_id=str(uuid.uuid4()),
        results=(ChannelResult("reliable", False, "outbox 写失败"),),
    )


PLAN_ID = uuid.uuid4()


class TestDualSourceAggregation:
    """循环 A：双源聚合与章节组装。"""

    @pytest.mark.asyncio
    async def test_full_data_generates_report_with_eleven_sections(self) -> None:
        """八步全在位 → 报告成功 + section_count=11 + degraded=0。"""
        service, mocks = _make_service(trace_view=_make_trace_view(_full_stages_payload()))
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.section_count == 11
        assert report.degraded_section_count == 0
        assert report.report_type is ReportType.MARKDOWN
        mocks["chain"].query_chain_trace.assert_awaited_once_with(PLAN_ID)

    @pytest.mark.asyncio
    async def test_report_markdown_contains_all_frozen_section_titles(self) -> None:
        """渲染文本含全部冻结章节标题（H1/第 1 章/四小节/第 2 章/六子/2.7/附录 B）。"""
        service, mocks = _make_service(trace_view=_make_trace_view(_full_stages_payload()))
        await service.generate_markdown_report(PLAN_ID)
        memory_id = mocks["l0"].write.call_args.args[0]
        text = mocks["l0"].write.call_args.args[2]
        assert memory_id.startswith(str(PLAN_ID))
        for title in (
            "# 战略规划报告（BLM 前两阶段）",
            "## 1 业绩差距分析",
            "### 1.1 财务差距",
            "### 1.2 运营差距",
            "### 1.3 根因分析",
            "### 1.4 业务组合健康度",
            "## 2 市场洞察",
            "### 2.1 看趋势",
            "### 2.2 看市场与客户",
            "### 2.3 看竞争",
            "### 2.4 看自己",
            "### 2.5 看机会",
            "### 2.6 机会差距分析",
            "### 2.7 市场洞察综合",
            "## 附录 B 降级与数据缺失记录",
        ):
            assert title in text, f"冻结章节标题缺失: {title}"

    @pytest.mark.asyncio
    async def test_gap_fields_rendered_in_subsections(self) -> None:
        """gap 四字段渲染（root_causes 逐项列表——列表项数一致）。"""
        service, mocks = _make_service(trace_view=_make_trace_view(_full_stages_payload()))
        await service.generate_markdown_report(PLAN_ID)
        text = mocks["l0"].write.call_args.args[2]
        assert "财务差距结论（达成率 85%）" in text
        assert "- 根因一：组织能力缺口" in text
        assert "- 根因二：流程效率不足" in text

    @pytest.mark.asyncio
    async def test_six_schema_fields_rendered(self) -> None:
        """六 Schema 领域字段全量渲染（CR1-F3：每字段至少一条值级断言——删任一映射即红）。"""
        service, mocks = _make_service(trace_view=_make_trace_view(_full_stages_payload()))
        await service.generate_markdown_report(PLAN_ID)
        text = mocks["l0"].write.call_args.args[2]
        # trend：PESTEL 全六维（表格数据行）+ 技术路线图 + 情景计划
        assert "| 政治 | 政策稳定 |" in text
        assert "| 经济 | 温和增长 |" in text
        assert "| 社会 | 人口结构变化 |" in text
        assert "| 技术 | AI 成熟度爬升 |" in text
        assert "| 环境 | 双碳约束 |" in text
        assert "| 法律 | 数据合规强化 |" in text
        assert "- 试点验证" in text  # technology_roadmap
        assert "- 基准情景" in text  # scenario_plans
        assert "trend 步骤摘要" in text  # summary 公共前缀（正向渲染）
        assert "- trend 发现一" in text  # findings 公共前缀
        # market_customer：三组列表 + 加粗行标签
        assert "- 大企业客户" in text  # customer_segments
        assert "- 价格敏感度高" in text  # demand_priority_matrix
        assert "- 痛点：决策效率低" in text  # value_proposition_map
        assert "**客户细分画像**" in text
        assert "**需求优先级矩阵（$APPEALS）**" in text
        assert "**价值主张地图**" in text
        # competition：五力全五行 + 雷达表数据行 + 策略建议
        assert "| 供应商议价能力 | 中等 |" in text
        assert "| 购买者议价能力 | 较强 |" in text
        assert "| 新进入者威胁 | 中等 |" in text
        assert "| 替代品威胁 | 较低 |" in text
        assert "| 现有竞争者强度 | 高 |" in text
        assert "| 维度 1 | 研发能力强 |" in text  # competitor_radar 表格承载（OD-9）
        assert "- 强化差异化" in text  # strategy_recommendations
        # self：三组列表
        assert "- 数据分析能力" in text  # internal_capabilities
        assert "- 有价值" in text  # vrio_assessment
        assert "- 人才缺口" in text  # resource_constraints
        # opportunity：三组列表
        assert "- 相邻市场渗透" in text  # opportunity_list
        assert "- 优先级一：相邻市场" in text  # priority_ranking
        assert "- 市场渗透路径" in text  # growth_path
        # opportunity_gap：三组列表
        assert "- 收入差距 20%" in text  # gap_quantification
        assert "- 研发匹配度高" in text  # capability_match_matrix
        assert "- 能力补强" in text  # closure_strategies

    def test_step_field_blocks_kind_sequences_frozen(self) -> None:
        """六子步骤块型序列冻结（CR1-F3：期望字面钉死——删任一映射块即红）。

        期望序列与「要素渲染映射冻结表」逐字对齐，不从实现侧派生（防同源恒真）。
        """
        # trend：PESTEL 表 + 技术路线图列表 + 情景计划列表
        trend_kinds = tuple(block.kind for block in _step_field_blocks("trend", _make_insight_payload("trend")))
        assert trend_kinds == ("table", "bullet_list", "bullet_list")
        # competition：五力表 + 雷达表（OD-9）+ 策略建议列表
        competition_kinds = tuple(
            block.kind for block in _step_field_blocks("competition", _make_insight_payload("competition"))
        )
        assert competition_kinds == ("table", "table", "bullet_list")
        # 其余四步：三组「加粗行标签段落 + 列表」交替（paragraph/bullet ×3）
        for step in ("market_customer", "self", "opportunity", "opportunity_gap"):
            kinds = tuple(block.kind for block in _step_field_blocks(step, _make_insight_payload(step)))
            assert kinds == ("paragraph", "bullet_list") * 3, step

    @pytest.mark.asyncio
    async def test_synthesis_conclusions_and_degraded_inputs(self) -> None:
        """synthesis 双列表渲染（conclusions 列表 + degraded_inputs 显式列举）。"""
        service, mocks = _make_service(trace_view=_make_trace_view(_full_stages_payload()))
        await service.generate_markdown_report(PLAN_ID)
        text = mocks["l0"].write.call_args.args[2]
        assert "- 综合结论一：聚焦核心市场" in text
        assert "market_insight_trend" in text  # degraded_inputs 显式列举


class TestDegradationThreeStates:
    """循环 A：降级三态判定（payload 形态优先于 degraded 锚——AC-4 冻结版）。"""

    @pytest.mark.asyncio
    async def test_missing_insight_step_counts_one_and_renders_skeleton(self) -> None:
        """六子缺一步 → degraded==1 + H3 骨架 + [数据缺失] callout 唯一块。"""
        stages = _full_stages_payload(step_override={"market_insight_trend": None})
        service, mocks = _make_service(trace_view=_make_trace_view(stages))
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 1
        assert report.section_count == 11  # 恒 11 与数据缺否无关（R3-1）
        text = mocks["l0"].write.call_args.args[2]
        assert "### 2.1 看趋势" in text
        assert "> ⚠️ [数据缺失] 看趋势：该步骤归档记录不可用" in text
        # CR2-F11：degraded_stages 收缺行 stage（与 degraded_section_count 同口径）
        saved_metadata = mocks["report_repo"].save.call_args.kwargs.get("metadata") or {}
        assert saved_metadata.get("degraded_stages") == ["market_insight_trend"]

    @pytest.mark.asyncio
    async def test_missing_gap_renders_four_subsection_skeletons(self) -> None:
        """gap 缺行 → 四小节全骨架 + degraded==4（单测层参数化变体）。"""
        stages = _full_stages_payload(step_override={"performance_gap": None})
        service, mocks = _make_service(trace_view=_make_trace_view(stages))
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 4
        text = mocks["l0"].write.call_args.args[2]
        for sub in ("### 1.1 财务差距", "### 1.2 运营差距", "### 1.3 根因分析", "### 1.4 业务组合健康度"):
            assert sub in text
        assert text.count("> ⚠️ [数据缺失]") == 4

    @pytest.mark.asyncio
    async def test_missing_synthesis_counts_one(self) -> None:
        """synthesis 缺行 → degraded==1（单测层参数化变体）。"""
        stages = _full_stages_payload(step_override={"market_insight_synthesis": None})
        service, _ = _make_service(trace_view=_make_trace_view(stages))
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 1

    @pytest.mark.asyncio
    async def test_envelope_payload_renders_degraded_callout_with_reason(self) -> None:
        """信封态 → [降级] callout 带 reason 传导 + degraded==1 + 跳过字段渲染。"""
        stages = _full_stages_payload(step_override={"market_insight_trend": _make_envelope_payload("LLM 调用失败（注入）")})
        service, mocks = _make_service(trace_view=_make_trace_view(stages))
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 1
        text = mocks["l0"].write.call_args.args[2]
        assert "> ⚠️ [降级] 看趋势：LLM 调用失败（注入）" in text
        # 信封态跳过字段渲染（summary/findings 等不出现——trend 正常产物的摘要不渲染）
        assert "trend 步骤摘要" not in text

    @pytest.mark.asyncio
    async def test_envelope_without_reason_uses_fallback_text(self) -> None:
        """信封无 reason 键 → 固定兜底文案（禁解析 reflection 文本）。"""
        stages = _full_stages_payload(step_override={"market_insight_competition": _make_envelope_payload(None)})
        service, mocks = _make_service(trace_view=_make_trace_view(stages))
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 1
        text = mocks["l0"].write.call_args.args[2]
        assert "> ⚠️ [降级] 看竞争：降级（原因未随归档行结构化持久化）" in text

    @pytest.mark.asyncio
    async def test_degraded_anchor_overlay_not_counted(self) -> None:
        """锚叠加态（payload 完整+锚 True）→ callout 叠加 + degraded==0 + 附录 B [降级] 行。"""
        stages = _full_stages_payload()
        service, mocks = _make_service(trace_view=_make_trace_view(stages, degraded_stages=frozenset({"market_insight_self"})))
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 0  # 内容完整非缺失——锚叠加不计
        text = mocks["l0"].write.call_args.args[2]
        assert "> ⚠️ [降级] 看自己：" in text
        assert "| [降级] | 看自己 |" in text  # 附录 B 两类全收
        # CR2-F11 负向断言：锚叠加 stage 不进 degraded_stages（禁从 appendix_b 派生的守护锚
        # ——附录 B 该场景有 [降级] 行而清单必须为空，两口径分叉即红）
        saved_metadata = mocks["report_repo"].save.call_args.kwargs.get("metadata") or {}
        assert saved_metadata.get("degraded_stages") == []

    @pytest.mark.asyncio
    async def test_gap_degraded_anchor_uses_payload_reason(self) -> None:
        """gap 降级（asdict 含 reason）→ callout 取 payload.degrade_reason（解析次序①）。"""
        stages = _full_stages_payload(gap_degraded=True)
        service, mocks = _make_service(trace_view=_make_trace_view(stages, degraded_stages=frozenset({"performance_gap"})))
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 0
        text = mocks["l0"].write.call_args.args[2]
        assert "> ⚠️ [降级] 业绩差距分析：检索降级（工具不可用）" in text

    @pytest.mark.asyncio
    async def test_appendix_b_records_missing_rows(self) -> None:
        """附录 B 记录 [数据缺失] 行（类型/步骤/原因三列）。"""
        stages = _full_stages_payload(step_override={"market_insight_trend": None})
        service, mocks = _make_service(trace_view=_make_trace_view(stages))
        await service.generate_markdown_report(PLAN_ID)
        text = mocks["l0"].write.call_args.args[2]
        assert "| 类型 | 步骤 | 原因 |" in text
        assert "| [数据缺失] | 看趋势 | 该步骤归档记录不可用 |" in text

    @pytest.mark.asyncio
    async def test_broken_payload_json_treated_as_missing(self) -> None:
        """payload 解析失败（final_answer 非 JSON）→ [数据缺失]（三态判定①）。"""
        view = _make_trace_view(_full_stages_payload())
        broken = ChainOfThought(
            input_summary="i",
            reflection="r",
            tools_used=(),
            constraints_check="c",
            final_answer="{broken json",
        )
        view.records[0]["chain"] = broken
        service, mocks = _make_service(trace_view=view)
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 4  # performance_gap 行不可解析 → 四小节缺失
        # CR2-F11：解析失败形态（行在位）也进 degraded_stages——missing_stages 为空可对照
        saved_metadata = mocks["report_repo"].save.call_args.kwargs.get("metadata") or {}
        assert saved_metadata.get("degraded_stages") == ["performance_gap"]
        assert saved_metadata.get("missing_stages") == []  # 行在位（两清单语义区分锚）

    @pytest.mark.asyncio
    async def test_list_payload_treated_as_missing(self) -> None:
        """payload 为合法 JSON 数组（非 dict 形态）→ [数据缺失]（CR1-F12①分支覆盖）。"""
        view = _make_trace_view(_full_stages_payload())
        array_chain = ChainOfThought(
            input_summary="i",
            reflection="r",
            tools_used=(),
            constraints_check="c",
            final_answer='["要点一", "要点二"]',
        )
        view.records[1]["chain"] = array_chain  # market_insight_trend
        service, mocks = _make_service(trace_view=view)
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 1
        text = mocks["l0"].write.call_args.args[2]
        assert "> ⚠️ [数据缺失] 看趋势：该步骤归档记录不可用" in text

    @pytest.mark.asyncio
    async def test_non_str_final_answer_treated_as_missing(self) -> None:
        """final_answer 非 str（json.loads 抛 TypeError 路径）→ [数据缺失]（CR1-F12②分支覆盖）。

        真实 ChainOfThought VO 强校验 final_answer 为非空 str，该路径经真实 VO
        不可达——SimpleNamespace 替身直击异常分支（_classify_payload 容错面）。
        """
        view = _make_trace_view(_full_stages_payload())
        view.records[1]["chain"] = SimpleNamespace(final_answer=None)  # market_insight_trend
        service, mocks = _make_service(trace_view=view)
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 1
        text = mocks["l0"].write.call_args.args[2]
        assert "> ⚠️ [数据缺失] 看趋势：该步骤归档记录不可用" in text

    @pytest.mark.asyncio
    async def test_empty_dict_payload_treated_as_missing_not_envelope(self) -> None:
        """空 dict payload（final_answer='{}'）→ [数据缺失] 而非 [降级] 信封（CR1-F14 钉死）。

        键集 ⊆ 判定对 {} 恒真——空 payload 无任何降级信号，语义是内容缺失；
        附录 B 类型列应为 [数据缺失] 非 [降级]。
        """
        view = _make_trace_view(_full_stages_payload())
        empty_chain = ChainOfThought(
            input_summary="i",
            reflection="r",
            tools_used=(),
            constraints_check="c",
            final_answer="{}",
        )
        view.records[1]["chain"] = empty_chain  # market_insight_trend
        service, mocks = _make_service(trace_view=view)
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.degraded_section_count == 1
        text = mocks["l0"].write.call_args.args[2]
        assert "> ⚠️ [数据缺失] 看趋势：该步骤归档记录不可用" in text
        assert "| [数据缺失] | 看趋势 |" in text
        assert "| [降级] | 看趋势 |" not in text


class TestTotalMissingRaises490:
    """循环 A：数据源全缺。"""

    @pytest.mark.asyncio
    async def test_zero_total_raises_report_generation_error(self) -> None:
        """total==0 → 490（code/message/context 断言——可观测事实口径）。"""
        service, _ = _make_service(trace_view=_make_trace_view({}))
        with pytest.raises(ReportGenerationError) as exc_info:
            await service.generate_markdown_report(PLAN_ID)
        assert exc_info.value.code == "EXCEPTION_490"
        assert exc_info.value.message == "该 plan_id 无思维链归档记录，无法生成报告"
        assert exc_info.value.context["plan_id"] == str(PLAN_ID)

    @pytest.mark.asyncio
    async def test_snapshot_present_does_not_rescue_490(self) -> None:
        """最新快照在位亦同判（时间线摘要非报告素材）。"""
        service, _ = _make_service(
            trace_view=_make_trace_view({}),
            snapshot=_make_snapshot([_make_timeline_entry("performance_gap")]),
        )
        with pytest.raises(ReportGenerationError):
            await service.generate_markdown_report(PLAN_ID)


class TestSnapshotTimelineAppendixA:
    """循环 A：latest 快照辅源（timeline → 附录 A）。"""

    @pytest.mark.asyncio
    async def test_timeline_renders_appendix_a_table(self) -> None:
        """快照在位 → 附录 A 五列表（display_name 三源映射）。"""
        timeline = [
            _make_timeline_entry("performance_gap"),
            _make_timeline_entry("trend"),
            _make_timeline_entry("market_insight_synthesis", degraded=True),
        ]
        service, mocks = _make_service(
            trace_view=_make_trace_view(_full_stages_payload()),
            snapshot=_make_snapshot(timeline),
        )
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.section_count == 11  # 附录不计入
        text = mocks["l0"].write.call_args.args[2]
        assert "## 附录 A 执行时间线" in text
        assert "| 步骤 | 开始 | 完成 | 状态 | 降级 |" in text
        assert "| 业绩差距分析 |" in text  # performance_gap → PERFORMANCE_GAP_CONFIG.display_name
        assert "| 看趋势 |" in text  # 六子裸值 → MARKET_INSIGHT_STEP_CONFIG
        assert "| 市场洞察综合 |" in text  # market_insight_synthesis → SYNTHESIS_DISPLAY_NAME（第三源——CR1-F1 实证值）

    @pytest.mark.asyncio
    async def test_snapshot_read_failure_degrades_to_omitted_appendix_a(self) -> None:
        """快照读异常（辅源容错面）→ 报告成功 + 附录 A 省略 + timeline_available=false（CR1-F13）。

        端口契约「缺失/TTL 过期/读失败同形态容错」的第三形态——删掉 try/except
        后 Redis 抖动直接炸报告生成（辅源阻断主链违反 AC-4「不阻断」）。
        """
        service, mocks = _make_service(trace_view=_make_trace_view(_full_stages_payload()))
        mocks["snapshot_repo"].load.side_effect = RuntimeError("Redis 连接抖动（注入）")
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.section_count == 11  # 报告照常生成
        text = mocks["l0"].write.call_args.args[2]
        assert "## 附录 A 执行时间线" not in text
        saved_metadata = mocks["report_repo"].save.call_args.kwargs.get("metadata") or {}
        assert saved_metadata.get("timeline_available") is False

    @pytest.mark.asyncio
    async def test_snapshot_malformed_state_data_degrades_to_omitted_appendix_a(self) -> None:
        """快照 state_data 非 dict 形态损坏 → 附录 A 省略 + 报告成功（CR2-F10 容器级守卫）。

        Redis 反序列化可返回任意 JSON 类型——形态损坏走 AttributeError 逃逸
        非 DomainError 即违「辅源不阻断」信封（SimpleNamespace 注入——真实
        实体 state_data 注解为 dict 不宜带脏形态构造）。
        """
        from typing import cast

        malformed = SimpleNamespace(state_data="形态损坏的字符串")  # truthy 非 dict
        service, mocks = _make_service(
            trace_view=_make_trace_view(_full_stages_payload()),
            snapshot=cast("CheckpointSnapshot", malformed),
        )
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.section_count == 11
        text = mocks["l0"].write.call_args.args[2]
        assert "## 附录 A 执行时间线" not in text

    @pytest.mark.asyncio
    async def test_snapshot_timeline_mixed_entries_skip_malformed(self) -> None:
        """timeline 混合 list（元素级损坏）→ 跳过畸形条目其余行照常（CR2-F10 元素级守卫）。

        `["ok"（非 dict）, 42（非 dict）, 合法条目]` 形态：容器守卫放行后
        若无元素级守卫，`entry.get` AttributeError 逃逸——混合形态即红。
        """
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        snapshot = CheckpointSnapshot(
            session_id="blm-planning-plan-1",
            stage_id="blm_planning",
            state_data={
                "plan_id": "plan-1",
                "timeline": ["畸形字符串条目", 42, _make_timeline_entry("performance_gap")],
            },
            timestamp=datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc),
        )
        service, mocks = _make_service(trace_view=_make_trace_view(_full_stages_payload()), snapshot=snapshot)
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.section_count == 11  # 报告照常生成
        text = mocks["l0"].write.call_args.args[2]
        assert "## 附录 A 执行时间线" in text  # 合法条目照常渲染
        assert "| 业绩差距分析 |" in text  # 合法行保留
        assert "畸形字符串条目" not in text.split("附录 A")[1]  # 畸形条目跳过

    @pytest.mark.asyncio
    async def test_timeline_unknown_step_shows_raw_value(self) -> None:
        """映射 miss（未知 step 值）直显裸值（防未来配置增步炸渲染）。"""
        timeline = [_make_timeline_entry("future_unknown_step")]
        service, mocks = _make_service(
            trace_view=_make_trace_view(_full_stages_payload()),
            snapshot=_make_snapshot(timeline),
        )
        await service.generate_markdown_report(PLAN_ID)
        text = mocks["l0"].write.call_args.args[2]
        assert "| future_unknown_step |" in text

    @pytest.mark.asyncio
    async def test_snapshot_missing_omits_appendix_a(self) -> None:
        """快照缺失 → 无附录 A + 报告成功（不阻断）+ metadata.timeline_available=False。"""
        service, mocks = _make_service(
            trace_view=_make_trace_view(_full_stages_payload()),
            snapshot=None,
        )
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.report_id  # 成功返回
        text = mocks["l0"].write.call_args.args[2]
        assert "## 附录 A 执行时间线" not in text

    @pytest.mark.asyncio
    async def test_snapshot_timeline_key_absent_omits_appendix_a(self) -> None:
        """快照在位但无 timeline 键 → 附录 A 省略（同缺失形态）。"""
        service, mocks = _make_service(
            trace_view=_make_trace_view(_full_stages_payload()),
            snapshot=_make_snapshot(None),
        )
        await service.generate_markdown_report(PLAN_ID)
        text = mocks["l0"].write.call_args.args[2]
        assert "## 附录 A 执行时间线" not in text


class TestPersistenceOrchestration:
    """循环 B：L0/L2 持久化编排与 491 包装。"""

    @pytest.mark.asyncio
    async def test_l0_write_memory_type_and_memory_id_anchor(self) -> None:
        """L0 write：memory_type="reports" 单源 + memory_id 锚 plan_id + file_path 派生。"""
        service, mocks = _make_service(trace_view=_make_trace_view(_full_stages_payload()))
        report = await service.generate_markdown_report(PLAN_ID)
        call = mocks["l0"].write.call_args
        assert call.args[1] == REPORT_FILE_MEMORY_TYPE
        assert call.args[0].startswith(f"{PLAN_ID}_")
        assert report.file_path == f"reports/{call.args[0]}.md"

    @pytest.mark.asyncio
    async def test_l0_write_returns_false_raises_491(self) -> None:
        """L0 write 返回 False（端口契约面）→ 491 layer="l0"。"""
        service, _ = _make_service(trace_view=_make_trace_view(_full_stages_payload()), l0_write_returns=False)
        with pytest.raises(ReportStorageError) as exc_info:
            await service.generate_markdown_report(PLAN_ID)
        assert exc_info.value.code == "EXCEPTION_491"
        assert exc_info.value.layer == "l0"

    @pytest.mark.asyncio
    async def test_l0_write_oserror_wrapped_491(self) -> None:
        """L0 write 抛 OSError（真实适配器主形态）→ 491 layer="l0" 包装。"""
        service, _ = _make_service(
            trace_view=_make_trace_view(_full_stages_payload()),
            l0_side_effect=OSError("磁盘写失败"),
        )
        with pytest.raises(ReportStorageError) as exc_info:
            await service.generate_markdown_report(PLAN_ID)
        assert exc_info.value.layer == "l0"
        assert exc_info.value.cause is not None

    @pytest.mark.asyncio
    async def test_l2_save_failure_wrapped_491(self) -> None:
        """L2 save 失败 → 491 layer="l2" 包装。"""
        service, _ = _make_service(
            trace_view=_make_trace_view(_full_stages_payload()),
            save_side_effect=RuntimeError("连接失败"),
        )
        with pytest.raises(ReportStorageError) as exc_info:
            await service.generate_markdown_report(PLAN_ID)
        assert exc_info.value.layer == "l2"

    @pytest.mark.asyncio
    async def test_l2_save_called_with_metadata(self) -> None:
        """L2 save 携带 metadata（timeline_available/缺失步清单——可观测面）。"""
        stages = _full_stages_payload(step_override={"market_insight_trend": None})
        service, mocks = _make_service(
            trace_view=_make_trace_view(stages),
            snapshot=_make_snapshot([_make_timeline_entry("performance_gap")]),
        )
        await service.generate_markdown_report(PLAN_ID)
        metadata = mocks["report_repo"].save.call_args.kwargs.get("metadata") or {}
        assert metadata.get("timeline_available") is True
        assert metadata.get("missing_stages") == ["market_insight_trend"]

    @pytest.mark.asyncio
    async def test_l2_save_metadata_timeline_unavailable(self) -> None:
        """快照缺失 → metadata.timeline_available=False（R3-3 载体——直查 PG JSONB 面）。"""
        service, mocks = _make_service(trace_view=_make_trace_view(_full_stages_payload()), snapshot=None)
        await service.generate_markdown_report(PLAN_ID)
        metadata = mocks["report_repo"].save.call_args.kwargs.get("metadata") or {}
        assert metadata.get("timeline_available") is False


class TestEventPublication:
    """循环 B：ReportGenerated 组装与发布宽容语义。"""

    @pytest.mark.asyncio
    async def test_event_assembled_with_three_keys(self) -> None:
        """事件组装值级断言（独立构造期望事件比对——report_id/report_type/file_path）。"""
        from src.domain.events.workflow_events import ReportGenerated

        service, mocks = _make_service(trace_view=_make_trace_view(_full_stages_payload()))
        report = await service.generate_markdown_report(PLAN_ID)
        event = mocks["publisher"].publish.call_args.args[0]
        expected = ReportGenerated(report_id=report.report_id, report_type="markdown", file_path=report.file_path)
        assert event.report_id == expected.report_id
        assert event.report_type == expected.report_type == "markdown"
        assert event.file_path == expected.file_path
        # 三键非空（构造点防线——事件类缺省空串漏传不炸）
        assert event.report_id is not None
        assert event.report_type
        assert event.file_path

    @pytest.mark.asyncio
    async def test_publish_failed_result_tolerated_with_warning(self, caplog) -> None:
        """发布失败形态①：失败 PublishResult → warning + 返回成功（双防线 is_success 先判）。"""
        import logging

        service, _ = _make_service(
            trace_view=_make_trace_view(_full_stages_payload()),
            publish_side_effect=_failed_publish_result(),
        )
        with caplog.at_level(logging.WARNING, logger="src.application.services.report_generation_service"):
            report = await service.generate_markdown_report(PLAN_ID)
        assert report.report_id  # 报告正常返回成功
        assert any("ReportGenerated" in record.message or "发布降级" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_publish_raise_tolerated_with_warning(self, caplog) -> None:
        """发布失败形态②：publish raise → warning + 返回成功（except 兜底防线）。"""
        import logging

        service, _ = _make_service(
            trace_view=_make_trace_view(_full_stages_payload()),
            publish_side_effect=RuntimeError("事件总线不可达"),
        )
        with caplog.at_level(logging.WARNING, logger="src.application.services.report_generation_service"):
            report = await service.generate_markdown_report(PLAN_ID)
        assert report.report_id
        assert any("ReportGenerated" in record.message or "发布降级" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_generation_ms_non_negative(self) -> None:
        """generation_ms ≥0（生成窗口毫秒——AC-7 口径）。"""
        service, _ = _make_service(trace_view=_make_trace_view(_full_stages_payload()))
        report = await service.generate_markdown_report(PLAN_ID)
        assert report.generation_ms >= 0
