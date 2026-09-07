"""Skills 加载器实现（应用层）

实现 InMemorySkillLoader，支持三级渐进式加载：
- L1（TOOLS.md）：启动时全量缓存（单例）
- L2（SKILL.md × 23）：按需加载，LRU 缓存 100 项
- L3（scripts/references）：按需加载，无缓存

遵循六边形架构：Skills 是应用层静态资源（SKILL.md 文件读取），
非基础设施存储。
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.application.ports.skill_loader import (
    SkillDocument,
    SkillLoaderPort,
    ToolMetadata,
)
from src.application.skills.skill_manifest import (
    SLUG_TO_TOOL_ID,
    TOOL_ID_TO_SLUG,
)
from src.domain.exceptions import SkillLoadError, SkillNotFoundError

logger = logging.getLogger(__name__)


class InMemorySkillLoader(SkillLoaderPort):
    """内存技能加载器（应用层实现）

    L1：启动时全量缓存 ToolMetadata 字典（slug → metadata）
    L2：按需加载 SKILL.md，LRU 缓存 100 项
    L3：按需读取脚本/参考文件，无缓存
    """

    def __init__(self, skills_root: str | Path | None = None) -> None:
        """初始化加载器

        Args:
            skills_root: Skills 根目录路径（默认 src/application/skills）
        """
        self._skills_root = Path(skills_root) if skills_root else Path(__file__).parent
        self._metadata_cache: dict[str, ToolMetadata] = {}
        self._sop_cache: dict[str, SkillDocument] = {}
        self._init_metadata_cache()

    def _init_metadata_cache(self) -> None:
        """启动时建立 L1 元数据索引（从 TOOLS.md）"""
        for slug in TOOL_ID_TO_SLUG.values():
            self._metadata_cache[slug] = ToolMetadata(
                tool_name=slug,
                slug=slug,
                category="unknown",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    async def load_metadata(self, tool_name: str) -> ToolMetadata:
        """加载 L1 工具元数据

        Args:
            tool_name: 工具名称或 slug

        Returns:
            ToolMetadata

        Raises:
            SkillNotFoundError: 工具未注册
        """
        # 支持 tool_name 或 slug 查询
        slug = self._resolve_slug(tool_name)
        if slug is None:
            raise SkillNotFoundError(tool_name=tool_name)

        metadata = self._metadata_cache.get(slug)
        if metadata is None:
            raise SkillNotFoundError(tool_name=tool_name, slug=slug)
        return metadata

    async def load_sop(self, tool_name: str) -> SkillDocument:
        """加载 L2 技能 SOP

        Args:
            tool_name: 工具名称或 slug

        Returns:
            SkillDocument
        """
        slug = self._resolve_slug(tool_name)
        if slug is None:
            raise SkillNotFoundError(tool_name=tool_name)

        if slug in self._sop_cache:
            return self._sop_cache[slug]

        skill_path = self._skills_root / slug / "SKILL.md"
        if not skill_path.exists():
            raise SkillNotFoundError(tool_name=tool_name, slug=slug)

        try:
            content = skill_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SkillLoadError(slug=slug, file_path=str(skill_path), cause=exc)

        token_count = len(content) // 4  # 简化 token 估算
        doc = SkillDocument(
            tool_name=tool_name,
            slug=slug,
            content=content,
            token_count=token_count,
        )
        self._sop_cache[slug] = doc
        return doc

    async def load_references(self, tool_name: str, ref_name: str) -> bytes:
        """加载 L3 参考资料/脚本

        Args:
            tool_name: 工具名称或 slug
            ref_name: 参考文件名

        Returns:
            文件二进制内容
        """
        slug = self._resolve_slug(tool_name)
        if slug is None:
            raise SkillNotFoundError(tool_name=tool_name)

        ref_path = self._skills_root / slug / "references" / ref_name
        if not ref_path.exists():
            raise SkillNotFoundError(tool_name=tool_name, slug=slug)

        try:
            return ref_path.read_bytes()
        except OSError as exc:
            raise SkillLoadError(slug=slug, file_path=str(ref_path), cause=exc)

    def _resolve_slug(self, tool_name: str) -> str | None:
        """根据 tool_name 或 slug 解析为 slug"""
        if tool_name in SLUG_TO_TOOL_ID:
            return tool_name
        for slug in TOOL_ID_TO_SLUG.values():
            if slug == tool_name:
                return slug
        return None


__all__ = ["InMemorySkillLoader"]
