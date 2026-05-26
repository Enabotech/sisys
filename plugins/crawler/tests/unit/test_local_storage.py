"""本地存储单元测试

验证 LocalStorage 的文件存储和存在检查

"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from plugins.crawler.storage.local_storage import LocalStorage


class TestLocalStorage:
    """LocalStorage 测试"""

    @pytest.mark.asyncio
    async def test_store_file_copies_to_output_dir(self) -> None:
        """store_file 应将文件复制到输出目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(output_dir=tmpdir)
            src = Path(tmpdir) / "source.txt"
            src.write_text("hello")
            result = await storage.store_file("output.txt", str(src), "text/plain", {})
            assert Path(result).exists()
            assert Path(result).read_text() == "hello"

    @pytest.mark.asyncio
    async def test_store_file_preserves_content(self) -> None:
        """存储后内容应一致"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(output_dir=tmpdir)
            src = Path(tmpdir) / "source.txt"
            src.write_text("test content")
            result = await storage.store_file("output.txt", str(src), "text/plain", {})
            assert Path(result).read_text() == "test content"

    @pytest.mark.asyncio
    async def test_file_exists_returns_true(self) -> None:
        """已存储的文件 file_exists 应返回 True"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(output_dir=tmpdir)
            src = Path(tmpdir) / "source.txt"
            src.write_text("hello")
            await storage.store_file("output.txt", str(src), "text/plain", {})
            assert await storage.file_exists("output.txt")

    @pytest.mark.asyncio
    async def test_file_exists_returns_false(self) -> None:
        """不存在的文件 file_exists 应返回 False"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(output_dir=tmpdir)
            assert not await storage.file_exists("nonexistent.txt")

    def test_creates_output_dir(self) -> None:
        """输出目录不存在时应自动创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "nested" / "output"
            LocalStorage(output_dir=str(output))
            assert output.exists()
