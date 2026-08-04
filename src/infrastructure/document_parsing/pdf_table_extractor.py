"""基础设施层 PDF 表格初始检测器

使用 pdfplumber 从 PDF 页面中检测表格区域，提取行列结构，
转换为 ParsedTable 值对象。实现 TableDetectorPort 端口协议。

pdfplumber 为 MIT 许可证，专有表格检测算法，无 Ghostscript 系统依赖。
"""

from __future__ import annotations

import logging
from typing import Any

from src.domain.ports.table_detector import TableDetectorPort
from src.domain.value_objects.parsed_document import ParsedTable

logger = logging.getLogger(__name__)

# pdfplumber 延迟导入，仅在运行时加载
_pdfplumber: Any = None


def _ensure_pdfplumber() -> Any:
    """确保 pdfplumber 已导入

    Returns:
        pdfplumber 模块

    Raises:
        ImportError: pdfplumber 未安装
    """
    global _pdfplumber
    if _pdfplumber is None:
        try:
            import pdfplumber as _plumber

            _pdfplumber = _plumber
        except ImportError as e:
            raise ImportError("pdfplumber 未安装。请执行: poetry add pdfplumber") from e
    return _pdfplumber


class PdfTableDetector(TableDetectorPort):
    """PDF 专用表格检测器

    使用 pdfplumber 逐页检测 PDF 页面中的表格区域，
    提取行列结构并转换为 ParsedTable 值对象列表。
    实现 TableDetectorPort 端口协议。

    降级策略：
    - 非 PDF MIME 类型 → 直接返回空列表
    - pdfplumber 运行时异常 → WARNING 日志 + 空列表
    - 单页检测异常 → 跳过该页，继续处理其他页
    """

    def detect(
        self,
        file_path: str,
        mime_type: str,
    ) -> list[ParsedTable]:
        """从 PDF 文件中检测表格

        Args:
            file_path: PDF 文件路径
            mime_type: 文档 MIME 类型

        Returns:
            检测到的 ParsedTable 列表（仅含 rows 字段，无语义信息）
        """
        # MIME 类型过滤：支持带参数的 MIME 类型（如 "application/pdf; charset=utf-8"）
        if not mime_type.startswith("application/pdf"):
            return []

        try:
            pl = _ensure_pdfplumber()
        except ImportError:
            logger.warning("pdfplumber 未安装，PDF 表格检测不可用", exc_info=True)
            return []

        detected_tables: list[ParsedTable] = []

        try:
            with pl.open(file_path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    try:
                        page_tables = self._extract_tables_from_page(page)
                        detected_tables.extend(page_tables)
                    except (ValueError, TypeError, RuntimeError, OSError, AttributeError):
                        logger.warning(
                            "PDF 页面表格检测失败，跳过该页（page=%d）",
                            page_idx + 1,
                            exc_info=True,
                        )
        except (ValueError, TypeError, RuntimeError, OSError, AttributeError):
            logger.warning(
                "PDF 文件打开失败: %s",
                file_path,
                exc_info=True,
            )
            return []

        return detected_tables

    @staticmethod
    def _extract_tables_from_page(page: Any) -> list[ParsedTable]:
        """从单个 PDF 页面提取表格

        Args:
            page: pdfplumber 页面对象

        Returns:
            该页检测到的 ParsedTable 列表
        """
        raw_tables = page.extract_tables()
        if not raw_tables:
            return []

        # 过滤 None 行（部分 PDF 变种可能返回 None 作为行）
        raw_tables = [rt for rt in raw_tables if rt is not None]

        result: list[ParsedTable] = []
        for raw_table in raw_tables:
            if not raw_table:
                continue

            # 过滤 None 行
            raw_table = [r for r in raw_table if r is not None]

            # 将 pdfplumber 返回的二维列表转为 list[list[str]]
            rows: list[list[str]] = []
            for raw_row in raw_table:
                row = [str(cell) if cell is not None else "" for cell in raw_row]
                rows.append(row)

            if rows:
                result.append(ParsedTable(rows=rows))

        return result
