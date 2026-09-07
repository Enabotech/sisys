"""应用层 Skills 包

包含 Skills 三级渐进式加载骨架：
- TOOLS.md: L1 元数据索引
- SKILL.md × 23: L2 SOP（每个工具一份）
- scripts/ + references/: L3 按需加载
- skill_manifest.py: tool_id ↔ slug 双向映射
- loader.py: InMemorySkillLoader 实现
"""

from src.application.skills.loader import InMemorySkillLoader
from src.application.skills.skill_manifest import (
    SLUG_TO_TOOL_ID,
    TOOL_ID_TO_SLUG,
    get_slug,
    get_tool_id,
)

__all__ = [
    "InMemorySkillLoader",
    "TOOL_ID_TO_SLUG",
    "SLUG_TO_TOOL_ID",
    "get_slug",
    "get_tool_id",
]
