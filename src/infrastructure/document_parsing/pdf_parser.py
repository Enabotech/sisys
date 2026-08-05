"""PDF 文档解析器

使用 pypdf 提取 PDF 文本的解析器实现，支持加密检测、多页处理与文件大小保护。
通过 visitor_text 提取逐行文本位置，输出归一化 [0, 1] 页面坐标 bbox。
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from pypdf import PdfReader

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.value_objects.parsed_document import (
    BoundingBox,
    ParsedDocument,
    ParsedElement,
    ParsedPage,
)
from src.infrastructure.document_parsing._limits import (
    MAX_PDF_BYTES,
    MAX_PDF_PAGES,
)

logger = logging.getLogger(__name__)

# 同一行文本的 Y 坐标聚类容差（PDF 用户空间单位，约 5pt）
_LINE_Y_TOLERANCE = 5.0


class PDFParser(DocumentParserPort):
    """PDF 文档解析器

    使用 pypdf.PdfReader 提取文本内容，支持：
    - 纯文本提取
    - 多页文档处理
    - 加密 PDF 检测与拒绝
    - 空文档检测
    - 文件大小与页数上限保护
    - 表格结构契约预留（真实检测推迟至 Story 2-4）
    """

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """解析 PDF 文件

        Args:
            file_path: 本地 PDF 文件路径
            mime_type: MIME 类型（PDFParser 忽略此参数）

        Returns:
            结构化解析结果（每行文本包含归一化 [0, 1] bbox 坐标）
        """
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        # 防御解压炸弹：解析前校验文件大小
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            logger.exception("PDF 文件大小检查失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="无法访问文件，请检查文件路径或权限",
                parse_timestamp=timestamp,
            )
        if file_size > MAX_PDF_BYTES:
            size_mb = file_size // (1024 * 1024)
            limit_mb = MAX_PDF_BYTES // (1024 * 1024)
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message=(f"PDF 文件大小 {size_mb}MB 超过 {limit_mb}MB 限制，可能为解压炸弹"),
                parse_timestamp=timestamp,
            )

        try:
            with open(file_path, "rb") as f:
                reader = PdfReader(f)

                if reader.is_encrypted:
                    return ParsedDocument(
                        document_id=doc_id,
                        mime_type=mime_type,
                        parse_status="failed",
                        error_message="PDF 文档已加密，无法解析",
                        parse_timestamp=timestamp,
                    )

                num_pages = len(reader.pages)
                if num_pages == 0:
                    return ParsedDocument(
                        document_id=doc_id,
                        mime_type=mime_type,
                        parse_status="failed",
                        error_message="PDF 文档为空，包含 0 页",
                        parse_timestamp=timestamp,
                    )

                if num_pages > MAX_PDF_PAGES:
                    return ParsedDocument(
                        document_id=doc_id,
                        mime_type=mime_type,
                        parse_status="failed",
                        error_message=(f"PDF 文档页数({num_pages})超过限制({MAX_PDF_PAGES})，请分段处理"),
                        parse_timestamp=timestamp,
                    )

                # 表格检测：PDF 表格初始检测由 DocumentParsingService
                # 在 _apply_table_detection() 步骤中通过 PdfTableDetector 完成
                pages: list[ParsedPage] = []
                for i, page in enumerate(reader.pages):
                    page_number = i + 1
                    # 逐行提取文本并附带归一化 bbox 坐标
                    texts = self._extract_text_elements(page, page_number)
                    pages.append(
                        ParsedPage(
                            page_number=page_number,
                            texts=texts,
                            tables=[],
                            images=[],
                        )
                    )

                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    pages=pages,
                    parse_status="completed",
                    parse_timestamp=timestamp,
                )
        except Exception:
            # 安全：原始异常可能含文件路径，详细 traceback 记录到日志
            logger.exception("PDF 文件解析失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="PDF 解析失败，请检查文件是否损坏或重试",
                parse_timestamp=timestamp,
            )

    @staticmethod
    def _extract_text_elements(page: Any, page_number: int) -> list[ParsedElement]:
        """从 PDF 页面逐行提取文本元素并附带归一化 bbox 坐标

        使用 pypdf 的 visitor_text 回调捕获每个文本绘制操作的位置
        （tm_matrix[4]=x, tm_matrix[5]=y），按 Y 坐标聚类为行，
        转换为 [0, 1] 页面归一化坐标（x: 左→右, y: 上→下）。

        降级策略：visitor_text 无法获取坐标时回退为整页单元素（bbox=None）。

        Args:
            page: pypdf PageObject 实例
            page_number: 1-indexed 页码

        Returns:
            带归一化 bbox 的 ParsedElement 列表（按阅读顺序排列）
        """
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        if page_width <= 0 or page_height <= 0:
            # 页面尺寸异常，回退为无 bbox 整页提取
            text = page.extract_text() or ""
            if text.strip():
                return [ParsedElement(content=text.strip())]
            return []

        # 收集文本运行（每行绘制操作）
        runs: list[dict[str, Any]] = []

        def _visitor(text: str, cm: Any, tm: Any, font_dict: Any, font_size: float) -> None:
            """visitor_text 回调：收集文本位置信息"""
            stripped = text.strip()
            if not stripped:
                return
            x = float(tm[4])
            y = float(tm[5])
            runs.append(
                {
                    "text": stripped,
                    "x": x,
                    "y": y,
                    "font_size": font_size if font_size > 0 else 12.0,
                }
            )

        try:
            page.extract_text(visitor_text=_visitor)
        except Exception:
            logger.warning("第 %d 页 visitor_text 提取失败，回退为无 bbox 整页提取", page_number, exc_info=True)
            text = page.extract_text() or ""
            if text.strip():
                return [ParsedElement(content=text.strip())]
            return []

        if not runs:
            # 无文本运行（空白页或纯图像 PDF），回退
            text = page.extract_text() or ""
            if text.strip():
                return [ParsedElement(content=text.strip())]
            return []

        # 按 Y 坐标聚类为文本行（扫描顺序：从上到下，从左到右）
        lines = PDFParser._cluster_runs_by_y(runs)

        # 构建 ParsedElement（按阅读顺序：Y 降序 = 页面上方优先）
        elements: list[ParsedElement] = []
        for line_runs in lines:
            # 按 X 坐标排序（从左到右）
            line_runs.sort(key=lambda r: r["x"])

            # 计算行的聚合 bbox
            min_x = min(r["x"] for r in line_runs)
            max_x = max(r["x"] + len(r["text"]) * r["font_size"] * 0.5 for r in line_runs)
            max_y = max(r["y"] for r in line_runs)
            min_y = min(r["y"] - r["font_size"] for r in line_runs)

            # 拼接文本
            line_text = " ".join(r["text"] for r in line_runs)

            # PDF 坐标（原点左下）→ 归一化 [0,1]（原点左上）
            bbox = BoundingBox(
                x=min_x / page_width,
                y=1.0 - (max_y / page_height),  # 翻转 Y 轴
                width=max(0.0, (max_x - min_x) / page_width),
                height=max(0.0, (max_y - min_y) / page_height),
                page=page_number,
            )

            elements.append(ParsedElement(content=line_text, bbox=bbox))

        return elements

    @staticmethod
    def _cluster_runs_by_y(runs: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """按 Y 坐标将文本运行聚类为行

        使用贪心聚类：将 Y 坐标差值在容差内的运行归为同一行，
        并按行 Y 坐标降序排列（从上到下阅读顺序）。

        Args:
            runs: 文本运行列表，每项包含 x、y、text、font_size 键

        Returns:
            按 Y 降序排列的行列表，每行为按 X 排序的文本运行列表
        """
        if not runs:
            return []

        # 按 Y 降序排列（页面上方优先）
        sorted_runs = sorted(runs, key=lambda r: r["y"], reverse=True)

        lines: list[list[dict[str, Any]]] = []
        current_line: list[dict[str, Any]] = [sorted_runs[0]]
        current_y = sorted_runs[0]["y"]

        for run in sorted_runs[1:]:
            if abs(run["y"] - current_y) <= _LINE_Y_TOLERANCE:
                current_line.append(run)
            else:
                lines.append(current_line)
                current_line = [run]
                current_y = run["y"]

        lines.append(current_line)
        return lines
