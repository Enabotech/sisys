"""应用层技能加载器端口模块

定义 SkillLoaderPort 协议（六边形约束），
支持 Skills 三级渐进式加载（L1 元数据 / L2 SOP / L3 references）。

设计依据：Story 4.1a AC-5/AC-6
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ToolMetadata:
    """L1 工具元数据（TOOLS.md 内容）"""

    tool_name: str
    slug: str
    category: str
    input_schema: dict
    output_schema: dict


@dataclass(frozen=True)
class SkillDocument:
    """L2 技能 SOP 文档（SKILL.md 内容）"""

    tool_name: str
    slug: str
    content: str
    token_count: int


@runtime_checkable
class SkillLoaderPort(Protocol):
    """技能加载器端口协议（六边形约束）

    实现位置：src/application/skills/loader.py（应用层静态资源）

    三级加载触发逻辑：
    - L1（TOOLS.md）：启动时全量缓存（单例）
    - L2（SKILL.md × 23）：按需加载，LRU 缓存 100 项
    - L3（scripts/references）：按需加载，无缓存
    """

    async def load_metadata(self, tool_name: str) -> ToolMetadata:
        """加载 L1 工具元数据（TOOLS.md）

        Args:
            tool_name: 工具名称（如 "PESTEL 分析"）

        Returns:
            ToolMetadata 元数据

        Raises:
            SkillNotFoundError: 工具未注册到 skill_manifest
            SkillLoadError: TOOLS.md 读取/解析失败
        """
        ...

    async def load_sop(self, tool_name: str) -> SkillDocument:
        """加载 L2 技能 SOP（SKILL.md）

        Args:
            tool_name: 工具名称

        Returns:
            SkillDocument 完整 SOP 文档

        Raises:
            SkillNotFoundError: tool_name 找不到对应 SKILL.md
            SkillLoadError: SKILL.md 读取/YAML 解析失败
        """
        ...

    async def load_references(self, tool_name: str, ref_name: str) -> bytes:
        """加载 L3 参考资料/脚本

        Args:
            tool_name: 工具名称
            ref_name: 参考文件名（如 "industry_benchmarks.json"）

        Returns:
            参考文件二进制内容

        Raises:
            SkillNotFoundError: 参考文件不存在
            SkillLoadError: 文件读取失败
        """
        ...
