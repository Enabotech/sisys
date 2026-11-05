"""Story 6-7 TraceabilityTreeService 单元测试（TDD 循环 A/B）

TDD 循环 A：五 VO 键集 exact set 断言（frozenset(fields()) 形态——6-6 EXPECTED_OUTCOME_KEYS
激活先例）+ TraceabilityTreePort Protocol 签名存在性（inspect.signature 键位断言——
6-4 CR1-R3 手法）。

TDD 循环 B：四段编排全场景矩阵（单测 Mock 红线合规——AsyncMock spec=ProtocolClass/
具体应用类；验收/集成面零 mock 分立）：
    ①收集段：kind 过滤 / 空归档空树 / 脏 stage 行读侧过滤
    ②判 run 段：stage 分组 last-write-wins + 并列 archive_id 决胜 + 双 synthesis 取新
      + adopted/total 对照 + synthesis 提取双形态 + 乱序输入→有序 children
    ③切片段：depth 四档（depth=1 退化档含 get_point/find 双零调用）+ point_missing
      降级（None 返回与 Exception 抛出两分支各一腿）
    ④文档段：document 去重缓存（find 恰一次调用计数）+ page 匹配（脏形态降 None）
      + document_missing（None/Exception 两分支）+ 跳转载荷六键 + bbox 透传 + jump_ready 派生
    ⑤顶层容错：query_archive 抛出 → 空树 + build_degraded=True + degraded_stages 上卷
"""

from __future__ import annotations

import inspect
import json
import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ===================================================================
# 期望键集常量（Task 0.1 冻结唯一版本——键集 exact set 断言锚）
# ===================================================================

EXPECTED_TREE_KEYS: frozenset[str] = frozenset(
    {
        "plan_id",
        "root",
        "adopted_archives",
        "total_archives",
        "degraded_stages",
        "build_degraded",
        "generated_at",
    }
)
EXPECTED_CONCLUSION_KEYS: frozenset[str] = frozenset({"plan_id", "title", "summary", "stage_count", "children"})
EXPECTED_STAGE_KEYS: frozenset[str] = frozenset(
    {
        "stage",
        "display_name",
        "summary",
        "degraded",
        "degrade_reason",
        "tools_used",
        "reflection_excerpt",
        "evidence_count",
        "children",
    }
)
EXPECTED_CHUNK_KEYS: frozenset[str] = frozenset({"chunk_id", "content_excerpt", "page_start", "page_end", "status", "children"})
EXPECTED_DOCUMENT_KEYS: frozenset[str] = frozenset(
    {
        "document_id",
        "filename",
        "version",
        "page",
        "object_key",
        "bucket",
        "bbox",
        "status",
        "jump_ready",
    }
)

_GAP_STAGE = "performance_gap"
_TREND_STAGE = "market_insight_trend"
_SYNTHESIS_STAGE = "market_insight_synthesis"


# ===================================================================
# TDD 循环 A：五 VO 键集契约 + 端口签名
# ===================================================================


