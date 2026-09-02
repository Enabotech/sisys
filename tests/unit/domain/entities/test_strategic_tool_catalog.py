"""Tests for StrategicToolCatalog domain entity."""

import uuid

from src.domain.entities.tool import Tool, ToolCategory


def _make_tool(**kwargs) -> Tool:
    """Factory helper for Tool."""
    defaults: dict = {
        "tool_id": uuid.uuid4(),
        "name": "Test Tool",
    }
    defaults.update(kwargs)
    return Tool(**defaults)


class TestStrategicToolCatalog:
    """Test StrategicToolCatalog constants."""

    def test_catalog_exists(self):
        """StrategicToolCatalog module can be imported."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        assert TOOL_CATALOG is not None

    def test_catalog_count(self):
        """TOOL_CATALOG contains exactly 23 tools."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        assert len(TOOL_CATALOG) == 23

    def test_all_tools_have_unique_ids(self):
        """All tools have unique UUIDs."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        ids = [tool.tool_id for tool in TOOL_CATALOG]
        assert len(ids) == len(set(ids))

    def test_all_tools_have_unique_names(self):
        """All tools have unique names."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        names = [tool.name for tool in TOOL_CATALOG]
        assert len(names) == len(set(names))

    def test_all_tools_have_valid_category(self):
        """All tools belong to extended ToolCategory enum."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        strategic_categories = {
            ToolCategory.ENVIRONMENT_ANALYSIS,
            ToolCategory.COMPETITIVE_ANALYSIS,
            ToolCategory.STRATEGIC_SELECTION,
            ToolCategory.BUSINESS_MODEL,
            ToolCategory.EXECUTION_MANAGEMENT,
        }
        for tool in TOOL_CATALOG:
            assert tool.category in strategic_categories, f"Tool '{tool.name}' has invalid category: {tool.category}"

    def test_all_tools_have_non_empty_input_schema(self):
        """All tools have non-empty input_schema."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        for tool in TOOL_CATALOG:
            assert tool.input_schema, f"Tool '{tool.name}' has empty input_schema"
            assert isinstance(tool.input_schema, dict)

    def test_all_tools_have_non_empty_output_schema(self):
        """All tools have non-empty output_schema."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        for tool in TOOL_CATALOG:
            assert tool.output_schema, f"Tool '{tool.name}' has empty output_schema"
            assert isinstance(tool.output_schema, dict)

    def test_all_tools_have_description(self):
        """All tools have non-empty description."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        for tool in TOOL_CATALOG:
            assert tool.description, f"Tool '{tool.name}' has empty description"

    def test_all_tools_pass_validation(self):
        """All tools pass entity validation."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        for tool in TOOL_CATALOG:
            assert tool.validate(), f"Tool '{tool.name}' failed validation"

    def test_environment_analysis_tools_count(self):
        """ENVIRONMENT_ANALYSIS category has exactly 3 tools."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        tools = [t for t in TOOL_CATALOG if t.category == ToolCategory.ENVIRONMENT_ANALYSIS]
        assert len(tools) == 3

    def test_competitive_analysis_tools_count(self):
        """COMPETITIVE_ANALYSIS category has exactly 3 tools."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        tools = [t for t in TOOL_CATALOG if t.category == ToolCategory.COMPETITIVE_ANALYSIS]
        assert len(tools) == 3

    def test_strategic_selection_tools_count(self):
        """STRATEGIC_SELECTION category has exactly 6 tools."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        tools = [t for t in TOOL_CATALOG if t.category == ToolCategory.STRATEGIC_SELECTION]
        assert len(tools) == 6

    def test_business_model_tools_count(self):
        """BUSINESS_MODEL category has exactly 3 tools."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        tools = [t for t in TOOL_CATALOG if t.category == ToolCategory.BUSINESS_MODEL]
        assert len(tools) == 3

    def test_execution_management_tools_count(self):
        """EXECUTION_MANAGEMENT category has exactly 8 tools."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        tools = [t for t in TOOL_CATALOG if t.category == ToolCategory.EXECUTION_MANAGEMENT]
        assert len(tools) == 8


class TestToolSchemaValidity:
    """Test that all tools have valid JSON Schema dictionaries."""

    def test_input_schema_has_type_or_properties(self):
        """input_schema contains JSON Schema keywords."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        for tool in TOOL_CATALOG:
            schema = tool.input_schema
            # JSON Schema should have type, properties, or $ref
            has_valid_keywords = any(key in schema for key in ("type", "properties", "$ref", "allOf", "anyOf"))
            assert has_valid_keywords, f"Tool '{tool.name}' input_schema lacks JSON Schema keywords"

    def test_output_schema_has_type_or_properties(self):
        """output_schema contains JSON Schema keywords."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        for tool in TOOL_CATALOG:
            schema = tool.output_schema
            has_valid_keywords = any(key in schema for key in ("type", "properties", "$ref", "allOf", "anyOf"))
            assert has_valid_keywords, f"Tool '{tool.name}' output_schema lacks JSON Schema keywords"

    def test_known_tool_names_present(self):
        """Key strategic tools are present in catalog."""
        from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

        names = {t.name for t in TOOL_CATALOG}
        expected_names = {
            "PESTEL 分析",
            "波特五力",
            "$APPEALS",
            "竞争对手分析",
            "价值链分析",
            "VRIO 框架",
            "安索夫矩阵",
            "SWOT-TOWS",
            "GE-麦肯锡矩阵",
        }
        for name in expected_names:
            assert name in names, f"Expected tool '{name}' not found in catalog"
