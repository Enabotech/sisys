"""Tests for ToolRepositoryPort and InMemoryToolRepository."""

import uuid

import pytest

from src.domain.entities.tool import Tool, ToolCategory
from src.domain.exceptions import EntityValidationError
from src.domain.exceptions.tool_exceptions import (
    ToolAlreadyExistsError,
    ToolNotFoundError,
)
from src.domain.ports.tool_repository import ToolRepositoryPort
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository


def _make_tool(**kwargs) -> Tool:
    """Factory helper for Tool."""
    defaults: dict = {
        "tool_id": uuid.uuid4(),
        "name": "Test Tool",
        "category": ToolCategory.ANALYSIS,
    }
    defaults.update(kwargs)
    return Tool(**defaults)


class TestToolRepositoryPortProtocol:
    """Test ToolRepositoryPort Protocol definition."""

    def test_is_protocol(self):
        """ToolRepositoryPort is a Protocol."""
        from typing import Protocol

        assert issubclass(ToolRepositoryPort, Protocol)

    def test_has_save_method(self):
        """ToolRepositoryPort has save method."""
        assert hasattr(ToolRepositoryPort, "save")

    def test_has_get_by_id_method(self):
        """ToolRepositoryPort has get_by_id method."""
        assert hasattr(ToolRepositoryPort, "get_by_id")

    def test_has_get_by_name_method(self):
        """ToolRepositoryPort has get_by_name method."""
        assert hasattr(ToolRepositoryPort, "get_by_name")

    def test_has_list_all_method(self):
        """ToolRepositoryPort has list_all method."""
        assert hasattr(ToolRepositoryPort, "list_all")

    def test_has_list_by_category_method(self):
        """ToolRepositoryPort has list_by_category method."""
        assert hasattr(ToolRepositoryPort, "list_by_category")

    def test_has_delete_method(self):
        """ToolRepositoryPort has delete method."""
        assert hasattr(ToolRepositoryPort, "delete")

    def test_has_count_method(self):
        """ToolRepositoryPort has count method."""
        assert hasattr(ToolRepositoryPort, "count")

    def test_implements_protocol(self):
        """InMemoryToolRepository implements ToolRepositoryPort."""
        assert isinstance(InMemoryToolRepository(), ToolRepositoryPort)


class TestInMemoryToolRepositoryCRUD:
    """Test InMemoryToolRepository CRUD operations."""

    def test_save_and_get_by_id(self):
        """Save tool and retrieve by ID."""
        repo = InMemoryToolRepository()
        tool = _make_tool(tool_id=uuid.UUID("00000000-0000-0000-0000-000000000001"))
        repo.save(tool)
        result = repo.get_by_id(tool.tool_id)
        assert result == tool

    def test_save_and_get_by_name(self):
        """Save tool and retrieve by name."""
        repo = InMemoryToolRepository()
        tool = _make_tool(name="PESTEL 分析")
        repo.save(tool)
        result = repo.get_by_name("PESTEL 分析")
        assert result == tool

    def test_get_by_id_not_found(self):
        """Get non-existent tool by ID raises ToolNotFoundError."""
        repo = InMemoryToolRepository()
        with pytest.raises(ToolNotFoundError):
            repo.get_by_id(uuid.uuid4())

    def test_get_by_name_not_found(self):
        """Get non-existent tool by name raises ToolNotFoundError."""
        repo = InMemoryToolRepository()
        with pytest.raises(ToolNotFoundError):
            repo.get_by_name("Non-existent Tool")

    def test_save_duplicate_id_raises(self):
        """Save tool with duplicate ID raises ToolAlreadyExistsError."""
        repo = InMemoryToolRepository()
        tool_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        tool1 = _make_tool(tool_id=tool_id, name="Tool 1")
        tool2 = _make_tool(tool_id=tool_id, name="Tool 2")
        repo.save(tool1)
        with pytest.raises(ToolAlreadyExistsError):
            repo.save(tool2)

    def test_save_duplicate_name_raises(self):
        """Save tool with duplicate name raises ToolAlreadyExistsError."""
        repo = InMemoryToolRepository()
        tool1 = _make_tool(name="PESTEL 分析")
        tool2 = _make_tool(name="PESTEL 分析")
        repo.save(tool1)
        with pytest.raises(ToolAlreadyExistsError):
            repo.save(tool2)

    def test_list_all(self):
        """List all tools."""
        repo = InMemoryToolRepository()
        tool1 = _make_tool(name="Tool 1")
        tool2 = _make_tool(name="Tool 2")
        repo.save(tool1)
        repo.save(tool2)
        result = repo.list_all()
        assert len(result) == 2

    def test_list_by_category(self):
        """List tools by category."""
        repo = InMemoryToolRepository()
        tool1 = _make_tool(
            name="Tool 1",
            category=ToolCategory.ENVIRONMENT_ANALYSIS,
        )
        tool2 = _make_tool(
            name="Tool 2",
            category=ToolCategory.COMPETITIVE_ANALYSIS,
        )
        repo.save(tool1)
        repo.save(tool2)
        result = repo.list_by_category(ToolCategory.ENVIRONMENT_ANALYSIS)
        assert len(result) == 1
        assert result[0] == tool1

    def test_delete(self):
        """Delete tool by ID."""
        repo = InMemoryToolRepository()
        tool = _make_tool()
        repo.save(tool)
        repo.delete(tool.tool_id)
        with pytest.raises(ToolNotFoundError):
            repo.get_by_id(tool.tool_id)

    def test_delete_not_found(self):
        """Delete non-existent tool raises ToolNotFoundError."""
        repo = InMemoryToolRepository()
        with pytest.raises(ToolNotFoundError):
            repo.delete(uuid.uuid4())

    def test_empty_repository(self):
        """Empty repository returns empty list."""
        repo = InMemoryToolRepository()
        assert repo.list_all() == []
        assert repo.list_by_category(ToolCategory.ANALYSIS) == []