class TestTraceabilityTreeValueObjects:
    """五 VO 键集 exact set + frozen 纪律 + 端口 Protocol 签名."""

    def test_traceability_tree_seven_keys(self) -> None:
        """TraceabilityTree 7 键（含 build_degraded 顶层降级哨兵 + degraded_stages 上卷——DR1-9）."""
        from src.application.ports.traceability_tree import TraceabilityTree

        assert {f.name for f in fields_of(TraceabilityTree)} == set(EXPECTED_TREE_KEYS)

    def test_conclusion_node_five_keys(self) -> None:
        """ConclusionNode 5 键."""
        from src.application.ports.traceability_tree import ConclusionNode

        assert {f.name for f in fields_of(ConclusionNode)} == set(EXPECTED_CONCLUSION_KEYS)

    def test_stage_node_nine_keys(self) -> None:
        """StageNode 9 键（三元组承载：evidence_count/tools_used+reflection_excerpt/summary）."""
        from src.application.ports.traceability_tree import StageNode

        assert {f.name for f in fields_of(StageNode)} == set(EXPECTED_STAGE_KEYS)

    def test_chunk_node_six_keys(self) -> None:
        """ChunkNode 6 键（页码两键取 Qdrant payload 扩键通道）."""
        from src.application.ports.traceability_tree import ChunkNode

        assert {f.name for f in fields_of(ChunkNode)} == set(EXPECTED_CHUNK_KEYS)

    def test_document_node_nine_keys(self) -> None:
        """DocumentNode 9 键（含 jump_ready 派生布尔）."""
        from src.application.ports.traceability_tree import DocumentNode

        assert {f.name for f in fields_of(DocumentNode)} == set(EXPECTED_DOCUMENT_KEYS)

    def test_value_objects_frozen(self) -> None:
        """五 VO 全 frozen dataclass（不可变纪律——frozen 逃逸口仅 bbox MappingProxyType 包裹）."""
        import dataclasses

        from src.application.ports import traceability_tree as port_module

        for vo_name in ("TraceabilityTree", "ConclusionNode", "StageNode", "ChunkNode", "DocumentNode"):
            vo_class: Any = getattr(port_module, vo_name)
            assert dataclasses.is_dataclass(vo_class), f"{vo_name} 应为 dataclass"
            instance = make_minimal_vo(vo_class)
            first_field = dataclasses.fields(instance)[0].name
            with pytest.raises(FrozenInstanceError):
                setattr(instance, first_field, "mutated")

    def test_port_protocol_signature(self) -> None:
        """TraceabilityTreePort 单方法签名（async 钦定——DR1-10；depth 默认 4；keyword-only）."""
        from src.application.ports.traceability_tree import TraceabilityTreePort

        assert hasattr(TraceabilityTreePort, "build_trace_tree")
        sig = inspect.signature(TraceabilityTreePort.build_trace_tree)
        assert set(sig.parameters) == {"self", "plan_id", "depth"}, f"端口参数键位: {set(sig.parameters)}"
        assert sig.parameters["depth"].default == 4
        assert sig.parameters["plan_id"].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["depth"].kind is inspect.Parameter.KEYWORD_ONLY
        import asyncio

        assert asyncio.iscoroutinefunction(TraceabilityTreePort.build_trace_tree), "端口方法应 async（DR1-10）"

    def test_port_is_runtime_checkable_protocol(self) -> None:
        """端口是 runtime_checkable Protocol（isinstance 结构检查可用——行为验证形态）."""
        from typing import get_type_hints

        from src.application.ports.traceability_tree import TraceabilityTree, TraceabilityTreePort

        assert getattr(TraceabilityTreePort, "_is_protocol", False) is True, "应带 typing.Protocol 标记"

        class _Impl:
            async def build_trace_tree(self, *, plan_id: str, depth: int = 4) -> TraceabilityTree:
                raise NotImplementedError

        assert isinstance(_Impl(), TraceabilityTreePort), "runtime_checkable 应允许 isinstance 结构检查"
        hints = get_type_hints(TraceabilityTreePort.build_trace_tree)
        assert "TraceabilityTree" in str(hints.get("return")), f"返回类型应为 TraceabilityTree，实际 {hints.get('return')}"


# ===================================================================
# 共享构造 helper（循环 B——实体直造 mock 返回可控）
# ===================================================================


def fields_of(dataclass_type: type) -> Any:
    """dataclasses.fields 惰性包装（测试可读性）."""
    import dataclasses

    return dataclasses.fields(dataclass_type)


def make_minimal_vo(vo_class: Any) -> Any:
    """以最小参数构造 VO 实例（frozen 突变测试用）.

    各 VO 均为带默认值或可最小构造的 frozen dataclass；children/元组键传空容器。
    """
    import dataclasses

    kwargs: dict[str, Any] = {}
    for field_info in dataclasses.fields(vo_class):
        if field_info.default is not dataclasses.MISSING or field_info.default_factory is not dataclasses.MISSING:
            continue
        name = field_info.name
        if name in ("children", "degraded_stages", "tools_used"):
            kwargs[name] = ()
        elif name in ("adopted_archives", "total_archives", "stage_count", "evidence_count", "version"):
            kwargs[name] = 0
        elif name in ("build_degraded", "degraded"):
            kwargs[name] = False
        elif name in ("page", "page_start", "page_end", "bbox", "object_key"):
            kwargs[name] = None
        else:
            kwargs[name] = "x"
    return vo_class(**kwargs)


def _make_chain_dict(stage: str, *, index: int = 0) -> dict[str, Any]:
    """构造 chain dict（五键——6-4 写入侧形态）."""
    payload: dict[str, Any]
    if stage == _SYNTHESIS_STAGE:
        payload = {"conclusions": [f"综合结论一（{index}）", f"综合结论二（{index}）"], "degraded_inputs": []}
    elif stage == _GAP_STAGE:
        payload = {
            "financial_gap": "财务差距",
            "operational_gap": "运营差距",
            "root_causes": ["根因一"],
            "portfolio_health": "核心稳健",
            "degraded": False,
            "degrade_reason": "",
        }
    else:
        payload = {"summary": f"步骤摘要（{stage}#{index}）", "findings": ["发现一"]}
    return {
        "input_summary": f"输入摘要（{stage}#{index}）",
        "reflection": f"反思内容（{stage}#{index}）" + "细节" * 80,
        "tools_used": [f"tool-{stage}-{index}"],
        "constraints_check": {},
        "final_answer": json.dumps(payload, ensure_ascii=False),
    }


