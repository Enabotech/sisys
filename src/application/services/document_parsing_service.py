"""应用层文档解析服务

编排文档解析流程：获取文档 → MinIO 下载 → 临时文件桥接 → 解析 → 版面检测（可选）→ 表格语义提取（可选）→ 状态更新 → 事件发布。
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
from dataclasses import replace
from typing import TYPE_CHECKING

from src.domain.entities.document import Document, ParseStatus
from src.domain.events.document_events import DocumentProcessed
from src.domain.exceptions.ocr_exceptions import OCRConnectionError, OCRProcessingError
from src.domain.ports.document_repository import DocumentQuery
from src.domain.services.scanned_page_detector import detect_scanned_pages
from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage, ParsedTable

if TYPE_CHECKING:
    import redis.asyncio as aioredis

    from src.application.ports.document_storage_port import DocumentStoragePort
    from src.domain.ports.document_parser import DocumentParserPort
    from src.domain.ports.document_repository import DocumentRepositoryPort
    from src.domain.ports.event_publisher import EventPublisher
    from src.domain.ports.layout_detector import LayoutDetector
    from src.domain.ports.ocr import OCRPort
    from src.domain.ports.pdf_page_renderer import PdfPageRendererPort
    from src.domain.ports.table_extractor import TableExtractorPort

logger = logging.getLogger(__name__)

_ALLOWED_TEMP_SUFFIXES = frozenset(
    {
        ".pdf",
        ".docx",
        ".txt",
        ".tmp",
        ".pptx",
        ".xlsx",
        ".csv",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".tiff",
        ".tif",
        ".html",
        ".htm",
        ".md",
        ".rtf",
    }
)


class DocumentParsingService:
    """文档解析编排服务

    编排完整的文档解析流程：
    1. 从仓储获取 Document 实体
    2. 从 MinIO 下载文件到临时文件（桥接 AsyncIterator → file_path）
    3. 调用解析器获取 ParsedDocument
    4. 更新 Document 状态和元数据
    5. 发布 DocumentProcessed 事件
    6. 清理临时文件
    """

    _LOCK_TTL = 600  # 分布式锁 TTL（秒）= 解析 300s + 下载 120s + 缓冲 180s

    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        document_storage: DocumentStoragePort,
        event_publisher: EventPublisher,
        document_parser: DocumentParserPort,
        redis_client: "aioredis.Redis | None" = None,
        layout_detector: "LayoutDetector | None" = None,
        pdf_page_renderer: "PdfPageRendererPort | None" = None,
        table_extractor: "TableExtractorPort | None" = None,
        ocr: "OCRPort | None" = None,
    ) -> None:
        self._repository = document_repository
        self._storage = document_storage
        self._publisher = event_publisher
        self._parser = document_parser
        self._redis = redis_client
        self._layout_detector = layout_detector
        self._pdf_page_renderer = pdf_page_renderer
        self._table_extractor = table_extractor
        self._ocr = ocr

    async def parse_document(self, document_id: uuid.UUID, tenant_id: str) -> Document:
        """解析文档

        Args:
            document_id: 文档 ID
            tenant_id: 租户标识符

        Returns:
            更新后的 Document 实体
        """
        query = DocumentQuery(tenant_id=tenant_id, document_id=document_id)
        document = await self._repository.find(query)

        if document is None:
            logger.warning("文档不存在 (document_id=%s, tenant=%s)", document_id, tenant_id)
            return Document(
                document_id=document_id,
                filename="",
                parse_status=ParseStatus.FAILED,
                metadata={"parse_error": "文档不存在"},
            )

        # 检查 storage_object_key
        object_key = document.metadata.get("storage_object_key")
        if not object_key:
            logger.warning("文档缺少 storage_object_key (document_id=%s)", document_id)
            document.parse_status = ParseStatus.FAILED
            document.metadata["parse_error"] = "文档缺少 storage_object_key"
            await self._repository.save(document)  # 持久化失败状态，避免文档永久 PENDING
            return document

        # 分布式锁：防止多实例并发处理同一文档（Redis SET NX，对标 DualIdempotencyChecker 模式）
        lock_acquired = False
        lock_key = f"docparse:lock:{document_id}"
        temp_path = ""

        try:
            if self._redis is not None:
                lock_acquired = (await self._redis.set(lock_key, "1", nx=True, ex=self._LOCK_TTL)) or False
                if not lock_acquired:
                    logger.info("文档 %s 正在被其他实例处理，跳过", document_id)
                    return document

            # 乐观锁：仅当状态为 PENDING 时才更新为 IN_PROGRESS
            if document.parse_status != ParseStatus.PENDING:
                # 已被其他调用处理，跳过
                return document

            document.parse_status = ParseStatus.IN_PROGRESS
            await self._repository.save(document)

            # 下载文件到临时文件（120 秒超时，覆盖慢速 MinIO 连接）
            temp_path = await asyncio.wait_for(
                self._download_to_temp("raw-documents", object_key),
                timeout=120.0,
            )

            # 解析文档（CPU 密集型，使用线程池避免阻塞事件循环，300 秒超时）
            parsed_doc = await asyncio.wait_for(
                asyncio.to_thread(self._parser.parse, temp_path, document.mime_type),
                timeout=300.0,
            )

            # 用真实文档 ID 覆盖解析器随机生成的 ID
            parsed_doc = replace(parsed_doc, document_id=str(document.document_id))

            if parsed_doc.is_failed():
                document.parse_status = ParseStatus.FAILED
                document.metadata["parse_error"] = parsed_doc.error_message or "解析失败"
                await self._repository.save(document)
                return document

            # 版面检测增强（仅 PDF + layout_detector 注入时触发，运行时错误不阻断解析）
            parsed_doc = await self._apply_layout_detection(parsed_doc, temp_path, document.mime_type)

            # 表格语义提取增强（table_extractor 注入时触发，运行时错误不阻断解析）
            parsed_doc = await self._apply_table_extraction(parsed_doc, temp_path, document.mime_type)

            # OCR 解析增强（ocr 端口注入时触发，对扫描件执行 OCR 识别，运行时错误不阻断解析）
            parsed_doc, ocr_metadata = await self._apply_ocr(parsed_doc, temp_path, document.mime_type)

            # OCR 失败时提前返回（解析状态为 FAILED）
            if parsed_doc.is_failed():
                document.parse_status = ParseStatus.FAILED
                document.metadata["parse_error"] = parsed_doc.error_message or "OCR 解析失败"
                await self._repository.save(document)
                return document

            # 更新状态和元数据
            document.parse_status = ParseStatus.COMPLETED
            result_dict = parsed_doc.to_dict()
            # 将 OCR 元数据合并到 parse_result（AC-4 要求持久化）
            if ocr_metadata:
                result_dict["ocr_metadata"] = ocr_metadata
            document.metadata["parse_result"] = result_dict
            saved_doc = await self._repository.save(document)

            # 发布事件
            event = DocumentProcessed(
                document_id=saved_doc.document_id,
                parse_result=result_dict,
                tenant_id=tenant_id,
            )
            await self._publisher.publish(event)

            return saved_doc

        except asyncio.TimeoutError:
            document.parse_status = ParseStatus.FAILED
            document.metadata["parse_error"] = "文档解析超时，请重试"
            await self._repository.save(document)
            logger.warning("文档解析超时 (document_id=%s, tenant=%s)", document_id, tenant_id)
            return document

        except asyncio.CancelledError:
            document.parse_status = ParseStatus.FAILED
            document.metadata["parse_error"] = "文档解析被取消"
            try:
                await self._repository.save(document)
            except Exception:
                logger.warning("取消路径中状态持久化失败: %s", document_id, exc_info=True)
            logger.warning("文档解析被取消 (document_id=%s, tenant=%s)", document_id, tenant_id)
            raise

        except Exception:
            document.parse_status = ParseStatus.FAILED
            document.metadata["parse_error"] = "文档解析失败，请检查文件是否损坏或重试"
            await self._repository.save(document)
            logger.exception("文档解析异常 (document_id=%s, tenant=%s)", document_id, tenant_id)
            return document

        finally:
            if lock_acquired and self._redis is not None:
                try:
                    await self._redis.delete(lock_key)
                except Exception:
                    logger.warning("分布式锁释放失败: %s", lock_key, exc_info=True)
            if temp_path:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass  # 文件不存在，清理成功
                except OSError as e:
                    logger.warning("临时文件清理失败: %s - %s", temp_path, e)

    async def _download_to_temp(self, bucket_type: str, object_key: str) -> str:
        """从 MinIO 下载文件到临时文件

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键

        Returns:
            临时文件路径
        """
        # 后缀白名单校验（防止恶意文件类型）
        ext = os.path.splitext(object_key)[1].lower() or ".tmp"
        if ext not in _ALLOWED_TEMP_SUFFIXES:
            ext = ".tmp"
        stream = self._storage.retrieve(bucket_type, object_key)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        try:
            os.fchmod(tmp.fileno(), 0o600)  # 文件描述符级权限设置，消除 chmod TOCTOU 窗口（移入 try 防止 FD 泄漏）
            buffer = bytearray()
            try:
                async for chunk in stream:
                    buffer.extend(chunk)
                    if len(buffer) >= 65536:  # 64KB 刷新阈值，减少线程池调用频率
                        await asyncio.to_thread(tmp.write, bytes(buffer))
                        buffer.clear()
                if buffer:  # 剩余字节
                    await asyncio.to_thread(tmp.write, bytes(buffer))
            finally:
                if hasattr(stream, "aclose"):
                    await stream.aclose()  # 显式关闭流，防止 MinIO 连接泄漏
            await asyncio.to_thread(tmp.close)
            return tmp.name
        except (Exception, asyncio.CancelledError):
            tmp.close()
            if os.path.exists(tmp.name):
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass  # 清理失败时静默处理，正要抛出原异常
            raise

    async def _apply_layout_detection(
        self,
        parsed_doc: ParsedDocument,
        file_path: str,
        mime_type: str,
    ) -> ParsedDocument:
        """对已解析文档应用版面检测增强（仅 PDF 格式，逐页独立降级）

        算法流程：
        1. 检查 layout_detector 和 pdf_page_renderer 是否已注入
        2. 仅 PDF 格式触发检测，其他格式跳过
        3. 逐页渲染 PDF 页面为 PNG → 调用 detect() → 顺序匹配 → 填充 bbox
        4. 单页检测失败不影响其他页面（逐页独立 try/except）
        5. 运行时错误不阻断解析流程（记录日志并返回原文档）

        MVP 匹配策略：
        - 当前 PDFParser 不输出 bbox（均为 None），无法做 IoU 空间匹配
        - 降级为按顺序一一对应检测结果与文本/表格元素
        - 当 PDFParser 未来输出非 None bbox 时，应替换为 layout_matching.match_detections()
        - Table 标签检测结果按顺序映射到 ParsedTable.bbox

        Args:
            parsed_doc: 已完成文本解析的 ParsedDocument
            file_path: PDF 文件临时路径
            mime_type: 文件 MIME 类型

        Returns:
            增强后的 ParsedDocument（bbox 字段已填充）或原文档（降级时）
        """
        # 降级条件：layout_detector 或 pdf_page_renderer 未注入
        if self._layout_detector is None or self._pdf_page_renderer is None:
            return parsed_doc

        # 降级条件：非 PDF 格式
        if mime_type != "application/pdf":
            return parsed_doc

        enhanced_pages: list[ParsedPage] = []
        for page in parsed_doc.pages:
            try:
                # 渲染 PDF 页面为 PNG 图像
                image_bytes = await asyncio.to_thread(self._pdf_page_renderer.render_page, file_path, page.page_number)

                # 版面检测
                detections = await asyncio.to_thread(self._layout_detector.detect, image_bytes, page.page_number)

                if not detections:
                    # 无检测结果，保持原页不变
                    enhanced_pages.append(page)
                    continue

                # 筛选 Table 和非 Table 检测结果，分别处理
                table_detections = [d for d in detections if d.label == "Table"]
                text_detections = [d for d in detections if d.label != "Table"]

                # 处理文本元素 bbox 填充
                enhanced_texts = self._apply_text_detections(page.texts, text_detections)

                # 处理表格元素 bbox 填充
                enhanced_tables = self._apply_table_detections(page.tables, table_detections)

                enhanced_pages.append(
                    ParsedPage(
                        page_number=page.page_number,
                        texts=enhanced_texts,
                        tables=enhanced_tables,
                        images=page.images,
                    )
                )

            except Exception:
                # 单页检测失败不影响其他页面，保留原始页面继续处理
                logger.warning("第 %d 页版面检测失败，跳过该页增强", page.page_number, exc_info=True)
                enhanced_pages.append(page)

        return replace(parsed_doc, pages=enhanced_pages)

    async def _apply_table_extraction(
        self,
        parsed_doc: ParsedDocument,
        file_path: str,
        mime_type: str,
    ) -> ParsedDocument:
        """对已解析文档应用表格语义提取增强

        降级策略（与 _apply_layout_detection 对齐）：
        1. table_extractor 未注入（None）→ 跳过增强，保留原始 tables
        2. 运行时异常 → WARNING 日志 + 返回原文档（解析状态不受影响）
        3. 初始化失败（ImportError）→ 由 composition_root 处理，此处不涉及

        Args:
            parsed_doc: 已完成解析的 ParsedDocument
            file_path: 文档临时文件路径
            mime_type: 文档 MIME 类型

        Returns:
            增强后的 ParsedDocument 或原文档（降级时）
        """
        # 降级条件：table_extractor 未注入
        if self._table_extractor is None:
            return parsed_doc

        # 收集所有页面中的表格
        all_tables: list[ParsedTable] = []
        for page in parsed_doc.pages:
            all_tables.extend(page.tables)

        if not all_tables:
            return parsed_doc

        try:
            # 调用 table_extractor 进行语义增强
            enhanced_tables = await asyncio.to_thread(
                self._table_extractor.extract,
                file_path,
                mime_type,
                all_tables,
            )

            # 将增强后的表格重新分配到各页面
            enhanced_pages: list[ParsedPage] = []
            table_idx = 0
            for page in parsed_doc.pages:
                original_count = len(page.tables)
                page_tables = enhanced_tables[table_idx : table_idx + original_count]
                table_idx += original_count
                enhanced_pages.append(
                    ParsedPage(
                        page_number=page.page_number,
                        texts=page.texts,
                        tables=page_tables if page_tables else page.tables,
                        images=page.images,
                    )
                )

            return replace(parsed_doc, pages=enhanced_pages)

        except Exception:
            # 运行时异常降级：WARNING 日志 + 返回原文档
            logger.warning(
                "表格语义提取失败，降级保留原始表格（文档 MIME=%s）",
                mime_type,
                exc_info=True,
            )
            return parsed_doc

    @staticmethod
    def _apply_text_detections(
        elements: list[ParsedElement],
        detections: list,
    ) -> list[ParsedElement]:
        """将非 Table 检测结果按顺序映射到文本元素的 bbox

        MVP 降级策略：由于 PDFParser 当前不输出 bbox（均为 None），
        无法使用 IoU 空间匹配，采用顺序索引一一对应。

        Args:
            elements: 文本元素列表
            detections: 非 Table 类型的检测结果列表

        Returns:
            增强后的文本元素列表
        """
        if not elements:
            return elements

        enhanced: list[ParsedElement] = []
        for idx, elem in enumerate(elements):
            if idx < len(detections) and elem.bbox is None:
                det = detections[idx]
                enhanced.append(
                    ParsedElement(
                        content=elem.content,
                        bbox=det.bbox,
                        confidence=elem.confidence,
                        metadata={
                            **elem.metadata,
                            "layout_confidence": det.confidence,
                        },
                    )
                )
            else:
                enhanced.append(elem)
        return enhanced

    @staticmethod
    def _apply_table_detections(
        tables: list[ParsedTable],
        table_detections: list,
    ) -> list[ParsedTable]:
        """将 Table 标签检测结果按顺序映射到 ParsedTable 的 bbox

        DocLayNet 映射：label='Table' 的检测结果映射到 ParsedTable.bbox。
        MVP 降级策略：顺序索引一一对应。

        Args:
            tables: 表格元素列表
            table_detections: label='Table' 的检测结果列表

        Returns:
            增强后的表格元素列表
        """
        if not tables or not table_detections:
            return tables

        enhanced: list[ParsedTable] = []
        for idx, table in enumerate(tables):
            if idx < len(table_detections) and table.bbox is None:
                det = table_detections[idx]
                enhanced.append(
                    ParsedTable(
                        rows=table.rows,
                        bbox=det.bbox,
                        confidence=table.confidence,
                        metadata={
                            **table.metadata,
                            "layout_confidence": det.confidence,
                        },
                    )
                )
            else:
                enhanced.append(table)
        return enhanced

    async def _apply_ocr(
        self,
        parsed_doc: ParsedDocument,
        file_path: str,
        mime_type: str,
    ) -> tuple[ParsedDocument, dict]:
        """对已解析文档应用 OCR 增强（扫描件 PDF 识别）

        算法流程：
        0. OCR 端口未注入时静默跳过
        1. 文件大小守卫：仅对 ≤ 50MB 的文件执行 OCR，50-100MB 的 PDF 跳过并记录 WARNING
        2. 调用 detect_scanned_pages() 识别需要 OCR 的页码
        3. 无扫描页时直接返回
        4. 调用 OCRPort.recognize() 执行 OCR 识别
        5. 部分页失败处理：成功页合并回 ParsedDocument，失败页保持原始状态
        6. 标记低置信度元素（needs_review）
        7. OCR 标签隔离：block_label 暂存到 metadata["ocr_block_label"]

        Args:
            parsed_doc: 已完成解析的 ParsedDocument
            file_path: 文档临时文件路径
            mime_type: 文档 MIME 类型

        Returns:
            (OCR 增强后的 ParsedDocument 或原文档（降级时）, OCR 元数据字典)
        """
        # 降级条件：ocr 端口未注入
        if self._ocr is None:
            return parsed_doc, {}

        # 文件大小守卫：仅对 ≤ 50MB 的文件执行 OCR
        # 使用领域层常量，避免直接依赖基础设施层
        from src.domain.ports.ocr import OCR_MAX_BYTES

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            logger.warning("OCR 步骤无法获取文件大小，跳过 OCR: %s", file_path, exc_info=True)
            return parsed_doc, {}

        # 0 字节文件：跳过 OCR，记录 WARNING
        if file_size == 0:
            logger.warning("空文件跳过 OCR: %s", file_path)
            return parsed_doc, {}

        # 50-100MB：跳过 OCR，记录 WARNING
        # MAX_PDF_BYTES 为 100MB，在此用于检测 50-100MB 的 PDF 文件
        max_pdf_bytes = 100 * 1024 * 1024  # 100MB

        if file_size > OCR_MAX_BYTES:
            if file_size <= max_pdf_bytes and mime_type == "application/pdf":
                logger.warning(
                    "PDF 文件大小 %dMB 超过 OCR 限制 %dMB，跳过 OCR 步骤（基础解析不受影响）",
                    file_size // (1024 * 1024),
                    OCR_MAX_BYTES // (1024 * 1024),
                )
                return parsed_doc, {}
            logger.warning(
                "文件大小 %dMB 超过 OCR 限制 %dMB，跳过 OCR 步骤",
                file_size // (1024 * 1024),
                OCR_MAX_BYTES // (1024 * 1024),
            )
            return parsed_doc, {}

        try:
            # 扫描页检测
            scanned_pages = detect_scanned_pages(parsed_doc.pages)
            if not scanned_pages:
                logger.info("未检测到扫描页，跳过 OCR 步骤")
                return parsed_doc, {}

            logger.info("检测到扫描页: %s，执行 OCR 识别", scanned_pages)

            # 调用 OCR 识别（OCRPort.recognize 为 async def，直接 await）
            ocr_results = await self._ocr.recognize(file_path, scanned_pages)

            if not ocr_results:
                logger.info("OCR 返回空结果，保持原始文档状态")
                return parsed_doc, {}

            # 按页合并 OCR 结果
            page_map = {r.page_number: r for r in ocr_results}
            ocr_pages: list[ParsedPage] = []
            failed_pages: list[int] = []

            for page in parsed_doc.pages:
                if page.page_number in page_map:
                    ocr_page_result = page_map[page.page_number]
                    # 标记低置信度元素
                    elements = self._mark_low_confidence(ocr_page_result.elements)
                    ocr_pages.append(
                        ParsedPage(
                            page_number=page.page_number,
                            texts=elements,
                            tables=page.tables,
                            images=page.images,
                        )
                    )
                elif page.page_number in scanned_pages:
                    # 扫描页但 OCR 未返回结果 → 部分页失败
                    failed_pages.append(page.page_number)
                    ocr_pages.append(page)
                else:
                    # 非扫描页，保持原样
                    ocr_pages.append(page)

            parsed_doc = replace(parsed_doc, pages=ocr_pages)

            # 构建 OCR 元数据（用于持久化到 Document.metadata["parse_result"]）
            ocr_metadata: dict = {
                "ocr_engine": "paddleocr-vl",
                "ocr_scanned_pages": scanned_pages,
                "ocr_processed_pages": list(page_map.keys()),
            }
            if failed_pages:
                ocr_metadata["ocr_failed_pages"] = failed_pages
                ocr_metadata["partial_ocr_failure"] = True

            return parsed_doc, ocr_metadata

        except OCRConnectionError:
            # OCR 服务不可达：返回 FAILED 状态，不泄露内部细节
            logger.warning("OCR 服务不可用，扫描件解析失败: %s", mime_type, exc_info=True)
            return replace(
                parsed_doc,
                parse_status="failed",
                error_message="OCR 服务不可用，请稍后重试",
            ), {}

        except OCRProcessingError:
            # OCR 处理错误：返回 FAILED 状态
            logger.warning("OCR 处理异常，扫描件解析失败: %s", mime_type, exc_info=True)
            return replace(
                parsed_doc,
                parse_status="failed",
                error_message="OCR 处理异常，请检查文件是否可读",
            ), {}

        except Exception:
            logger.warning(
                "OCR 解析意外异常，降级保留原始文档（文档 MIME=%s）",
                mime_type,
                exc_info=True,
            )
            return parsed_doc, {}

    @staticmethod
    def _mark_low_confidence(elements: list[ParsedElement]) -> list[ParsedElement]:
        """标记低置信度元素

        对 confidence < OCR_CONFIDENCE_THRESHOLD 的元素，
        在 metadata 中设置 needs_review = True。

        Args:
            elements: 待标记的元素列表

        Returns:
            标记后的元素列表
        """
        from src.domain.ports.ocr import OCR_CONFIDENCE_THRESHOLD

        result: list[ParsedElement] = []
        for elem in elements:
            if elem.confidence < OCR_CONFIDENCE_THRESHOLD:
                result.append(
                    ParsedElement(
                        content=elem.content,
                        bbox=elem.bbox,
                        confidence=elem.confidence,
                        metadata={
                            **elem.metadata,
                            "needs_review": True,
                        },
                    )
                )
            else:
                result.append(elem)
        return result
