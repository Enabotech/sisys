"""Tests for Tool domain entity."""

import uuid
from typing import cast

import pytest

from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.exceptions import EntityValidationError


def _make_tool(**kwargs) -> Tool:
    """Factory helper for Tool."""
    defaults: dict = {
        "tool_id": uuid.uuid4(),
        "name": "Test Tool",
    }
    defaults.update(kwargs)
    return Tool(**defaults)


class TestToolCreation:
    """Test Tool entity creation."""

    def test_create_minimal_tool(self):
        """Can create a tool with minimal arguments."""
        tool = _make_tool()
        assert tool.tool_id is not None
        assert tool.name == "Test Tool"
        assert tool.status == ToolStatus.ACTIVE
        assert tool.input_schema == {}
        assert tool.output_schema == {}


class TestToolCategory:
    """Test ToolCategory enum extension for strategic tools."""

    def test_original_categories_exist(self):
        """Original 5 categories remain intact."""
        assert ToolCategory.ANALYSIS == "analysis"
        assert ToolCategory.GENERATION == "generation"
        assert ToolCategory.VALIDATION == "validation"
        assert ToolCategory.VISUALIZATION == "visualization"
        assert ToolCategory.OTHER == "other"

    def test_strategic_categories_exist(self):
        """5 new strategic categories exist."""
        assert ToolCategory.ENVIRONMENT_ANALYSIS == "environment_analysis"
        assert ToolCategory.COMPETITIVE_ANALYSIS == "competitive_analysis"
        assert ToolCategory.STRATEGIC_SELECTION == "strategic_selection"
        assert ToolCategory.BUSINESS_MODEL == "business_model"
        assert ToolCategory.EXECUTION_MANAGEMENT == "execution_management"

    def test_total_category_count(self):
        """ToolCategory has exactly 10 values (5 original + 5 strategic)."""
        assert len(ToolCategory) == 10

    def test_all_categories_are_unique(self):
        """All category values are unique."""
        values = [cat.value for cat in ToolCategory]
        assert len(values) == len(set(values))

    def test_strategic_categories_do_not_collide_with_original(self):
        """Strategic categories do not overlap with original categories."""
        original = {"analysis", "generation", "validation", "visualization", "other"}
        strategic = {
            "environment_analysis",
            "competitive_analysis",
            "strategic_selection",
            "business_model",
            "execution_management",
        }
        assert original.isdisjoint(strategic)


class TestToolValidation:
    """Test Tool invariant validation."""

    def test_valid_tool_passes(self):
        """Correctly constructed tool passes validation."""
        tool = _make_tool()
        assert tool.validate() is True

    def test_invalid_id_fails(self):
        """Tool with non-UUID id fails validation."""
        tool = _make_tool()
        object.__setattr__(tool, "tool_id", cast(uuid.UUID, "not-a-uuid"))
        with pytest.raises(EntityValidationError, match="tool_id must be a valid UUID"):
            tool.validate()

    def test_empty_name_fails(self):
        """Tool with empty name fails validation."""
        tool = _make_tool(name="")
        with pytest.raises(EntityValidationError, match="name must not be empty"):
            tool.validate()

    def test_invalid_input_schema_fails(self):
        """Tool with non-dict input_schema fails validation."""
        tool = _make_tool()
        object.__setattr__(tool, "input_schema", cast(dict, "not a dict"))
        with pytest.raises(EntityValidationError, match="input_schema must be a dict"):
            tool.validate()

    def test_invalid_output_schema_fails(self):
        """Tool with non-dict output_schema fails validation."""
        tool = _make_tool()
        object.__setattr__(tool, "output_schema", cast(dict, "not a dict"))
        with pytest.raises(EntityValidationError, match="output_schema must be a dict"):
            tool.validate()
