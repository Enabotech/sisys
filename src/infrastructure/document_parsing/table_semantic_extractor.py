"""基础设施层 通用表格语义提取编排器

编排调用领域服务（表头检测、列类型推断、合并单元格还原），
对解析器产出的原始 ParsedTable 进行语义增强。

实现 TableExtractorPort 端口协议。
"""

from __future__ import annotations

import dataclasses
import logging

from src.domain.services.table_column_classifier import classify_columns
from src.domain.services.table_header_detector import detect_header
from src.domain.value_objects.parsed_document import ColumnInfo, ParsedTable

logger = logging.getLogger(__name__)


class TableSemanticExtractor:
    """通用表格语义提取编排器

    编排调用三个领域服务对 ParsedTable 进行语义增强：
    1. detect_header — 表头检测
    2. classify_columns — 列类型推断
    3. resolve_merged_cells — 合并单元格还原（V1，仅 xlsx）

    降级策略：单个表格增强失败时不影响其他表格，
    降级返回原始 ParsedTable（语义字段保持默认值）。
    """

    def extract(
        self,
        file_path: str,
        mime_type: str,
        tables: list[ParsedTable],
    ) -> list[ParsedTable]:
        """对原始表格列表执行语义提取

        Args:
            file_path: 源文档文件路径
            mime_type: 源文档 MIME 类型
            tables: 解析器产出的原始 ParsedTable 列表

        Returns:
            语义增强后的 ParsedTable 列表
        """
        if not tables:
            return []

        enhanced: list[ParsedTable] = []
        for table in tables:
            try:
                enhanced_table = self._enhance_single_table(table, mime_type)
                enhanced.append(enhanced_table)
            except Exception:
                logger.warning(
                    "表格语义提取失败，降级返回原始表格（行数=%d）",
                    len(table.rows),
                    exc_info=True,
                )
                enhanced.append(table)

        return enhanced

    def _enhance_single_table(
        self,
        table: ParsedTable,
        mime_type: str,
    ) -> ParsedTable:
        """增强单个表格的语义信息

        Args:
            table: 原始 ParsedTable
            mime_type: 文档 MIME 类型

        Returns:
            语义增强后的 ParsedTable
        """
        if not table.rows:
            return table

        # 1. 表头检测
        header_row_index, header_confidence = detect_header(table.rows)

        header: list[str] | None = None
        data_rows: list[list[str]] = table.rows
        if header_row_index is not None:
            header = table.rows[header_row_index]
            data_rows = table.rows[header_row_index + 1 :]

        # 2. 列类型推断
        column_types = classify_columns(data_rows, column_names=header)

        # 3. 合并单元格还原（V1：仅 xlsx 格式）
        merged_cells = None
        if "spreadsheetml" in mime_type or "xlsx" in mime_type:
            # V1: xlsx 合并单元格信息由上层 PdfTableExtractor/ExcelParser 提供
            # 此处仅标记为 None（暂不从 file_path 读取合并信息）
            merged_cells = None

        # 4. 计算综合置信度
        semantic_confidence = self._calc_semantic_confidence(
            header_confidence=header_confidence,
            column_types=column_types,
        )

        # 5. 使用 dataclasses.replace 构建增强后的 ParsedTable
        return dataclasses.replace(
            table,
            header=header,
            column_types=column_types,
            merged_cells=merged_cells,
            semantic_confidence=semantic_confidence,
            metadata={
                **table.metadata,
                "header_row_indices": [header_row_index] if header_row_index is not None else [],
                "header_confidence": header_confidence,
            },
        )

    def _calc_semantic_confidence(
        self,
        header_confidence: float,
        column_types: list[ColumnInfo],
    ) -> float:
        """计算语义提取综合置信度

        Args:
            header_confidence: 表头检测置信度
            column_types: 列类型推断结果

        Returns:
            综合置信度（0.0~1.0）
        """
        if not column_types:
            return header_confidence * 0.5

        avg_col_confidence = sum(ct.confidence for ct in column_types) / len(column_types)
        return round((header_confidence * 0.4 + avg_col_confidence * 0.6), 4)
