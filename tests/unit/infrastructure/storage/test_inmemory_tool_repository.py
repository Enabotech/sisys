"""Tests for ToolRepositoryPort and InMemoryToolRepository."""

import uuid

import pytest

from src.domain.entities.tool import Tool, ToolCategory
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
