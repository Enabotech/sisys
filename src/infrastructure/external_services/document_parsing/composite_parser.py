"""组合文档解析器

按 MIME 类型路由到具体解析器（PDF/Word/TXT）的组合模式实现。
通过 dict[str, DocumentParserPort] 注入实现 OCP 扩展（新增格式仅需在
composition_root 注册路由，无需修改本类）。
"""

from __future__ import annotations

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.value_objects.parsed_document import ParsedDocument


class CompositeDocumentParser(DocumentParserPort):
    """组合文档解析器 — 按 MIME 类型路由

    通过 parsers 字典接收 MIME → 解析器映射，新增格式无需修改本类
    （仅在 composition_root 注册新映射即可），符合 OCP。
    """

    def __init__(self, parsers: dict[str, DocumentParserPort]) -> None:
        """初始化组合解析器

        Args:
            parsers: MIME 类型 → 解析器实例的映射字典
        """
        self._parsers = dict(parsers)

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """按 MIME 类型路由解析

        Args:
            file_path: 本地文件路径
            mime_type: MIME 类型（用于路由决策）

        Returns:
            结构化解析结果

        Raises:
            ValueError: 不支持的 MIME 类型
        """
        parser = self._parsers.get(mime_type)
        if parser is None:
            raise ValueError(f"不支持的 MIME 类型: {mime_type}")
        return parser.parse(file_path, mime_type)
