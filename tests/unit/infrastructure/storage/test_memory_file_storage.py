"""Tests for MemoryFileStorage.

验证 MemoryFileStorage 作为 FileMemoryAdapter 的包装层：
- 文件操作正确委托给 adapter
- 索引操作使用 asyncio.to_thread 调用 adapter 同步方法
- search_index 支持大小写不敏感匹配
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.fs.memory_file_storage import MemoryFileStorage


@pytest.fixture
def mock_adapter():
    """创建 mock FileMemoryAdapter 并注入到 MemoryFileStorage

    使用构造器注入模式（Cosmic Python），不使用 @patch
    """
    adapter = MagicMock()
    adapter.write = AsyncMock(return_value=True)
    adapter.read = AsyncMock(return_value="content")
    adapter.delete = AsyncMock(return_value=True)
    adapter.exists = AsyncMock(return_value=True)
    adapter.list_memories = AsyncMock(return_value=["id-1", "id-2"])
    adapter.update_index = MagicMock()
    adapter.read_index = MagicMock(return_value=[])
    return adapter


@pytest.fixture
def storage(mock_adapter):
    """创建注入 mock adapter 的 MemoryFileStorage 实例"""
    return MemoryFileStorage(mock_adapter)


# ---------------------------------------------------------------------------
# 文件操作委托验证
# ---------------------------------------------------------------------------


class TestWriteDelegation:
    """验证 write 方法正确委托给 adapter"""

    async def test_calls_adapter_write_with_correct_args(self, storage, mock_adapter):
        """验证传递给 adapter.write 的参数正确"""
        await storage.write("mem-1", "user", "hello")

        mock_adapter.write.assert_awaited_once_with("mem-1", "user", "hello")

    async def test_returns_adapter_write_result(self, storage, mock_adapter):
        """验证返回 adapter.write 的结果"""
        mock_adapter.write.return_value = False

        result = await storage.write("mem-1", "user", "hello")

        assert result is False

    async def test_propagates_adapter_exception(self, storage, mock_adapter):
        """验证 adapter.write 抛出异常时正确传播"""
        mock_adapter.write.side_effect = OSError("disk full")

        with pytest.raises(OSError, match="disk full"):
            await storage.write("mem-1", "user", "hello")


class TestReadDelegation:
    """验证 read 方法正确委托给 adapter"""

    async def test_calls_adapter_read_with_correct_args(self, storage, mock_adapter):
        """验证传递给 adapter.read 的参数正确"""
        await storage.read("mem-1", "feedback")

        mock_adapter.read.assert_awaited_once_with("mem-1", "feedback")

    async def test_returns_adapter_read_result(self, storage, mock_adapter):
        """验证返回 adapter.read 的内容"""
        mock_adapter.read.return_value = "记忆内容"

        result = await storage.read("mem-1", "feedback")

        assert result == "记忆内容"

    async def test_propagates_file_not_found(self, storage, mock_adapter):
        """验证文件不存在时传播 FileNotFoundError"""
        mock_adapter.read.side_effect = FileNotFoundError("not found")

        with pytest.raises(FileNotFoundError):
            await storage.read("missing-id", "user")


class TestDeleteDelegation:
    """验证 delete 方法正确委托给 adapter"""

    async def test_calls_adapter_delete_with_correct_args(self, storage, mock_adapter):
        """验证传递给 adapter.delete 的参数正确"""
        await storage.delete("mem-1", "user")

        mock_adapter.delete.assert_awaited_once_with("mem-1", "user")

    async def test_returns_adapter_delete_result(self, storage, mock_adapter):
        """验证返回 adapter.delete 的结果"""
        mock_adapter.delete.return_value = False

        result = await storage.delete("nonexistent", "user")

        assert result is False


class TestExistsDelegation:
    """验证 exists 方法正确委托给 adapter"""

    async def test_calls_adapter_exists_with_correct_args(self, storage, mock_adapter):
        """验证传递给 adapter.exists 的参数正确"""
        await storage.exists("mem-1", "project")

        mock_adapter.exists.assert_awaited_once_with("mem-1", "project")

    async def test_returns_adapter_exists_result(self, storage, mock_adapter):
        """验证返回 adapter.exists 的布尔结果"""
        mock_adapter.exists.return_value = False

        result = await storage.exists("missing-id", "project")

        assert result is False


class TestListMemoriesDelegation:
    """验证 list_memories 方法正确委托给 adapter"""

    async def test_calls_adapter_list_memories_with_correct_args(self, storage, mock_adapter):
        """验证传递给 adapter.list_memories 的参数正确"""
        await storage.list_memories("user")

        mock_adapter.list_memories.assert_awaited_once_with("user")

    async def test_returns_adapter_list_memories_result(self, storage, mock_adapter):
        """验证返回 adapter.list_memories 的结果"""
        ids = ["aaa", "bbb", "ccc"]
        mock_adapter.list_memories.return_value = ids

        result = await storage.list_memories("user")

        assert result == ids


# ---------------------------------------------------------------------------
# 索引操作验证
# ---------------------------------------------------------------------------


class TestUpdateIndex:
    """验证 update_index 使用 asyncio.to_thread 调用 adapter 同步方法"""

    async def test_delegates_to_adapter_update_index(self, storage, mock_adapter):
        """验证 update_index 通过 to_thread 委托给 adapter.update_index"""
        entry = {"name": "test", "type": "user", "memory_id": "id-1", "description": "描述"}

        await storage.update_index(entry)

        # MemoryFileStorage 将单个 entry 包装为列表传给 adapter.update_index
        mock_adapter.update_index.assert_called_once_with([entry])

    async def test_delegates_entry_with_multiple_fields(self, storage, mock_adapter):
        """验证包含多个字段的条目正确传递"""
        entry = {
            "name": "复杂记忆",
            "type": "reference",
            "memory_id": "complex-id",
            "description": "这是一段详细描述",
        }

        await storage.update_index(entry)

        mock_adapter.update_index.assert_called_once_with([entry])


class TestRemoveFromIndex:
    """验证 remove_from_index 按memory_id 过滤并更新索引"""

    async def test_removes_entry_by_memory_id(self, storage, mock_adapter):
        """验证按 memory_id 过滤移除指定条目"""
        entries = [
            {"name": "a", "type": "user", "memory_id": "keep-me", "description": "保留"},
            {"name": "b", "type": "user", "memory_id": "remove-me", "description": "移除"},
            {"name": "c", "type": "feedback", "memory_id": "keep-too", "description": "保留"},
        ]
        mock_adapter.read_index.return_value = entries

        await storage.remove_from_index("remove-me")

        # 最终传给 update_index 的列表应不包含被移除的条目
        mock_adapter.update_index.assert_called_once_with(
            [
                {"name": "a", "type": "user", "memory_id": "keep-me", "description": "保留"},
                {"name": "c", "type": "feedback", "memory_id": "keep-too", "description": "保留"},
            ]
        )

    async def test_no_match_keeps_all_entries(self, storage, mock_adapter):
        """验证 memory_id 不匹配时保留所有条目"""
        entries = [
            {"name": "a", "type": "user", "memory_id": "id-1", "description": "a"},
            {"name": "b", "type": "user", "memory_id": "id-2", "description": "b"},
        ]
        mock_adapter.read_index.return_value = entries

        await storage.remove_from_index("nonexistent-id")

        mock_adapter.update_index.assert_called_once_with(entries)

    async def test_empty_index_stays_empty(self, storage, mock_adapter):
        """验证空索引移除后仍为空"""
        mock_adapter.read_index.return_value = []

        await storage.remove_from_index("any-id")

        mock_adapter.update_index.assert_called_once_with([])

    async def test_entry_missing_memory_id_field_is_kept(self, storage, mock_adapter):
        """验证缺少 memory_id 字段的条目不会被移除"""
        entries = [
            {"name": "no-id", "type": "user", "description": "缺少memory_id"},
            {"name": "has-id", "type": "user", "memory_id": "target", "description": "有id"},
        ]
        mock_adapter.read_index.return_value = entries

        await storage.remove_from_index("target")

        # 缺少 memory_id 的条目 e.get("memory_id") 返回 None != "target"，保留
        mock_adapter.update_index.assert_called_once_with([{"name": "no-id", "type": "user", "description": "缺少memory_id"}])


class TestSearchIndex:
    """验证 search_index 大小写不敏感匹配 name 和 description 字段"""

    async def test_match_name_case_insensitive(self, storage, mock_adapter):
        """验证按 name 字段大小写不敏感匹配"""
        entries = [
            {"name": "Python Guide", "type": "reference", "memory_id": "id-1", "description": "指南"},
        ]
        mock_adapter.read_index.return_value = entries

        result = await storage.search_index("python")

        assert len(result) == 1
        assert result[0]["memory_id"] == "id-1"

    async def test_match_description_case_insensitive(self, storage, mock_adapter):
        """验证按 description 字段大小写不敏感匹配"""
        entries = [
            {"name": "guide", "type": "reference", "memory_id": "id-1", "description": "Python Best Practices"},
        ]
        mock_adapter.read_index.return_value = entries

        result = await storage.search_index("python best")

        assert len(result) == 1
        assert result[0]["memory_id"] == "id-1"

    async def test_no_match_returns_empty(self, storage, mock_adapter):
        """验证无匹配时返回空列表"""
        entries = [
            {"name": "Java Guide", "type": "reference", "memory_id": "id-1", "description": "Java 指南"},
        ]
        mock_adapter.read_index.return_value = entries

        result = await storage.search_index("python")

        assert result == []

    async def test_multiple_matches(self, storage, mock_adapter):
        """验证多个匹配结果全部返回"""
        entries = [
            {"name": "Python Basics", "type": "reference", "memory_id": "id-1", "description": "基础教程"},
            {"name": "Advanced Python", "type": "reference", "memory_id": "id-2", "description": "高级教程"},
            {"name": "Java Guide", "type": "reference", "memory_id": "id-3", "description": "Java 教程"},
        ]
        mock_adapter.read_index.return_value = entries

        result = await storage.search_index("python")

        assert len(result) == 2
        assert {r["memory_id"] for r in result} == {"id-1", "id-2"}

    async def test_empty_index_returns_empty(self, storage, mock_adapter):
        """验证空索引搜索返回空列表"""
        mock_adapter.read_index.return_value = []

        result = await storage.search_index("anything")

        assert result == []

    async def test_match_mixed_case_query(self, storage, mock_adapter):
        """验证查询字符串包含大小写混合时仍能匹配"""
        entries = [
            {"name": "python guide", "type": "reference", "memory_id": "id-1", "description": "教程"},
        ]
        mock_adapter.read_index.return_value = entries

        result = await storage.search_index("PyThOn")

        assert len(result) == 1

    async def test_entry_missing_name_and_description(self, storage, mock_adapter):
        """验证条目缺少 name/description 字段时不匹配（不报错）"""
        entries = [
            {"type": "user", "memory_id": "id-1"},
        ]
        mock_adapter.read_index.return_value = entries

        result = await storage.search_index("anything")

        assert result == []

    async def test_partial_match_on_name(self, storage, mock_adapter):
        """验证查询是 name 子串时也能匹配"""
        entries = [
            {"name": "awesome-python-tips", "type": "reference", "memory_id": "id-1", "description": "技巧"},
        ]
        mock_adapter.read_index.return_value = entries

        result = await storage.search_index("python")

        assert len(result) == 1
