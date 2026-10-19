"""SkillSelector——Skill 选择器实现（Story 5-2 — GAP-CRITICAL-08b 交付）

ACTIVE 纯过滤查询：get_all_slugs() 枚举 → 逐 slug load_metadata →
status == "active" 过滤 → 按 slug 清单序返回 tuple。

权威口径（interface-design.md §5.5 + architecture.md GAP-CRITICAL-08b）：
- Skill 触发由 LLM 基于 L1 description 自主判断（5.3 工作流实现）
- 本选择器仅作查询接口——无关键词权重排序、无语义相似度打分、无 Top-K
  推荐（epics L1546 旧文案已废弃，偏离声明 D-1）
"""

from __future__ import annotations

from src.application.ports.skill_loader import SkillLoaderPort, ToolMetadata
from src.application.ports.skill_selector import SkillSelectorPort
from src.application.skills.skill_manifest import get_all_slugs


class SkillSelector(SkillSelectorPort):
    """Skill 选择器（无连接状态纯查询——组合注入 skill_loader 端口消费 L1 元数据）。

    Attributes:
        _skill_loader: Skills 加载端口（L1 元数据单工具查询——slug 直传合法，
            _resolve_slug 支持 slug/tool_name/UUID 三形态寻址）
    """

    def __init__(self, skill_loader: SkillLoaderPort) -> None:
        """初始化选择器。

        Args:
            skill_loader: Skills 加载端口（组合注入——R2 应用层端口组合原则）
        """
        self._skill_loader = skill_loader

    async def list_active_skills(self) -> tuple[ToolMetadata, ...]:
        """返回 status=="active" 的全量 L1 元数据（按 slug 清单稳定序）。

        枚举源 get_all_slugs()（23 slug 全量静态映射真源）；过滤后保持 slug
        清单序（零排序副作用——返回顺序与清单一致是 AC-3.2 断言契约）。

        Returns:
            tuple[ToolMetadata, ...]: ACTIVE 工具元数据清单

        Raises:
            SkillNotFoundError: 元数据查询未命中（传播不静默——缺档案是资产缺陷）
        """
        result: list[ToolMetadata] = []
        for slug in get_all_slugs():
            meta = await self._skill_loader.load_metadata(slug)
            if meta.status == "active":
                result.append(meta)
        return tuple(result)
