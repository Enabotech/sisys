"""Skills Manifest — tool_id ↔ slug 双向映射

23 种战略工具的 slug（kebab-case 格式）与 tool_id 双向映射。
供 SkillLoader 启动时建立索引，Agent 可通过 tool_name 或 slug 查询对应 Tool。

数据来源：与 src/domain/entities/strategic_tool_catalog.py 23 个 TOOL_CATALOG 实例一一对应。
"""

from __future__ import annotations

import uuid

# 23 种工具的 tool_id → slug 映射（与 strategic_tool_catalog.py 一一对应）
TOOL_ID_TO_SLUG: dict[uuid.UUID, str] = {
    uuid.UUID("00000000-0000-0000-0000-000000000001"): "pestel-analysis",
    uuid.UUID("00000000-0000-0000-0000-000000000002"): "porters-five-forces",
    uuid.UUID("00000000-0000-0000-0000-000000000003"): "appeals-analysis",
    uuid.UUID("00000000-0000-0000-0000-000000000004"): "competitor-analysis",
    uuid.UUID("00000000-0000-0000-0000-000000000005"): "value-chain-analysis",
    uuid.UUID("00000000-0000-0000-0000-000000000006"): "vrio-framework",
    uuid.UUID("00000000-0000-0000-0000-000000000007"): "ansoff-matrix",
    uuid.UUID("00000000-0000-0000-0000-000000000008"): "swot-tows",
    uuid.UUID("00000000-0000-0000-0000-000000000009"): "ge-mckinsey-matrix",
    uuid.UUID("00000000-0000-0000-0000-000000000010"): "space-matrix",
    uuid.UUID("00000000-0000-0000-0000-000000000011"): "scenario-planning",
    uuid.UUID("00000000-0000-0000-0000-000000000012"): "value-curve-analysis",
    uuid.UUID("00000000-0000-0000-0000-000000000013"): "value-proposition-canvas",
    uuid.UUID("00000000-0000-0000-0000-000000000014"): "business-model-canvas",
    uuid.UUID("00000000-0000-0000-0000-000000000015"): "disruptive-innovation",
    uuid.UUID("00000000-0000-0000-0000-000000000016"): "bsc-scorecard",
    uuid.UUID("00000000-0000-0000-0000-000000000017"): "strategy-map",
    uuid.UUID("00000000-0000-0000-0000-000000000018"): "org-design-framework",
    uuid.UUID("00000000-0000-0000-0000-000000000019"): "dependency-graph",
    uuid.UUID("00000000-0000-0000-0000-000000000020"): "raci-matrix",
    uuid.UUID("00000000-0000-0000-0000-000000000021"): "gantt-chart",
    uuid.UUID("00000000-0000-0000-0000-000000000022"): "kpi-tree",
    uuid.UUID("00000000-0000-0000-0000-000000000023"): "change-management",
}

# slug → tool_id 反向映射
SLUG_TO_TOOL_ID: dict[str, uuid.UUID] = {slug: tid for tid, slug in TOOL_ID_TO_SLUG.items()}


def get_slug(tool_id: uuid.UUID) -> str | None:
    """根据 tool_id 查询 slug"""
    return TOOL_ID_TO_SLUG.get(tool_id)


def get_tool_id(slug: str) -> uuid.UUID | None:
    """根据 slug 查询 tool_id"""
    return SLUG_TO_TOOL_ID.get(slug)


# ============================================================
# 路由查询辅助函数（业界最佳实践：capability-based / tag-based）
# ============================================================


def get_metadata(slug: str) -> dict | None:
    """查询 Skill 元数据 dict（向后兼容 stub）。

    Returns:
        包含 slug/tool_id/name 的 dict，或 None（slug 不存在）
    """
    if slug not in SLUG_TO_TOOL_ID:
        return None
    return {
        "slug": slug,
        "tool_id": str(SLUG_TO_TOOL_ID[slug]),
        "name": slug,
    }


def get_all_slugs() -> list[str]:
    """列出所有 23 个 Skill slugs。"""
    return list(SLUG_TO_TOOL_ID.keys())


def get_slugs_by_category(category: str) -> list[str]:
    """根据分类返回 slugs 列表（静态映射）。"""
    category_prefixes = {
        "environment_analysis": ("pestel", "porters", "appeals"),
        "competitive_analysis": ("competitor", "value-chain", "vrio"),
        "strategic_selection": (
            "ansoff",
            "swot",
            "ge-mckinsey",
            "space",
            "scenario",
            "value-curve",
        ),
        "business_model": (
            "value-proposition",
            "business-model",
            "disruptive",
        ),
        "execution_management": (
            "bsc",
            "strategy-map",
            "org-design",
            "dependency",
            "raci",
            "gantt",
            "kpi",
            "change-management",
        ),
    }
    prefixes = category_prefixes.get(category, ())
    return [slug for slug in SLUG_TO_TOOL_ID if any(slug.startswith(p) for p in prefixes)]


__all__ = [
    "TOOL_ID_TO_SLUG",
    "SLUG_TO_TOOL_ID",
    "get_slug",
    "get_tool_id",
    "get_metadata",
    "get_all_slugs",
    "get_slugs_by_category",
]
