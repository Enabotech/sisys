"""Tests for MemoryRouter.

RED PHASE: 验证 MemoryRouter 路径路由功能
"""

from __future__ import annotations

import uuid

from src.infrastructure.config.memory import MemoryConfig
from src.infrastructure.storage.fs.memory_router import MemoryRouter


class TestMemoryRouterInit:
    """MemoryRouter 初始化验证"""

    def test_init_with_config(self, tmp_path):
        """验证使用配置初始化"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)
        assert router.config is not None
        assert router.config.memory_l0_path == str(tmp_path)


class TestMemoryRouterPrivatePath:
    """MemoryRouter Private 路径策略验证"""

    def test_private_memory_path_format(self, tmp_path):
        """验证 Private 记忆路径格式"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        memory_id = str(uuid.uuid4())
        path = router.get_memory_path("user", memory_id, is_group=False)

        assert path == f"user/{memory_id}.md"

    def test_private_memory_path_user_type(self, tmp_path):
        """验证 Private user 类型路径"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        memory_id = str(uuid.uuid4())
        path = router.get_memory_path("user", memory_id, is_group=False)

        assert path.startswith("user/")
        assert path.endswith(f"{memory_id}.md")

    def test_private_memory_path_feedback_type(self, tmp_path):
        """验证 Private feedback 类型路径"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        memory_id = str(uuid.uuid4())
        path = router.get_memory_path("feedback", memory_id, is_group=False)

        assert path.startswith("feedback/")
        assert path.endswith(f"{memory_id}.md")

    def test_private_memory_path_project_type(self, tmp_path):
        """验证 Private project 类型路径"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        memory_id = str(uuid.uuid4())
        path = router.get_memory_path("project", memory_id, is_group=False)

        assert path.startswith("project/")
        assert path.endswith(f"{memory_id}.md")

    def test_private_memory_path_reference_type(self, tmp_path):
        """验证 Private reference 类型路径"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        memory_id = str(uuid.uuid4())
        path = router.get_memory_path("reference", memory_id, is_group=False)

        assert path.startswith("reference/")
        assert path.endswith(f"{memory_id}.md")


class TestMemoryRouterGroupPath:
    """MemoryRouter Group 路径策略验证"""

    def test_group_memory_path_format(self, tmp_path):
        """验证 Group 记忆路径格式"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        memory_id = str(uuid.uuid4())
        path = router.get_memory_path("user", memory_id, is_group=True)

        assert path == f"group/user/{memory_id}.md"

    def test_group_memory_path_user_type(self, tmp_path):
        """验证 Group user 类型路径"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        memory_id = str(uuid.uuid4())
        path = router.get_memory_path("user", memory_id, is_group=True)

        assert path.startswith("group/user/")
        assert path.endswith(f"{memory_id}.md")

    def test_group_memory_path_feedback_type(self, tmp_path):
        """验证 Group feedback 类型路径"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        memory_id = str(uuid.uuid4())
        path = router.get_memory_path("feedback", memory_id, is_group=True)

        assert path.startswith("group/feedback/")
        assert path.endswith(f"{memory_id}.md")


class TestMemoryRouterIndexPath:
    """MemoryRouter 索引路径验证"""

    def test_private_index_path(self, tmp_path):
        """验证 Private 记忆使用主索引"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        index_path = router.get_index_path(is_group=False)
        assert index_path == "MEMORY.md"

    def test_group_index_path(self, tmp_path):
        """验证 Group 记忆使用独立索引"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        index_path = router.get_index_path(is_group=True)
        assert index_path == "group/MEMORY.md"


class TestMemoryRouterResolve:
    """MemoryRouter 解析功能验证"""

    def test_resolve_private_memory_path(self, tmp_path):
        """验证解析 Private 记忆完整路径"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        memory_id = str(uuid.uuid4())
        full_path = router.resolve_path("user", memory_id, is_group=False)

        base = tmp_path / "user" / f"{memory_id}.md"
        assert full_path == base

    def test_resolve_group_memory_path(self, tmp_path):
        """验证解析 Group 记忆完整路径"""
        config = MemoryConfig(memory_l0_path=str(tmp_path))
        router = MemoryRouter(config)

        memory_id = str(uuid.uuid4())
        full_path = router.resolve_path("user", memory_id, is_group=True)

        base = tmp_path / "group" / "user" / f"{memory_id}.md"
        assert full_path == base
