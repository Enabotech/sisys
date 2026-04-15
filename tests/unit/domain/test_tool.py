"""Tests for Tool domain entity."""

import uuid

import pytest

from src.domain.entities.tool import Tool, ToolStatus


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


class TestToolValidation:
    """Test Tool invariant validation."""

    def test_valid_tool_passes(self):
        """Correctly constructed tool passes validation."""
        tool = _make_tool()
        assert tool.validate() is True

    def test_invalid_id_fails(self):
        """Tool with non-UUID id fails validation."""
        tool = _make_tool()
        tool.tool_id = "not-a-uuid"  # type: ignore
        with pytest.raises(ValueError, match="tool_id must be a valid UUID"):
            tool.validate()

    def test_empty_name_fails(self):
        """Tool with empty name fails validation."""
        tool = _make_tool(name="")
        with pytest.raises(ValueError, match="name must not be empty"):
            tool.validate()

    def test_invalid_input_schema_fails(self):
        """Tool with non-dict input_schema fails validation."""
        tool = _make_tool()
        tool.input_schema = "not a dict"  # type: ignore
        with pytest.raises(ValueError, match="input_schema must be a dict"):
            tool.validate()

    def test_invalid_output_schema_fails(self):
        """Tool with non-dict output_schema fails validation."""
        tool = _make_tool()
        tool.output_schema = "not a dict"  # type: ignore
        with pytest.raises(ValueError, match="output_schema must be a dict"):
            tool.validate()
