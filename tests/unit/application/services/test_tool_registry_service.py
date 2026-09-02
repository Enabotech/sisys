"""Tests for ToolRegistryServicePort and ToolRegistryService."""

import logging
import uuid
from unittest.mock import MagicMock

import pytest

from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.application.services.tool_registry_service import ToolRegistryService
from src.domain.entities.tool import Tool, ToolCategory
from src.domain.exceptions import EntityValidationError
from src.domain.exceptions.tool_exceptions import ToolNotFoundError
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


class TestToolRegistryServicePortProtocol:
    """Test ToolRegistryServicePort Protocol definition."""

    def test_is_protocol(self):
        """ToolRegistryServicePort is a Protocol."""
        from typing import Protocol

        assert issubclass(ToolRegistryServicePort, Protocol)

    def test_has_register_all_method(self):
        """ToolRegistryServicePort has register_all method."""
        assert hasattr(ToolRegistryServicePort, "register_all")

    def test_has_get_tool_method(self):
        """ToolRegistryServicePort has get_tool method."""
        assert hasattr(ToolRegistryServicePort, "get_tool")

    def test_has_get_tools_by_category_method(self):
        """ToolRegistryServicePort has get_tools_by_category method."""
        assert hasattr(ToolRegistryServicePort, "get_tools_by_category")

    def test_has_list_all_tools_method(self):
        """ToolRegistryServicePort has list_all_tools method."""
        assert hasattr(ToolRegistryServicePort, "list_all_tools")

    def test_has_tool_count_method(self):
        """ToolRegistryServicePort has tool_count method."""
        assert hasattr(ToolRegistryServicePort, "tool_count")

    def test_implements_protocol(self):
        """ToolRegistryService implements ToolRegistryServicePort."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        assert isinstance(service, ToolRegistryServicePort)


class TestToolRegistryServiceRegisterAll:
    """Test ToolRegistryService.register_all."""

    def test_register_all_23_tools(self):
        """register_all registers exactly 23 tools."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        assert service.tool_count() == 23

    def test_register_all_idempotent(self):
        """register_all is idempotent (no duplicate errors)."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        # Second call should not raise
        service.register_all()
        assert service.tool_count() == 23

    def test_register_all_logs_skip_on_duplicate(self, caplog):
        """register_all 第二次调用时对重复工具记录 debug 日志."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()

        with caplog.at_level(
            logging.DEBUG,
            logger="src.application.services.tool_registry_service",
        ):
            service.register_all()

        skip_logs = [r for r in caplog.records if "跳过" in r.getMessage() or "skip" in r.getMessage().lower()]
        assert len(skip_logs) >= 1
        assert all(r.levelno == logging.DEBUG for r in skip_logs)

    def test_register_all_no_log_on_first_call(self, caplog):
        """register_all 首次调用时不记录 skip 日志."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)

        with caplog.at_level(
            logging.DEBUG,
            logger="src.application.services.tool_registry_service",
        ):
            service.register_all()

        skip_logs = [r for r in caplog.records if "跳过" in r.getMessage() or "skip" in r.getMessage().lower()]
        assert len(skip_logs) == 0


class TestToolRegistryServiceGetTool:
    """Test ToolRegistryService.get_tool."""

    def test_get_tool_by_id(self):
        """Get tool by ID returns correct tool."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        tools = service.list_all_tools()
        tool = tools[0]
        result = service.get_tool(tool_id=tool.tool_id)
        assert result == tool

    def test_get_tool_by_name(self):
        """Get tool by name returns correct tool."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        result = service.get_tool(tool_name="PESTEL 分析")
        assert result.name == "PESTEL 分析"

    def test_get_tool_not_found(self):
        """Get non-existent tool raises ToolNotFoundError."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        with pytest.raises(ToolNotFoundError):
            service.get_tool(tool_id=uuid.uuid4())

    def test_get_tool_not_found_by_name(self):
        """Get non-existent tool by name raises ToolNotFoundError."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        with pytest.raises(ToolNotFoundError):
            service.get_tool(tool_name="Non-existent Tool")

    def test_get_tool_without_id_or_name(self):
        """Get tool without id or name raises EntityValidationError (参数验证失败)."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        with pytest.raises(EntityValidationError) as exc_info:
            service.get_tool()
        assert exc_info.value.context["parameter"] == "tool_id|tool_name"


class TestToolRegistryServiceCategoryQuery:
    """Test ToolRegistryService.get_tools_by_category."""

    def test_get_tools_by_category(self):
        """Get tools by category returns correct list."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        tools = service.get_tools_by_category(ToolCategory.ENVIRONMENT_ANALYSIS)
        assert len(tools) == 3

    def test_environment_analysis_count(self):
        """ENVIRONMENT_ANALYSIS has 3 tools."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        tools = service.get_tools_by_category(ToolCategory.ENVIRONMENT_ANALYSIS)
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert "PESTEL 分析" in names
        assert "波特五力" in names
        assert "$APPEALS" in names

    def test_competitive_analysis_count(self):
        """COMPETITIVE_ANALYSIS has 3 tools."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        tools = service.get_tools_by_category(ToolCategory.COMPETITIVE_ANALYSIS)
        assert len(tools) == 3

    def test_strategic_selection_count(self):
        """STRATEGIC_SELECTION has 6 tools."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        tools = service.get_tools_by_category(ToolCategory.STRATEGIC_SELECTION)
        assert len(tools) == 6

    def test_business_model_count(self):
        """BUSINESS_MODEL has 3 tools."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        tools = service.get_tools_by_category(ToolCategory.BUSINESS_MODEL)
        assert len(tools) == 3

    def test_execution_management_count(self):
        """EXECUTION_MANAGEMENT has 8 tools."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        tools = service.get_tools_by_category(ToolCategory.EXECUTION_MANAGEMENT)
        assert len(tools) == 8

    def test_category_empty_result(self):
        """Category with no tools returns empty list."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        tools = service.get_tools_by_category(ToolCategory.ANALYSIS)
        assert tools == []


class TestToolRegistryServiceToolCount:
    """Test ToolRegistryService.tool_count."""

    def test_tool_count_before_register(self):
        """tool_count is 0 before register_all."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        assert service.tool_count() == 0

    def test_tool_count_after_register(self):
        """tool_count is 23 after register_all."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()
        assert service.tool_count() == 23

    def test_tool_count_delegates_to_repository(self):
        """tool_count 委托 repository.count() 而非 list_all()."""
        mock_repo = MagicMock(spec=ToolRepositoryPort)
        mock_repo.count.return_value = 23
        service = ToolRegistryService(repository=mock_repo)
        assert service.tool_count() == 23
        mock_repo.count.assert_called_once_with()
        mock_repo.list_all.assert_not_called()

    def test_tool_count_zero_on_empty_repository(self):
        """空仓储时 tool_count 委托 repository.count() 返回 0."""
        mock_repo = MagicMock(spec=ToolRepositoryPort)
        mock_repo.count.return_value = 0
        service = ToolRegistryService(repository=mock_repo)
        assert service.tool_count() == 0
        mock_repo.count.assert_called_once_with()
