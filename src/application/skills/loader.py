"""Skills 加载器实现（应用层）

实现 InMemorySkillLoader，支持三级渐进式加载 + 真实 YAML frontmatter 解析：
- L1（TOOLS.md）：启动时全量缓存（单例）+ 真实加载 + Markdown 表解析
- L2（SKILL.md × 23）：按需加载，OrderedDict 实现真实 LRU（100 项）
- L3（scripts/references）：按需加载，无缓存

遵循六边形架构：Skills 是应用层静态资源（SKILL.md 文件读取），
非基础设施存储。

业界最佳实践对标：Anthropic Claude Code Skills / LangChain Tool Schema
- description 即触发器
- 渐进披露（L1 < 500 tokens / L2 500-3000 tokens）
- 代码优先（scripts/ 用于确定性任务）
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections import OrderedDict
from pathlib import Path

from src.application.ports.skill_loader import (
    SkillDocument,
    SkillLoaderPort,
    ToolMetadata,
)
from src.application.skills.frontmatter import (
    FrontmatterParseError,
    normalize_metadata,
    parse_frontmatter,
)
from src.application.skills.skill_manifest import (
    SLUG_TO_TOOL_ID,
    TOOL_ID_TO_SLUG,
)
from src.domain.exceptions import SkillLoadError, SkillNotFoundError

logger = logging.getLogger(__name__)

_LRU_CAPACITY = 100
_TOOLS_MD_FILENAME = "TOOLS.md"
_TABLE_ROW_PATTERN = re.compile(r"^\|\s*([a-z0-9][a-z0-9\-]*)\s*\|")


class InMemorySkillLoader(SkillLoaderPort):
    """内存技能加载器（应用层实现）。

    关键设计：
    - L1：从 TOOLS.md 解析 markdown 表，启动时全量缓存
    - L2：OrderedDict LRU 100 项，命中时 move_to_end，超容时淘汰最旧
    - L3：scripts/ + references/ 按需读取，无缓存
    - YAML frontmatter 真实解析（pyyaml.safe_load）
    - 路由查询：match_by_capability / match_by_tag / match_by_trigger
    """

    def __init__(self, skills_root: str | Path | None = None) -> None:
        """初始化加载器。

        Args:
            skills_root: Skills 根目录路径（默认 src/application/skills）
        """
        self._skills_root = Path(skills_root) if skills_root else Path(__file__).parent
        self._metadata_cache: dict[str, ToolMetadata] = {}
        self._sop_cache: OrderedDict[str, SkillDocument] = OrderedDict()
        self._init_metadata_cache()

    # ============================================================
    # L1 元数据加载（启动时全量缓存）
    # ============================================================

    def _init_metadata_cache(self) -> None:
        """从 TOOLS.md 解析 markdown 表，启动时建立 L1 索引。

        失败降级：单条解析失败时 logger.warning 但不中断，确保
        Skills 系统对单点故障有韧性。
        """
        tools_md = self._skills_root / _TOOLS_MD_FILENAME
        if not tools_md.exists():
            logger.warning(
                "TOOLS.md 不存在，回退到空 L1 索引: %s",
                tools_md,
            )
            return

        try:
            # 同步方法内直接调用 read_text，无需 asyncio.to_thread 绕道
            # （_init_metadata_cache 在 __init__ 同步上下文中调用，本身不能 await）
            content = tools_md.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("TOOLS.md 读取失败: %s", exc)
            return

        for line in content.split("\n"):
            stripped = line.strip()
            # 跳过表头、分隔符、空行
            if not stripped or stripped.startswith("#") or "---" in stripped:
                continue
            match = _TABLE_ROW_PATTERN.match(stripped)
            if not match:
                continue
            slug = match.group(1)
            try:
                meta = self._parse_table_row(stripped)
            except (IndexError, ValueError) as exc:
                # 降级策略：单行格式错误不影响整体索引
                logger.warning("TOOLS.md 行解析失败: %s | %s", slug, exc)
                continue
            self._metadata_cache[slug] = meta

        logger.info(
            "L1 索引建立: %d 个 Skills（TOOLS.md）",
            len(self._metadata_cache),
        )

    def _parse_table_row(self, row: str) -> ToolMetadata:
        """解析 markdown 表行 → ToolMetadata。

        期望列：slug | tool_name | category | input_schema | output_schema |
               description | capabilities | tags
        """
        cells = [c.strip() for c in row.split("|") if c.strip()]
        if len(cells) < 8:
            # 兼容旧版（5 列）TOOLS.md，仅填充核心字段
            cells = cells + ["", "", ""] * (8 - len(cells))

        return ToolMetadata(
            tool_name=cells[1],
            slug=cells[0],
            category=cells[2],
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            description=cells[5],
            capabilities=tuple(cells[6].split(",")) if cells[6] else (),
            tags=tuple(cells[7].split(",")) if cells[7] else (),
        )

    # ============================================================
    # L2 SKILL.md 加载（OrderedDict LRU 100）
    # ============================================================

    async def load_sop(self, tool_name: str) -> SkillDocument:
        """加载 L2 技能 SOP（SKILL.md），含真实 YAML frontmatter 解析。

        Args:
            tool_name: 工具名称或 slug

        Returns:
            SkillDocument（含 frontmatter + body + 完整 content）

        Raises:
            SkillNotFoundError: 找不到对应 SKILL.md
            SkillLoadError: 文件 IO/YAML 解析失败
            FrontmatterParseError: frontmatter 格式错误
        """
        slug = self._resolve_slug(tool_name)
        if slug is None:
            raise SkillNotFoundError(tool_name=tool_name)

        # LRU 缓存命中（命中时 move_to_end 刷新位置）
        if slug in self._sop_cache:
            self._sop_cache.move_to_end(slug)
            return self._sop_cache[slug]

        skill_path = self._skills_root / slug / "SKILL.md"
        if not skill_path.exists():
            raise SkillNotFoundError(tool_name=tool_name, slug=slug)

        try:
            raw_text = await asyncio.to_thread(skill_path.read_text, encoding="utf-8")
        except OSError as exc:
            raise SkillLoadError(slug=slug, file_path=str(skill_path), cause=exc)

        try:
            meta_dict, body = parse_frontmatter(raw_text)
        except FrontmatterParseError:
            # 解析失败时回退到基础元数据（向后兼容 + 容错）
            logger.warning(
                "SKILL.md frontmatter 解析失败，使用基础元数据: %s",
                slug,
            )
            meta_dict = {"slug": slug, "name": tool_name, "version": "1.0.0"}
            body = raw_text

        frontmatter = normalize_metadata(meta_dict)
        token_count = self._estimate_tokens(body)
        doc = SkillDocument(
            tool_name=frontmatter.tool_name,
            slug=slug,
            content=raw_text,
            token_count=token_count,
            frontmatter=frontmatter,
            body=body,
        )

        # LRU 淘汰：超过容量时淘汰最旧
        self._sop_cache[slug] = doc
        if len(self._sop_cache) > _LRU_CAPACITY:
            self._sop_cache.popitem(last=False)

        return doc

    def _estimate_tokens(self, text: str) -> int:
        """token 启发估算（chars / 4）。

        中英文混合场景的保守估算。中文字符约等于 1.5 token，
        为简化使用 chars/4 作为业界常用估算。

        Args:
            text: 输入文本

        Returns:
            估算 token 数
        """
        return len(text) // 4

    # ============================================================
    # L1 元数据加载（按 slug 查询）
    # ============================================================

    async def load_metadata(self, tool_name: str) -> ToolMetadata:
        """加载 L1 工具元数据。

        Args:
            tool_name: 工具名称或 slug

        Returns:
            ToolMetadata 元数据

        Raises:
            SkillNotFoundError: 工具未注册
        """
        slug = self._resolve_slug(tool_name)
        if slug is None:
            raise SkillNotFoundError(tool_name=tool_name)

        meta = self._metadata_cache.get(slug)
        if meta is None:
            raise SkillNotFoundError(tool_name=tool_name, slug=slug)
        return meta

    # ============================================================
    # L3 References / Scripts 加载（无缓存）
    # ============================================================

    async def load_references(self, tool_name: str, ref_name: str) -> bytes:
        """加载 L3 参考资料。

        Args:
            tool_name: 工具名称或 slug
            ref_name: 参考文件名

        Returns:
            参考文件二进制内容

        Raises:
            SkillNotFoundError: 参考文件不存在
            SkillLoadError: 文件读取失败
        """
        slug = self._resolve_slug(tool_name)
        if slug is None:
            raise SkillNotFoundError(tool_name=tool_name)

        ref_path = self._skills_root / slug / "references" / ref_name
        if not ref_path.exists():
            raise SkillNotFoundError(tool_name=tool_name, slug=slug)

        try:
            return await asyncio.to_thread(ref_path.read_bytes)
        except OSError as exc:
            raise SkillLoadError(slug=slug, file_path=str(ref_path), cause=exc)

    async def load_script(self, tool_name: str, script_name: str) -> bytes:
        """加载 L3 脚本（确定性任务，代码优先原则）。

        Args:
            tool_name: 工具名称或 slug
            script_name: 脚本文件名

        Returns:
            脚本文件二进制内容

        Raises:
            SkillNotFoundError: 脚本不存在
            SkillLoadError: 文件读取失败
        """
        slug = self._resolve_slug(tool_name)
        if slug is None:
            raise SkillNotFoundError(tool_name=tool_name)

        script_path = self._skills_root / slug / "scripts" / script_name
        if not script_path.exists():
            raise SkillNotFoundError(tool_name=tool_name, slug=slug)

        try:
            return await asyncio.to_thread(script_path.read_bytes)
        except OSError as exc:
            raise SkillLoadError(slug=slug, file_path=str(script_path), cause=exc)

    # ============================================================
    # 路由查询（capability-based / tag-based / trigger-based）
    # ============================================================

    def match_by_capability(self, capability: str) -> list[str]:
        """根据能力标签返回匹配的 Skill slugs（capability-based 检索）。"""
        if not capability:
            return []
        capability_lower = capability.lower()
        matches: list[str] = []
        for slug, meta in self._metadata_cache.items():
            for cap in meta.capabilities:
                if cap.lower() == capability_lower or capability_lower in cap.lower():
                    matches.append(slug)
                    break
        return matches

    def match_by_tag(self, tag: str) -> list[str]:
        """根据 tag 返回匹配的 Skill slugs。"""
        if not tag:
            return []
        tag_lower = tag.lower()
        matches: list[str] = []
        for slug, meta in self._metadata_cache.items():
            for t in meta.tags:
                if t.lower() == tag_lower or tag_lower in t.lower():
                    matches.append(slug)
                    break
        return matches

    def match_by_trigger(self, query: str) -> list[str]:
        """基于触发词匹配 Skills（LLM-based routing 前置步骤）。

        匹配优先级：triggers 完全匹配 > triggers 部分匹配 > description 包含 > name 包含
        """
        if not query:
            return []
        query_lower = query.lower()
        matches: list[tuple[int, str]] = []
        for slug, meta in self._metadata_cache.items():
            score = 0
            for trigger in meta.triggers:
                trigger_lower = trigger.lower()
                if trigger_lower == query_lower:
                    score = max(score, 100)
                elif trigger_lower in query_lower or query_lower in trigger_lower:
                    score = max(score, 50)
            if meta.tool_name and meta.tool_name in query:
                score = max(score, 20)
            if score > 0:
                matches.append((score, slug))
        matches.sort(key=lambda x: (-x[0], x[1]))
        return [slug for _, slug in matches]

    # ============================================================
    # 辅助方法
    # ============================================================

    def _resolve_slug(self, tool_name: str) -> str | None:
        """根据 tool_name 或 slug 解析为 slug。

        支持：
        - 直接传入 slug（如 "pestel-analysis"）
        - 传入 Tool.name（如 "PESTEL 分析"）
        - 传入 tool_id UUID 字符串
        """
        if not tool_name:
            return None

        # 1. 直接匹配 slug
        if tool_name in SLUG_TO_TOOL_ID:
            return tool_name

        # 2. 通过 tool_name 查找（遍历 manifest）
        for slug in TOOL_ID_TO_SLUG.values():
            meta = self._metadata_cache.get(slug)
            if meta and meta.tool_name == tool_name:
                return slug

        # 3. 尝试作为 UUID
        try:
            tool_uuid = uuid.UUID(tool_name)
            return TOOL_ID_TO_SLUG.get(tool_uuid)
        except (ValueError, AttributeError):
            return None


__all__ = ["InMemorySkillLoader"]
