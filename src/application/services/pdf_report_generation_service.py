"""PDF 报告生成服务（Story 6-5b——引文聚合三段链 + 六段编排）。

六段编排（AC-1）：①chain 归档主源聚合复用（``aggregate_report_document``
——6-5a 聚合公开化，行为零变）→ ②latest 快照辅源（容错）→ ③引文聚合
（evidence_refs 首消费三段链）→ ④PDF 渲染（``PdfRendererPort.render``——
同步调用，reportlab 纯 CPU 渲染无 I/O，量级评估：亚秒级 CPU 段在 gather
并发下互斥执行放大有限，L4/PG 侧全异步不阻塞 loop——口径维持不经
to_thread）→ ⑤L4 WORM 归档 + L2 元数据行 → ⑥``ReportGenerated`` 事件
（report_type="pdf"）。

引文三段链（AC-3/OD-6）：收集（``query_archive`` EVIDENCE_PACKAGE 行
``assumptions["evidence_refs"]`` 去重保序）→ 解析（``get_point`` →
payload.document_id str→UUID → ``find(DocumentQuery(tenant_id 注入))`` →
filename + ``metadata["chunks"]`` 匹配 page_start）→ 组装（附录 C section
追加进文档 IR）。降级三态宽容（引文是增强面非阻断面）；整体容错边界
（解析链任一依赖异常——query_archive/get_point/find 抛异常时降级空
附录 C——增强面故障不炸主链，与事件发布宽容哲学同构）。

事件发布宽容形态（AC-5）：与 6-5a ``_publish_event`` 同款代码复制为
本服务私有方法（6-5a 文件冻结不可提取共享——重复是冻结面的代价；
形态溯源 report_generation_service.py:243-276）。
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from src.application.ports.chain_of_thought_archive import CHAIN_ARCHIVE_KIND, ChainOfThoughtArchiveServicePort
from src.application.ports.pdf_report import (
    APPENDIX_C_TITLE,
    EVIDENCE_BUCKET_TYPE,
    PDF_OBJECT_KEY_TEMPLATE,
    PdfRendererPort,
)
from src.application.services.agent_workflow_context import MVP_TENANT_ID
from src.application.services.report_generation_service import (
    BLM_PLANNING_SESSION_PREFIX,
    aggregate_report_document,
)
from src.application.services.strategic_archive_service import StrategicArchiveService
from src.domain.entities.strategic_archive import ArchiveType
from src.domain.entities.strategic_report import ReportType, StrategicReport
from src.domain.events.workflow_events import ReportGenerated
from src.domain.exceptions import (
    PdfRenderingError,
    ReportEvidenceStorageError,
    ReportGenerationError,
    ReportStorageError,
)
from src.domain.ports.archive_repository import ArchiveQuery
from src.domain.ports.document_repository import DocumentQuery, DocumentRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.report_repository import ReportRepositoryProtocol
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.value_objects.citation_entry import CitationEntry
from src.domain.value_objects.markdown_report import (
    MarkdownReportDocument,
    ReportBlock,
    ReportSection,
)

__all__ = ["PdfReportGenerationService"]

logger = logging.getLogger(__name__)

#: 引文收集显式 limit（八步现值 8 行虽低于 ArchiveQuery 默认 20，显式传参为
#: 未来同型行扩展余量——对齐 6-4 ``_TRACE_QUERY_LIMIT=50`` 显式传参先例）
_CITATION_QUERY_LIMIT: int = 64

#: 附录 C 降态占位文案（两降级态冻结——AC-3 增量冻结表钦定；status 值域
#: 三元组冻结使映射键完备，resolved 态走 filename 不经此映射）
_UNAVAILABLE_TEXTS: dict[str, str] = {
    "point_missing": "[溯源不可用：检索点缺失]",
    "document_missing": "[溯源不可用：文档记录缺失]",
}

#: 附录 C 表头四列（增量冻结表钦定）
_CITATION_TABLE_HEADERS: tuple[str, ...] = ("#", "文档名", "页码", "切片标识")

#: 附录 C 切片标识列显示截断长度（chunk_id 前 8 位——完整值入 L2 metadata）
_CHUNK_ID_DISPLAY_LENGTH: int = 8

#: WORM 保留天数（7 年——architecture §10.1 报告交付物审计语义；与 L4 端口
#: 默认值同值显式传参——调用点值级断言锚）
_RETENTION_DAYS: int = 2555

#: archived_at 可空列的排序下界（None 回落 epoch——6-4 query_chain_trace 同款）
_EPOCH_FLOOR = datetime.min.replace(tzinfo=timezone.utc)


class PdfReportGenerationService:
    """PDF 报告生成服务（``PdfReportGenerationServicePort`` 实现——六段编排）。

    九依赖 keyword-only 注入（R2 具体应用端口组合 R1 基础端口 L3/L4/
    DocumentRepository + 既有应用端口）；collection/tenant_id 是服务构造
    参数（配置态注入非依赖态——测试覆写注入通道，生产走组合根默认值）。
    服务无状态（SINGLETON 并发共享安全——引文解析局部累积清单与 6-5a
    附录 B 登记清单同纪律，禁持每次调用的可变实例态——AC-7）。
    """

    def __init__(
        self,
        *,
        chain_archive_service: ChainOfThoughtArchiveServicePort,
        snapshot_repository: SnapshotRepositoryProtocol,
        report_repository: ReportRepositoryProtocol,
        event_publisher: EventPublisher,
        pdf_renderer: PdfRendererPort,
        l4_object: L4ObjectPort,
        l3_vector: L3VectorPort,
        document_repository: DocumentRepositoryPort,
        archive_service: StrategicArchiveService,
        collection: str = "documents",
        tenant_id: str = str(MVP_TENANT_ID),
    ) -> None:
        """初始化服务（九依赖 + 两配置参数）。

        Args:
            chain_archive_service: chain 归档服务（聚合主源）。
            snapshot_repository: 快照仓储（辅源）。
            report_repository: L2 报告元数据仓储。
            event_publisher: 事件发布器（宽容语义）。
            pdf_renderer: PDF 渲染器（同步纯 CPU）。
            l4_object: L4 对象存储端口（WORM 归档）。
            l3_vector: L3 向量检索端口（引文解析①get_point）。
            document_repository: documents 仓储（引文解析②find）。
            archive_service: 战略档案服务（query_archive——assumptions 读径；
                注入具体类：application 同层引用合法）。
            collection: 引文检索 collection（默认 "documents"——与 chunk
                索引写侧 collection 字面量对齐，非 BLM_SEARCH_COLLECTION
                env 传导（env 覆写只影响检索服务侧））。
            tenant_id: 引文链租户（默认 str(MVP_TENANT_ID)——DocumentQuery
                必填且 PG find 硬过滤，数据链无租户可用注入是唯一来源）。
        """
        self._chain_archive_service = chain_archive_service
        self._snapshot_repository = snapshot_repository
        self._report_repository = report_repository
        self._event_publisher = event_publisher
        self._pdf_renderer = pdf_renderer
        self._l4_object = l4_object
        self._l3_vector = l3_vector
        self._document_repository = document_repository
        self._archive_service = archive_service
        self._collection = collection
        self._tenant_id = tenant_id

    async def generate_pdf_report(self, plan_id: uuid.UUID) -> StrategicReport:
        """按 plan_id 生成 PDF 报告（六段编排——AC-1）。

        Args:
            plan_id: 规划任务标识。

        Returns:
            StrategicReport 实体（report_type=PDF、file_path=L4 对象键逻辑路径）。

        Raises:
            ReportGenerationError: 490——数据源全缺（chain total==0 两形态同判）。
            PdfRenderingError: 492——渲染失败（reportlab 原生异常领域包装）。
            ReportEvidenceStorageError: 493——L4 证据归档失败。
            ReportStorageError: 491（layer="l2"）——L2 元数据行落库失败。
        """
        started = time.perf_counter()
        # ① 聚合主源（空档案 total==0 → 490——两形态同判）
        trace = await self._chain_archive_service.query_chain_trace(plan_id)
        if trace.total == 0:
            raise ReportGenerationError(plan_id=str(plan_id))
        # ② latest 快照辅源（缺失/读失败同形态容错）
        snapshot = await self._load_snapshot(plan_id)
        # ③ 引文聚合（整体容错——增强面故障不炸主链）
        citations, stage_of = await self._aggregate_citations(plan_id)
        # ③④ 聚合复用 + 附录 C 组装进 IR + 渲染（同步纯 CPU）
        aggregation = aggregate_report_document(str(plan_id), trace.records, snapshot, started)
        document = self._append_citation_section(aggregation.document, citations)
        report_id = uuid.uuid4()
        # ④ 渲染（492 包装）
        try:
            pdf_bytes = self._pdf_renderer.render(document)
        except Exception as error:
            raise PdfRenderingError(plan_id=str(plan_id), cause=error) from error
        # ⑤ L4 WORM 归档（493 包装）——Story 钦定顺序：渲染→L4→实体构造→L2 save
        object_key = PDF_OBJECT_KEY_TEMPLATE.format(plan_id=plan_id, report_id=report_id)
        try:
            await self._l4_object.archive(
                bucket_type=EVIDENCE_BUCKET_TYPE,
                object_key=object_key,
                content=pdf_bytes,
                retention_days=_RETENTION_DAYS,
            )
        except Exception as error:
            raise ReportEvidenceStorageError(plan_id=str(plan_id), cause=error) from error
        # 实体构造（generation_ms 终点紧贴 L2 落库——含渲染+L4 段，6-5a 同款
        # 窗口口径；与聚合 metadata「执行耗时」行双窗口辨析：前者是实体字段、
        # 后者是元信息表行，终点同源；与 P95 窗口【聚合起点→事件发布返回】
        # 起点/终点均异的采样统计口径）
        generation_ms = int((time.perf_counter() - started) * 1000)
        report = StrategicReport(
            report_id=report_id,
            plan_id=str(plan_id),
            report_type=ReportType.PDF,
            file_path=object_key,
            section_count=self._count_sections(document),
            degraded_section_count=aggregation.degraded_count,
            generation_ms=generation_ms,
        )
        # ⑤b L2 元数据行（491 layer="l2"——L2 落库失败语义精确归宿）
        metadata: dict[str, Any] = dict(aggregation.metadata)
        metadata["citation_count"] = len(citations)
        metadata["unresolvable_citation_count"] = sum(1 for c in citations if c.status != "resolved")
        metadata["citations"] = [
            {**self._citation_to_dict(entry), "stage": stage_of.get(entry.chunk_id, "")} for entry in citations
        ]
        try:
            await self._report_repository.save(report, metadata=metadata)
        except Exception as error:
            raise ReportStorageError(layer="l2", cause=error) from error
        # ⑥ 事件发布（宽容语义）
        await self._publish_event(report)
        return report

    # ------------------------------------------------------------------
    # 引文聚合三段链（AC-3）
    # ------------------------------------------------------------------

    async def _aggregate_citations(self, plan_id: uuid.UUID) -> tuple[list[CitationEntry], dict[str, str]]:
        """引文聚合三段链（整体容错——降级空清单不炸主链）。

        Args:
            plan_id: 规划任务标识。

        Returns:
            (引文条目清单, chunk_id→首现步骤名映射)；整体故障时空清单——
            citation_count==0。
        """
        try:
            archives = await self._archive_service.query_archive(
                ArchiveQuery(
                    plan_id=plan_id,
                    archive_type=ArchiveType.EVIDENCE_PACKAGE,
                    limit=_CITATION_QUERY_LIMIT,
                )
            )
        except Exception as error:
            logger.warning("引文收集降级（归档库不可达——空附录 C 不阻断报告）: plan_id=%s error=%s", plan_id, error)
            return [], {}
        # archived_at 升序（首现次序=归档写入序——与 6-4 query_chain_trace 同款
        # 排序；None 回落 epoch 下界保证稳定性）
        ordered_rows = sorted(archives, key=lambda archive: archive.archived_at or _EPOCH_FLOOR)
        ordered: list[str] = []
        stage_of: dict[str, str] = {}
        for archive in ordered_rows:
            basis = archive.decision_basis or {}
            if basis.get("kind") != CHAIN_ARCHIVE_KIND:
                continue
            stage = str(basis.get("stage", ""))
            refs = (archive.assumptions or {}).get("evidence_refs", [])
            if not isinstance(refs, list):
                continue
            for chunk_id in refs:
                if not isinstance(chunk_id, str) or not chunk_id:
                    continue
                if chunk_id not in stage_of:
                    ordered.append(chunk_id)
                    stage_of[chunk_id] = stage
        entries: list[CitationEntry] = []
        for position, chunk_id in enumerate(ordered, start=1):
            entry = await self._resolve_citation(position, chunk_id, stage_of[chunk_id])
            if entry is None:
                return [], {}
            entries.append(entry)
        return entries, stage_of

    async def _resolve_citation(self, index: int, chunk_id: str, stage: str) -> CitationEntry | None:
        """解析单条引文（三态降级判定——整体容错边界内逐条降级）。

        Args:
            index: 引文索引（去重保序首现次序）。
            chunk_id: 切片标识。
            stage: 首现步骤名（步骤归属信息——OD-6）。

        Returns:
            引文条目；解析链依赖异常时 None（整体降级空清单——上层中断迭代）。

        Raises:
            无外抛——解析链依赖异常在本方法内捕获转为整体降级信号。
        """
        try:
            point = await self._l3_vector.get_point(self._collection, chunk_id)
        except Exception as error:
            logger.warning(
                "引文解析整体降级（检索服务不可达——空附录 C 不阻断报告）: plan_id 上下文 chunk=%s error=%s",
                chunk_id,
                error,
            )
            return None
        if point is None:
            return CitationEntry(
                index=index,
                document_id="",
                chunk_id=chunk_id,
                filename="",
                page=0,
                status="point_missing",
            )
        payload = point.get("payload") or {}
        document_id_raw = payload.get("document_id")
        document_id = str(document_id_raw) if document_id_raw else ""
        if not document_id:
            return CitationEntry(
                index=index,
                document_id="",
                chunk_id=chunk_id,
                filename="",
                page=0,
                status="point_missing",
            )
        try:
            document_uuid = uuid.UUID(document_id)
        except ValueError:
            return CitationEntry(
                index=index,
                document_id="",
                chunk_id=chunk_id,
                filename="",
                page=0,
                status="point_missing",
            )
        # find 与 get_point 同形态容错（解析链任一依赖异常 → 整体降级空附录 C
        # ——增强面故障不炸主链，R2D-1 整体容错边界）
        try:
            document = await self._document_repository.find(DocumentQuery(tenant_id=self._tenant_id, document_id=document_uuid))
        except Exception as error:
            logger.warning(
                "引文解析整体降级（文档库不可达——空附录 C 不阻断报告）: chunk=%s error=%s",
                chunk_id,
                error,
            )
            return None
        if document is None:
            return CitationEntry(
                index=index,
                document_id="",
                chunk_id=chunk_id,
                filename="",
                page=0,
                status="document_missing",
            )
        # chunks/page_start 脏形态守卫（JSONB 外部可写面——None/非 list/非 int
        # 一律降级 page=0；与 uuid.UUID 守卫同密度。负数 page_start 经守卫
        # 降 0，顺带消除 int() 解析后触发 VO 242（page<0）炸链的潜在路径）
        page = 0
        chunks_meta = document.metadata.get("chunks")
        if isinstance(chunks_meta, list):
            for chunk_meta in chunks_meta:
                if isinstance(chunk_meta, dict) and str(chunk_meta.get("chunk_id", "")) == chunk_id:
                    raw_page = chunk_meta.get("page_start")
                    if isinstance(raw_page, int) and not isinstance(raw_page, bool) and raw_page > 0:
                        page = raw_page
                    break
        return CitationEntry(
            index=index,
            document_id=document_id,
            chunk_id=chunk_id,
            filename=document.filename,
            page=page,
            status="resolved",
        )

    def _append_citation_section(
        self, document: MarkdownReportDocument, citations: list[CitationEntry]
    ) -> MarkdownReportDocument:
        """组装附录 C section 追加进文档 IR（table 四列/空态 callout）。

        Args:
            document: 聚合产物 IR（不可变 VO——经替换构造追加）。
            citations: 引文条目清单。

        Returns:
            追加附录 C 后的新文档 IR。
        """
        if citations:
            rows = tuple(
                (
                    str(entry.index),
                    entry.filename if entry.status == "resolved" else _UNAVAILABLE_TEXTS[entry.status],
                    f"p.{entry.page}" if entry.status == "resolved" and entry.page > 0 else "-",
                    entry.chunk_id[:_CHUNK_ID_DISPLAY_LENGTH],
                )
                for entry in citations
            )
            block = ReportBlock(kind="table", headers=_CITATION_TABLE_HEADERS, rows=rows)
        else:
            block = ReportBlock(kind="callout", text="本报告无检索证据引用")
        section = ReportSection(title=APPENDIX_C_TITLE, level=2, blocks=(block,))
        return MarkdownReportDocument(
            plan_id=document.plan_id,
            title=document.title,
            meta_rows=document.meta_rows,
            sections=(*document.sections, section),
            toc_enabled=document.toc_enabled,
        )

    @staticmethod
    def _citation_to_dict(entry: CitationEntry) -> dict[str, Any]:
        """引文条目转 L2 metadata 字典（七键——6-8/6-7 查询面）。

        Args:
            entry: 引文条目。

        Returns:
            七键字典（index/document_id/chunk_id/filename/page/status/stage——
            stage 由调用方上下文合入，见 _aggregate_citations 组装位）。
        """
        return {
            "index": entry.index,
            "document_id": entry.document_id,
            "chunk_id": entry.chunk_id,
            "filename": entry.filename,
            "page": entry.page,
            "status": entry.status,
        }

    @staticmethod
    def _count_sections(document: MarkdownReportDocument) -> int:
        """正文章节数（H3 小节口径——与 6-5a 恒 11 同源派生；附录 C 是 H2 附录不计入）。

        Args:
            document: 文档 IR。

        Returns:
            level==3 小节数。
        """
        return sum(1 for section in document.sections if section.level == 3)

    # ------------------------------------------------------------------
    # 辅源/事件（6-5a 同款形态复制——冻结面代价）
    # ------------------------------------------------------------------

    async def _load_snapshot(self, plan_id: uuid.UUID) -> Any:
        """加载 latest 快照（容错——异常与缺失同形态返回 None）。

        Args:
            plan_id: 规划任务标识。

        Returns:
            CheckpointSnapshot 或 None（读失败不阻断报告生成）。
        """
        try:
            return await self._snapshot_repository.load(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}")
        except Exception as error:
            logger.warning("latest 快照读取失败（附录 A 省略——辅源容错）: plan_id=%s error=%s", plan_id, error)
            return None

    async def _publish_event(self, report: StrategicReport) -> None:
        """发布 ReportGenerated（宽容语义——双防线失败检出 + warning 不上抛）。

        同款代码复制（6-5a report_generation_service.py:243-276 形态溯源——
        该文件冻结不可提取共享）；构造点显式传三键（事件类三键有缺省空串，
        漏传不炸产空串事件，唯一防线在构造点）。

        Args:
            report: 报告实体。
        """
        event = ReportGenerated(
            report_id=report.report_id,
            report_type=report.report_type.value,
            file_path=report.file_path,
        )
        try:
            result = await self._event_publisher.publish(event)
            if not result.is_success:
                logger.warning(
                    "ReportGenerated 发布降级（报告已落盘不回滚）: report_id=%s event_type=%s error=%s",
                    report.report_id,
                    event.event_type,
                    result.partial_error,
                )
        except Exception as error:
            logger.warning(
                "ReportGenerated 发布降级（报告已落盘不回滚）: report_id=%s event_type=%s error=%s",
                report.report_id,
                event.event_type,
                error,
            )
