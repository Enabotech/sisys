"""应用层 Skill 选择器端口（Story 5-2 — GAP-CRITICAL-08b 交付）

SkillSelectorPort——Skill 选择器查询端口（interface-design.md §5.5 权威口径）：
仅作 ACTIVE 全量查询接口，Skill 触发由 LLM 基于 L1 description 自主判断（5.3
工作流实现）；禁止关键词权重排序/语义相似度打分/Top-K 推荐（epics L1546 旧
文案已废弃——偏离声明 D-1，architecture.md GAP-CRITICAL-08b「删除硬编码，
模型自决」）。

实现见 src/application/skills/registry/selector.py（SkillSelector——组合注入
skill_loader 端口消费 L1 元数据，R2 应用层端口组合注入原则）。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.application.ports.skill_loader import ToolMetadata


@runtime_checkable
class SkillSelectorPort(Protocol):
    """Skill 选择器端口（ACTIVE 纯过滤查询，零排序零打分零 Top-K）。

    端口名带 Port 后缀对齐 SkillLoaderPort 先例，与实现类 SkillSelector
    异名防 import 二义。
    """

    async def list_active_skills(self) -> tuple[ToolMetadata, ...]:
        """返回 status=="active" 的全量 L1 元数据（按 slug 清单稳定序）。

        Returns:
            tuple[ToolMetadata, ...]: ACTIVE 工具元数据清单（无排序打分、无 Top-K）

        Raises:
            SkillNotFoundError: skill_loader 元数据查询未命中（传播不静默）
        """
        ...