def _make_archive(
    *,
    stage: str,
    chunk_ids: tuple[str, ...] = (),
    index: int = 0,
    archived_at: datetime | None = None,
    archive_id: uuid.UUID | None = None,
    kind: str = "blm_chain_of_thought",
    plan_id: uuid.UUID | None = None,
) -> Any:
    """StrategicArchive 实体直造（archived_at 显式可控——单测判 run 分组专用）."""
    from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive

    chain = _make_chain_dict(stage, index=index)
    return StrategicArchive(
        archive_id=archive_id or uuid.uuid4(),
        plan_id=plan_id or uuid.uuid4(),
        archive_type=ArchiveType.EVIDENCE_PACKAGE,
        assumptions={"tools_used": list(chain["tools_used"]), "evidence_refs": list(chunk_ids)},
        decision_basis={"kind": kind, "stage": stage, "chain": chain, "degraded": False},
        archived_at=archived_at,
    )


def _make_point_payload(chunk_id: str, document_id: str, *, content: str = "切片内容", page: int | None = 3) -> dict[str, Any]:
    """get_point 返回点结构（{id, vector, payload}——端口 docstring 契约；payload 8 业务键——Task 1 扩键后形态）."""
    return {
        "id": 1234567890,
        "vector": [0.1] * 8,
        "payload": {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "parent_chunk_id": None,
            "index_level": "child",
            "content": content,
            "chunk_header": "标题",
            "page_start": page,
            "page_end": page,
        },
    }


def _make_document_mock(document_id: str, *, filename: str = "doc.pdf", chunks_meta: list[dict[str, Any]] | None = None) -> Any:
    """Document 实体 mock（find 返回——单测依赖返回值形态）."""
    from src.domain.entities.document import Document

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = uuid.UUID(document_id)
    mock_doc.filename = filename
    mock_doc.version = 1
    mock_doc.metadata = {
        "chunks": chunks_meta if chunks_meta is not None else [{"chunk_id": "chunk-a", "page_start": 3, "page_end": 3}],
        "storage_object_key": f"raw-documents/test/{document_id}.pdf",
    }
    return mock_doc


def _make_service(
    *,
    archives: list[Any] | None = None,
    points: dict[str, dict[str, Any] | None] | None = None,
    documents: dict[str, Any] | None = None,
    query_error: Exception | None = None,
    point_error: Exception | None = None,
    find_error: Exception | None = None,
) -> tuple[Any, dict[str, AsyncMock]]:
    """构造被测服务与三依赖 AsyncMock 替身.

    - strategic_archive_service: AsyncMock(spec=StrategicArchiveService)——仓内无同名 Port
      （DR1-8），spec 具体类可行（不调 __init__、async 方法自动子 mock）
    - l3_vector: AsyncMock(spec=L3VectorPort)；document_repository: AsyncMock(spec=DocumentRepositoryPort)
    - points: chunk_id → get_point 返回（None=point_missing）；documents: document_id → find 返回
    """
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.application.services.traceability_tree_service import TraceabilityTreeService
    from src.domain.ports.document_repository import DocumentRepositoryPort
    from src.domain.ports.l3_vector import L3VectorPort

    archive_service = AsyncMock(spec=StrategicArchiveService)
    if query_error is not None:
        archive_service.query_archive.side_effect = query_error
    else:
        archive_service.query_archive.return_value = archives or []

    l3_vector = AsyncMock(spec=L3VectorPort)
    if point_error is not None:
        l3_vector.get_point.side_effect = point_error
    else:

        async def _get_point(collection: str, point_id: str) -> dict[str, Any] | None:
            return (points or {}).get(point_id)

        l3_vector.get_point.side_effect = _get_point

    document_repository = AsyncMock(spec=DocumentRepositoryPort)
    if find_error is not None:
        document_repository.find.side_effect = find_error
    else:

        async def _find(query: Any) -> Any:
            return (documents or {}).get(str(query.document_id))

        document_repository.find.side_effect = _find

    service = TraceabilityTreeService(
        strategic_archive_service=archive_service,
        l3_vector=l3_vector,
        document_repository=document_repository,
        search_collection="test-collection",
    )
    return service, {"archive": archive_service, "l3": l3_vector, "repo": document_repository}


def _make_archive_v2(
    *,
    stage: str,
    chunk_ids: tuple[str, ...] = (),
    index: int = 0,
    archived_at: datetime | None = None,
    archive_id: uuid.UUID | None = None,
    kind: str = "blm_chain_of_thought",
    plan_id: uuid.UUID | None = None,
    final_answer_override: str | None = None,
    degraded: bool = False,
) -> Any:
    """StrategicArchive 实体直造（扩展覆写位——final_answer/degraded 测试分支专用）."""
    from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive

    chain = _make_chain_dict(stage, index=index)
    if final_answer_override is not None:
        chain["final_answer"] = final_answer_override
    return StrategicArchive(
        archive_id=archive_id or uuid.uuid4(),
        plan_id=plan_id or uuid.uuid4(),
        archive_type=ArchiveType.EVIDENCE_PACKAGE,
        assumptions={"tools_used": list(chain["tools_used"]), "evidence_refs": list(chunk_ids)},
        decision_basis={"kind": kind, "stage": stage, "chain": chain, "degraded": degraded},
        archived_at=archived_at,
    )


