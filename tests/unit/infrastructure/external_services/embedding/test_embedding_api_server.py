"""Embedding API Server 单元测试

使用 FastAPI TestClient 验证嵌入 API 服务的端点、请求校验和编码功能。
测试不加载真实 BGE-M3 模型，通过覆盖 app.state.model 注入 mock。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_model() -> MagicMock:
    """构造 mock BGEM3FlagModel"""
    model = MagicMock()

    def mock_encode(texts, return_dense=False, return_sparse=False, **kwargs):
        result = {}
        n = len(texts) if isinstance(texts, list) else 1
        if return_dense:
            result["dense_vecs"] = np.random.randn(n, 1024).astype(np.float32)
        if return_sparse:
            result["lexical_weights"] = [{100: 0.5, 200: 0.3} for _ in range(n)]
        return result

    model.encode.side_effect = mock_encode
    return model


@pytest.fixture
def client(mock_model: MagicMock) -> TestClient:
    """创建 TestClient 并注入 mock 模型"""
    from src.infrastructure.external_services.embedding.embedding_api_server import app

    app.state.model = mock_model
    return TestClient(app)


class TestEmbeddingAPIHealthCheck:
    """健康检查端点"""

    def test_health_returns_ok(self, client: TestClient) -> None:
        """GET /health 返回状态 ok"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "model" in data


class TestEmbeddingAPIDenseEncoding:
    """Dense 编码端点"""

    def test_dense_encoding_returns_1024_dim(self, client: TestClient) -> None:
        """POST /v1/embeddings Dense 编码返回 1024 维向量"""
        resp = client.post("/v1/embeddings", json={"texts": ["测试文本"], "return_sparse": False})
        assert resp.status_code == 200
        data = resp.json()
        assert "dense" in data
        assert len(data["dense"]) == 1
        assert len(data["dense"][0]) == 1024

    def test_dense_encoding_batch(self, client: TestClient) -> None:
        """批量编码返回正确数量"""
        resp = client.post("/v1/embeddings", json={"texts": ["A", "B", "C"], "return_sparse": False})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dense"]) == 3

    def test_dense_encoding_sparse_is_null(self, client: TestClient) -> None:
        """return_sparse=False 时 sparse 字段为 null"""
        resp = client.post("/v1/embeddings", json={"texts": ["test"], "return_sparse": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sparse"] is None


class TestEmbeddingAPISparseEncoding:
    """Sparse 编码端点"""

    def test_sparse_encoding_returns_both_dense_and_sparse(self, client: TestClient) -> None:
        """return_sparse=True 同时返回 dense 和 sparse"""
        resp = client.post("/v1/embeddings", json={"texts": ["测试"], "return_sparse": True})
        assert resp.status_code == 200
        data = resp.json()
        assert "dense" in data
        assert "sparse" in data
        assert data["sparse"] is not None

    def test_sparse_encoding_has_indices_and_values(self, client: TestClient) -> None:
        """sparse 返回结果包含 indices 和 values"""
        resp = client.post("/v1/embeddings", json={"texts": ["测试"], "return_sparse": True})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["sparse"], list)
        assert len(data["sparse"]) == 1
        assert "indices" in data["sparse"][0]
        assert "values" in data["sparse"][0]


class TestEmbeddingAPIValidation:
    """请求校验"""

    def test_empty_texts_returns_422(self, client: TestClient) -> None:
        """空 texts 列表返回 422"""
        resp = client.post("/v1/embeddings", json={"texts": [], "return_sparse": False})
        assert resp.status_code == 422

    def test_missing_texts_field_returns_422(self, client: TestClient) -> None:
        """缺少 texts 字段返回 422"""
        resp = client.post("/v1/embeddings", json={"return_sparse": False})
        assert resp.status_code == 422

    def test_texts_exceeds_max_batch_size_returns_422(self, client: TestClient) -> None:
        """texts 超过 64 条返回 422"""
        resp = client.post("/v1/embeddings", json={"texts": ["x"] * 65, "return_sparse": False})
        assert resp.status_code == 422
