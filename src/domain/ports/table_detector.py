"""领域层 表格检测端口

定义表格检测器的 Protocol 接口，从文档中初始检测表格区域，
返回原始的 ParsedTable 列表（不含语义信息）。

与 TableSemanticEnhancerPort 职责分离：
- TableDetectorPort: 从文档中检测/提取表格（初始检测）
- TableSemanticEnhancerPort: 对已提取的表格做语义增强（表头/列类型）
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.parsed_document import ParsedTable


@runtime_checkable
class TableDetectorPort(Protocol):
    """表格检测端口协议

    从文档中初始检测表格区域，提取行列结构，
    返回原始的 ParsedTable 列表（不含语义信息）。

    Methods:
        detect: 从文档中检测表格，返回原始 ParsedTable 列表
    """

    def detect(
        self,
        file_path: str,
        mime_type: str,
    ) -> list[ParsedTable]:
        """从文档中检测表格

        Args:
            file_path: 源文档文件路径
            mime_type: 源文档 MIME 类型

        Returns:
            ParsedTable 列表（仅含 rows 字段，无语义信息）
        """
        ...
