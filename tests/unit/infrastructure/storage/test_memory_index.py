"""Tests for MemoryIndex.

RED PHASE: 验证 MemoryIndex 索引管理功能。
"""

from __future__ import annotations

import uuid

from src.infrastructure.config.memory import MemoryConfig
from src.infrastructure.storage.memory_index import MemoryIndex


class TestMemoryIndexInit:
    """MemoryIndex 初始化验证"""

    def test_init_with_config(self, tmp_path):
        """验证使用配置初始化"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)
        assert index.config is not None
        assert index.config.memory_l0_path == str(tmp_path)

    def test_index_path_from_config(self, tmp_path):
        """验证索引路径来自配置"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)
        assert index._index_path == tmp_path / "MEMORY.md"


class TestMemoryIndexUpdateEntry:
    """MemoryIndex 更新条目验证"""

    def test_update_entry_creates_index(self, tmp_path):
        """验证更新条目时创建索引文件"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        entry = {
            "name": "test-memory",
            "type": "user",
            "memory_id": str(uuid.uuid4()),
            "description": "测试记忆",
        }
        index.update_entry(entry)

        index_path = tmp_path / "MEMORY.md"
        assert index_path.exists()

    def test_update_entry_format(self, tmp_path):
        """验证索引条目格式正确"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        memory_id = str(uuid.uuid4())
        entry = {
            "name": "my-test-memory",
            "type": "user",
            "memory_id": memory_id,
            "description": "这是描述",
        }
        index.update_entry(entry)

        content = (tmp_path / "MEMORY.md").read_text()
        assert f"- [my-test-memory](user/{memory_id}.md) — 这是描述" in content

    def test_update_entry_multiple_types(self, tmp_path):
        """验证多种类型的索引条目"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        entries = [
            {"name": "user-memory", "type": "user", "memory_id": str(uuid.uuid4()), "description": "用户记忆"},
            {"name": "feedback-note", "type": "feedback", "memory_id": str(uuid.uuid4()), "description": "反馈"},
            {"name": "project-info", "type": "project", "memory_id": str(uuid.uuid4()), "description": "项目"},
            {"name": "ref-doc", "type": "reference", "memory_id": str(uuid.uuid4()), "description": "参考"},
        ]
        for entry in entries:
            index.update_entry(entry)

        content = (tmp_path / "MEMORY.md").read_text()
        assert "- [user-memory](user/" in content
        assert "- [feedback-note](feedback/" in content
        assert "- [project-info](project/" in content
        assert "- [ref-doc](reference/" in content

    def test_update_entry_same_memory_id_updates(self, tmp_path):
        """验证相同 memory_id 更新条目"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        memory_id = str(uuid.uuid4())
        entry1 = {
            "name": "original-name",
            "type": "user",
            "memory_id": memory_id,
            "description": "原始描述",
        }
        index.update_entry(entry1)

        entry2 = {
            "name": "updated-name",
            "type": "user",
            "memory_id": memory_id,
            "description": "更新描述",
        }
        index.update_entry(entry2)

        content = (tmp_path / "MEMORY.md").read_text()
        assert "updated-name" in content
        assert "original-name" not in content


class TestMemoryIndexRemoveEntry:
    """MemoryIndex 移除条目验证"""

    def test_remove_entry_existing(self, tmp_path):
        """验证移除已存在的条目"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        memory_id = str(uuid.uuid4())
        entry = {
            "name": "to-be-removed",
            "type": "user",
            "memory_id": memory_id,
            "description": "将被删除",
        }
        index.update_entry(entry)
        assert (tmp_path / "MEMORY.md").exists()

        index.remove_entry(memory_id)

        content = (tmp_path / "MEMORY.md").read_text()
        assert "to-be-removed" not in content

    def test_remove_entry_nonexistent_no_raise(self, tmp_path):
        """验证移除不存在的条目不抛出异常"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        # 不应抛出异常
        index.remove_entry(str(uuid.uuid4()))


