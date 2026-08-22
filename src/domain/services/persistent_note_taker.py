"""领域层持久化笔记服务模块

实现检索-压缩循环的前置步骤（系统公理二：压缩前必须持久化）。
从检索结果中提取关键实体与关系，记录检索血缘，生成结构化摘要，
为后续 ContextCompressor 提供已持久化的 PersistentNote。

设计决策：
- 注入 EntityExtractionPort（实体抽取）+ AuditServicePort（血缘审计）
  + L1CachePort（笔记缓存）
- 遵循六边形架构：领域层零外部依赖，仅依赖领域层端口
- PersistentNote 为不可变值对象，persisted/persisted_at 通过 object.__setattr__ 写入
- 实体摘要持久化至 StrategicArchive 由应用层编排完成（领域层不依赖应用层）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.domain.exceptions import EntityValidationError
from src.domain.ports.audit_service import AuditServicePort
from src.domain.ports.entity_extraction import EntityExtractionPort, ExtractionResult
from src.domain.ports.l1_cache import L1CachePort
from src.domain.ports.l3_vector import SearchResult

# 笔记 Redis 缓存 TTL（30 天，与设计文档 §17.1.5.1 对齐）
_NOTE_CACHE_TTL_SECONDS = 30 * 24 * 3600

# 实体抽取输入内容上限（~20K 字符，避免超长输入）
_ENTITY_EXTRACTION_CONTENT_LIMIT = 20000

# 笔记关键实体保留上限（对齐设计文档 Top-20 语义）
_ENTITY_LIMIT = 20


@dataclass(frozen=True)
class PersistentNote:
    """持久化笔记值对象

    检索-压缩循环中，压缩前必须完成持久化的笔记数据。

    Attributes:
        note_id: 笔记唯一标识
        query: 原始查询文本
        user_id: 发起用户 ID
        session_id: 会话 ID
        entities: 提取的关键实体（Top-20，序列化 dict 列表）
        extraction_result: 实体抽取原始结果（含 relations）
        lineage: 检索血缘记录
        summary: 结构化摘要（由上层摘要服务回填）
        persisted: 是否已完成持久化（压缩前校验必须为 True）
        persisted_at: 持久化完成时间
        created_at: 笔记创建时间
    """

    note_id: UUID = field(default_factory=uuid4)
    query: str = ""
    user_id: str = ""
    session_id: str = ""
    entities: list[dict[str, Any]] = field(default_factory=list)
    extraction_result: ExtractionResult = field(
        default_factory=lambda: ExtractionResult(extraction_metadata={"strategy": "none", "entity_count": 0}),
    )
    lineage: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    persisted: bool = False
    persisted_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 L1 缓存存储）

        Returns:
            可 JSON 序列化的 dict 表示
        """
        return {
            "note_id": str(self.note_id),
            "query": self.query,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "entities": self.entities,
            "lineage": self.lineage,
            "summary": self.summary,
            "persisted": self.persisted,
            "persisted_at": self.persisted_at.isoformat() if self.persisted_at else None,
            "created_at": self.created_at.isoformat(),
        }