class TestInMemoryToolRepositoryCount:
    """Test InMemoryToolRepository.count O(1) 行为."""

    def test_count_empty_repository(self):
        """空仓储 count 返回 0."""
        repo = InMemoryToolRepository()
        assert repo.count() == 0

    def test_count_after_single_save(self):
        """单次保存后 count 返回 1."""
        repo = InMemoryToolRepository()
        repo.save(_make_tool())
        assert repo.count() == 1

    def test_count_after_multiple_saves(self):
        """多次保存后 count 返回累计数量."""
        repo = InMemoryToolRepository()
        for i in range(5):
            repo.save(_make_tool(name=f"Tool {i}"))
        assert repo.count() == 5

    def test_count_after_delete(self):
        """删除后 count 减少."""
        repo = InMemoryToolRepository()
        tool = _make_tool()
        repo.save(tool)
        assert repo.count() == 1
        repo.delete(tool.tool_id)
        assert repo.count() == 0


class TestInMemoryToolRepositorySaveGuard:
    """Test InMemoryToolRepository.save() 仓储层二次守卫."""

    def test_save_rejects_invalid_category(self):
        """save() 拒绝 category 非枚举值（__post_init__ 在构造期已阻止，但 mutation 场景由仓储层兜底）."""
        from typing import cast

        from src.domain.entities.tool import ToolCategory

        repo = InMemoryToolRepository()
        # 绕过 __post_init__ 直接构造（模拟 mutation）
        tool = _make_tool()
        object.__setattr__(
            tool,
            "category",
            cast(ToolCategory, "analysis"),
        )
        with pytest.raises(EntityValidationError, match="category 必须为 ToolCategory 枚举值"):
            repo.save(tool)

    def test_save_rejects_invalid_status(self):
        """save() 拒绝 status 非枚举值."""
        from typing import cast

        from src.domain.entities.tool import ToolStatus

        repo = InMemoryToolRepository()
        tool = _make_tool()
        object.__setattr__(tool, "status", cast(ToolStatus, "active"))
        with pytest.raises(EntityValidationError, match="status 必须为 ToolStatus 枚举值"):
            repo.save(tool)

    def test_save_validates_before_duplicate_check(self):
        """save() 校验前置：非法工具优先抛 EntityValidationError 而非 ToolAlreadyExistsError."""
        from typing import cast

        repo = InMemoryToolRepository()
        # 第一个 tool 正常保存
        tool1 = _make_tool()
        repo.save(tool1)
        # 第二个 tool 同名同 ID，但 category 被 mutation 为非法
        tool2 = _make_tool(name=tool1.name)
        object.__setattr__(tool2, "tool_id", tool1.tool_id)
        object.__setattr__(
            tool2,
            "category",
            cast(ToolCategory, "invalid"),
        )
        # 期望：抛 EntityValidationError 而非 ToolAlreadyExistsError（校验在前）
        with pytest.raises(EntityValidationError):
            repo.save(tool2)
