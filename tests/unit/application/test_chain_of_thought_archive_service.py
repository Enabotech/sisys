"""Story 6-4 — ChainOfThoughtArchiveService 单元测试（组装+归档+追溯）。

TDD 循环 A（组装与归档）+ 循环 B（追溯查询）：

覆盖面（Task 1 红→绿钦定）：
- compose_step_chain 纯函数三型×五字段参数化（R1-F3——gap/六子/synthesis
  素材分列；R1-F13 模块级纯函数零 I/O 零 LLM——P95 采样对象）
- 部分降级 payload=产物原样（R2-F2 两形态各一用例：全降级信封 + 部分降级
  产物在位原样——丢弃真实产物恰违背审计初衷）
- 445 改写（构造配方 tool_slug=" " 纯空白串——R2-F3 唯一可达 242 通道；
  端口返回 None——R1-F5 组装失败 chain 缺席台账语义）
- 284 捕获降级台账（AsyncMock(spec=StrategicArchiveService) 抛
  ArchiveStorageError → ChainRecord(archived=False)）
- 归档载荷三键映射断言（decision_basis kind+stage+chain+degraded /
  assumptions tools_used+evidence_refs / evidence_blob 结构化 JSON——AC-3
  唯一真源；期望值独立构造非读回自比）
- query_chain_trace（循环 B）：档案清单→视图组装 / 五字段 round-trip 重构
  VO（tools_used=tuple(...) 归一——R1-F9 PG JSONB 读回 list 必拒）/
  include_blob 解引用（L4ObjectPort.retrieve 流式下载——单测层 mock 注入）/
  object_storage=None × include_blob=True → blob_content=None 不抛（R2-F4）/
  空清单 / archived_at 升序排序

Mock 形态（单元测试 Mock 端口红线合规——AsyncMock(spec=ProtocolClass) +
_make_*() 工厂函数，集成 Mock 工厂子模式）。async 测试函数裸 async def
（asyncio_mode=auto——BDD 步骤禁 asyncio 标记红线仅限验收层）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit/application/test_chain_of_thought_archive_service.py -v
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.chain_of_thought_archive import (
    CHAIN_ARCHIVE_KIND,
    ChainOfThoughtArchiveServicePort,
    ChainRecord,
    StepChainMaterial,
)
from src.application.services.chain_of_thought_archive_service import (
    ChainOfThoughtArchiveService,
    compose_step_chain,
)
from src.domain.entities.strategic_archive import ArchiveType
from src.domain.exceptions import ArchiveStorageError, EntityValidationError

#: 测试基准 plan_id（UUID 形态——归档是首个 UUID 硬消费方 R3-F4）
PLAN_UUID = uuid.uuid4()

#: 六子步骤型基准素材（组装映射断言的构造基座——三型分列之六子型）
_STEP_MATERIAL = StepChainMaterial(
    stage="market_insight_trend",
    display_name="看趋势",
    role_prefix="以 CEO 宏观趋势判断与 CTO 技术趋势分析的双重视角",
    task="制定新能源汽车行业五年战略规划",
    evidence_count=5,
    tool_slug="PESTEL 分析",
    evidence_refs=("chunk-001", "chunk-002", "chunk-003"),
    summary="市场洞察产物:trend（结构化要点）",
    findings_count=2,
    degraded=False,
    degrade_reason="",
    payload={"summary": "市场洞察产物:trend（结构化要点）", "findings": ["发现一", "发现二"]},
    structured_ok=True,
)

#: gap 型基准素材（无 findings/structured_output——素材=artifacts 六属性形态）
_GAP_MATERIAL = StepChainMaterial(
    stage="performance_gap",
    display_name="业绩差距分析",
    role_prefix="以 CFO 财务差距量化与 COO 运营差距分析的双重视角",
    task="制定新能源汽车行业五年战略规划",
    evidence_count=5,
    tool_slug="SWOT-TOWS",
    evidence_refs=("gap-ref-1",),
    summary="财务差距量化：营收达成率 82%",
    findings_count=3,
    degraded=False,
    degrade_reason="",
    payload={
        "financial_gap": "财务差距量化：营收达成率 82%",
        "operational_gap": "运营差距分析",
        "root_causes": ["根因一"],
        "portfolio_health": "健康度评估",
        "degraded": False,
        "degrade_reason": "",
    },
    structured_ok=True,
)

#: synthesis 型基准素材（无工具无检索——tool_slug 恒空/证据恒 0）
_SYNTHESIS_MATERIAL = StepChainMaterial(
    stage="market_insight_synthesis",
    display_name="市场洞察综合",
    role_prefix="CMO",
    task="制定新能源汽车行业五年战略规划",
    evidence_count=0,
    tool_slug="",
    evidence_refs=(),
    summary="",
    findings_count=2,
    degraded_inputs_count=1,
    degraded=False,
    degrade_reason="",
    payload={"conclusions": ["结论一", "结论二"], "degraded_inputs": ["trend"]},
    structured_ok=True,
)

#: 三型素材总表（round-trip 断言按 stage 取材）
_MATERIALS_BY_STAGE: dict[str, StepChainMaterial] = {
    _GAP_MATERIAL.stage: _GAP_MATERIAL,
    _STEP_MATERIAL.stage: _STEP_MATERIAL,
    _SYNTHESIS_MATERIAL.stage: _SYNTHESIS_MATERIAL,
}


def _make_material(**overrides: Any) -> StepChainMaterial:
    """六子步骤型素材工厂（字段覆写——参数化用例构造面）。"""
    from dataclasses import replace

    return replace(_STEP_MATERIAL, **overrides)


def _make_archive_entity(*, archive_id: uuid.UUID, plan_id: uuid.UUID, decision_basis: dict | None = None) -> Any:
    """StrategicArchive 实体构造工厂（归档返回面——真实实体形态非 dict）。"""
    from datetime import UTC, datetime

    from src.domain.entities.strategic_archive import StrategicArchive

    return StrategicArchive(
        archive_id=archive_id,
        plan_id=plan_id,
        plan_type="SP",
        archive_type=ArchiveType.EVIDENCE_PACKAGE,
        assumptions={},
        decision_basis=decision_basis or {},
        execution_deviation={},
        metadata_ref=f"strategic_archives:{archive_id}",
        created_at=datetime.now(UTC),
        archived_at=datetime.now(UTC),
    )


def _make_archive_service_mock(*, archive_side_effect: Any = None) -> Any:
    """StrategicArchiveService 替身工厂（AsyncMock(spec=具体类)——单元测试 Mock 红线）。

    Args:
        archive_side_effect: archive_plan 副作用注入（284 失败注入面）。
    """
    from src.application.services.strategic_archive_service import StrategicArchiveService

    mock = AsyncMock(spec=StrategicArchiveService)
    if archive_side_effect is not None:
        mock.archive_plan = AsyncMock(side_effect=archive_side_effect)
    else:
        mock.archive_plan = AsyncMock(return_value=_make_archive_entity(archive_id=uuid.uuid4(), plan_id=PLAN_UUID))
    mock.query_archive = AsyncMock(return_value=[])
    return mock


def _make_service(*, archive_side_effect: Any = None, object_storage: Any = None) -> ChainOfThoughtArchiveService:
    """组装归档服务工厂（归档替身 + 可选 L4 解引用通道注入）。"""
    archive_mock = _make_archive_service_mock(archive_side_effect=archive_side_effect)
    return ChainOfThoughtArchiveService(
        archive_service=archive_mock,
        object_storage=object_storage,
    )


# ===================================================================
# 循环 A：compose_step_chain 纯函数（R1-F13——零 I/O 零 LLM）
# ===================================================================


class TestComposeStepChain:
    """纯组装函数三型×五字段（R1-F3 分列公式判别——期望独立构造）。"""

    def test_insight_step_five_fields_formula(self) -> None:
        """六子型五字段（input_summary 公式/reflection 要点计数/constraints 三段）。"""
        chain = compose_step_chain(_STEP_MATERIAL)
        assert chain.input_summary == (
            "看趋势｜以 CEO 宏观趋势判断与 CTO 技术趋势分析的双重视角｜任务: 制定新能源汽车行业五年战略规划｜检索证据 5 条"
        )
        assert chain.reflection == "步骤产出: 市场洞察产物:trend（结构化要点）；要点 2 项；流程正常"
        assert chain.constraints_check == "结构化输出值域校验: 通过；证据充分性: 充足；降级标记: False"
        assert chain.tools_used == ("PESTEL 分析",)
        assert json.loads(chain.final_answer) == _STEP_MATERIAL.payload

    def test_performance_gap_five_fields_formula(self) -> None:
        """gap 型五字段（根因计数/四字段完整性段/六键 payload）。"""
        chain = compose_step_chain(_GAP_MATERIAL)
        assert chain.input_summary == (
            "业绩差距分析｜以 CFO 财务差距量化与 COO 运营差距分析的双重视角｜"
            "任务: 制定新能源汽车行业五年战略规划｜检索证据 5 条"
        )
        assert chain.reflection == "步骤产出: 财务差距量化：营收达成率 82%；根因 3 项；流程正常"
        assert chain.constraints_check == "四字段产物完整性: 通过；证据充分性: 充足；降级标记: False"
        assert chain.tools_used == ("SWOT-TOWS",)
        assert json.loads(chain.final_answer) == _GAP_MATERIAL.payload

    def test_synthesis_five_fields_formula(self) -> None:
        """synthesis 型五字段（模块常量语义/结论计数/两键 payload/空轨迹）。"""
        chain = compose_step_chain(_SYNTHESIS_MATERIAL)
        assert chain.input_summary == ("市场洞察综合｜CMO｜任务: 制定新能源汽车行业五年战略规划｜综合结论 2 项")
        assert chain.reflection == "综合结论 2 项；降级输入 1 项；流程正常"
        assert chain.constraints_check == "结论产出判定: 通过；降级输入: 1 项；降级标记: False"
        assert chain.tools_used == ()
        assert json.loads(chain.final_answer) == _SYNTHESIS_MATERIAL.payload

    def test_no_tool_step_empty_tuple_legal(self) -> None:
        """空元组合法（无工具步/工具降级步——(none) 展示占位由 VO 处理）。"""
        chain = compose_step_chain(_make_material(tool_slug=""))
        assert chain.tools_used == ()

    def test_evidence_insufficient_marker(self) -> None:
        """证据充分性不足段（n<3——不足口径）。"""
        chain = compose_step_chain(_make_material(evidence_count=2))
        assert "证据充分性: 不足" in chain.constraints_check

    def test_structured_missing_marker(self) -> None:
        """结构化校验缺失段（structured_ok=False——降级步口径）。"""
        chain = compose_step_chain(_make_material(structured_ok=False))
        assert "结构化输出值域校验: 缺失" in chain.constraints_check

    def test_degraded_reflection_suffix_and_marker(self) -> None:
        """部分降级形态（R2-F2——payload 产物原样 + 降级三处承载）。"""
        material = _make_material(degraded=True, degrade_reason="检索取数失败：连接超时", structured_ok=True)
        chain = compose_step_chain(material)
        # payload=产物原样（非信封——部分降级不丢弃真实产物）
        assert json.loads(chain.final_answer) == material.payload
        # 降级事实三处承载：reflection 后缀 / constraints_check 标记
        assert chain.reflection.endswith("；降级: 检索取数失败：连接超时")
        assert chain.constraints_check.endswith("降级标记: True")

    def test_full_degraded_envelope_payload(self) -> None:
        """全降级形态（R2-F2——产物缺席 payload=信封 + degrade_reason 在位）。"""
        material = _make_material(
            degraded=True,
            degrade_reason="LLM 调用失败：超时",
            structured_ok=False,
            payload={"degraded": True, "degrade_reason": "LLM 调用失败：超时"},
        )
        chain = compose_step_chain(material)
        assert json.loads(chain.final_answer) == {"degraded": True, "degrade_reason": "LLM 调用失败：超时"}

    def test_synthesis_degraded_formula(self) -> None:
        """synthesis 降级形态（conclusions 空——结论产出判定缺失）。"""
        from dataclasses import replace

        material = replace(
            _SYNTHESIS_MATERIAL,
            findings_count=0,
            degraded=True,
            degrade_reason="综合 LLM 降级",
            structured_ok=False,
            payload={"conclusions": [], "degraded_inputs": ["trend"]},
        )
        chain = compose_step_chain(material)
        assert chain.reflection == "综合结论 0 项；降级输入 1 项；降级: 综合 LLM 降级"
        assert chain.constraints_check == "结论产出判定: 缺失；降级输入: 1 项；降级标记: True"

    def test_blank_tool_slug_raises_242(self) -> None:
        """素材缺陷构造红（R2-F3——tool_slug=" " 纯空白串 truthy 进元组后被
        VO 元素级守卫拒绝，唯一可达 242 通道）。"""
        material = _make_material(tool_slug=" ")
        with pytest.raises(EntityValidationError) as exc_info:
            compose_step_chain(material)
        assert exc_info.value.code == "EXCEPTION_242"


# ===================================================================
# 循环 A：compose_and_archive_step_chain（组装+归档编排）
# ===================================================================


class TestComposeAndArchiveStepChain:
    """组装+归档单步（载荷三键映射/445 None/284 台账）。"""

    async def test_archive_payload_three_keys_mapping(self) -> None:
        """归档载荷三键映射（decision_basis kind+stage 锚/assumptions 过程素材/blob JSON）。"""
        archive_mock = _make_archive_service_mock()
        service = ChainOfThoughtArchiveService(archive_service=archive_mock, object_storage=None)
        record = await service.compose_and_archive_step_chain(PLAN_UUID, "market_insight_trend", _STEP_MATERIAL)
        assert record is not None and record.archived
        # 归档调用载荷断言（期望独立构造——AC-3 唯一真源）
        call_kwargs = archive_mock.archive_plan.await_args.kwargs
        assert call_kwargs["plan_id"] == PLAN_UUID
        assert call_kwargs["plan_type"] == "SP"
        assert call_kwargs["archive_type"] == ArchiveType.EVIDENCE_PACKAGE
        decision_basis = call_kwargs["decision_basis"]
        assert decision_basis["kind"] == CHAIN_ARCHIVE_KIND
        assert decision_basis["stage"] == "market_insight_trend"
        assert decision_basis["degraded"] is False
        chain_dict = decision_basis["chain"]
        assert chain_dict["tools_used"] == ["PESTEL 分析"]  # tuple→JSON array
        assert json.loads(chain_dict["final_answer"]) == _STEP_MATERIAL.payload
        assumptions = call_kwargs["assumptions"]
        assert assumptions["tools_used"] == ["PESTEL 分析"]
        assert assumptions["evidence_refs"] == ["chunk-001", "chunk-002", "chunk-003"]
        blob_json = json.loads(call_kwargs["evidence_blob"].decode("utf-8"))
        assert blob_json["stage"] == "market_insight_trend"
        assert json.loads(blob_json["chain"]["final_answer"]) == _STEP_MATERIAL.payload

    async def test_assembly_failure_returns_none(self, caplog: pytest.LogCaptureFixture) -> None:
        """445 降级（组装失败 → None——R1-F5 chain 缺席台账；不抛出中断）。"""
        archive_mock = _make_archive_service_mock()
        service = ChainOfThoughtArchiveService(archive_service=archive_mock, object_storage=None)
        material = _make_material(tool_slug=" ")  # R2-F3 构造配方
        record = await service.compose_and_archive_step_chain(PLAN_UUID, "market_insight_trend", material)
        assert record is None, "组装失败 445 应返回 None（chain 缺席——AC-4 台账语义）"
        archive_mock.archive_plan.assert_not_awaited()
        # 445 触发可见性（AC-1 验证标准——改写异常进 warning 日志，missing_fields 携缺失字段名）
        warning_text = " ".join(record.message for record in caplog.records if record.levelname == "WARNING")
        assert "EXCEPTION_445" in warning_text, f"445 触发不可见（warning 日志缺编码）: {warning_text!r}"
        assert "tools_used" in warning_text, f"missing_fields 未携缺失字段名: {warning_text!r}"

    async def test_archive_storage_error_degrades_to_false_ledger(self) -> None:
        """284 降级台账（归档失败 → ChainRecord(archived=False) 不抛出）。"""

        def _raise_284(*args: Any, **kwargs: Any) -> Any:
            raise ArchiveStorageError(layer="l4", cause=RuntimeError("MinIO 不可达"))

        archive_mock = _make_archive_service_mock(archive_side_effect=_raise_284)
        service = ChainOfThoughtArchiveService(archive_service=archive_mock, object_storage=None)
        record = await service.compose_and_archive_step_chain(PLAN_UUID, "performance_gap", _GAP_MATERIAL)
        assert record is not None, "归档失败应返回 ChainRecord(archived=False) 非 None"
        assert record.archived is False
        assert record.archive_id == ""
        assert record.stage == "performance_gap"

    async def test_three_type_materials_run_accumulation_shape(self) -> None:
        """三型代表素材 run 形态（CR1-F9 如实化：3 条=三型各一，非 8 条全序——
        每步一条 ChainRecord 的逐型判别，全 run 8 条形态由集成①/验收 S1 承载）。"""
        archive_mock = _make_archive_service_mock()
        service = ChainOfThoughtArchiveService(archive_service=archive_mock, object_storage=None)
        materials = [_GAP_MATERIAL, _STEP_MATERIAL, _SYNTHESIS_MATERIAL]
        stages = ["performance_gap", "market_insight_trend", "market_insight_synthesis"]
        records: list[ChainRecord] = []
        for stage, material in zip(stages, materials):
            record = await service.compose_and_archive_step_chain(PLAN_UUID, stage, material)
            if record is not None:  # 成功路径 None 不出现（445 降级面另测）
                records.append(record)
        assert len(records) == 3 and all(record.archived for record in records)
        assert [record.stage for record in records] == stages
        assert archive_mock.archive_plan.await_count == 3

    async def test_returns_chain_record_with_archive_id(self) -> None:
        """归档成功返回 archive_id 非空（L2 行主键回填）。"""
        archive_uuid = uuid.uuid4()
        archive_mock = _make_archive_service_mock()
        archive_mock.archive_plan = AsyncMock(return_value=_make_archive_entity(archive_id=archive_uuid, plan_id=PLAN_UUID))
        service = ChainOfThoughtArchiveService(archive_service=archive_mock, object_storage=None)
        record = await service.compose_and_archive_step_chain(PLAN_UUID, "market_insight_trend", _STEP_MATERIAL)
        assert record is not None
        assert record.archive_id == str(archive_uuid)


# ===================================================================
# 循环 B：query_chain_trace（追溯查询）
# ===================================================================


def _make_trace_archive_rows() -> list[Any]:
    """构造追溯读回档案行（decision_basis.chain 携五字段——PG JSONB 形态模拟：
    tools_used 为 list（R1-F9 归一口径的读回前提）。"""
    from datetime import UTC, datetime, timedelta

    rows = []
    base_time = datetime.now(UTC) - timedelta(minutes=10)
    for index, (stage, material) in enumerate(_MATERIALS_BY_STAGE.items()):
        chain = compose_step_chain(material)
        decision_basis = {
            "kind": CHAIN_ARCHIVE_KIND,
            "stage": stage,
            "degraded": material.degraded,
            "chain": {
                "input_summary": chain.input_summary,
                "reflection": chain.reflection,
                "tools_used": list(chain.tools_used),  # PG JSONB 读回 list 形态
                "constraints_check": chain.constraints_check,
                "final_answer": chain.final_answer,
            },
        }
        entity = _make_archive_entity(archive_id=uuid.uuid4(), plan_id=PLAN_UUID, decision_basis=decision_basis)
        entity.archived_at = base_time + timedelta(seconds=index)  # 升序可判
        entity.blob_ref = f"{entity.archive_id}/blob.json"  # L4 对象键（解引用通道前提）
        rows.append(entity)
    return rows


class TestQueryChainTrace:
    """追溯查询（视图组装/round-trip 重构/include_blob 解引用）。"""

    @staticmethod
    def _make_service_with_rows(rows: list[Any], *, object_storage: Any = None) -> tuple[Any, Any]:
        archive_mock = _make_archive_service_mock()
        archive_mock.query_archive = AsyncMock(return_value=rows)
        service = ChainOfThoughtArchiveService(archive_service=archive_mock, object_storage=object_storage)
        return service, archive_mock

    async def test_trace_view_assembly_and_sorting(self) -> None:
        """视图组装 + archived_at 升序 + total/archived_count。"""
        rows = _make_trace_archive_rows()
        service, archive_mock = self._make_service_with_rows(rows)
        view = await service.query_chain_trace(PLAN_UUID, include_blob=False)
        assert view.total == 3
        assert view.archived_count == 3
        assert [record["stage"] for record in view.records] == list(_MATERIALS_BY_STAGE)
        # ArchiveQuery 构造口径（显式 limit=50——R1-F17）
        query = archive_mock.query_archive.await_args.args[0]
        assert query.plan_id == PLAN_UUID
        assert query.archive_type == ArchiveType.EVIDENCE_PACKAGE
        assert query.limit == 50

    async def test_roundtrip_reconstructs_vo_with_tuple_normalization(self) -> None:
        """五字段 round-trip 重构 VO（tools_used list→tuple 归一——R1-F9）。"""
        rows = _make_trace_archive_rows()
        service, _ = self._make_service_with_rows(rows)
        view = await service.query_chain_trace(PLAN_UUID, include_blob=False)
        for record in view.records:
            chain = record["chain"]
            expected = compose_step_chain(_MATERIALS_BY_STAGE[record["stage"]])
            assert chain == expected, f"stage={record['stage']} round-trip 不等值（tuple 归一缺失即 242/不等）"
            assert isinstance(chain.tools_used, tuple), "tools_used 未归一 tuple（VO 242 守卫必拒 list）"

    async def test_include_blob_dereferences_l4(self) -> None:
        """include_blob=True 经 object_storage.retrieve 流式解引用（R1-F6 通道
        + CR1-F8 通道计数佐证——期望值与 decision_basis 同源的判别力缺口由
        retrieve 逐行调用断言补位：退化实现不走 L4 直接复制行内数据时计数红）。"""
        rows = _make_trace_archive_rows()
        object_storage = AsyncMock()
        blob_contents: dict[str, bytes] = {}
        expected_tools: dict[str, list[str]] = {}
        retrieve_calls: list[str] = []
        for row in rows:
            blob_json = {"stage": row.decision_basis["stage"], "chain": row.decision_basis["chain"]}
            blob_contents[row.blob_ref] = json.dumps(blob_json, ensure_ascii=False, sort_keys=True).encode("utf-8")
            expected_tools[row.decision_basis["stage"]] = row.decision_basis["chain"]["tools_used"]

        def _retrieve(*, bucket_type: str, object_key: str, version_id: str | None = None) -> Any:
            retrieve_calls.append(object_key)
            data = blob_contents[object_key]

            async def _stream() -> Any:
                yield data

            return _stream()

        object_storage.retrieve = _retrieve
        service, _ = self._make_service_with_rows(rows, object_storage=object_storage)
        view = await service.query_chain_trace(PLAN_UUID, include_blob=True)
        assert sorted(retrieve_calls) == sorted(str(row.blob_ref) for row in rows), (
            "retrieve 未按 blob_ref 逐行解引用（CR1-F8——blob 通道未真实走过的退化实现）"
        )
        assert len(view.records) == 3
        for record in view.records:
            blob_content = record["blob_content"]
            assert blob_content is not None, f"stage={record['stage']} blob_content 未填充"
            assert blob_content["stage"] == record["stage"]
            assert blob_content["chain"]["tools_used"] == expected_tools[record["stage"]]

    async def test_include_blob_without_object_storage_degrades_to_none(self) -> None:
        """object_storage=None × include_blob=True（R2-F4——warning + 槽位 None 不抛）。"""
        rows = _make_trace_archive_rows()
        service, _ = self._make_service_with_rows(rows, object_storage=None)
        view = await service.query_chain_trace(PLAN_UUID, include_blob=True)  # 不抛异常即过
        assert all(record["blob_content"] is None for record in view.records)
        assert view.total == 3

    async def test_empty_plan_returns_empty_view(self) -> None:
        """空清单（无档案合法 plan_id——查询面幂等读不抛异常）。"""
        service, _ = self._make_service_with_rows([])
        view = await service.query_chain_trace(uuid.uuid4(), include_blob=False)
        assert view.total == 0
        assert view.records == []


# ===================================================================
# 端口契约形态（Protocol 结构面——行为验证见上）
# ===================================================================


class TestPortShape:
    """端口协议形态（runtime_checkable——注入链消费面）。"""

    def test_service_implements_port(self) -> None:
        """服务实现端口协议（runtime_checkable isinstance 判定）。"""
        service = _make_service()
        assert isinstance(service, ChainOfThoughtArchiveServicePort)

    def test_chain_record_dataclass_fields(self) -> None:
        """ChainRecord 四字段（stage/chain/archived/archive_id）。"""
        from src.domain.value_objects.chain_of_thought import ChainOfThought

        record = ChainRecord(
            stage="market_insight_trend",
            chain=compose_step_chain(_STEP_MATERIAL),
            archived=True,
            archive_id="abc",
        )
        assert record.stage == "market_insight_trend"
        assert isinstance(record.chain, ChainOfThought)
        assert record.archived is True
        assert record.archive_id == "abc"
