"""Tests for Tool domain entity."""

import uuid
from datetime import UTC, datetime
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
        """构造空名称工具时 __post_init__ 自动触发 EntityValidationError."""
        with pytest.raises(EntityValidationError, match="name must not be empty"):
            _make_tool(name="")

    def test_name_too_long_fails(self):
        """name 长度超过 200 字符时构造失败."""
        with pytest.raises(EntityValidationError, match="name 长度不能超过 200 字符"):
            _make_tool(name="a" * 201)

    def test_description_too_long_fails(self):
        """description 长度超过 500 字符时构造失败."""
        with pytest.raises(
            EntityValidationError,
            match="description 长度不能超过 500 字符",
        ):
            _make_tool(description="d" * 501)

    def test_description_at_max_length_passes(self):
        """description 长度等于上限时构造成功."""
        tool = _make_tool(description="d" * 500)
        assert len(tool.description) == 500

    def test_invalid_category_type_fails(self):
        """category 传入非枚举值时构造失败."""
        with pytest.raises(
            EntityValidationError,
            match="category 必须为 ToolCategory 枚举值",
        ):
            _make_tool(category=cast(ToolCategory, "analysis"))

    def test_invalid_status_type_fails(self):
        """status 传入非枚举值时构造失败."""
        with pytest.raises(
            EntityValidationError,
            match="status 必须为 ToolStatus 枚举值",
        ):
            _make_tool(status=cast(ToolStatus, "active"))

    def test_invalid_version_format_fails(self):
        """version 不符合 SemVer X.Y.Z 时构造失败."""
        with pytest.raises(
            EntityValidationError,
            match="version 必须符合 SemVer X.Y.Z 格式",
        ):
            _make_tool(version="not-semver")

    def test_version_rejects_two_segment(self):
        """version 仅两段（如 '1.0'）被 SemVer 拒绝."""
        with pytest.raises(
            EntityValidationError,
            match="version 必须符合 SemVer X.Y.Z 格式",
        ):
            _make_tool(version="1.0")

    def test_version_rejects_v_prefix(self):
        """version 带 v 前缀被 SemVer 拒绝."""
        with pytest.raises(
            EntityValidationError,
            match="version 必须符合 SemVer X.Y.Z 格式",
        ):
            _make_tool(version="v1.0.0")

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

    def test_empty_schema_is_valid(self):
        """空 schema（默认 field 工厂产出 {}）合法，守护其他测试夹具."""
        tool = _make_tool()  # 默认 input_schema={} output_schema={}
        assert tool.input_schema == {}
        assert tool.output_schema == {}
        assert tool.validate() is True

    def test_input_schema_without_keywords_fails(self):
        """非空 input_schema 缺少 JSON Schema 关键词时构造失败."""
        with pytest.raises(
            EntityValidationError,
            match="input_schema 非空时必须包含 JSON Schema 关键词",
        ):
            _make_tool(input_schema={"description": "no keywords"})

    def test_output_schema_without_keywords_fails(self):
        """非空 output_schema 缺少 JSON Schema 关键词时构造失败."""
        with pytest.raises(
            EntityValidationError,
            match="output_schema 非空时必须包含 JSON Schema 关键词",
        ):
            _make_tool(output_schema={"description": "no keywords"})

    def test_schema_with_type_keyword_passes(self):
        """含 type 关键词的 schema 合法."""
        tool = _make_tool(
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        assert tool.validate() is True

    def test_schema_with_properties_keyword_passes(self):
        """含 properties 关键词的 schema 合法."""
        tool = _make_tool(
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
        )
        assert tool.validate() is True

    def test_post_init_auto_validates(self):
        """__post_init__ 自动调用 validate()，构造即校验."""
        # 默认参数下 _make_tool() 必不抛错，构造成功即说明 __post_init__ 已生效
        tool = _make_tool()
        assert tool is not None

    def test_naive_datetime_fails(self):
        """created_at 缺失时区信息时构造失败."""
        with pytest.raises(
            EntityValidationError,
            match="created_at/updated_at 必须为 timezone-aware",
        ):
            _make_tool(
                created_at=datetime(2024, 1, 1),  # noqa: DTZ001
                updated_at=datetime(2024, 1, 2),  # noqa: DTZ001
            )

    def test_updated_before_created_fails(self):
        """updated_at 早于 created_at 时构造失败."""
        with pytest.raises(
            EntityValidationError,
            match="updated_at 不能早于 created_at",
        ):
            _make_tool(
                created_at=datetime(2024, 6, 1, tzinfo=UTC),
                updated_at=datetime(2024, 1, 1, tzinfo=UTC),
            )

    def test_created_equals_updated_passes(self):
        """created_at == updated_at 时构造成功（时序等值边界）."""
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        tool = _make_tool(created_at=ts, updated_at=ts)
        assert tool.created_at == tool.updated_at
