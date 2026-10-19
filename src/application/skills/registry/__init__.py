"""Skills 注册与选择器包（Story 5-2 — GAP-CRITICAL-08b）

包入口：SkillSelector（ACTIVE 纯过滤查询——interface-design.md §5.5 权威口径，
触发由 LLM 自主判断；目录规划位见 architecture.md §13.11 L2299）。
"""

from src.application.skills.registry.selector import SkillSelector

__all__ = ["SkillSelector"]
