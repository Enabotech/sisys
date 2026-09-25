"""Skills YAML frontmatter 解析器

对标业界最佳实践（Anthropic Skills / Jekyll / Hugo frontmatter 规范）：
- YAML 块由 `---` 分隔
- 使用 `yaml.safe_load`（禁止任意代码执行）
- 必需字段：slug（kebab-case）、name、version（SemVer）
- 可选字段：description / when_to_use / when_not_to_use / capabilities / tags /
  status / rule_version / reliability_score / execution_count / token_budget_l1/l2 /
  depends_on / triggers / tool_id / tool_name

设计原则：
- 纯函数，零外部副作用
- 严格校验必需字段 + 格式
- 失败抛 FrontmatterParseError（含字段路径）
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from src.application.ports.skill_loader import ToolMetadata
from src.domain.exceptions.base_exceptions import DomainError
from src.domain.value_objects.data_source import DataSourceApiType, DataSourceRef

FRONTMATTER_DELIMITER = "---"
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

REQUIRED_FIELDS: frozenset[str] = frozenset({"slug", "name", "version"})
LIST_FIELDS: frozenset[str] = frozenset(
    {
        "when_to_use",
        "when_not_to_use",
        "capabilities",
        "tags",
        "depends_on",
        "triggers",
    }
)


class FrontmatterParseError(DomainError):
    """YAML frontmatter 解析/校验失败。

    继承自 DomainError 以获得完整的 (message, cause, context) 契约。
    """


def parse_frontmatter(raw_text: str) -> tuple[dict[str, Any], str]:
    """解析 SKILL.md 文件的 YAML frontmatter。

    Args:
        raw_text: 完整文件内容

    Returns:
        (metadata_dict, body_text) 元组

    Raises:
        FrontmatterParseError: frontmatter 缺失/YAML 语法错误/字段校验失败
    """
    if not raw_text:
        raise FrontmatterParseError(
            message="文件内容为空",
            context={"stage": "parse_frontmatter"},
        )

    lines = raw_text.split("\n")
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        raise FrontmatterParseError(
            message=f"缺少起始 {FRONTMATTER_DELIMITER} 分隔符",
            context={"stage": "parse_frontmatter", "first_line": lines[0] if lines else ""},
        )

    # 查找结束分隔符
    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIMITER:
            end_idx = i
            break

    if end_idx is None:
        raise FrontmatterParseError(
            message=f"缺少结束 {FRONTMATTER_DELIMITER} 分隔符",
            context={"stage": "parse_frontmatter"},
        )

    yaml_block = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])

    try:
        meta = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        raise FrontmatterParseError(
            message=f"YAML 语法错误: {exc}",
            context={"stage": "yaml_parse", "yaml_error": str(exc)},
            cause=exc,
        ) from exc

    if not isinstance(meta, dict):
        raise FrontmatterParseError(
            message="frontmatter 顶层必须是 dict",
            context={"stage": "validate_type", "actual_type": type(meta).__name__},
        )

    # 必需字段校验
    missing = REQUIRED_FIELDS - set(meta.keys())
    if missing:
        raise FrontmatterParseError(
            message=f"frontmatter 缺少必需字段: {sorted(missing)}",
            context={"stage": "validate_required", "missing": sorted(missing)},
        )

    # slug 格式校验
    slug = meta["slug"]
    if not isinstance(slug, str) or not SLUG_PATTERN.match(slug):
        raise FrontmatterParseError(
            message=f"slug 必须为 kebab-case 格式: {slug!r}",
            context={"stage": "validate_slug", "value": str(slug)},
        )

    # version 格式校验
    version = meta["version"]
    if not isinstance(version, str) or not SEMVER_PATTERN.match(version):
        raise FrontmatterParseError(
            message=f"version 必须符合 SemVer X.Y.Z: {version!r}",
            context={"stage": "validate_version", "value": str(version)},
        )

    # list 字段归一化（list → tuple 保持 hashability）
    for field_name in LIST_FIELDS:
        if field_name in meta:
            value = meta[field_name]
            if isinstance(value, list):
                meta[field_name] = tuple(value)
            elif isinstance(value, str):
                # 兼容 YAML 单值字符串（视为单元素列表）
                meta[field_name] = (value,)
            elif not isinstance(value, tuple):
                raise FrontmatterParseError(
                    message=f"{field_name} 必须是 list 或 string",
                    context={
                        "stage": "normalize_list_field",
                        "field": field_name,
                        "actual_type": type(value).__name__,
                    },
                )

    return meta, body


def _parse_data_source_refs(raw: Any) -> tuple[DataSourceRef, ...]:
    """将 frontmatter data_sources 键（YAML list of dict）转换为 DataSourceRef 元组。

    Args:
        raw: YAML 解析后的原始值（期望 list[dict]，空值归一化为空元组）

    Returns:
        DataSourceRef 元组

    Raises:
        FrontmatterParseError: 项缺必需字段 / api_type 非法 / 结构类型错误
    """
    if raw is None:
        return ()
    if not isinstance(raw, list | tuple):
        raise FrontmatterParseError(
            message="data_sources 必须是 list",
            context={"stage": "normalize_data_sources", "field": "data_sources", "actual_type": type(raw).__name__},
        )
    refs: list[DataSourceRef] = []
    for idx, item in enumerate(raw):
        field_path = f"data_sources[{idx}]"
        if not isinstance(item, dict):
            raise FrontmatterParseError(
                message=f"{field_path} 必须是 dict",
                context={"stage": "normalize_data_sources", "field": field_path, "actual_type": type(item).__name__},
            )
        missing = {"name", "url", "api_type"} - set(item.keys())
        if missing:
            raise FrontmatterParseError(
                message=f"{field_path} 缺少必需字段: {sorted(missing)}",
                context={"stage": "normalize_data_sources", "field": field_path, "missing": sorted(missing)},
            )
        try:
            api_type = DataSourceApiType(item["api_type"])
        except ValueError as exc:
            raise FrontmatterParseError(
                message=f"{field_path}.api_type 非法: {item['api_type']!r}",
                context={"stage": "normalize_data_sources", "field": f"{field_path}.api_type"},
                cause=exc,
            ) from exc
        required_fields = item.get("required_fields", ())
        if isinstance(required_fields, list):
            required_fields = tuple(required_fields)
        try:
            refs.append(
                DataSourceRef(
                    name=item["name"],
                    url=item["url"],
                    api_type=api_type,
                    ttl_seconds=item.get("ttl_seconds", 86400),
                    required_fields=required_fields,
                )
            )
        except DomainError as exc:
            raise FrontmatterParseError(
                message=f"{field_path} 值对象校验失败: {exc.message}",
                context={"stage": "normalize_data_sources", "field": field_path},
                cause=exc,
            ) from exc
    return tuple(refs)


def normalize_metadata(
    meta: dict[str, Any],
    fallback_category: str = "",
    fallback_input_schema: dict | None = None,
    fallback_output_schema: dict | None = None,
) -> ToolMetadata:
    """将解析后的 dict 转换为 ToolMetadata dataclass。

    Args:
        meta: parse_frontmatter 返回的 metadata dict
        fallback_category: 当 meta 缺少 category 时使用的回退值
        fallback_input_schema: 当 meta 缺少 input_schema 时使用的回退值
        fallback_output_schema: 当 meta 缺少 output_schema 时使用的回退值

    Returns:
        ToolMetadata 实例
    """
    return ToolMetadata(
        tool_name=meta.get("name", meta.get("tool_name", "")),
        slug=meta["slug"],
        category=meta.get("category", fallback_category),
        input_schema=meta.get("input_schema", fallback_input_schema or {}),
        output_schema=meta.get("output_schema", fallback_output_schema or {}),
        description=meta.get("description", ""),
        when_to_use=meta.get("when_to_use", ()),
        when_not_to_use=meta.get("when_not_to_use", ()),
        capabilities=meta.get("capabilities", ()),
        tags=meta.get("tags", ()),
        version=meta["version"],
        status=meta.get("status", "active"),
        rule_version=meta.get("rule_version"),
        token_budget_l1=meta.get("token_budget_l1", 0),
        token_budget_l2=meta.get("token_budget_l2", 0),
        depends_on=meta.get("depends_on", ()),
        triggers=meta.get("triggers", ()),
        data_sources=_parse_data_source_refs(meta.get("data_sources")),
    )


__all__ = [
    "FRONTMATTER_DELIMITER",
    "REQUIRED_FIELDS",
    "LIST_FIELDS",
    "SLUG_PATTERN",
    "SEMVER_PATTERN",
    "FrontmatterParseError",
    "parse_frontmatter",
    "normalize_metadata",
]