class PersistentNoteTaker:
    """持久化笔记记录器 — 压缩前必须调用

    流程（对齐架构设计 §17.1.5.1）：
    1. 提取关键实体与关系 → 实体抽取端口
    2. 构建检索血缘（query/top_k/document_ids/user_id/session_id/timestamp）
    3. 记录检索血缘 → 审计服务端口
    4. 持久化完成标记（persisted=True）+ 序列化至 L1 缓存（TTL 30 天）

    注意：本服务是领域层编排，聚焦"提取实体 + 记录血缘 + 标记持久化"，
    不直接持有应用层 StrategicArchiveService（领域层禁止依赖应用层）。
    实体/摘要持久化至 StrategicArchive 由应用层编排服务组合完成。
    """

    def __init__(
        self,
        entity_extractor: EntityExtractionPort,
        audit_service: AuditServicePort | None = None,
        l1_cache: L1CachePort | None = None,
    ) -> None:
        """初始化持久化笔记记录器

        Args:
            entity_extractor: 实体抽取端口（规则基 + LLM 混合由应用层注入）
            audit_service: 审计服务端口（可选，用于血缘记录，None 时降级跳过）
            l1_cache: L1 缓存端口（可选，用于笔记缓存，None 时降级跳过）
        """
        self._entity_extractor = entity_extractor
        self._audit_service = audit_service
        self._l1_cache = l1_cache

    async def take_notes(
        self,
        query: str,
        retrieved_docs: list[SearchResult],
        user_id: str,
        session_id: str,
    ) -> PersistentNote:
        """执行持久化笔记步骤

        输入检索文档列表，提取实体、构建血缘、标记持久化完成。

        Args:
            query: 原始查询文本
            retrieved_docs: 检索结果文档列表
            user_id: 发起用户 ID
            session_id: 会话 ID

        Returns:
            已标记持久化的 PersistentNote

        Raises:
            EntityValidationError: 查询文本为空时
        """
        if not query or not query.strip():
            raise EntityValidationError(
                message="query must not be empty",
                context={"service": "PersistentNoteTaker", "field": "query"},
            )

        note = PersistentNote(
            query=query,
            user_id=user_id,
            session_id=session_id,
        )

        # 1. 提取关键实体与关系
        content = self._build_content(retrieved_docs)
        await self._extract_entities(note, content)

        # 2. 构建检索血缘
        object.__setattr__(
            note,
            "lineage",
            {
                "query": query,
                "top_k": len(retrieved_docs),
                "document_ids": [str(r.get("id", "")) for r in retrieved_docs if isinstance(r, dict)],
                "user_id": user_id,
                "session_id": session_id,
                "timestamp": note.created_at.isoformat(),
            },
        )

        # 3. 记录检索血缘到审计日志
        await self._record_lineage(note)

        # 4. 持久化完成标记 + 缓存
        object.__setattr__(note, "persisted", True)
        object.__setattr__(note, "persisted_at", datetime.now(UTC))
        await self._cache_note(note)

        return note

    async def _extract_entities(self, note: PersistentNote, content: str) -> None:
        """提取实体并写入笔记

        实体抽取失败时降级为空实体列表，不阻断持久化流程。

        Args:
            note: 持久化笔记
            content: 合并后的检索内容文本
        """
        if not content:
            return
        try:
            result = await self._entity_extractor.extract_entities(content)
            object.__setattr__(note, "extraction_result", result)
            object.__setattr__(
                note,
                "entities",
                [
                    {
                        "name": e.name,
                        "entity_type": e.entity_type,
                        "confidence": e.confidence,
                        "extraction_source": e.extraction_source,
                        "normalized_name": e.normalized_name or e.name,
                    }
                    for e in result.entities
                ][:_ENTITY_LIMIT],
            )
        except Exception:
            # 实体抽取失败降级：空实体列表（不阻断持久化）
            object.__setattr__(
                note,
                "extraction_result",
                ExtractionResult(extraction_metadata={"strategy": "rule", "entity_count": 0}),
            )
            object.__setattr__(note, "entities", [])

    async def _record_lineage(self, note: PersistentNote) -> None:
        """记录检索血缘到审计日志

        审计服务未注入或记录失败时不阻断主流程（降级跳过）。

        Args:
            note: 持久化笔记
        """
        if self._audit_service is None:
            return
        try:
            await self._audit_service.record(
                actor=note.user_id or "system",
                action_type="retrieval:lineage",
                target_resource=f"session:{note.session_id}",
                new_value=note.lineage,
                correlation_id=str(note.note_id),
            )
        except Exception:
            # 血缘记录失败降级跳过
            return

    async def _cache_note(self, note: PersistentNote) -> None:
        """序列化笔记至 L1 缓存（TTL 30 天）

        缓存失败不阻断主流程（L1 是可选的性能优化）。

        Args:
            note: 持久化笔记
        """
        if self._l1_cache is None:
            return
        try:
            await self._l1_cache.set(
                key=f"note:{note.note_id}",
                value=json.dumps(note.to_dict(), ensure_ascii=False),
                ttl=_NOTE_CACHE_TTL_SECONDS,
            )
        except Exception:
            # 缓存失败降级跳过
            return

    @staticmethod
    def verify_persisted(note: PersistentNote) -> bool:
        """验证持久化是否完成（压缩前检查）

        Args:
            note: 持久化笔记

        Returns:
            True 表示持久化已完成，False 表示未完成
        """
        return note.persisted and note.persisted_at is not None

    @staticmethod
    def _build_content(retrieved_docs: list[SearchResult]) -> str:
        """从检索结果构建合并内容文本（用于实体抽取）

        Args:
            retrieved_docs: 检索结果列表

        Returns:
            合并后的内容文本（上限 _ENTITY_EXTRACTION_CONTENT_LIMIT 字符）
        """
        parts: list[str] = []
        for r in retrieved_docs:
            if not isinstance(r, dict):
                continue
            payload = r.get("payload", {})
            if not isinstance(payload, dict):
                continue
            content = payload.get("content") or payload.get("summary_text") or ""
            if content:
                parts.append(str(content))
        merged = "\n".join(parts)
        return merged[:_ENTITY_EXTRACTION_CONTENT_LIMIT]


__all__ = [
    "PersistentNote",
    "PersistentNoteTaker",
]
