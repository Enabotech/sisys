"""Embedding API 契约测试

验证 OpenAPI 3.1 契约定义与实际 FastAPI 实现一致。
遵循 story-template.md §SDD 规范定义 — API 契约测试
"""

from __future__ import annotations

from typing import Any, cast

import yaml
from fastapi.testclient import TestClient
from openapi_spec_validator import validate_spec


def load_openapi_spec() -> dict[str, Any]:
    """加载 OpenAPI 契约文件"""
    with open("docs/api/openapi.yaml") as f:
        return cast(dict[str, Any], yaml.safe_load(f))


def test_openapi_spec_is_valid() -> None:
    """OpenAPI 3.1 规范语法正确"""
    spec = load_openapi_spec()
    validate_spec(cast(Any, spec))  # openapi_spec_validator 类型标注不完整


class TestEmbeddingPathsInContract:
    """Embedding API 路径在契约中定义"""

    def test_health_path_exists(self) -> None:
        """GET /health 路径存在"""
        spec = load_openapi_spec()
        assert "/health" in spec["paths"]
        assert "get" in spec["paths"]["/health"]

    def test_embeddings_path_exists(self) -> None:
        """POST /v1/embeddings 路径存在"""
        spec = load_openapi_spec()
        assert "/v1/embeddings" in spec["paths"]
        assert "post" in spec["paths"]["/v1/embeddings"]


class TestEmbeddingSchemasInContract:
    """Embedding API schemas 在契约中定义"""

    def test_embed_request_schema(self) -> None:
        """EmbedRequest schema 存在且包含必要字段"""
        spec = load_openapi_spec()
        schemas = spec["components"]["schemas"]
        assert "EmbedRequest" in schemas
        assert "texts" in schemas["EmbedRequest"]["properties"]
        assert "return_sparse" in schemas["EmbedRequest"]["properties"]

    def test_embed_response_schema(self) -> None:
        """EmbedResponse schema 存在且包含必要字段"""
        spec = load_openapi_spec()
        schemas = spec["components"]["schemas"]
        assert "EmbedResponse" in schemas
        assert "dense" in schemas["EmbedResponse"]["properties"]
        assert "sparse" in schemas["EmbedResponse"]["properties"]

    def test_health_response_schema(self) -> None:
        """EmbeddingHealthResponse schema 存在且包含必要字段"""
        spec = load_openapi_spec()
        schemas = spec["components"]["schemas"]
        assert "EmbeddingHealthResponse" in schemas
        assert "status" in schemas["EmbeddingHealthResponse"]["properties"]


class TestEmbeddingContractMatchesImplementation:
    """契约与 FastAPI 实现一致"""

    client: TestClient

    @classmethod
    def setup_class(cls) -> None:
        """创建 TestClient 并注入 mock 模型"""
        from unittest.mock import MagicMock

        import numpy as np

        from src.infrastructure.external_services.embedding.embedding_api_server import app

        model = MagicMock()

        def mock_encode(texts, return_dense=False, return_sparse=False, **kwargs):
            result = {}
            n = len(texts) if isinstance(texts, list) else 1
            if return_dense:
                result["dense_vecs"] = np.random.randn(n, 1024).astype(np.float32)
            if return_sparse:
                result["lexical_weights"] = [{str(i): 0.5 for i in range(3)} for _ in range(n)]
            return result

        model.encode.side_effect = mock_encode
        app.state.model = model
        app.state.model_name = "BAAI/bge-m3"
        app.state.device = "cpu"
        app.state.load_error = None
        cls.client = TestClient(app)

    def test_health_200_matches_contract(self) -> None:
        """GET /health 200 响应符合 HealthResponse schema"""
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "model" in data
        assert "device" in data

    def test_embeddings_200_matches_contract(self) -> None:
        """POST /v1/embeddings 200 响应符合 EmbedResponse schema"""
        resp = self.client.post("/v1/embeddings", json={"texts": ["test"], "return_sparse": True})
        assert resp.status_code == 200
        data = resp.json()
        assert "dense" in data
        assert len(data["dense"]) == 1
        assert len(data["dense"][0]) == 1024
        assert "sparse" in data
        assert data["sparse"] is not None

    def test_embeddings_422_on_empty_texts(self) -> None:
        """空 texts 返回 422（契约定义的行为）"""
        resp = self.client.post("/v1/embeddings", json={"texts": [], "return_sparse": False})
        assert resp.status_code == 422
