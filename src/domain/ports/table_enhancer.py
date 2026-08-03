"""领域层 表格语义增强端口

定义表格语义增强器的 Protocol 接口，接收解析器产出的原始 ParsedTable 列表，
返回语义增强后的 ParsedTable 列表（含表头、列类型、合并单元格等结构化信息）。

与 TableDetectorPort 职责分离：
- TableDetectorPort: 从文档中检测/提取表格（初始检测）
- TableSemanticEnhancerPort: 对已提取的表格做语义增强（表头/列类型）
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.parsed_document import ParsedTable


@runtime_checkable
class TableSemanticEnhancerPort(Protocol):
    """表格语义增强端口协议

    对解析器产出的原始 ParsedTable 列表执行语义增强，
    包括表头识别、列类型推断、合并单元格还原等操作。

    Methods:
        enhance: 对原始表格列表执行语义增强，返回增强后的表格列表
    """

    def enhance(
        self,
        tables: list[ParsedTable],
        mime_type: str,
    ) -> list[ParsedTable]:
        """对原始表格列表执行语义增强

        Args:
            tables: 解析器产出的原始 ParsedTable 列表
            mime_type: 源文档 MIME 类型（用于判断处理策略）

        Returns:
            语义增强后的 ParsedTable 列表（header/column_types/merged_cells 字段已填充）
        """
        ...
