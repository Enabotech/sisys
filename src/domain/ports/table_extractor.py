"""领域层 表格语义提取端口

定义表格语义提取器的 Protocol 接口，接收解析器产出的原始 ParsedTable 列表，
返回语义增强后的 ParsedTable 列表（含表头、列类型、合并单元格等结构化信息）。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.parsed_document import ParsedTable


@runtime_checkable
class TableExtractorPort(Protocol):
    """表格语义提取端口协议

    统一的表格语义提取接口，接收原始 ParsedTable 列表，
    对每个表格执行表头识别、列类型推断、合并单元格还原等语义增强操作。

    Methods:
        extract: 对原始表格列表执行语义提取，返回增强后的表格列表
    """

    def extract(
        self,
        file_path: str,
        mime_type: str,
        tables: list[ParsedTable],
    ) -> list[ParsedTable]:
        """对原始表格列表执行语义提取

        Args:
            file_path: 源文档文件路径（用于 PDF 表格检测等场景）
            mime_type: 源文档 MIME 类型（用于判断处理策略）
            tables: 解析器产出的原始 ParsedTable 列表

        Returns:
            语义增强后的 ParsedTable 列表（header/column_types/merged_cells 字段已填充）
        """
        ...
