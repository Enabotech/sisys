"""generate_embedding task 单元测试

验证 generate_embedding 通过 resolver 获取 embedding_service 并生成嵌入
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGenerateEmbedding:
    """generate_embedding 任务测试"""

    @pytest.mark.asyncio
    async def test_returns_embedding_on_success(self) -> None:
        """成功时返回嵌入向量"""
        import uuid

        doc_id = str(uuid.uuid4())
        mock_embedding_svc = MagicMock()
        mock_embedding_svc.encode_text.return_value = [0.1] * 1024

        mock_repo = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.metadata = {
            "parse_result": {
                "pages": [
                    {"texts": [{"content": "测试文本内容"}]},
                ]
            }
        }
        mock_repo.find = AsyncMock(return_value=mock_doc)

        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = lambda name: {
            "embedding_service": mock_embedding_svc,
            "document_repository": mock_repo,
        }[name]

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

            result = await generate_embedding({"status": "completed", "document_id": doc_id, "pages": 1})
            assert len(result) == 1024

    @pytest.mark.asyncio
    async def test_returns_empty_on_failure(self) -> None:
        """失败时返回空列表（向后兼容）"""
        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = RuntimeError("端口不可用")

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

            result = await generate_embedding(
                {"status": "failed", "document_id": "00000000-0000-0000-0000-000000000000", "error": "解析失败"}
            )
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_text(self) -> None:
        """无文本内容时返回空列表"""
        import uuid

        doc_id = str(uuid.uuid4())
        mock_embedding_svc = MagicMock()
        mock_repo = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.metadata = {"parse_result": {"pages": []}}
        mock_repo.find = AsyncMock(return_value=mock_doc)

        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = lambda name: {
            "embedding_service": mock_embedding_svc,
            "document_repository": mock_repo,
        }[name]

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

            result = await generate_embedding({"status": "completed", "document_id": doc_id, "pages": 0})
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_doc_not_found(self) -> None:
        """文档不存在时返回空列表"""
        import uuid

        doc_id = str(uuid.uuid4())
        mock_embedding_svc = MagicMock()
        mock_repo = AsyncMock()
        mock_repo.find = AsyncMock(return_value=None)

        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = lambda name: {
            "embedding_service": mock_embedding_svc,
            "document_repository": mock_repo,
        }[name]

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

            result = await generate_embedding({"status": "completed", "document_id": doc_id, "pages": 1})
            assert result == []
