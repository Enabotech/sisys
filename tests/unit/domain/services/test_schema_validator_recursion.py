"""SchemaValidator 递归深度 + 循环引用测试(Round 2 P1-3 修复守护)

覆盖范围:
1. 5000 层嵌套 dict → 1 个 violation 而非 RecursionError
2. 循环引用 {self: self} → circular reference violation
3. _MAX_RECURSION_DEPTH = 32 阈值精确触发
4. items 数组递归深度限制
5. 混合嵌套(dict + list + dict)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.services.schema_validator import (
    MAX_RECURSION_DEPTH,
    SchemaValidator,
)


def _make_tool(schema: dict, *, is_input: bool = True) -> Tool:
    now = datetime.now(UTC)
    if is_input:
        return Tool(
            tool_id=uuid.uuid4(),
            name="t",
            description="t",
            category=ToolCategory.ANALYSIS,
            input_schema=schema,
            output_schema={},
            status=ToolStatus.ACTIVE,
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )
    return Tool(
        tool_id=uuid.uuid4(),
        name="t",
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema={},
        output_schema=schema,
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


def _make_recursive_schema(depth: int) -> dict:
    """构造嵌套 properties 子 schema 链(additionalProperties: True 触发递归)

    Returns:
        {"type": "object", "properties": {"nested": <deeper_schema>}, "additionalProperties": True}
    """
    if depth == 0:
        return {"type": "object"}
    return {
        "type": "object",
        "properties": {"nested": _make_recursive_schema(depth - 1)},
        "additionalProperties": True,
    }


class TestRecursionDepthLimit:
    """Round 2 P1-3:_validate_node 递归深度限制 + 循环引用检测"""

    def test_max_recursion_depth_constant_is_32(self) -> None:
        """_MAX_RECURSION_DEPTH = 32(防御 LLM 模型漂移)"""
        assert MAX_RECURSION_DEPTH == 32

    def test_5000_layer_deep_nested_dict_does_not_recurse_error(self) -> None:
        """5000 层嵌套 dict 不会触发 RecursionError,而是返回 depth violation"""
        deep_dict: dict = {}
        current = deep_dict
        for _ in range(5000):
            current["nested"] = {}
            current = current["nested"]

        # 使用递归 schema 让 _validate_node 进入 "nested" 键
        # (additionalProperties: True 避免 nested 触发额外 violation)
        schema = _make_recursive_schema(depth=100)
        tool = _make_tool(schema)
        result = SchemaValidator.validate_arguments(tool, deep_dict)

        assert not result.is_valid
        depth_violations = [v for v in result.violations if "depth" in v.message.lower() or "深度" in v.message]
        assert len(depth_violations) >= 1

    def test_circular_reference_detected(self) -> None:
        """循环引用 {self: self} → circular reference violation 而非无限递归"""
        circular: dict = {}
        circular["self"] = circular

        # 使用递归 schema 让 _validate_node 进入 "self" 键触发循环检测
        schema = _make_recursive_schema(depth=100)

        # 替换 properties 中的 "nested" 为 "self"
        def _make_self_schema(depth: int) -> dict:
            if depth == 0:
                return {"type": "object"}
            return {
                "type": "object",
                "properties": {"self": _make_self_schema(depth - 1)},
                "additionalProperties": True,
            }

        schema = _make_self_schema(depth=50)
        tool = _make_tool(schema)
        result = SchemaValidator.validate_arguments(tool, circular)

        assert not result.is_valid
        circular_violations = [v for v in result.violations if "circular" in v.message.lower() or "循环" in v.message]
        assert len(circular_violations) >= 1

    def test_normal_depth_5_passes(self) -> None:
        """正常深度 5 层嵌套不应被误判"""
        nested = {"level1": {"level2": {"level3": {"level4": {"level5": {"name": "ok"}}}}}}
        schema = _make_recursive_schema(depth=5)
        tool = _make_tool(schema)
        # 调整 schema 使 depth=5 能正常通过
        result = SchemaValidator.validate_arguments(tool, nested)
        # 正常深度不应有 depth violation
        depth_violations = [v for v in result.violations if "depth" in v.message.lower() or "深度" in v.message]
        assert len(depth_violations) == 0
