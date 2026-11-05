"""Story 3.5 索引管道 payload 扩展单元测试

⚠️ 索引已统一迁移至事件驱动链（ChunkIndexingHandler）：
- generate_embedding / index_document 已删除（document_tasks.py），全文索引轨废弃。
- 本文件仅保留 ChunkIndexingHandler 存在的验证（分块级索引由事件处理器承担）。
"""

from __future__ import annotations

import pytest


class TestChunkIndexingHandler:
    """ChunkIndexingHandler 分块索引处理器（事件驱动链）"""

    @pytest.mark.asyncio
    async def test_handler_exists_in_application_event_handlers(self) -> None:
        """ChunkIndexingHandler 应存在于应用层事件处理器"""
        import importlib

        try:
            mod = importlib.import_module("src.application.event_handlers.chunk_indexing_handler")
        except ImportError:
            pytest.fail("src.application.event_handlers.chunk_indexing_handler 模块不存在")
        assert hasattr(mod, "ChunkIndexingHandler"), "ChunkIndexingHandler 类不存在"

    @pytest.mark.asyncio
    async def test_handler_has_handle_method(self) -> None:
        """ChunkIndexingHandler 应包含 handle 方法"""
        import importlib

        try:
            mod = importlib.import_module("src.application.event_handlers.chunk_indexing_handler")
            cls = getattr(mod, "ChunkIndexingHandler")
        except ImportError:
            pytest.fail("src.application.event_handlers.chunk_indexing_handler 模块不存在")
        assert hasattr(cls, "handle_chunk_indexed"), "ChunkIndexingHandler 应包含 handle_chunk_indexed 方法"

    @pytest.mark.asyncio
    async def test_handler_writes_chunk_level_payload(self) -> None:
        """ChunkIndexingHandler 的 upsert 点应包含 index_level=parent/child"""
        from unittest.mock import AsyncMock, MagicMock

        from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler
        from src.domain.events.workflow_events import RAGIndexed

        captured: dict = {}

        async def _fake_upsert(collection: str, points: list[dict]) -> bool:
            captured["collection"] = collection
            captured["payloads"] = [p.get("payload", {}) for p in points]
            return True

        mock_l3 = AsyncMock()
        mock_l3.upsert_points.side_effect = _fake_upsert
        mock_embedding = AsyncMock()
        mock_embedding.embed_documents.return_value = [[0.1] * 1024]
        mock_repo = AsyncMock()
        mock_repo.find.return_value = MagicMock(
            metadata={
                "chunks": [
                    {"chunk_id": "c1", "content": "块1内容", "index_level": "parent", "parent_chunk_id": None},
                    {"chunk_id": "c2", "content": "块2内容", "index_level": "child", "parent_chunk_id": "c1"},
                ]
            }
        )

        handler = ChunkIndexingHandler(
            embedding_service=mock_embedding,
            l3_vector=mock_l3,
            document_repository=mock_repo,
        )
        event = RAGIndexed(document_id=MagicMock(), chunk_count=2, tenant_id="test")
        await handler.handle_chunk_indexed(event)

        assert captured.get("collection") == "documents"
        assert len(captured.get("payloads", [])) == 2
        levels = {p.get("index_level") for p in captured["payloads"]}
        assert levels == {"parent", "child"}, f"分块级索引应包含 parent/child，实际: {levels}"

    @pytest.mark.asyncio
    async def test_handler_writes_page_number_payload_keys(self) -> None:
        """Story 6-7 payload 扩键：构造面 8 键（+page_start/page_end——6.5b-DF1 半边清偿）

        构造面 8 键 exact set 断言（handler 层不含 infra 追加的 created_at——Qdrant
        实存第 9 键口径分立，读回断言见集成场景④，DR1-3）；legacy chunks（dict 无
        页码键——历史文档 metadata 旧形态）降 None 不炸（.get 缺省存量兼容）。
        """
        from unittest.mock import AsyncMock, MagicMock

        from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler
        from src.domain.events.workflow_events import RAGIndexed
        from src.domain.ports.document_repository import DocumentRepositoryPort
        from src.domain.ports.embedding_service import EmbeddingServicePort
        from src.domain.ports.l3_vector import L3VectorPort

        captured: dict = {}

        async def _fake_upsert(collection: str, points: list[dict]) -> bool:
            captured["payloads"] = [p.get("payload", {}) for p in points]
            return True

        # spec 契约约束（单测 Mock 纪律——R1-F8；宿主既有用例形态不触碰）
        mock_l3 = AsyncMock(spec=L3VectorPort)
        mock_l3.upsert_points.side_effect = _fake_upsert
        mock_embedding = AsyncMock(spec=EmbeddingServicePort)
        mock_embedding.embed_documents.return_value = [[0.1] * 1024, [0.1] * 1024]
        mock_repo = AsyncMock(spec=DocumentRepositoryPort)
        mock_repo.find.return_value = MagicMock(
            metadata={
                "chunks": [
                    {
                        "chunk_id": "p1",
                        "content": "带页码块",
                        "index_level": "child",
                        "parent_chunk_id": None,
                        "page_start": 2,
                        "page_end": 3,
                    },
                    {"chunk_id": "p2", "content": "legacy 块", "index_level": "child", "parent_chunk_id": "p1"},
                ]
            }
        )

        handler = ChunkIndexingHandler(
            embedding_service=mock_embedding,
            l3_vector=mock_l3,
            document_repository=mock_repo,
        )
        event = RAGIndexed(document_id=MagicMock(), chunk_count=2, tenant_id="test")
        await handler.handle_chunk_indexed(event)

        payloads = captured["payloads"]
        assert len(payloads) == 2
        expected_keys = {
            "chunk_id",
            "document_id",
            "parent_chunk_id",
            "index_level",
            "content",
            "chunk_header",
            "page_start",
            "page_end",
        }
        for payload in payloads:
            assert set(payload.keys()) == expected_keys, (
                f"构造面 payload 应恰 8 键（含 page_start/page_end），实际: {sorted(payload.keys())}"
            )
        assert payloads[0]["page_start"] == 2, "带页码 chunk 应透传 page_start 值"
        assert payloads[0]["page_end"] == 3, "带页码 chunk 应透传 page_end 值"
        assert payloads[1]["page_start"] is None, "legacy chunk（无页码键）应降 None 不炸"
        assert payloads[1]["page_end"] is None, "legacy chunk（无页码键）应降 None 不炸"
        # 既有 6 键值级不变断言
        assert payloads[0]["chunk_id"] == "p1"
        assert payloads[0]["index_level"] == "child"
        assert payloads[0]["content"] == "带页码块"
        assert payloads[1]["chunk_id"] == "p2"