class TestMemoryIndexReadEntries:
    """MemoryIndex 读取条目验证"""

    def test_read_entries_empty(self, tmp_path):
        """验证读取空索引"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        entries = index.read_entries()
        assert entries == []

    def test_read_entries_multiple(self, tmp_path):
        """验证读取多个条目"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        entries = [
            {"name": "memory-1", "type": "user", "memory_id": str(uuid.uuid4()), "description": "描述1"},
            {"name": "memory-2", "type": "feedback", "memory_id": str(uuid.uuid4()), "description": "描述2"},
        ]
        for entry in entries:
            index.update_entry(entry)

        read_entries = index.read_entries()
        assert len(read_entries) == 2
        names = [e["name"] for e in read_entries]
        assert "memory-1" in names
        assert "memory-2" in names

    def test_read_entries_returns_dict_with_required_fields(self, tmp_path):
        """验证读取条目包含必需字段"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        memory_id = str(uuid.uuid4())
        entry = {
            "name": "complete-entry",
            "type": "user",
            "memory_id": memory_id,
            "description": "完整条目",
        }
        index.update_entry(entry)

        read_entries = index.read_entries()
        assert len(read_entries) == 1
        assert read_entries[0]["name"] == "complete-entry"
        assert read_entries[0]["type"] == "user"
        assert read_entries[0]["memory_id"] == memory_id
        assert read_entries[0]["description"] == "完整条目"


class TestMemoryIndexTruncation:
    """MemoryIndex 截断策略验证"""

    def test_truncate_preserves_latest_200_lines(self, tmp_path):
        """验证截断保留最新 200 行"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        # 创建超过 200 行的索引
        for i in range(250):
            entry = {
                "name": f"memory-{i}",
                "type": "user",
                "memory_id": str(uuid.uuid4()),
                "description": f"描述 {i}",
            }
            index.update_entry(entry)

        # 触发截断
        index.truncate()

        # 读取索引内容
        content = (tmp_path / "MEMORY.md").read_text()
        lines = [line for line in content.splitlines() if line.strip() and not line.startswith("#")]

        # 应该正好 200 行
        assert len(lines) == 200

        # 最后一行应该是 memory-249（最新）
        assert "memory-249" in lines[-1]
        # 第一行应该是 memory-50（最旧保留）
        assert "memory-50" in lines[0]

    def test_truncate_under_200_lines_no_change(self, tmp_path):
        """验证不足 200 行时不截断"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        # 创建 50 行
        for i in range(50):
            entry = {
                "name": f"memory-{i}",
                "type": "user",
                "memory_id": str(uuid.uuid4()),
                "description": f"描述 {i}",
            }
            index.update_entry(entry)

        content_before = (tmp_path / "MEMORY.md").read_text()
        lines_before = [line for line in content_before.splitlines() if line.strip() and not line.startswith("#")]

        # 触发截断
        index.truncate()

        content_after = (tmp_path / "MEMORY.md").read_text()
        lines_after = [line for line in content_after.splitlines() if line.strip() and not line.startswith("#")]

        assert len(lines_before) == len(lines_after) == 50

    def test_truncate_exactly_200_lines_no_change(self, tmp_path):
        """验证正好 200 行时不截断"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        # 创建正好 200 行
        for i in range(200):
            entry = {
                "name": f"memory-{i}",
                "type": "user",
                "memory_id": str(uuid.uuid4()),
                "description": f"描述 {i}",
            }
            index.update_entry(entry)

        content_before = (tmp_path / "MEMORY.md").read_text()
        lines_before = [line for line in content_before.splitlines() if line.strip() and not line.startswith("#")]

        index.truncate()

        content_after = (tmp_path / "MEMORY.md").read_text()
        lines_after = [line for line in content_after.splitlines() if line.strip() and not line.startswith("#")]

        assert len(lines_before) == len(lines_after) == 200


class TestMemoryIndexSearch:
    """MemoryIndex 搜索功能验证"""

    def test_search_by_name(self, tmp_path):
        """验证按名称搜索"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        entries = [
            {"name": "apple-pie", "type": "user", "memory_id": str(uuid.uuid4()), "description": "苹果派"},
            {"name": "banana-bread", "type": "user", "memory_id": str(uuid.uuid4()), "description": "香蕉面包"},
            {"name": "apple-juice", "type": "user", "memory_id": str(uuid.uuid4()), "description": "苹果汁"},
        ]
        for entry in entries:
            index.update_entry(entry)

        results = index.search("apple")
        assert len(results) == 2
        names = [e["name"] for e in results]
        assert "apple-pie" in names
        assert "apple-juice" in names

    def test_search_case_insensitive(self, tmp_path):
        """验证搜索大小写不敏感"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        entry = {
            "name": "TestMemory",
            "type": "user",
            "memory_id": str(uuid.uuid4()),
            "description": "测试",
        }
        index.update_entry(entry)

        results = index.search("testmemory")
        assert len(results) == 1
        assert results[0]["name"] == "TestMemory"

    def test_search_no_match(self, tmp_path):
        """验证搜索无匹配"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        entry = {
            "name": "specific-memory",
            "type": "user",
            "memory_id": str(uuid.uuid4()),
            "description": "特定记忆",
        }
        index.update_entry(entry)

        results = index.search("nonexistent")
        assert results == []


class TestMemoryIndexGroupIsolation:
    """MemoryIndex 分组隔离验证"""

    def test_private_memory_path(self, tmp_path):
        """验证 Private 记忆路径格式"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        entry = {
            "name": "private-memory",
            "type": "user",
            "memory_id": str(uuid.uuid4()),
            "description": "私有记忆",
        }
        index.update_entry(entry)

        content = (tmp_path / "MEMORY.md").read_text()
        assert "user/" in content  # Private 使用 user/ 而非 group/user/

    def test_group_memory_path(self, tmp_path):
        """验证 Group 记忆路径格式"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        index = MemoryIndex(config)

        entry = {
            "name": "group-memory",
            "type": "user",
            "memory_id": str(uuid.uuid4()),
            "description": "组记忆",
            "is_group": True,  # Group 记忆
        }
        index.update_entry(entry)

        content = (tmp_path / "MEMORY.md").read_text()
        assert "group/user/" in content  # Group 使用 group/user/
