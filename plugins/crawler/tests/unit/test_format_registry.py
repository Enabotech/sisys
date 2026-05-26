"""文件格式处理器注册表单元测试

TDD 阶段：绿
验证注册、查找、检测、默认处理器加载

"""

from __future__ import annotations

from plugins.crawler.core.format.registry import FileFormatHandlerRegistry
from plugins.crawler.core.value_objects import FileMetadata


class _StubHandler:
    """测试用桩处理器"""

    def __init__(self, extensions: tuple[str, ...], mimes: tuple[str, ...]) -> None:
        self._extensions = extensions
        self._mimes = mimes

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return self._extensions

    @property
    def supported_mime_types(self) -> tuple[str, ...]:
        return self._mimes

    def can_handle(self, file_path: str, mime_type: str) -> bool:
        return mime_type in self._mimes or any(file_path.endswith(f".{e}") for e in self._extensions)

    def extract_metadata(self, file_path: str) -> FileMetadata:
        return FileMetadata(title="stub")


class TestFileFormatHandlerRegistry:
    """FileFormatHandlerRegistry 测试"""

    def test_register_and_get(self) -> None:
        """注册后应能按扩展名查找"""
        registry = FileFormatHandlerRegistry()
        handler = _StubHandler(("epub",), ("application/epub+zip",))
        registry.register(handler)
        assert registry.get_handler("epub") is handler

    def test_get_handler_case_insensitive(self) -> None:
        """扩展名查找应不区分大小写"""
        registry = FileFormatHandlerRegistry()
        handler = _StubHandler(("pdf",), ("application/pdf",))
        registry.register(handler)
        assert registry.get_handler("PDF") is handler

    def test_get_handler_unknown_returns_none(self) -> None:
        """未注册的扩展名应返回 None"""
        registry = FileFormatHandlerRegistry()
        assert registry.get_handler("xyz") is None

    def test_register_overwrites_duplicate(self) -> None:
        """重复注册同一扩展名应覆盖"""
        registry = FileFormatHandlerRegistry()
        handler1 = _StubHandler(("pdf",), ("application/pdf",))
        handler2 = _StubHandler(("pdf",), ("application/pdf",))
        registry.register(handler1)
        registry.register(handler2)
        assert registry.get_handler("pdf") is handler2

    def test_detect_format_by_mime(self) -> None:
        """应能通过 MIME 类型检测格式"""
        registry = FileFormatHandlerRegistry()
        handler = _StubHandler(("epub",), ("application/epub+zip",))
        registry.register(handler)
        result = registry.detect_format("file.unknown", "application/epub+zip")
        assert result is handler

    def test_detect_format_unknown_returns_none(self) -> None:
        """未知 MIME 应返回 None"""
        registry = FileFormatHandlerRegistry()
        assert registry.detect_format("file.xyz", "application/unknown") is None

    def test_supported_extensions_list(self) -> None:
        """应返回排序后的扩展名列表"""
        registry = FileFormatHandlerRegistry()
        registry.register(_StubHandler(("zip",), ("application/zip",)))
        registry.register(_StubHandler(("pdf",), ("application/pdf",)))
        exts = registry.supported_extensions_list()
        assert exts == ["pdf", "zip"]

    def test_register_default_handlers(self) -> None:
        """默认处理器应覆盖所有内置格式"""
        registry = FileFormatHandlerRegistry()
        registry.register_default_handlers()
        for ext in ("pdf", "docx", "pptx", "xlsx", "txt", "csv", "jpeg", "png", "zip", "tar"):
            assert registry.get_handler(ext) is not None, f"缺少默认处理器: {ext}"

    def test_clear(self) -> None:
        """clear 后应清空所有处理器"""
        registry = FileFormatHandlerRegistry()
        registry.register(_StubHandler(("pdf",), ("application/pdf",)))
        registry.clear()
        assert registry.get_handler("pdf") is None
