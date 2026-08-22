"""PersistentNoteTaker 领域服务单元测试

验证持久化笔记服务的核心流程：
1. 空查询抛出 EntityValidationError
2. 正常流程：实体抽取 → 血缘记录 → 持久化标记
3. 降级策略：实体抽取失败降级、审计服务未注入降级
4. verify_persisted 前置条件检查

遵循 Mock 端口策略（仅单元测试允许）。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import EntityValidationError
from src.domain.ports.entity_extraction import ExtractionResult
from src.domain.ports.l3_vector import SearchResult
from src.domain.services.persistent_note_taker import PersistentNote, PersistentNoteTaker


def _make_search_result(
    doc_id: str = "doc-1",
    score: float = 0.9,
    content: str = "测试文档内容",
) -> SearchResult:
    """构造测试用 SearchResult"""
    return SearchResult(id=doc_id, score=score, payload={"content": content})


class TestPersistentNoteTaker:
    """PersistentNoteTaker 单元测试"""

    async def test_empty_query_raises_validation_error(self) -> None:
        """空查询时抛出 EntityValidationError"""
        mock_extractor = AsyncMock(spec=[])
        service = PersistentNoteTaker(entity_extractor=mock_extractor)

        with pytest.raises(EntityValidationError, match="query must not be empty"):
            await service.take_notes(
                query="",
                retrieved_docs=[],
                user_id="test-user",
                session_id="test-session",
            )

    async def test_empty_query_whitespace_raises_validation_error(self) -> None:
        """空查询（仅空白字符）时抛出 EntityValidationError"""
        mock_extractor = AsyncMock(spec=[])
        service = PersistentNoteTaker(entity_extractor=mock_extractor)

        with pytest.raises(EntityValidationError):
            await service.take_notes(
                query="   ",
                retrieved_docs=[],
                user_id="test-user",
                session_id="test-session",
            )

    async def test_take_notes_normal_flow(self) -> None:
        """正常流程：提取实体 → 构建血缘 → 持久化标记"""
        mock_extractor = AsyncMock()
        mock_extractor.extract_entities.return_value = ExtractionResult(
            entities=(),
            extraction_metadata={"strategy": "rule", "entity_count": 0},
        )
        service = PersistentNoteTaker(entity_extractor=mock_extractor)

        docs = [_make_search_result(doc_id="doc-1", content="企业战略规划文档内容")]
        note = await service.take_notes(
            query="企业战略规划分析",
            retrieved_docs=docs,
            user_id="test-user",
            session_id="test-session",
        )

        assert isinstance(note, PersistentNote)
        assert note.persisted is True, "持久化标记应为 True"
        assert note.persisted_at is not None, "持久化时间不应为空"
        assert note.query == "企业战略规划分析"
        assert note.user_id == "test-user"
        assert note.session_id == "test-session"
        assert "query" in note.lineage
        assert note.lineage["query"] == "企业战略规划分析"
        assert note.lineage["top_k"] == 1
        assert note.lineage["document_ids"] == ["doc-1"]

    async def test_take_notes_with_entities(self) -> None:
        """带实体抽取的完整流程"""
        from src.domain.ports.entity_extraction import ExtractedEntity, ExtractionResult

        mock_extractor = AsyncMock()
        mock_extractor.extract_entities.return_value = ExtractionResult(
            entities=(
                ExtractedEntity(name="战略规划", entity_type="CONCEPT", confidence=0.85, extraction_source="rule"),
                ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.95, extraction_source="rule"),
            ),
            extraction_metadata={"strategy": "rule", "entity_count": 2},
        )
        service = PersistentNoteTaker(entity_extractor=mock_extractor)

        docs = [_make_search_result(doc_id="doc-1", content="BLM 战略规划方法")]
        note = await service.take_notes(
            query="战略规划方法",
            retrieved_docs=docs,
            user_id="test-user",
            session_id="test-session",
        )

        assert note.persisted is True
        assert len(note.entities) == 2
        assert note.entities[0]["name"] == "战略规划"
        assert note.entities[1]["name"] == "BLM"

    async def test_entity_extraction_failure_degradation(self) -> None:
        """实体抽取失败降级为空实体列表（不阻断持久化）"""
        mock_extractor = AsyncMock()
        mock_extractor.extract_entities.side_effect = Exception("抽取服务不可用")
        service = PersistentNoteTaker(entity_extractor=mock_extractor)

        docs = [_make_search_result(doc_id="doc-1", content="测试内容")]
        note = await service.take_notes(
            query="测试",
            retrieved_docs=docs,
            user_id="test-user",
            session_id="test-session",
        )

        assert note.persisted is True, "实体抽取失败不应阻断持久化"
        assert note.entities == [], "实体抽取失败时 entities 应为空列表"
        assert note.extraction_result.extraction_metadata.get("strategy") == "failed"

    async def test_audit_service_not_injected(self) -> None:
        """审计服务未注入时降级跳过"""
        mock_extractor = AsyncMock()
        mock_extractor.extract_entities.return_value = ExtractionResult(
            entities=(),
            extraction_metadata={"strategy": "rule", "entity_count": 0},
        )
        # 不注入 audit_service，验证降级跳过
        service = PersistentNoteTaker(entity_extractor=mock_extractor)

        docs = [_make_search_result(doc_id="doc-1", content="测试")]
        note = await service.take_notes(
            query="测试",
            retrieved_docs=docs,
            user_id="test-user",
            session_id="test-session",
        )

        assert note.persisted is True
        assert note.lineage is not None

    async def test_audit_service_failure_degradation(self) -> None:
        """审计服务记录失败时降级跳过（不阻断主流程）"""
        mock_extractor = AsyncMock()
        mock_extractor.extract_entities.return_value = ExtractionResult(
            entities=(),
            extraction_metadata={"strategy": "rule", "entity_count": 0},
        )
        mock_audit = AsyncMock()
        mock_audit.record = AsyncMock(side_effect=Exception("审计服务不可用"))

        service = PersistentNoteTaker(
            entity_extractor=mock_extractor,
            audit_service=mock_audit,
        )

        docs = [_make_search_result(doc_id="doc-1", content="测试")]
        note = await service.take_notes(
            query="测试",
            retrieved_docs=docs,
            user_id="test-user",
            session_id="test-session",
        )

        assert note.persisted is True, "审计失败不应阻断持久化"

    async def test_no_docs_returns_empty_lineage(self) -> None:
        """无检索文档时正常返回空血缘"""
        mock_extractor = AsyncMock()
        mock_extractor.extract_entities.return_value = ExtractionResult(
            entities=(),
            extraction_metadata={"strategy": "none", "entity_count": 0},
        )
        service = PersistentNoteTaker(entity_extractor=mock_extractor)

        note = await service.take_notes(
            query="测试",
            retrieved_docs=[],
            user_id="test-user",
            session_id="test-session",
        )

        assert note.persisted is True
        assert note.lineage["top_k"] == 0
        assert note.lineage["document_ids"] == []

    async def test_l1_cache_set_called(self) -> None:
        """L1 缓存注入时 set 被调用"""
        mock_extractor = AsyncMock()
        mock_extractor.extract_entities.return_value = ExtractionResult(
            entities=(),
            extraction_metadata={"strategy": "rule", "entity_count": 0},
        )
        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock(return_value=True)

        service = PersistentNoteTaker(
            entity_extractor=mock_extractor,
            l1_cache=mock_cache,
        )

        docs = [_make_search_result(doc_id="doc-1", content="测试")]
        note = await service.take_notes(
            query="测试",
            retrieved_docs=docs,
            user_id="test-user",
            session_id="test-session",
        )

        assert note.persisted is True
        mock_cache.set.assert_called_once()
        assert mock_cache.set.call_args[1]["key"].startswith("note:")

    async def test_l1_cache_not_injected(self) -> None:
        """L1 缓存未注入时降级跳过"""
        mock_extractor = AsyncMock()
        mock_extractor.extract_entities.return_value = ExtractionResult(
            entities=(),
            extraction_metadata={"strategy": "rule", "entity_count": 0},
        )
        # 不注入 l1_cache
        service = PersistentNoteTaker(entity_extractor=mock_extractor)

        docs = [_make_search_result(doc_id="doc-1", content="测试")]
        note = await service.take_notes(
            query="测试",
            retrieved_docs=docs,
            user_id="test-user",
            session_id="test-session",
        )

        assert note.persisted is True

    async def test_verify_persisted_true(self) -> None:
        """已持久化的笔记通过 verify_persisted"""
        from datetime import UTC, datetime

        note = PersistentNote(persisted=True, persisted_at=datetime.now(UTC))
        assert PersistentNoteTaker.verify_persisted(note) is True

    async def test_verify_persisted_false_when_not_persisted(self) -> None:
        """未持久化的笔记不通过 verify_persisted"""
        note = PersistentNote()
        assert PersistentNoteTaker.verify_persisted(note) is False

    async def test_verify_persisted_false_when_no_timestamp(self) -> None:
        """persisted=True 但 persisted_at=None 时 verify_persisted 返回 False"""
        note = PersistentNote(persisted=True, persisted_at=None)
        assert PersistentNoteTaker.verify_persisted(note) is False

    async def test_build_content_empty_docs(self) -> None:
        """空文档列表返回空字符串"""
        result = PersistentNoteTaker._build_content([])
        assert result == ""

    async def test_build_content_with_payload(self) -> None:
        """有 payload 的文档合并内容"""
        docs = [
            _make_search_result(doc_id="doc-1", content="文档一内容"),
            _make_search_result(doc_id="doc-2", content="文档二内容"),
        ]
        result = PersistentNoteTaker._build_content(docs)
        assert "文档一内容" in result
        assert "文档二内容" in result

    async def test_build_content_respects_limit(self) -> None:
        """合并内容不超过 _ENTITY_EXTRACTION_CONTENT_LIMIT 字符"""
        from src.domain.services.persistent_note_taker import _ENTITY_EXTRACTION_CONTENT_LIMIT

        long_content = "A" * (_ENTITY_EXTRACTION_CONTENT_LIMIT + 1000)
        docs = [_make_search_result(doc_id="doc-1", content=long_content)]
        result = PersistentNoteTaker._build_content(docs)
        assert len(result) <= _ENTITY_EXTRACTION_CONTENT_LIMIT

    async def test_persistent_note_to_dict(self) -> None:
        """PersistentNote.to_dict() 序列化验证"""
        from datetime import UTC, datetime

        note = PersistentNote(
            query="测试",
            user_id="test-user",
            session_id="test-session",
            persisted=True,
            persisted_at=datetime.now(UTC),
        )
        d = note.to_dict()
        assert d["note_id"] == str(note.note_id)
        assert d["query"] == "测试"
        assert d["persisted"] is True
        assert d["persisted_at"] is not None

    async def test_persistent_note_frozen(self) -> None:
        """PersistentNote 是 frozen dataclass"""
        note = PersistentNote(query="测试")
        with pytest.raises(AttributeError):
            note.query = "修改"  # type: ignore[misc]

    async def test_extraction_entity_limit(self) -> None:
        """实体数量限制为 Top-20"""
        from src.domain.ports.entity_extraction import ExtractedEntity

        entities = tuple(
            ExtractedEntity(name=f"entity-{i}", entity_type="CONCEPT", confidence=0.8, extraction_source="rule")
            for i in range(30)
        )
        mock_extractor = AsyncMock()
        mock_extractor.extract_entities.return_value = ExtractionResult(
            entities=entities,
            extraction_metadata={"strategy": "rule", "entity_count": 30},
        )
        service = PersistentNoteTaker(entity_extractor=mock_extractor)

        docs = [_make_search_result(doc_id="doc-1", content="测试内容")]
        note = await service.take_notes(
            query="测试",
            retrieved_docs=docs,
            user_id="test-user",
            session_id="test-session",
        )

        assert len(note.entities) == 20


class TestPersistentNoteValueObject:
    """PersistentNote 值对象测试"""

    def test_default_creation(self) -> None:
        """默认创建带有 note_id 和 created_at"""
        note = PersistentNote()
        assert note.note_id is not None
        assert note.created_at is not None
        assert note.persisted is False

    def test_default_extraction_result(self) -> None:
        """默认 extraction_result 为"none"策略"""
        note = PersistentNote()
        assert note.extraction_result.extraction_metadata.get("strategy") == "none"

    def test_equality_based_on_note_id(self) -> None:
        """两个不同 note_id 的 PersistentNote 不相等"""
        note1 = PersistentNote()
        note2 = PersistentNote()
        assert note1 != note2
