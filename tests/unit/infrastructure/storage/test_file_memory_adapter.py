"""Tests for FileMemoryAdapter.

RED PHASE: 验证 FileMemoryAdapter 文件系统操作。
"""

from __future__ import annotations

import uuid

import pytest

from src.infrastructure.config.memory import MemoryConfig
from src.infrastructure.storage.file_memory_adapter import FileMemoryAdapter


class TestFileMemoryAdapterInit:
    """FileMemoryAdapter 初始化验证"""

    def test_init_with_config(self):
        """验证使用配置初始化"""
        config = MemoryConfig.from_env()
        adapter = FileMemoryAdapter(config)
        assert adapter.config is not None

    def test_init_with_custom_path(self, tmp_path):
        """验证使用自定义路径初始化"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))
        assert adapter.config.memory_l0_path == str(tmp_path)


class TestFileMemoryAdapterWrite:
    """FileMemoryAdapter 写入操作验证"""

    def test_write_creates_file(self, tmp_path):
        """验证写入创建文件"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        memory_id = str(uuid.uuid4())
        content = """---
name: test-memory
description: 测试记忆
type: user
originSessionId: test-session
---
这是测试记忆内容。
"""
        adapter.write(memory_id, "user", content)

        # 验证文件存在
        file_path = tmp_path / "user" / f"{memory_id}.md"
        assert file_path.exists()

    def test_write_creates_directory(self, tmp_path):
        """验证写入自动创建目录"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        memory_id = str(uuid.uuid4())
        adapter.write(memory_id, "feedback", "测试内容")

        dir_path = tmp_path / "feedback"
        assert dir_path.exists() and dir_path.is_dir()

    def test_write_content_correct(self, tmp_path):
        """验证写入内容正确"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        memory_id = str(uuid.uuid4())
        content = "测试内容"
        adapter.write(memory_id, "user", content)

        file_path = tmp_path / "user" / f"{memory_id}.md"
        assert file_path.read_text() == content


class TestFileMemoryAdapterRead:
    """FileMemoryAdapter 读取操作验证"""

    def test_read_existing_file(self, tmp_path):
        """验证读取已存在文件"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        memory_id = str(uuid.uuid4())
        content = "测试内容"
        file_path = tmp_path / "user" / f"{memory_id}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        read_content = adapter.read(memory_id, "user")
        assert read_content == content

    def test_read_nonexistent_raises(self, tmp_path):
        """验证读取不存在的文件抛出异常"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        with pytest.raises(FileNotFoundError):
            adapter.read(str(uuid.uuid4()), "user")


class TestFileMemoryAdapterDelete:
    """FileMemoryAdapter 删除操作验证"""

    def test_delete_existing_file(self, tmp_path):
        """验证删除已存在文件"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        memory_id = str(uuid.uuid4())
        file_path = tmp_path / "user" / f"{memory_id}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("测试内容")

        adapter.delete(memory_id, "user")
        assert not file_path.exists()

    def test_delete_nonexistent_no_raise(self, tmp_path):
        """验证删除不存在的文件不抛出异常"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        # 不应抛出异常
        adapter.delete(str(uuid.uuid4()), "user")


class TestFileMemoryAdapterList:
    """FileMemoryAdapter 列表操作验证"""

    def test_list_memories(self, tmp_path):
        """验证列出记忆"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        # 创建多个记忆
        for i in range(3):
            memory_id = str(uuid.uuid4())
            adapter.write(memory_id, "user", f"内容 {i}")

        memories = adapter.list("user")
        assert len(memories) == 3

    def test_list_empty_type(self, tmp_path):
        """验证列出空类型返回空列表"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        memories = adapter.list("nonexistent")
        assert memories == []


class TestFileMemoryAdapterUpdateIndex:
    """FileMemoryAdapter MEMORY.md 索引操作验证"""

    def test_update_index(self, tmp_path):
        """验证更新索引"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        entries = [
            {"name": "test-1", "type": "user", "memory_id": str(uuid.uuid4()), "description": "测试1"},
            {"name": "test-2", "type": "feedback", "memory_id": str(uuid.uuid4()), "description": "测试2"},
        ]

        adapter.update_index(entries)

        index_path = tmp_path / "MEMORY.md"
        assert index_path.exists()
        content = index_path.read_text()
        assert "- [test-1](user/" in content
        assert "- [test-2](feedback/" in content


class TestFileMemoryAdapterPathResolution:
    """FileMemoryAdapter 路径解析验证"""

    def test_path_format(self, tmp_path):
        """验证路径格式 {type}/{memory_id}.md"""
        adapter = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))

        memory_id = str(uuid.uuid4())
        adapter.write(memory_id, "reference", "内容")

        expected_path = tmp_path / "reference" / f"{memory_id}.md"
        assert expected_path.exists()

    def test_xdg_path_priority(self, monkeypatch, tmp_path):
        """验证 XDG 路径优先级"""
        # 设置 XDG_CONFIG_HOME
        xdg_path = tmp_path / "xdg"
        xdg_path.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_path))

        config = MemoryConfig.from_env()
        # XDG_CONFIG_HOME 已设置时，应该使用该路径
        assert str(xdg_path) in config.memory_l0_path
