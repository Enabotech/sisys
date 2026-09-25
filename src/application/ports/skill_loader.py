"""应用层技能加载器端口模块

定义 SkillLoaderPort 协议（六边形约束），
支持 Skills 三级渐进式加载（L1 元数据 / L2 SOP / L3 references + scripts）。

设计依据：Story 4.1a AC-5/AC-6 + 业界最佳实践（Anthropic Skills / LangChain Tool Schema）

三级加载触发逻辑：
- L1（TOOLS.md）：启动时全量缓存（单例）
- L2（SKILL.md）：按需加载，LRU 缓存 100 项
- L3（scripts/references）：按需加载，无缓存

向后兼容说明：
- ToolMetadata 在原 5 字段基础上扩展 7 字段（带默认值，调用方代码无需修改）
- SkillDocument 在原 4 字段基础上扩展 3 字段
- SkillLoaderPort Protocol 新增 4 个方法（load_script / match_by_*）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from src.domain.value_objects.data_source import DataSourceRef


@dataclass(frozen=True)
class ToolMetadata:
    """L1 工具元数据（TOOLS.md 内容 + frontmatter 合并）

    Attributes:
        tool_name: 工具名称（如 "PESTEL 分析"）
        slug: kebab-case 标识
        category: 战略工具分类（environment_analysis / competitive_analysis 等）
        input_schema: 输入 JSON Schema 字典
        output_schema: 输出 JSON Schema 字典
        description: 一句话功能描述（≤500 字符）
        when_to_use: 适用场景关键词列表（LLM 自动选择）
        when_not_to_use: 负向触发词列表（避免误路由）
        capabilities: 能力标签（用于 capability-based 检索）
        tags: 自由标签（用于分组/发现）
        version: SemVer 语义化版本号
        status: 状态（active / deprecated / experimental）
        rule_version: 业务规则版本（如 "BLM-v3.2"）
        token_budget_l1: L1 元数据 token 预算（启动时全量加载）
        token_budget_l2: L2 SKILL.md token 预算（按需加载）
        depends_on: 依赖的其他 Skills（用于组合）
        triggers: 触发短语（用于 LLM-based routing）
        data_sources: 声明的外部数据源白名单（Story 4.1b，Engine.Execute $DATA_SOURCE 采集依据）
    """

    tool_name: str
    slug: str
    category: str
    input_schema: dict
    output_schema: dict
    # === 扩展字段（向后兼容默认值）===
    description: str = ""
    when_to_use: tuple[str, ...] = ()
    when_not_to_use: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    version: str = "1.0.0"
    status: str = "active"
    rule_version: str | None = None
    token_budget_l1: int = 0
    token_budget_l2: int = 0
    depends_on: tuple[str, ...] = ()
    triggers: tuple[str, ...] = ()
    # Story 4.1b 扩展（向后兼容默认空 tuple）
    data_sources: tuple[DataSourceRef, ...] = ()


@dataclass(frozen=True)
class SkillDocument:
    """L2 技能 SOP 文档（SKILL.md 内容）

    Attributes:
        tool_name: 工具名称
        slug: kebab-case 标识
        content: 完整 SKILL.md 内容（含 frontmatter，向后兼容）
        token_count: token 数（启发估算：len(content) // 4）
        frontmatter: 解析后的元数据（ToolMetadata）
        body: 去除 frontmatter 的 Markdown body
        loaded_at: 加载时间戳
    """

    tool_name: str
    slug: str
    content: str
    token_count: int
    # === 扩展字段（向后兼容默认值）===
    frontmatter: ToolMetadata = field(
        default_factory=lambda: ToolMetadata(
            tool_name="",
            slug="",
            category="",
            input_schema={},
            output_schema={},
        )
    )
    body: str = ""
    loaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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
        """加载 L3 参考资料

        Args:
            tool_name: 工具名称
            ref_name: 参考文件名（如 "scoring_matrix.json"）

        Returns:
            参考文件二进制内容

        Raises:
            SkillNotFoundError: 参考文件不存在
            SkillLoadError: 文件读取失败
        """
        ...

    async def load_script(self, tool_name: str, script_name: str) -> bytes:
        """加载 L3 脚本（确定性任务，代码优先原则）

        Args:
            tool_name: 工具名称
            script_name: 脚本文件名（如 "aggregate_scores.py"）

        Returns:
            脚本文件二进制内容

        Raises:
            SkillNotFoundError: 脚本不存在
            SkillLoadError: 文件读取失败
        """
        ...

    def match_by_capability(self, capability: str) -> list[str]:
        """根据能力标签返回匹配的 Skill slugs（capability-based 检索）

        Args:
            capability: 能力标签（如 "environment_analysis"）

        Returns:
            匹配的 slugs 列表
        """
        ...

    def match_by_tag(self, tag: str) -> list[str]:
        """根据 tag 返回匹配的 Skill slugs

        Args:
            tag: 自由标签（如 "strategy"）

        Returns:
            匹配的 slugs 列表
        """
        ...

    def match_by_trigger(self, query: str) -> list[str]:
        """基于触发词匹配 Skills（LLM-based routing 前置步骤）

        Args:
            query: 用户查询或触发短语

        Returns:
            匹配的 slugs 列表（按匹配度排序）
        """
        ...
