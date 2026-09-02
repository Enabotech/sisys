"""集成测试：工具注册全链路

验证端口→服务→仓储→实体的完整注册流程。
"""

from __future__ import annotations

import uuid

import pytest

from src.application.services.tool_registry_service import ToolRegistryService
from src.domain.entities.tool import ToolCategory
from src.domain.exceptions.tool_exceptions import ToolNotFoundError
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository


class TestToolRegistrationIntegration:
    """Test end-to-end tool registration flow."""

    def test_full_registration_flow(self):
        """Complete registration flow: bootstrap → register_all → query → verify count=23."""
        # 1. Create repository and service
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)

        # 2. Register all tools
        service.register_all()

        # 3. Verify total count
        assert service.tool_count() == 23

        # 4. Verify category distribution
        env_tools = service.get_tools_by_category(ToolCategory.ENVIRONMENT_ANALYSIS)
        assert len(env_tools) == 3

        comp_tools = service.get_tools_by_category(ToolCategory.COMPETITIVE_ANALYSIS)
        assert len(comp_tools) == 3

        strat_tools = service.get_tools_by_category(ToolCategory.STRATEGIC_SELECTION)
        assert len(strat_tools) == 6

        biz_tools = service.get_tools_by_category(ToolCategory.BUSINESS_MODEL)
        assert len(biz_tools) == 3

        exec_tools = service.get_tools_by_category(ToolCategory.EXECUTION_MANAGEMENT)
        assert len(exec_tools) == 8

        # 5. Verify specific tool query
        pestel = service.get_tool(tool_name="PESTEL 分析")
        assert pestel.name == "PESTEL 分析"
        assert pestel.category == ToolCategory.ENVIRONMENT_ANALYSIS
        assert pestel.input_schema is not None
        assert pestel.output_schema is not None

    def test_tool_query_by_id_and_name(self):
        """Query tools by ID and name."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()

        tools = service.list_all_tools()
        first_tool = tools[0]

        # Query by ID
        by_id = service.get_tool(tool_id=first_tool.tool_id)
        assert by_id == first_tool

        # Query by name
        by_name = service.get_tool(tool_name=first_tool.name)
        assert by_name == first_tool

    def test_tool_not_found_error(self):
        """Query non-existent tool raises ToolNotFoundError."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()

        with pytest.raises(ToolNotFoundError):
            service.get_tool(tool_id=uuid.uuid4())

        with pytest.raises(ToolNotFoundError):
            service.get_tool(tool_name="Non-existent Tool")

    def test_list_all_tools(self):
        """List all tools returns complete list."""
        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        service.register_all()

        all_tools = service.list_all_tools()
        assert len(all_tools) == 23
        names = {t.name for t in all_tools}
        assert "PESTEL 分析" in names
        assert "波特五力" in names
        assert "SWOT-TOWS" in names
        assert "商业模式画布" in names
        assert "BSC 平衡计分卡" in names