class TestBuildTraceTree:
    """TDD 循环 B：四段编排全场景矩阵（单测 Mock 红线合规——AsyncMock spec）."""

    @pytest.mark.asyncio
    async def test_collect_kind_filter(self) -> None:
        """①收集段：非思维链行不计 total（kind 过滤——CHAIN_ARCHIVE_KIND 常量消费）."""
        plan_id = uuid.uuid4()
        chain_row = _make_archive(stage=_GAP_STAGE, chunk_ids=("chunk-a",), plan_id=plan_id)
        non_chain = _make_archive(stage=_TREND_STAGE, chunk_ids=("chunk-b",), kind="manual_note", plan_id=plan_id)
        service, _ = _make_service(archives=[chain_row, non_chain])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        assert tree.total_archives == 1, "kind 过滤后仅思维链行计入 total"
        assert [s.stage for s in tree.root.children] == [_GAP_STAGE]

    @pytest.mark.asyncio
    async def test_collect_empty_archives_empty_tree(self) -> None:
        """①空归档 → 空树幂等读（build_degraded=False——与顶层失败分立）."""
        service, _ = _make_service(archives=[])
        tree = await service.build_trace_tree(plan_id=str(uuid.uuid4()), depth=4)
        assert tree.root.children == ()
        assert tree.root.stage_count == 0
        assert tree.adopted_archives == 0
        assert tree.total_archives == 0
        assert tree.build_degraded is False
        assert tree.degraded_stages == ()

    @pytest.mark.asyncio
    async def test_collect_dirty_stage_filtered(self) -> None:
        """①脏 stage 行（∉七值域）→ 不产生 StageNode / 计 total 不计 adopted（DR3-4）."""
        plan_id = uuid.uuid4()
        gap = _make_archive(stage=_GAP_STAGE, chunk_ids=("chunk-a",), plan_id=plan_id)
        dirty = _make_archive(stage="unknown_stage", chunk_ids=("chunk-x",), plan_id=plan_id)
        service, _ = _make_service(archives=[gap, dirty])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        assert tree.total_archives == 2, "脏 stage 行计入 total"
        assert tree.adopted_archives == 1, "脏 stage 行不计 adopted"
        assert [s.stage for s in tree.root.children] == [_GAP_STAGE]

    @pytest.mark.asyncio
    async def test_collect_non_dict_decision_basis_filtered(self) -> None:
        """①非 dict 脏 decision_basis（JSONB 外部可写面）→ 排除出 total 不抛（R1-F1）.

        truthy 非 dict（如 JSON array）经 `_as_dict` 守卫降空 dict——kind 不可读按
        非思维链候选排除；恢复 `or {}` 形态则 AttributeError 逃逸（本用例必红）。
        """
        from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive

        plan_id = uuid.uuid4()
        gap = _make_archive(stage=_GAP_STAGE, chunk_ids=("chunk-a",), plan_id=plan_id)
        dirty_row = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=plan_id,
            archive_type=ArchiveType.EVIDENCE_PACKAGE,
            assumptions={"evidence_refs": ["chunk-dirty"]},
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        # 运行时脏数据注入（setattr 经动态属性绕类型面——脏形态本身就是实体类型注解的
        # 违例，JSONB 外部可写面语义；构造参数直塞会被 mypy 正确拦截）
        setattr(dirty_row, "decision_basis", ["not", "a", "dict"])
        service, _ = _make_service(archives=[gap, dirty_row])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        assert tree.total_archives == 1, "非 dict decision_basis 行不计 total（kind 不可读非候选）"
        assert tree.adopted_archives == 1
        assert [s.stage for s in tree.root.children] == [_GAP_STAGE]

    @pytest.mark.asyncio
    async def test_non_dict_assumptions_degrades_to_zero_evidence(self) -> None:
        """③非 dict 脏 assumptions → evidence_count=0 / 无 chunk 子节点 / 树不抛（R1-F1）."""
        from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive

        plan_id = uuid.uuid4()
        adopted_row = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=plan_id,
            archive_type=ArchiveType.EVIDENCE_PACKAGE,
            decision_basis={
                "kind": "blm_chain_of_thought",
                "stage": _GAP_STAGE,
                "chain": _make_chain_dict(_GAP_STAGE),
                "degraded": False,
            },
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        # 运行时脏数据注入（同上——类型注解违例即被测语义）
        setattr(adopted_row, "assumptions", "not-a-dict")
        service, _ = _make_service(archives=[adopted_row])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        stage_node = tree.root.children[0]
        assert stage_node.evidence_count == 0, "非 dict assumptions 降零证据"
        assert stage_node.children == (), "非 dict assumptions 无 chunk 子节点"
        assert tree.adopted_archives == 1

    @pytest.mark.asyncio
    async def test_judge_last_write_wins(self) -> None:
        """②判 run：同 stage 两行 → archived_at 最新行采纳（值级判别锚）."""
        plan_id = uuid.uuid4()
        old_row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-old",),
            index=0,
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        new_row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-new",),
            index=1,
            archived_at=datetime(2026, 1, 2, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, _ = _make_service(archives=[new_row, old_row])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        assert tree.adopted_archives == 1
        gap = tree.root.children[0]
        assert gap.summary == "输入摘要（performance_gap#1）", f"gap 型 summary 应取新行 input_summary: {gap.summary!r}"
        assert gap.tools_used == ("tool-performance_gap-1",)
        assert gap.evidence_count == 1

    @pytest.mark.asyncio
    async def test_judge_tiebreak_archive_id(self) -> None:
        """②并列 archived_at → archive_id 决胜（全序确定性——DR1-11）."""
        plan_id = uuid.uuid4()
        tied = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        row_a = _make_archive(
            stage=_GAP_STAGE,
            index=0,
            archived_at=tied,
            archive_id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
            plan_id=plan_id,
        )
        row_b = _make_archive(
            stage=_GAP_STAGE,
            index=1,
            archived_at=tied,
            archive_id=uuid.UUID("00000000-0000-4000-8000-000000000002"),
            plan_id=plan_id,
        )
        service, _ = _make_service(archives=[row_a, row_b])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        assert tree.root.children[0].tools_used == ("tool-performance_gap-1",), "并列时 archive_id 大者（index=1 行）应胜出"

    @pytest.mark.asyncio
    async def test_judge_none_archived_at_epoch_fallback(self) -> None:
        """②None archived_at 行回落 epoch 永不获胜；全 None stage 采纳 epoch 行计入 adopted."""
        plan_id = uuid.uuid4()
        none_row = _make_archive(stage=_GAP_STAGE, index=0, archived_at=None, plan_id=plan_id)
        dated_row = _make_archive(
            stage=_GAP_STAGE,
            index=1,
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        only_none = _make_archive(stage=_TREND_STAGE, index=0, archived_at=None, plan_id=plan_id)
        service, _ = _make_service(archives=[none_row, dated_row, only_none])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        assert tree.adopted_archives == 2, "gap(dated 胜出) + trend(全 None→epoch 采纳计入)"
        gap = next(s for s in tree.root.children if s.stage == _GAP_STAGE)
        assert gap.tools_used == ("tool-performance_gap-1",), "有非 None 行时 None 行永不获胜"

    @pytest.mark.asyncio
    async def test_judge_synthesis_latest_and_adopted(self) -> None:
        """②双 synthesis 行取新 + synthesis 计入 adopted（DR3-2——全 run total=8/adopted=8 同构）."""
        plan_id = uuid.uuid4()
        rows = [
            _make_archive(stage=_GAP_STAGE, archived_at=datetime(2026, 1, 1, tzinfo=UTC), plan_id=plan_id),
            _make_archive(stage=_TREND_STAGE, archived_at=datetime(2026, 1, 1, tzinfo=UTC), plan_id=plan_id),
        ]
        old_syn = _make_archive(
            stage=_SYNTHESIS_STAGE,
            index=0,
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        new_syn = _make_archive(
            stage=_SYNTHESIS_STAGE,
            index=1,
            archived_at=datetime(2026, 1, 2, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, _ = _make_service(archives=[*rows, old_syn, new_syn])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        assert tree.root.summary == "综合结论一（1）\n综合结论二（1）", (
            f"synthesis 应取最新行 conclusions: {tree.root.summary!r}"
        )
        assert tree.root.stage_count == 2, "synthesis 不入分析层（DR1-13）"
        assert tree.adopted_archives == 3, "gap + trend + synthesis 采纳"
        assert tree.total_archives == 4

    @pytest.mark.asyncio
    async def test_children_canonical_order_and_display_names(self) -> None:
        """②乱序输入（仓储 archived_at DESC 形态）→ root.children 流程规范序 + display_name 三源（DR3-1）."""
        plan_id = uuid.uuid4()
        trend = _make_archive(stage=_TREND_STAGE, archived_at=datetime(2026, 1, 3, tzinfo=UTC), plan_id=plan_id)
        gap = _make_archive(stage=_GAP_STAGE, archived_at=datetime(2026, 1, 2, tzinfo=UTC), plan_id=plan_id)
        competition = _make_archive(
            stage="market_insight_competition",
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, _ = _make_service(archives=[trend, gap, competition])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        assert [s.stage for s in tree.root.children] == [
            _GAP_STAGE,
            _TREND_STAGE,
            "market_insight_competition",
        ], "root.children 序应重排为流程规范序（禁透传遍历序）"
        assert [s.display_name for s in tree.root.children] == ["业绩差距分析", "看趋势", "看竞争"]

    @pytest.mark.asyncio
    async def test_depth1_conclusion_only_zero_calls(self) -> None:
        """③depth=1 退化档：root.children==() + get_point/find 双零调用（DR1-2）."""
        plan_id = uuid.uuid4()
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-a",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, mocks = _make_service(
            archives=[row],
            points={"chunk-a": _make_point_payload("chunk-a", str(uuid.uuid4()))},
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=1)
        assert tree.root.children == (), "depth=1 仅结论层"
        assert tree.root.stage_count == 1, "判 run 照常执行（stage_count 可用）"
        mocks["l3"].get_point.assert_not_called()
        mocks["repo"].find.assert_not_called()

    @pytest.mark.asyncio
    async def test_depth2_zero_point_calls(self) -> None:
        """③depth=2：分析层在位 + get_point 零调用（切片层零解析）."""
        plan_id = uuid.uuid4()
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-a",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, mocks = _make_service(
            archives=[row],
            points={"chunk-a": _make_point_payload("chunk-a", str(uuid.uuid4()))},
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        assert [s.stage for s in tree.root.children] == [_GAP_STAGE]
        assert tree.root.children[0].children == ()
        mocks["l3"].get_point.assert_not_called()
        mocks["repo"].find.assert_not_called()

    @pytest.mark.asyncio
    async def test_depth3_zero_find_calls(self) -> None:
        """③depth=3：切片层在位 + find 零调用（文档层零解析）."""
        plan_id = uuid.uuid4()
        document_id = str(uuid.uuid4())
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-a",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, mocks = _make_service(
            archives=[row],
            points={"chunk-a": _make_point_payload("chunk-a", document_id)},
            documents={document_id: _make_document_mock(document_id)},
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=3)
        chunks = tree.root.children[0].children
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "chunk-a"
        assert chunks[0].status == "resolved"
        assert chunks[0].children == ()
        mocks["repo"].find.assert_not_called()

    @pytest.mark.asyncio
    async def test_depth4_full_chain(self) -> None:
        """③depth=4：四层全链（默认深度全树）."""
        plan_id = uuid.uuid4()
        document_id = str(uuid.uuid4())
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-a",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, _ = _make_service(
            archives=[row],
            points={"chunk-a": _make_point_payload("chunk-a", document_id)},
            documents={document_id: _make_document_mock(document_id)},
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id))
        chunk = tree.root.children[0].children[0]
        assert chunk.children, "depth=4 应挂接文档层"
        assert chunk.children[0].status == "resolved"

    @pytest.mark.asyncio
    async def test_point_missing_none_return(self) -> None:
        """③get_point 返 None → ChunkNode.status=point_missing（children 空）."""
        plan_id = uuid.uuid4()
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-gone",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, _ = _make_service(archives=[row], points={"chunk-gone": None})
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        chunk = tree.root.children[0].children[0]
        assert chunk.status == "point_missing"
        assert chunk.children == ()
        assert chunk.page_start is None and chunk.page_end is None
        assert tree.degraded_stages == (_GAP_STAGE,)

    @pytest.mark.asyncio
    async def test_point_missing_exception_branch(self) -> None:
        """③get_point 抛出 → 同 point_missing 降级（节点捕获不炸树——DR3-9）."""
        plan_id = uuid.uuid4()
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-a",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, _ = _make_service(archives=[row], point_error=RuntimeError("qdrant unavailable"))
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        chunk = tree.root.children[0].children[0]
        assert chunk.status == "point_missing"

    @pytest.mark.asyncio
    async def test_document_dedup_cache_single_find(self) -> None:
        """④同 document_id 两 chunk → find 恰一次调用（去重缓存——DR2-9 调用计数归单测）."""
        plan_id = uuid.uuid4()
        document_id = str(uuid.uuid4())
        row = _make_archive(
            stage=_TREND_STAGE,
            chunk_ids=("chunk-a", "chunk-b"),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, mocks = _make_service(
            archives=[row],
            points={
                "chunk-a": _make_point_payload("chunk-a", document_id),
                "chunk-b": _make_point_payload("chunk-b", document_id),
            },
            documents={document_id: _make_document_mock(document_id)},
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        chunks = tree.root.children[0].children
        assert len(chunks) == 2
        assert mocks["repo"].find.call_count == 1, f"同 document_id 应恰一次 find，实际 {mocks['repo'].find.call_count}"
        assert chunks[0].children[0] is not chunks[1].children[0], "节点形态仍嵌套（非共享实例）"

    @pytest.mark.asyncio
    async def test_page_match_and_dirty_chunk(self) -> None:
        """④page 匹配：干净 chunk 取 page_start 值 / 脏 chunk（不在 chunks 列表）降 None."""
        plan_id = uuid.uuid4()
        document_id = str(uuid.uuid4())
        row = _make_archive(
            stage=_TREND_STAGE,
            chunk_ids=("chunk-clean", "chunk-dirty", "chunk-badpage"),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        chunks_meta: list[dict[str, Any]] = [
            {"chunk_id": "chunk-clean", "page_start": 3, "page_end": 3},
            {"chunk_id": "chunk-badpage", "page_start": "3"},
        ]
        service, _ = _make_service(
            archives=[row],
            points={
                "chunk-clean": _make_point_payload("chunk-clean", document_id),
                "chunk-dirty": _make_point_payload("chunk-dirty", document_id),
                "chunk-badpage": _make_point_payload("chunk-badpage", document_id),
            },
            documents={document_id: _make_document_mock(document_id, chunks_meta=chunks_meta)},
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        docs = {c.chunk_id: c.children[0] for c in tree.root.children[0].children}
        assert docs["chunk-clean"].page == 3
        assert docs["chunk-dirty"].page is None, "脏 chunk（不在 metadata.chunks）应降 None（非 6-5b 的 0 值语义）"
        assert docs["chunk-badpage"].page is None, "匹配到但 page_start 非正整数（字符串脏值）应降 None（R1-F10）"

    @pytest.mark.asyncio
    async def test_document_missing_none_return(self) -> None:
        """④find 返 None → DocumentNode.status=document_missing（filename 等降空值）."""
        plan_id = uuid.uuid4()
        document_id = str(uuid.uuid4())
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-a",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, _ = _make_service(
            archives=[row],
            points={"chunk-a": _make_point_payload("chunk-a", document_id)},
            documents={},
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        doc = tree.root.children[0].children[0].children[0]
        assert doc.status == "document_missing"
        assert doc.filename == ""
        assert doc.version == 0
        assert doc.page is None
        assert doc.object_key is None
        assert doc.jump_ready is False

    @pytest.mark.asyncio
    async def test_document_missing_exception_branch(self) -> None:
        """④find 抛出 → 同 document_missing 降级（节点捕获不炸树——DR3-9）."""
        plan_id = uuid.uuid4()
        document_id = str(uuid.uuid4())
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-a",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, _ = _make_service(
            archives=[row],
            points={"chunk-a": _make_point_payload("chunk-a", document_id)},
            find_error=RuntimeError("pg unavailable"),
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        doc = tree.root.children[0].children[0].children[0]
        assert doc.status == "document_missing"

    @pytest.mark.asyncio
    async def test_jump_payload_and_bbox_passthrough(self) -> None:
        """④跳转载荷六键值级 + bbox 透传（dict→MappingProxyType）+ jump_ready 派生."""
        plan_id = uuid.uuid4()
        document_id = str(uuid.uuid4())
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-a",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        point = _make_point_payload("chunk-a", document_id, content="x" * 500)
        point["payload"]["bbox"] = {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0, "page": 3}
        service, _ = _make_service(
            archives=[row],
            points={"chunk-a": point},
            documents={document_id: _make_document_mock(document_id, filename="年报.pdf")},
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        chunk = tree.root.children[0].children[0]
        doc = chunk.children[0]
        assert doc.filename == "年报.pdf"
        assert doc.version == 1
        assert doc.page == 3
        assert doc.object_key == f"raw-documents/test/{document_id}.pdf"
        assert doc.bucket == "raw-documents"
        assert dict(doc.bbox) == {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0, "page": 3}, "bbox 应透传不合成"
        assert doc.jump_ready is True
        assert chunk.content_excerpt == "x" * 300, "content_excerpt 应 300 字符截断"

    @pytest.mark.asyncio
    async def test_jump_ready_false_when_object_key_missing(self) -> None:
        """④jump_ready 派生：object_key 缺（metadata 无 storage_object_key）→ False."""
        plan_id = uuid.uuid4()
        document_id = str(uuid.uuid4())
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-a",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        doc_mock = _make_document_mock(document_id)
        doc_mock.metadata = {"chunks": [{"chunk_id": "chunk-a", "page_start": 3, "page_end": 3}]}
        service, _ = _make_service(
            archives=[row],
            points={"chunk-a": _make_point_payload("chunk-a", document_id)},
            documents={document_id: doc_mock},
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        doc = tree.root.children[0].children[0].children[0]
        assert doc.object_key is None
        assert doc.jump_ready is False, "object_key 缺失时半跳转不可达"
        assert doc.bbox is None, "payload 无 bbox 键时不得合成坐标（透传语义——R1-F2 None 分支锚）"

    @pytest.mark.asyncio
    async def test_payload_without_document_id_no_document_node(self) -> None:
        """④payload 缺 document_id（脏点）→ chunk 保持 resolved 且无文档子节点（R1-F1 升格锚）.

        「无引用」与 document_missing 分立：不产 DocumentNode、不调 find、不入
        degraded_stages——production 点恒带 document_id，该分支是脏点容错位。
        """
        plan_id = uuid.uuid4()
        row = _make_archive(
            stage=_GAP_STAGE,
            chunk_ids=("chunk-nodoc",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        point = _make_point_payload("chunk-nodoc", "irrelevant")
        del point["payload"]["document_id"]
        service, mocks = _make_service(archives=[row], points={"chunk-nodoc": point})
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        chunk = tree.root.children[0].children[0]
        assert chunk.status == "resolved", "缺 document_id 是脏点容错非 point_missing"
        assert chunk.children == (), "缺 document_id 不产 DocumentNode"
        assert tree.degraded_stages == (), "缺 document_id 不入降级上卷"
        mocks["repo"].find.assert_not_called()

    @pytest.mark.asyncio
    async def test_top_level_query_error_degraded_empty_tree(self) -> None:
        """⑤query_archive 抛出 → 空树降级 + build_degraded=True（与真空树分立——DR1-9）."""
        service, _ = _make_service(query_error=RuntimeError("pg down"))
        tree = await service.build_trace_tree(plan_id=str(uuid.uuid4()), depth=4)
        assert tree.root.children == ()
        assert tree.adopted_archives == 0
        assert tree.total_archives == 0
        assert tree.build_degraded is True, "顶层失败应以 build_degraded 哨兵分立"

    @pytest.mark.asyncio
    async def test_degraded_stages_rollup_ascending(self) -> None:
        """⑤degraded_stages 上卷：两 stage 各一失效 → 升序去重元组."""
        plan_id = uuid.uuid4()
        doc_id_trend = str(uuid.uuid4())
        comp = _make_archive(
            stage="market_insight_competition",
            chunk_ids=("chunk-comp",),
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        trend = _make_archive(
            stage=_TREND_STAGE,
            chunk_ids=("chunk-trend",),
            archived_at=datetime(2026, 1, 2, tzinfo=UTC),
            plan_id=plan_id,
        )
        service, _ = _make_service(
            archives=[comp, trend],
            points={"chunk-trend": _make_point_payload("chunk-trend", doc_id_trend)},  # comp 点缺
            documents={},
        )
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=4)
        assert tree.degraded_stages == ("market_insight_competition", _TREND_STAGE), "升序去重上卷"

    @pytest.mark.asyncio
    async def test_stage_summary_three_payload_types(self) -> None:
        """②StageNode.summary 三型分支（DR1-14）：六子取 payload.summary / gap 降 input_summary / 解析失败同降."""
        plan_id = uuid.uuid4()
        trend = _make_archive(
            stage=_TREND_STAGE,
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        gap = _make_archive(
            stage=_GAP_STAGE,
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        broken = _make_archive_v2(
            stage="market_insight_self",
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
            final_answer_override="not-a-json{{{",
        )
        service, _ = _make_service(archives=[trend, gap, broken])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        by_stage = {s.stage: s for s in tree.root.children}
        assert by_stage[_TREND_STAGE].summary == "步骤摘要（market_insight_trend#0）", "六子型应取 payload.summary"
        assert by_stage[_GAP_STAGE].summary == "输入摘要（performance_gap#0）", (
            "gap 型（payload 无 summary）应降 chain.input_summary"
        )
        assert by_stage["market_insight_self"].summary == "输入摘要（market_insight_self#0）", (
            "final_answer 解析失败应同降 input_summary"
        )

    @pytest.mark.asyncio
    async def test_stage_chain_defaults_and_reflection_truncation(self) -> None:
        """②chain 三键 .get 兜底（DR3-4）+ reflection 200 字符截断 + degraded/degrade_reason 独立取值."""
        plan_id = uuid.uuid4()
        archive = _make_archive_v2(
            stage=_GAP_STAGE,
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
            degraded=True,
        )
        # 剥离 chain 三键构造脏行形态
        archive.decision_basis["chain"] = {
            "input_summary": "仅输入摘要",
            "final_answer": json.dumps({"degrade_reason": "检索超时降级"}),
        }
        service, _ = _make_service(archives=[archive])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        stage = tree.root.children[0]
        assert stage.tools_used == (), "chain 缺 tools_used 应空元组兜底"
        assert stage.reflection_excerpt == "", "chain 缺 reflection 应空串兜底"
        assert stage.degraded is True, "degraded 取 decision_basis 顶层布尔"
        assert stage.degrade_reason == "检索超时降级", "degrade_reason 取 payload 键（与 degraded 独立取值）"

    @pytest.mark.asyncio
    async def test_reflection_excerpt_200_chars(self) -> None:
        """②reflection_excerpt 200 字符截断（源键名 reflection——DR1-14）."""
        plan_id = uuid.uuid4()
        archive = _make_archive_v2(
            stage=_TREND_STAGE,
            archived_at=datetime(2026, 1, 1, tzinfo=UTC),
            plan_id=plan_id,
        )
        archive.decision_basis["chain"]["reflection"] = "深" * 500
        service, _ = _make_service(archives=[archive])
        tree = await service.build_trace_tree(plan_id=str(plan_id), depth=2)
        assert tree.root.children[0].reflection_excerpt == "深" * 200
