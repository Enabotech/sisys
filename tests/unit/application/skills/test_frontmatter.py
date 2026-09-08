"""Story 4.1a Skills frontmatter 解析器单元测试

TDD 测试覆盖（≥8 测试）：
- 正常解析（含 list → tuple 转换）
- 缺起始分隔符
- 缺结束分隔符
- YAML 语法错误
- 顶层非 dict
- 缺必需字段
- 非 kebab-case slug
- 非 SemVer version
- 字符串单值归一化
"""

from __future__ import annotations

import pytest

from src.application.skills.frontmatter import (
    FrontmatterParseError,
    normalize_metadata,
    parse_frontmatter,
)


def _make_valid_frontmatter(**overrides: object) -> str:
    """构造有效 frontmatter 文本（可覆盖字段）。"""
    base: dict = {
        "slug": "test-skill",
        "name": "测试工具",
        "version": "1.0.0",
        "description": "测试用工具",
        "when_to_use": ["场景1", "场景2"],
        "capabilities": ["test_capability"],
    }
    base.update(overrides)
    yaml_lines = ["---"]
    for k, v in base.items():
        if isinstance(v, list):
            yaml_lines.append(f"{k}:")
            for item in v:
                yaml_lines.append(f"  - {item}")
        else:
            yaml_lines.append(f"{k}: {v!r}")
    yaml_lines.append("---")
    yaml_lines.append("# Body")
    yaml_lines.append("正文内容")
    return "\n".join(yaml_lines)


class TestFrontmatterParser:
    """YAML frontmatter 解析器测试。"""

    def test_parse_valid_frontmatter(self) -> None:
        """正常解析。"""
        raw = _make_valid_frontmatter()
        meta, body = parse_frontmatter(raw)
        assert meta["slug"] == "test-skill"
        assert meta["name"] == "测试工具"
        assert meta["version"] == "1.0.0"
        assert "Body" in body

    def test_parse_missing_start_delimiter(self) -> None:
        """缺起始分隔符。"""
        raw = "slug: x\nname: y\nversion: 1.0.0\n---\nbody"
        with pytest.raises(FrontmatterParseError) as exc:
            parse_frontmatter(raw)
        assert "起始" in exc.value.message

    def test_parse_missing_end_delimiter(self) -> None:
        """缺结束分隔符。"""
        raw = "---\nslug: x\nname: y\nversion: 1.0.0\nbody without end"
        with pytest.raises(FrontmatterParseError) as exc:
            parse_frontmatter(raw)
        assert "结束" in exc.value.message

    def test_parse_yaml_syntax_error(self) -> None:
        """YAML 语法错误。"""
        raw = "---\nslug: x: y: z\nname: y\nversion: 1.0.0\n---\nbody"
        with pytest.raises(FrontmatterParseError) as exc:
            parse_frontmatter(raw)
        assert "YAML" in exc.value.message

    def test_parse_top_level_not_dict(self) -> None:
        """顶层非 dict（如列表）。"""
        raw = "---\n- item1\n- item2\n---\nbody"
        with pytest.raises(FrontmatterParseError) as exc:
            parse_frontmatter(raw)
        assert "dict" in exc.value.message

    def test_parse_missing_required_field(self) -> None:
        """缺必需字段。"""
        raw = "---\nslug: x\nname: y\n---\nbody"  # 缺 version
        with pytest.raises(FrontmatterParseError) as exc:
            parse_frontmatter(raw)
        assert "version" in exc.value.context.get("missing", [])

    def test_parse_invalid_slug_format(self) -> None:
        """非 kebab-case slug。"""
        raw = _make_valid_frontmatter(slug="Invalid_Slug")
        with pytest.raises(FrontmatterParseError) as exc:
            parse_frontmatter(raw)
        assert "kebab-case" in exc.value.message

    def test_parse_invalid_version_format(self) -> None:
        """非 SemVer version。"""
        raw = _make_valid_frontmatter(version="v1.0")
        with pytest.raises(FrontmatterParseError) as exc:
            parse_frontmatter(raw)
        assert "SemVer" in exc.value.message

    def test_parse_list_to_tuple_conversion(self) -> None:
        """list 字段自动转为 tuple。"""
        raw = _make_valid_frontmatter(when_to_use=["a", "b", "c"])
        meta, _ = parse_frontmatter(raw)
        assert isinstance(meta["when_to_use"], tuple)
        assert meta["when_to_use"] == ("a", "b", "c")

    def test_parse_string_to_singleton_tuple(self) -> None:
        """字符串字段归一化为单元素 tuple。"""
        raw = _make_valid_frontmatter(capabilities="single_capability")
        meta, _ = parse_frontmatter(raw)
        assert meta["capabilities"] == ("single_capability",)


class TestNormalizeMetadata:
    """normalize_metadata 测试。"""

    def test_normalize_with_fallbacks(self) -> None:
        """使用回退值的归一化。"""
        meta = {
            "slug": "x",
            "name": "X",
            "version": "1.0.0",
        }
        result = normalize_metadata(
            meta,
            fallback_category="environment_analysis",
            fallback_input_schema={"type": "object"},
            fallback_output_schema={"type": "object"},
        )
        assert result.slug == "x"
        assert result.tool_name == "X"
        assert result.category == "environment_analysis"
        assert result.input_schema == {"type": "object"}
        assert result.version == "1.0.0"
