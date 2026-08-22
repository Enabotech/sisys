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
