"""基础设施层 通用表格语义增强编排器

编排调用领域服务（表头检测、列类型推断、合并单元格还原），
对解析器产出的原始 ParsedTable 进行语义增强。

实现 TableSemanticEnhancerPort 端口协议。
"""

from __future__ import annotations

import dataclasses
import logging

from src.domain.ports.table_enhancer import TableSemanticEnhancerPort
from src.domain.services.table_column_classifier import classify_columns
from src.domain.services.table_header_detector import detect_header
from src.domain.value_objects.parsed_document import ColumnInfo, ParsedTable

logger = logging.getLogger(__name__)


class TableSemanticExtractor(TableSemanticEnhancerPort):
    """通用表格语义增强编排器

    编排调用三个领域服务对 ParsedTable 进行语义增强：
    1. detect_header — 表头检测
    2. classify_columns — 列类型推断
    3. resolve_merged_cells — 合并单元格还原（V1，仅 xlsx）

    降级策略：单个表格增强失败时不影响其他表格，
    降级返回原始 ParsedTable（语义字段保持默认值）。

    部分失败语义：单个领域服务失败时，保留已成功的增强结果，
    失败的服务对应字段保持 None，metadata 中标记 "semantic_enhancement_error"。
    """

    def enhance(
        self,
        tables: list[ParsedTable],
        mime_type: str,
    ) -> list[ParsedTable]:
        """对原始表格列表执行语义增强

        Args:
            tables: 解析器产出的原始 ParsedTable 列表
            mime_type: 源文档 MIME 类型

        Returns:
            语义增强后的 ParsedTable 列表
        """
        if not tables:
            return []

        enhanced: list[ParsedTable] = []
        for table_idx, table in enumerate(tables):
            try:
                enhanced_table = self._enhance_single_table(table, mime_type)
                enhanced.append(enhanced_table)
            except (ValueError, TypeError, RuntimeError, AttributeError):
                logger.warning(
                    "表格语义增强失败，降级返回原始表格（table_index=%d, mime_type=%s, row_count=%d）",
                    table_idx,
                    mime_type,
                    len(table.rows),
                    exc_info=True,
                )
                # 降级表格在 metadata 中标记增强失败
                degraded = dataclasses.replace(
                    table,
                    metadata={
                        **table.metadata,
                        "semantic_enhancement_error": True,
                    },
                )
                enhanced.append(degraded)

        return enhanced

    def _enhance_single_table(
        self,
        table: ParsedTable,
        mime_type: str,
    ) -> ParsedTable:
        """增强单个表格的语义信息

        三个领域服务分别 try/except，单个失败不影响其他增强结果。

        Args:
            table: 原始 ParsedTable
            mime_type: 文档 MIME 类型

        Returns:
            语义增强后的 ParsedTable
        """
        if not table.rows:
            return table

        # 1. 表头检测
        header_row_index, header_confidence, header_failed = None, 0.0, False
        try:
            header_row_index, header_confidence = detect_header(table.rows)
        except (ValueError, TypeError, RuntimeError, AttributeError):
            logger.warning(
                "表头检测失败，降级为无表头（mime_type=%s）",
                mime_type,
                exc_info=True,
            )
            header_failed = True

        header: list[str] | None = None
        data_rows: list[list[str]] = table.rows
        if header_row_index is not None:
            header = list(table.rows[header_row_index])
            data_rows = list(table.rows[header_row_index + 1 :])

        # 2. 列类型推断
        column_types: list[ColumnInfo] = []
        column_types_failed = False
        try:
            column_types = classify_columns(data_rows, column_names=header)
        except (ValueError, TypeError, RuntimeError, AttributeError):
            logger.warning(
                "列类型推断失败，降级为空列表（mime_type=%s）",
                mime_type,
                exc_info=True,
            )
            column_types_failed = True

        # 3. 合并单元格还原（V1：仅 xlsx/spreadsheetml 格式）
        # 当前 V1 阶段暂不从 file_path 读取 xlsx 合并信息，merged_cells 保持 None
        merged_cells = None

        # 4. 计算综合置信度
        semantic_confidence = self._calc_semantic_confidence(
            header_confidence=header_confidence,
            column_types=column_types,
        )

        # 5. 构建 metadata，标记部分失败信息
        enhancement_metadata: dict = {
            "header_row_indices": [header_row_index] if header_row_index is not None else [],
            "header_confidence": header_confidence,
        }
        if header_failed or column_types_failed:
            enhancement_metadata["semantic_enhancement_error"] = True

        # 6. 使用 dataclasses.replace 构建增强后的 ParsedTable
        return dataclasses.replace(
            table,
            header=header,
            column_types=column_types if column_types else None,
            merged_cells=merged_cells,
            semantic_confidence=semantic_confidence,
            metadata={
                **table.metadata,
                **enhancement_metadata,
            },
        )

    @staticmethod
    def _calc_semantic_confidence(
        header_confidence: float,
        column_types: list[ColumnInfo],
    ) -> float:
        """计算语义增强综合置信度

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
