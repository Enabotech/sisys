"""LiteLLMRerankerClient 单元测试

验证重排序逻辑、top_k 截断语义、降级策略、分数映射。
使用 mock 隔离 litellm.rerank() API 调用。
"""

from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.reranker import RerankerPort
from src.infrastructure.external_services.reranker.config import RerankerConfig
from src.infrastructure.external_services.reranker.litellm_reranker_client import (
    LiteLLMRerankerClient,
)


class TestLiteLLMRerankerClient:
    """LiteLLMRerankerClient 测试"""

    @pytest.fixture
    def config(self) -> RerankerConfig:
        return RerankerConfig(model="BAAI/bge-reranker-v2-m3", top_k=20, timeout=10)

    @pytest.fixture
    def client(self, config: RerankerConfig) -> LiteLLMRerankerClient:
        return LiteLLMRerankerClient(config=config)

    @pytest.fixture
    def sample_results(self) -> list[SearchResult]:
        return [
            SearchResult(id="doc1", score=0.5, payload={"title": "文档1"}),
            SearchResult(id="doc2", score=0.4, payload={"title": "文档2"}),
            SearchResult(id="doc3", score=0.3, payload={"title": "文档3"}),
        ]

    def test_implements_reranker_port(self, client: LiteLLMRerankerClient) -> None:
        """验证实现 RerankerPort 接口"""
        assert isinstance(client, RerankerPort)

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self, client: LiteLLMRerankerClient) -> None:
        """空输入返回空列表"""
        result = await client.rerank("query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_fallback_on_no_litellm(
        self, client: LiteLLMRerankerClient, sample_results: list[SearchResult]
    ) -> None:
        """litellm 不可用时降级返回原始结果"""
        with patch("src.infrastructure.external_services.reranker.litellm_reranker_client._litellm_available", False):
            result = await client.rerank("query", sample_results, top_k=2)
            assert len(result) == 2
            assert result[0]["id"] == "doc1"
            assert result[0]["payload"]["original_score"] == 0.5

    @pytest.mark.asyncio
    async def test_rerank_success(self, client: LiteLLMRerankerClient, sample_results: list[SearchResult]) -> None:
        """重排序成功返回按新分数降序的结果"""
        from src.infrastructure.external_services.reranker import litellm_reranker_client as client_module

        mock_response = type(
            "RerankResponse",
            (),
            {
                "results": [
                    type("Result", (), {"index": 2, "relevance_score": 0.9})(),
                    type("Result", (), {"index": 0, "relevance_score": 0.7})(),
                    type("Result", (), {"index": 1, "relevance_score": 0.5})(),
                ]
            },
        )()

        mock_litellm = type("MockLitellm", (), {"rerank": AsyncMock(return_value=mock_response)})()

        with patch.object(client_module, "_litellm", mock_litellm):
            with patch.object(client_module, "_litellm_available", True):
                result = await client.rerank("query", sample_results, top_k=3)

                assert len(result) == 3
                assert result[0]["id"] == "doc3"
                assert result[1]["id"] == "doc1"
                assert result[2]["id"] == "doc2"

                assert result[0]["score"] == 0.9
                assert result[0]["payload"]["original_score"] == 0.3
                assert result[0]["payload"]["rerank_score"] == 0.9

    @pytest.mark.asyncio
    async def test_top_k_truncation(self, client: LiteLLMRerankerClient, sample_results: list[SearchResult]) -> None:
        """top_k 截断语义：litellm.rerank() 接收 top_k 参数"""
        from src.infrastructure.external_services.reranker import litellm_reranker_client as client_module

        mock_litellm = type(
            "MockLitellm",
            (),
            {
                "rerank": AsyncMock(
                    return_value=type(
                        "RerankResponse",
                        (),
                        {
                            "results": [
                                type("Result", (), {"index": 0, "relevance_score": 0.9})(),
                                type("Result", (), {"index": 1, "relevance_score": 0.7})(),
                            ]
                        },
                    )()
                )
            },
        )()

        with patch.object(client_module, "_litellm", mock_litellm):
            with patch.object(client_module, "_litellm_available", True):
                result = await client.rerank("query", sample_results, top_k=2)
                assert len(result) == 2
                # 验证 litellm.rerank() 被调用时 top_k=2
                call_kwargs = mock_litellm.rerank.call_args.kwargs
                assert call_kwargs.get("top_k") == 2

    @pytest.mark.asyncio
    async def test_top_k_greater_than_results(self, client: LiteLLMRerankerClient, sample_results: list[SearchResult]) -> None:
        """top_k >= len(results) 时返回全部"""
        from src.infrastructure.external_services.reranker import litellm_reranker_client as client_module

        mock_response = type(
            "RerankResponse",
            (),
            {
                "results": [
                    type("Result", (), {"index": 0, "relevance_score": 0.9})(),
                    type("Result", (), {"index": 1, "relevance_score": 0.7})(),
                    type("Result", (), {"index": 2, "relevance_score": 0.5})(),
                ]
            },
        )()

        mock_litellm = type("MockLitellm", (), {"rerank": AsyncMock(return_value=mock_response)})()
        with patch.object(client_module, "_litellm", mock_litellm):
            with patch.object(client_module, "_litellm_available", True):
                result = await client.rerank("query", sample_results, top_k=10)
                assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rerank_api_failure_fallback(self, client: LiteLLMRerankerClient, sample_results: list[SearchResult]) -> None:
        """API 调用失败时降级返回原始结果"""
        from src.infrastructure.external_services.reranker import litellm_reranker_client as client_module

        mock_litellm = type("MockLitellm", (), {"rerank": AsyncMock(side_effect=RuntimeError("API 不可用"))})()
        with patch.object(client_module, "_litellm", mock_litellm):
            with patch.object(client_module, "_litellm_available", True):
                result = await client.rerank("query", sample_results, top_k=2)
                assert len(result) == 2
                assert result[0]["id"] == "doc1"
                assert result[0]["payload"]["original_score"] == 0.5

    @pytest.mark.asyncio
    async def test_score_in_range(self, client: LiteLLMRerankerClient, sample_results: list[SearchResult]) -> None:
        """重排序分数在 [0, 1] 范围内"""
        from src.infrastructure.external_services.reranker import litellm_reranker_client as client_module

        mock_response = type(
            "RerankResponse",
            (),
            {
                "results": [
                    type("Result", (), {"index": 0, "relevance_score": 0.95})(),
                    type("Result", (), {"index": 1, "relevance_score": 0.75})(),
                    type("Result", (), {"index": 2, "relevance_score": 0.55})(),
                ]
            },
        )()

        mock_litellm = type("MockLitellm", (), {"rerank": AsyncMock(return_value=mock_response)})()
        with patch.object(client_module, "_litellm", mock_litellm):
            with patch.object(client_module, "_litellm_available", True):
                result = await client.rerank("query", sample_results, top_k=3)
                for r in result:
                    assert 0.0 <= r["score"] <= 1.0, f"分数 {r['score']} 不在 [0,1] 范围内"


class TestRerankerConfig:
    """RerankerConfig 测试"""

    def test_from_env_defaults(self) -> None:
        """验证 from_env() 默认值"""
        config = RerankerConfig.from_env()
        assert config.model == "BAAI/bge-reranker-v2-m3"
        assert config.top_k == 20
        assert config.timeout == 10

    def test_from_env_with_env_vars(self, monkeypatch) -> None:
        """验证环境变量覆盖"""
        monkeypatch.setenv("RERANKER_MODEL", "custom-model")
        monkeypatch.setenv("RERANKER_TOP_K", "50")
        monkeypatch.setenv("RERANKER_TIMEOUT", "30")
        monkeypatch.setenv("RERANKER_API_KEY", "test-key")
        monkeypatch.setenv("RERANKER_BASE_URL", "http://localhost:8000")

        config = RerankerConfig.from_env()
        assert config.model == "custom-model"
        assert config.top_k == 50
        assert config.timeout == 30
        assert config.api_key == "test-key"  # pragma: allowlist secret
        assert config.base_url == "http://localhost:8000"

    def test_frozen_dataclass(self) -> None:
        """验证 frozen dataclass"""
        config = RerankerConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(config, "model", "other-model")
