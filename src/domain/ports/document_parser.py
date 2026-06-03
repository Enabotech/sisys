"""领域层 文档解析端口

定义文档解析器的 Protocol 接口，支持多格式解析策略路由。
实现类通过 CompositeDocumentParser 按 MIME 类型路由到具体解析器。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.parsed_document import ParsedDocument


@runtime_checkable
class DocumentParserPort(Protocol):
    """文档解析端口协议

    统一的文档解析接口，接收本地文件路径和 MIME 类型，返回结构化解析结果。
    MIME 类型用于 CompositeDocumentParser 内部路由决策（选择 PDFParser/WordParser/TextParser），
    单格式解析器可忽略此参数。

    Methods:
        parse: 解析文档文件，返回结构化解析结果
    """

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """解析文档文件

        Args:
            file_path: 本地文件路径
            mime_type: 文档 MIME 类型（用于路由决策）

        Returns:
            结构化解析结果
        """
        ...
