"""PdfReportGenerationService 单元测试（Story 6-5b Task 3——引文聚合 + 六段编排）。

覆盖面：
- 聚合公开化（循环 A）：``aggregate_report_document`` 可 import 且行为在位
- 引文聚合三段链（循环 B）：收集去重保序（跨步骤共享 chunk 唯一+首现次序
  +stage 归属）/解析全链值级（get_point→payload.document_id str→UUID→
  find(tenant 注入)）/降级三态（point_missing/document_missing/page=0
  子形态）/整体容错（query_archive 与 get_point 连接级异常降级空附录 C）
- 六段编排（循环 C）：调用顺序（聚合→快照辅源→引文→渲染→L4+L2→事件）/
  490 同判/492 渲染包装/493 L4 包装/L4 调用参数值级（对象键模板+retention）
  /事件 report_type=pdf/发布失败两形态宽容/实体八字段

Mock 形态：九依赖 AsyncMock(spec=Port)（渲染器同步方法 MagicMock）——
no-mock 红线互斥裁定（渲染/存储失败注入归单测层——6-5a 三连先例）。

Run with:
    poetry run pytest tests/unit/application/test_pdf_report_generation_service.py -v
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.chain_of_thought_archive import (
    CHAIN_ARCHIVE_KIND,
    ChainOfThoughtArchiveServicePort,
)
from src.application.ports.pdf_report import (
    EVIDENCE_BUCKET_TYPE,
    PDF_OBJECT_KEY_TEMPLATE,
    PdfRendererPort,
)
from src.application.services.agent_workflow_context import MVP_TENANT_ID
from src.application.services.pdf_report_generation_service import PdfReportGenerationService
from src.application.services.report_generation_service import aggregate_report_document
from src.application.services.strategic_archive_service import StrategicArchiveService
from src.domain.entities.document import Document
from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.exceptions import (
    PdfRenderingError,
    ReportEvidenceStorageError,
    ReportGenerationError,
    ReportStorageError,
)
from src.domain.ports.document_repository import DocumentQuery, DocumentRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.report_repository import ReportRepositoryProtocol
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol

PLAN_ID = uuid.uuid4()

#: 测试租户（服务构造注入值——与预置查询闭环断言的期望源）
_TEST_TENANT = "unit-pdf-tenant"

#: 测试 collection（服务构造注入值）
_TEST_COLLECTION = "unit-pdf-collection"


def _make_chain_vo(payload: dict | None) -> Any:
    """构造 chain VO（payload None=缺行——final_answer 携带 JSON payload）。"""
    import json

    from src.domain.value_objects.chain_of_thought import ChainOfThought

    return ChainOfThought(
        input_summary="测试输入摘要",
        reflection="测试反思",
        tools_used=("工具一",),
        constraints_check="通过",
        final_answer=json.dumps(payload or {}, ensure_ascii=False),
    )


def _make_trace_view(stages: list[str]) -> Any:
    """构造聚合主源 TraceView（真实 DTO——CR2-F6 替身纪律）。"""
    from src.application.ports.chain_of_thought_archive import ChainOfThoughtTraceView

    records = [
        {
            "stage": stage,
            "chain": _make_chain_vo({"summary": f"摘要（{stage}）"}),
            "archive_id": f"archive-{stage}",
            "degraded": False,
            "blob_content": None,
        }
        for stage in stages
    ]
    return ChainOfThoughtTraceView(plan_id=str(PLAN_ID), records=records, total=len(records), archived_count=len(records))


def _make_archive_row(stage: str, evidence_refs: list[str] | None) -> StrategicArchive:
    """构造 EVIDENCE_PACKAGE 归档行（assumptions.evidence_refs 写侧形态——6-4 :200-203）。"""
    assumptions: dict[str, Any] = {"tools_used": []}
    if evidence_refs is not None:
        assumptions["evidence_refs"] = evidence_refs
    return StrategicArchive(
        archive_id=uuid.uuid4(),
        plan_id=PLAN_ID,
        plan_type="SP",
        archive_type=ArchiveType.EVIDENCE_PACKAGE,
        assumptions=assumptions,
        decision_basis={"kind": CHAIN_ARCHIVE_KIND, "stage": stage, "chain": {}, "degraded": False},
        archived_at=datetime(2026, 11, 4, 10, 0, 0, tzinfo=timezone.utc),
    )


def _make_document_row(document_id: uuid.UUID, filename: str, chunks: list[dict] | None = None) -> Document:
    """构造 documents 行实体（filename + metadata.chunks——页码解析链闭合源）。"""
    return Document(
        document_id=document_id,
        filename=filename,
        metadata={"chunks": chunks if chunks is not None else []},
        tenant_id=_TEST_TENANT,
    )


def _make_service(
    *,
    stages: list[str] | None = None,
    archive_rows: list[StrategicArchive] | None = None,
    points: dict[str, dict | None] | None = None,
    documents: dict[str, Document | None] | None = None,
    render_side_effect: Any = None,
    l4_side_effect: Any = None,
    publish_side_effect: Any = None,
) -> tuple[PdfReportGenerationService, dict[str, Any]]:
    """构造被测服务（九依赖 mock——渲染器同步 MagicMock，余 AsyncMock）。

    Args:
        stages: chain trace stage 清单（None=八步全量）。
        archive_rows: query_archive 返回行。
        points: chunk_id → get_point 返回（None=检索点缺失）。
        documents: document_id → find 返回（None=行缺失）。
        render_side_effect: 渲染异常注入。
        l4_side_effect: L4 archive 异常注入。
        publish_side_effect: 事件发布注入（失败 PublishResult/raise）。

    Returns:
        (服务实例, mock 依赖字典)。
    """
    if stages is None:
        stages = [
            "performance_gap",
            "market_insight_trend",
            "market_insight_market_customer",
            "market_insight_competition",
            "market_insight_self",
            "market_insight_opportunity",
            "market_insight_opportunity_gap",
            "market_insight_synthesis",
        ]
    chain = AsyncMock(spec=ChainOfThoughtArchiveServicePort)
    chain.query_chain_trace.return_value = _make_trace_view(stages)
    snapshot_repo = AsyncMock(spec=SnapshotRepositoryProtocol)
    snapshot_repo.load.return_value = None
    archive_service = AsyncMock(spec=StrategicArchiveService)
    archive_service.query_archive.return_value = archive_rows or []
    l3 = AsyncMock(spec=L3VectorPort)

    async def _get_point(collection: str, point_id: str) -> dict | None:
        if points is None:
            return None
        return points.get(point_id)

    l3.get_point.side_effect = _get_point
    document_repo = AsyncMock(spec=DocumentRepositoryPort)

    async def _find(query: DocumentQuery) -> Document | None:
        if documents is None:
            return None
        return documents.get(str(query.document_id))

    document_repo.find.side_effect = _find
    renderer = MagicMock(spec=PdfRendererPort)
    if render_side_effect is not None:
        renderer.render.side_effect = render_side_effect
    else:
        renderer.render.return_value = b"%PDF-mock-bytes"
    l4 = AsyncMock(spec=L4ObjectPort)
    if l4_side_effect is not None:
        l4.archive.side_effect = l4_side_effect
    else:
        l4.archive.side_effect = None
        l4.archive.return_value = "reports/x/y.pdf"
    report_repo = AsyncMock(spec=ReportRepositoryProtocol)

    async def _save(report: Any, metadata: dict | None = None) -> Any:
        return report

    report_repo.save.side_effect = _save
    publisher = AsyncMock(spec=EventPublisher)
    if publish_side_effect is not None:
        publisher.publish.side_effect = publish_side_effect
    else:
        publisher.publish.return_value = PublishResult(
            event_id=str(uuid.uuid4()), results=(ChannelResult("reliable", True, None),)
        )
    service = PdfReportGenerationService(
        chain_archive_service=chain,
        snapshot_repository=snapshot_repo,
        report_repository=report_repo,
        event_publisher=publisher,
        pdf_renderer=renderer,
        l4_object=l4,
        l3_vector=l3,
        document_repository=document_repo,
        archive_service=archive_service,
        collection=_TEST_COLLECTION,
        tenant_id=_TEST_TENANT,
    )
    return service, {
        "chain": chain,
        "snapshot_repo": snapshot_repo,
        "archive_service": archive_service,
        "l3": l3,
        "document_repo": document_repo,
        "renderer": renderer,
        "l4": l4,
        "report_repo": report_repo,
        "publisher": publisher,
    }


def _failed_publish_result() -> PublishResult:
    """构造失败 PublishResult（宽容防线① 注入形态）。"""
    return PublishResult(event_id=str(uuid.uuid4()), results=(ChannelResult("reliable", False, "写失败"),))


def _saved_metadata(mocks: dict[str, Any]) -> dict[str, Any]:
    """提取 L2 save 收到的 metadata（keyword 参——None/非 dict 形态内聚断言）。

    返回类型收窄为非空 dict（调用侧直索引的安全前提——mypy 收窄内聚位）。
    """
    call = mocks["report_repo"].save.call_args
    assert call is not None
    metadata = call.kwargs.get("metadata")
    assert isinstance(metadata, dict), f"save 未收到 dict metadata: {metadata!r}"
    return metadata


async def _generate(service: Any) -> Any:
    """执行生成（pytest-asyncio auto 模式）。"""
    return await service.generate_pdf_report(PLAN_ID)


# ======================================================================
# 循环 A：聚合公开化
# ======================================================================


class TestAggregatePublicFunction:
    """聚合函数公开化（OD-3——更名零行为变，双链消费单源）。"""

    def test_aggregate_report_document_importable_and_callable(self) -> None:
        """公开函数可 import 且可调用（ImportError 红先证的绿证）。"""
        assert callable(aggregate_report_document)

    def test_aggregate_returns_document_ir(self) -> None:
        """聚合返回 _Aggregation 结构（document 为双渲染共用 IR）。"""
        trace = _make_trace_view(["performance_gap"])
        aggregation = aggregate_report_document(str(PLAN_ID), trace.records, None, 0.0)
        document = aggregation.document
        assert document.plan_id == str(PLAN_ID)
        assert len(document.sections) > 0


# ======================================================================
# 循环 B：引文聚合三段链
# ======================================================================


class TestCitationAggregation:
    """引文聚合（收集去重保序/解析全链/降级三态/整体容错）。"""

    async def test_citation_resolved_full_chain(self) -> None:
        """解析全链值级（get_point→find→filename+page；find 参数 tenant/document_id 值级）。"""
        document_id = uuid.uuid4()
        service, mocks = _make_service(
            archive_rows=[_make_archive_row("market_insight_trend", ["chunk-aaa"])],
            points={"chunk-aaa": {"payload": {"document_id": str(document_id), "chunk_header": "标题"}}},
            documents={
                str(document_id): _make_document_row(
                    document_id, "战略研判参考报告.pdf", [{"chunk_id": "chunk-aaa", "page_start": 12}]
                )
            },
        )
        report = await _generate(service)
        assert report is not None
        metadata = _saved_metadata(mocks)
        assert metadata is not None
        citations = metadata["citations"]
        assert len(citations) == 1
        assert citations[0] == {
            "index": 1,
            "document_id": str(document_id),
            "chunk_id": "chunk-aaa",
            "filename": "战略研判参考报告.pdf",
            "page": 12,
            "status": "resolved",
            "stage": "market_insight_trend",
        }
        assert metadata["citation_count"] == 1
        assert metadata["unresolvable_citation_count"] == 0
        # find 调用参数值级：tenant_id==注入租户 + document_id==UUID 化值（payload str→转换链）
        find_query: DocumentQuery = mocks["document_repo"].find.call_args.args[0]
        assert find_query.tenant_id == _TEST_TENANT
        assert find_query.document_id == document_id
        # get_point 调用参数值级：collection==注入 collection + chunk_id
        point_args = mocks["l3"].get_point.call_args
        assert point_args.args == (_TEST_COLLECTION, "chunk-aaa")

    async def test_citation_dedup_preserves_first_occurrence_order(self) -> None:
        """跨步骤共享 chunk 去重保序（A 唯一 + 首现次序 + stage=首现步骤）。"""
        service, mocks = _make_service(
            archive_rows=[
                _make_archive_row("market_insight_trend", ["chunk-A"]),
                _make_archive_row("market_insight_competition", ["chunk-A", "chunk-B"]),
            ],
            points={},
            documents={},
        )
        await _generate(service)
        metadata = _saved_metadata(mocks)
        citations = metadata["citations"]
        assert metadata["citation_count"] == 2  # A 去重后唯一 + B
        first = next(c for c in citations if c["chunk_id"] == "chunk-A")
        second = next(c for c in citations if c["chunk_id"] == "chunk-B")
        assert first["index"] == 1 and second["index"] == 2
        assert first["stage"] == "market_insight_trend"  # A 锚首现步骤
        assert second["stage"] == "market_insight_competition"

    async def test_evidence_refs_key_missing_tolerated(self) -> None:
        """assumptions 无 evidence_refs 键容错（.get 缺省空——零引文）。"""
        service, mocks = _make_service(archive_rows=[_make_archive_row("market_insight_trend", None)])
        await _generate(service)
        metadata = _saved_metadata(mocks)
        assert metadata["citation_count"] == 0
        assert metadata["citations"] == []

    async def test_point_missing_degradation(self) -> None:
        """get_point 无点 → point_missing + unresolvable 计数。"""
        service, mocks = _make_service(
            archive_rows=[_make_archive_row("performance_gap", ["chunk-gone"])],
            points={"chunk-gone": None},
        )
        await _generate(service)
        metadata = _saved_metadata(mocks)
        assert metadata["citation_count"] == 1
        assert metadata["unresolvable_citation_count"] == 1
        assert metadata["citations"][0]["status"] == "point_missing"
        assert metadata["citations"][0]["chunk_id"] == "chunk-gone"
        assert metadata["citations"][0]["filename"] == ""

    async def test_document_missing_degradation(self) -> None:
        """documents 行缺失 → document_missing（附录 C 占位文案冻结契约）。"""
        document_id = uuid.uuid4()
        service, mocks = _make_service(
            archive_rows=[_make_archive_row("performance_gap", ["chunk-x"])],
            points={"chunk-x": {"payload": {"document_id": str(document_id)}}},
            documents={str(document_id): None},
        )
        await _generate(service)
        metadata = _saved_metadata(mocks)
        assert metadata["citations"][0]["status"] == "document_missing"
        assert metadata["unresolvable_citation_count"] == 1
        # 附录 C 文档名列占位文案（增量冻结表两态占位之一——CR1-F1 断言锚）
        document_vo = mocks["renderer"].render.call_args.args[0]
        appendix = [s for s in document_vo.sections if s.title == "附录 C 引文索引"]
        assert appendix[0].blocks[0].rows == (("1", "[溯源不可用：文档记录缺失]", "-", "chunk-x"),)

    async def test_page_missing_resolved_with_zero(self) -> None:
        """chunks 元数据无该 chunk_id → resolved+page=0（页缺失非独立态）。"""
        document_id = uuid.uuid4()
        service, mocks = _make_service(
            archive_rows=[_make_archive_row("performance_gap", ["chunk-y"])],
            points={"chunk-y": {"payload": {"document_id": str(document_id)}}},
            documents={str(document_id): _make_document_row(document_id, "无页码文档.pdf", [])},
        )
        await _generate(service)
        metadata = _saved_metadata(mocks)
        assert metadata["citations"][0]["status"] == "resolved"
        assert metadata["citations"][0]["page"] == 0
        assert metadata["unresolvable_citation_count"] == 0
        # 附录 C 页码列 resolved+page==0 → "-"（冻结契约三态第二态——CR1-F4 变异锚）
        document_vo = mocks["renderer"].render.call_args.args[0]
        appendix = [s for s in document_vo.sections if s.title == "附录 C 引文索引"]
        assert appendix[0].blocks[0].rows == (("1", "无页码文档.pdf", "-", "chunk-y"),)

    async def test_chunks_null_metadata_tolerated(self) -> None:
        """chunks 键值为 JSONB null → resolved+page=0（脏形态守卫——不炸主链）。"""
        document_id = uuid.uuid4()
        document_null_chunks = Document(
            document_id=document_id,
            filename="空块元数据.pdf",
            metadata={"chunks": None},
            tenant_id=_TEST_TENANT,
        )
        service, mocks = _make_service(
            archive_rows=[_make_archive_row("performance_gap", ["chunk-n"])],
            points={"chunk-n": {"payload": {"document_id": str(document_id)}}},
            documents={str(document_id): document_null_chunks},
        )
        await _generate(service)
        metadata = _saved_metadata(mocks)
        assert metadata["citations"][0]["status"] == "resolved"
        assert metadata["citations"][0]["page"] == 0

    async def test_page_start_dirty_string_tolerated(self) -> None:
        """page_start 为脏字符串 → resolved+page=0（int 守卫——非 int 降级非炸链）。"""
        document_id = uuid.uuid4()
        service, mocks = _make_service(
            archive_rows=[_make_archive_row("performance_gap", ["chunk-s"])],
            points={"chunk-s": {"payload": {"document_id": str(document_id)}}},
            documents={
                str(document_id): _make_document_row(document_id, "脏页码.pdf", [{"chunk_id": "chunk-s", "page_start": "3x"}])
            },
        )
        await _generate(service)
        metadata = _saved_metadata(mocks)
        assert metadata["citations"][0]["status"] == "resolved"
        assert metadata["citations"][0]["page"] == 0

    async def test_query_archive_failure_degrades_to_empty(self) -> None:
        """query_archive 抛异常 → 整体降级空附录 C（报告照常生成）。"""
        service, mocks = _make_service()
        mocks["archive_service"].query_archive.side_effect = RuntimeError("归档库不可达")
        report = await _generate(service)
        assert report is not None
        metadata = _saved_metadata(mocks)
        assert metadata["citation_count"] == 0
        assert metadata["citation_degraded"] is True  # R3-5：持久降级标记（审计分界）

    async def test_get_point_connection_error_degrades_to_empty(self) -> None:
        """get_point 解析链依赖异常 → 整体降级空（与 query_archive 异常同 try 边界）。"""
        service, mocks = _make_service(archive_rows=[_make_archive_row("performance_gap", ["chunk-z"])])
        mocks["l3"].get_point.side_effect = ConnectionError("Qdrant 不可达")
        report = await _generate(service)
        assert report is not None
        metadata = _saved_metadata(mocks)
        assert metadata["citation_count"] == 0
        assert metadata["citation_degraded"] is True  # R3-5：持久降级标记

    async def test_find_failure_degrades_to_empty(self) -> None:
        """find 抛解析链异常 → 整体降级空（与 get_point 同形态——CR1-F2 容错边界扩展）。"""
        document_id = uuid.uuid4()
        service, mocks = _make_service(
            archive_rows=[_make_archive_row("performance_gap", ["chunk-f"])],
            points={"chunk-f": {"payload": {"document_id": str(document_id)}}},
        )
        mocks["document_repo"].find.side_effect = ConnectionError("PG 不可达")
        report = await _generate(service)
        assert report is not None
        metadata = _saved_metadata(mocks)
        assert metadata["citation_count"] == 0
        assert metadata["citation_degraded"] is True  # R3-5：持久降级标记
        # 附录 C 空态说明（整体降级形态——非半截引文表）
        document_vo = mocks["renderer"].render.call_args.args[0]
        appendix = [s for s in document_vo.sections if s.title == "附录 C 引文索引"]
        assert appendix[0].blocks[0].kind == "callout"

    async def test_appendix_c_assembled_into_document(self) -> None:
        """引文条目组装进 document VO 附录 C（渲染器收到的 IR 含四列表格）。"""
        document_id = uuid.uuid4()
        service, mocks = _make_service(
            archive_rows=[_make_archive_row("performance_gap", ["chunk-aaa"])],
            points={"chunk-aaa": {"payload": {"document_id": str(document_id)}}},
            documents={
                str(document_id): _make_document_row(document_id, "报告.pdf", [{"chunk_id": "chunk-aaa", "page_start": 3}])
            },
        )
        await _generate(service)
        document = mocks["renderer"].render.call_args.args[0]
        appendix = [s for s in document.sections if s.title == "附录 C 引文索引"]
        assert len(appendix) == 1
        table_block = appendix[0].blocks[0]
        assert table_block.kind == "table"
        assert table_block.headers == ("#", "文档名", "页码", "切片标识")
        assert table_block.rows == (("1", "报告.pdf", "p.3", "chunk-aa"),)

    async def test_appendix_c_empty_note_when_no_citations(self) -> None:
        """零引文 → 附录 C 单行说明 callout（恒存在哲学）。"""
        service, mocks = _make_service(archive_rows=[])
        await _generate(service)
        document = mocks["renderer"].render.call_args.args[0]
        appendix = [s for s in document.sections if s.title == "附录 C 引文索引"]
        assert len(appendix) == 1
        assert appendix[0].blocks[0].kind == "callout"
        assert "本报告无检索证据引用" in appendix[0].blocks[0].text


# ======================================================================
# 循环 C：六段编排 + 事件
# ======================================================================


class TestSixStageOrchestration:
    """六段编排（顺序/490/492/493/L4 值级/事件/宽容/实体）。"""

    async def test_orchestration_call_order(self) -> None:
        """编排顺序：聚合主源→快照辅源→引文→渲染→L4→L2→事件（六段同构）。"""
        call_log: list[str] = []
        service, mocks = _make_service(archive_rows=[_make_archive_row("performance_gap", ["chunk-a"])])

        async def _trace(plan_id: Any) -> Any:
            call_log.append("aggregate_source")
            return _make_trace_view(["performance_gap", "market_insight_trend"])

        async def _load(session_id: str) -> Any:
            call_log.append("snapshot_aux")
            return None

        async def _query(query: Any) -> list:
            call_log.append("citation_collect")
            return [_make_archive_row("performance_gap", ["chunk-a"])]

        def _render(document: Any) -> bytes:
            call_log.append("render")
            return b"%PDF"

        async def _archive(**kwargs: Any) -> str:
            call_log.append("l4_archive")
            return "k"

        async def _save(report: Any, metadata: dict | None = None) -> Any:
            call_log.append("l2_save")
            return report

        async def _publish(event: Any) -> Any:
            call_log.append("publish")
            return PublishResult(event_id="e", results=(ChannelResult("reliable", True, None),))

        mocks["chain"].query_chain_trace.side_effect = _trace
        mocks["snapshot_repo"].load.side_effect = _load
        mocks["archive_service"].query_archive.side_effect = _query
        mocks["renderer"].render.side_effect = _render
        mocks["l4"].archive.side_effect = _archive
        mocks["report_repo"].save.side_effect = _save
        mocks["publisher"].publish.side_effect = _publish
        await _generate(service)
        assert call_log == [
            "aggregate_source",
            "snapshot_aux",
            "citation_collect",
            "render",
            "l4_archive",
            "l2_save",
            "publish",
        ]

    async def test_entity_pdf_fields(self) -> None:
        """实体八字段（report_type=PDF/file_path=对象键模板/计数恒 11）。"""
        service, _ = _make_service()
        report = await _generate(service)
        from src.domain.entities.strategic_report import ReportType

        assert report.report_type is ReportType.PDF
        expected_key = PDF_OBJECT_KEY_TEMPLATE.format(plan_id=PLAN_ID, report_id=report.report_id)
        assert report.file_path == expected_key
        assert report.section_count == 11
        assert report.degraded_section_count == 0
        assert report.generation_ms >= 0
        assert report.plan_id == str(PLAN_ID)

    async def test_490_when_trace_total_zero(self) -> None:
        """数据源全缺 → ReportGenerationError 490（PDF 链同判）+ 后续零调用。"""
        service, mocks = _make_service(stages=[])
        with pytest.raises(ReportGenerationError) as exc_info:
            await _generate(service)
        assert exc_info.value.code == "EXCEPTION_490"
        assert exc_info.value.context["plan_id"] == str(PLAN_ID)
        mocks["renderer"].render.assert_not_called()
        mocks["l4"].archive.assert_not_called()
        mocks["report_repo"].save.assert_not_called()

    async def test_492_render_failure_wrapped(self) -> None:
        """渲染异常 → PdfRenderingError 492（context.plan_id——reportlab 原生异常包装）。"""
        service, _ = _make_service(render_side_effect=ValueError("format not resolved: undefined destination"))
        with pytest.raises(PdfRenderingError) as exc_info:
            await _generate(service)
        assert exc_info.value.code == "EXCEPTION_492"
        assert exc_info.value.context["plan_id"] == str(PLAN_ID)

    async def test_493_l4_failure_wrapped(self) -> None:
        """L4 归档异常 → ReportEvidenceStorageError 493。"""
        service, _ = _make_service(l4_side_effect=OSError("MinIO 不可达"))
        with pytest.raises(ReportEvidenceStorageError) as exc_info:
            await _generate(service)
        assert exc_info.value.code == "EXCEPTION_493"
        assert exc_info.value.context["plan_id"] == str(PLAN_ID)

    async def test_l2_save_failure_raises_491(self) -> None:
        """L2 元数据落库失败 → ReportStorageError 491 layer="l2"（CR1-F6——491 语义精确归宿）。"""
        service, mocks = _make_service()
        mocks["report_repo"].save.side_effect = OSError("PG 不可达")
        with pytest.raises(ReportStorageError) as exc_info:
            await _generate(service)
        assert exc_info.value.code == "EXCEPTION_491"
        assert exc_info.value.layer == "l2"

    async def test_l4_archive_call_args_value_level(self) -> None:
        """L4 调用参数值级（bucket==archive-evidence/对象键模板/content/retention——无 content_type）。"""
        service, mocks = _make_service()
        report = await _generate(service)
        call = mocks["l4"].archive.call_args
        assert call.kwargs["bucket_type"] == EVIDENCE_BUCKET_TYPE
        assert call.kwargs["object_key"] == PDF_OBJECT_KEY_TEMPLATE.format(plan_id=PLAN_ID, report_id=report.report_id)
        assert call.kwargs["content"] == b"%PDF-mock-bytes"
        assert call.kwargs["retention_days"] == 2555
        assert "content_type" not in call.kwargs  # archive 签名无 content_type（OD-4——勿传）

    async def test_event_report_type_pdf(self) -> None:
        """事件三键值级（report_type=="pdf"/report_id/file_path——独立构造期望）。"""
        service, mocks = _make_service()
        report = await _generate(service)
        event = mocks["publisher"].publish.call_args.args[0]
        assert event.event_type == "ReportGenerated"
        assert event.report_id == report.report_id
        assert event.report_type == "pdf"
        assert event.file_path == report.file_path
        assert event.aggregate_id == report.report_id
        assert event.aggregate_type == "Report"

    async def test_event_failure_tolerated_failed_result(self) -> None:
        """发布失败（失败 PublishResult）→ 宽容（报告成功——防线①）。"""
        service, _ = _make_service(publish_side_effect=_failed_publish_result())
        report = await _generate(service)
        assert report is not None

    async def test_event_failure_tolerated_raise(self) -> None:
        """发布 raise → 宽容（报告成功——防线②）。"""
        service, _ = _make_service(publish_side_effect=RuntimeError("outbox 写失败"))
        report = await _generate(service)
        assert report is not None

    async def test_snapshot_load_failure_tolerated(self) -> None:
        """快照辅源读失败 → 容错（不阻断——与 6-5a :174 同形态）。"""
        service, mocks = _make_service()
        mocks["snapshot_repo"].load.side_effect = RuntimeError("Redis 不可达")
        report = await _generate(service)
        assert report is not None

    async def test_service_default_collection_and_tenant(self) -> None:
        """构造默认值（collection=="documents"/tenant_id==str(MVP_TENANT_ID)——OD-6 单源）。"""
        document_id = uuid.uuid4()
        chain = AsyncMock(spec=ChainOfThoughtArchiveServicePort)
        chain.query_chain_trace.return_value = _make_trace_view(["performance_gap"])
        snapshot_repo = AsyncMock(spec=SnapshotRepositoryProtocol)
        snapshot_repo.load.return_value = None
        archive_service = AsyncMock(spec=StrategicArchiveService)
        archive_service.query_archive.return_value = [_make_archive_row("performance_gap", ["chunk-d"])]
        l3 = AsyncMock(spec=L3VectorPort)
        l3.get_point.return_value = {"payload": {"document_id": str(document_id)}}
        document_repo = AsyncMock(spec=DocumentRepositoryPort)
        document_repo.find.return_value = _make_document_row(document_id, "x.pdf", [])
        renderer = MagicMock(spec=PdfRendererPort)
        renderer.render.return_value = b"%PDF"
        l4 = AsyncMock(spec=L4ObjectPort)
        l4.archive.return_value = "k"
        report_repo = AsyncMock(spec=ReportRepositoryProtocol)

        async def _save(report: Any, metadata: dict | None = None) -> Any:
            return report

        report_repo.save.side_effect = _save
        publisher = AsyncMock(spec=EventPublisher)
        publisher.publish.return_value = PublishResult(
            event_id=str(uuid.uuid4()), results=(ChannelResult("reliable", True, None),)
        )
        service = PdfReportGenerationService(
            chain_archive_service=chain,
            snapshot_repository=snapshot_repo,
            report_repository=report_repo,
            event_publisher=publisher,
            pdf_renderer=renderer,
            l4_object=l4,
            l3_vector=l3,
            document_repository=document_repo,
            archive_service=archive_service,
        )
        await service.generate_pdf_report(PLAN_ID)
        assert l3.get_point.call_args.args[0] == "documents"
        assert document_repo.find.call_args.args[0].tenant_id == str(MVP_TENANT_ID)
