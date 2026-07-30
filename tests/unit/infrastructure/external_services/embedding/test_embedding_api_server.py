"""Embedding API Server 单元测试

使用 FastAPI TestClient 验证嵌入 API 服务的端点、请求校验和编码功能。
测试不加载真实 BGE-M3 模型，通过覆盖 app.state.model 注入 mock。
"""

from __future__ import annotations

from collections.abc import Generator
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
            result["lexical_weights"] = [{"100": 0.5, "200": 0.3} for _ in range(n)]  # FlagEmbedding str keys
        return result

    model.encode.side_effect = mock_encode
    return model


@pytest.fixture
def client(mock_model: MagicMock) -> Generator[TestClient, None, None]:
    """创建 TestClient 并注入 mock 模型"""
    from src.infrastructure.external_services.embedding.embedding_api_server import app

    # 保存旧状态以便测试后恢复，避免全局状态泄漏
    old_state = {
        "model": getattr(app.state, "model", None),
        "model_name": getattr(app.state, "model_name", None),
        "device": getattr(app.state, "device", None),
        "load_error": getattr(app.state, "load_error", None),
    }
    app.state.model = mock_model
    app.state.model_name = "BAAI/bge-m3"
    app.state.device = "cpu"
    app.state.load_error = None
    yield TestClient(app)
    # 恢复旧状态
    app.state.model = old_state["model"]
    app.state.model_name = old_state["model_name"]
    app.state.device = old_state["device"]
    app.state.load_error = old_state["load_error"]


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

    def test_large_batch_accepted(self, client: TestClient) -> None:
        """大批量请求正常处理（无上限限制）"""
        resp = client.post("/v1/embeddings", json={"texts": ["x"] * 100, "return_sparse": False})
        assert resp.status_code == 200


@pytest.fixture
def client_no_model() -> Generator[TestClient, None, None]:
    """创建 TestClient，模型未加载（模拟启动失败场景）"""
    from src.infrastructure.external_services.embedding.embedding_api_server import app

    # 保存旧状态以便测试后恢复
    old_state = {
        "model": getattr(app.state, "model", None),
        "model_name": getattr(app.state, "model_name", None),
        "device": getattr(app.state, "device", None),
        "load_error": getattr(app.state, "load_error", None),
    }
    app.state.model = None
    app.state.model_name = "BAAI/bge-m3"
    app.state.device = "cpu"
    app.state.load_error = "Model download failed"
    yield TestClient(app)
    # 恢复旧状态
    app.state.model = old_state["model"]
    app.state.model_name = old_state["model_name"]
    app.state.device = old_state["device"]
    app.state.load_error = old_state["load_error"]


class TestEmbeddingAPI503Unavailable:
    """模型未加载时的 503 降级行为"""

    def test_health_returns_503_when_model_unavailable(self, client_no_model: TestClient) -> None:
        """模型未加载时 GET /health 返回 503"""
        resp = client_no_model.get("/health")
        assert resp.status_code == 503
        data = resp.json()
        assert data["detail"]["status"] == "unavailable"
        assert "error" in data["detail"]

    def test_embed_returns_503_when_model_unavailable(self, client_no_model: TestClient) -> None:
        """模型未加载时 POST /v1/embeddings 返回 503"""
        resp = client_no_model.post("/v1/embeddings", json={"texts": ["test"]})
        assert resp.status_code == 503


class TestEmbeddingAPISanitization:
    """NaN/Inf 防御性净化测试"""

    @pytest.fixture
    def client_with_nan_model(self) -> Generator[TestClient, None, None]:
        """注入会返回 NaN 的 mock 模型"""
        from src.infrastructure.external_services.embedding.embedding_api_server import app

        model = MagicMock()
        old_state = {
            "model": getattr(app.state, "model", None),
            "model_name": getattr(app.state, "model_name", None),
            "device": getattr(app.state, "device", None),
            "load_error": getattr(app.state, "load_error", None),
        }

        def mock_encode(texts, return_dense=False, return_sparse=False, **kwargs):
            n = len(texts) if isinstance(texts, list) else 1
            arr = np.random.randn(n, 1024).astype(np.float32)
            arr[0, 0] = np.nan
            arr[0, 1] = np.inf
            arr[0, 2] = -np.inf
            return {"dense_vecs": arr}

        model.encode.side_effect = mock_encode
        app.state.model = model
        app.state.model_name = "BAAI/bge-m3"
        app.state.device = "cpu"
        app.state.load_error = None
        yield TestClient(app)
        app.state.model = old_state["model"]
        app.state.model_name = old_state["model_name"]
        app.state.device = old_state["device"]
        app.state.load_error = old_state["load_error"]

    def test_nan_inf_sanitized_to_zero(self, client_with_nan_model: TestClient) -> None:
        """NaN/Inf 值被净化后 JSON 序列化成功"""
        resp = client_with_nan_model.post("/v1/embeddings", json={"texts": ["测试文本"], "return_sparse": False})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dense"]) == 1
        assert len(data["dense"][0]) == 1024
        # 前 3 个值应为 0.0（NaN/Inf/-Inf 被净化）
        assert data["dense"][0][0] == 0.0
        assert data["dense"][0][1] == 0.0
        assert data["dense"][0][2] == 0.0

    def test_normal_values_unchanged(self, client_with_nan_model: TestClient) -> None:
        """正常值（非 NaN/Inf）保留原值"""
        resp = client_with_nan_model.post("/v1/embeddings", json={"texts": ["测试文本"], "return_sparse": False})
        data = resp.json()
        # 第 3 个值之后应为正常值（非 0.0）
        assert data["dense"][0][3] != 0.0

    def test_sanitize_dense_vectors_importable(self) -> None:
        """_sanitize_dense_vectors 函数可导入"""
        from src.infrastructure.external_services.embedding.embedding_api_server import _sanitize_dense_vectors

        assert callable(_sanitize_dense_vectors)


class TestEmbeddingAPIConcurrency:
    """并发请求安全测试（模型推理锁）"""

    def test_concurrent_requests_succeed(self, client: TestClient) -> None:
        """并发请求均正常返回 200（不因锁争用而超时或死锁）"""
        import threading

        results = []
        errors = []

        def do_request():
            try:
                resp = client.post("/v1/embeddings", json={"texts": ["测试"], "return_sparse": False})
                results.append(resp.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=do_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发请求异常: {errors}"
        assert all(s == 200 for s in results), f"非 200 状态码: {results}"

    def test_embed_lock_prevents_race_condition(self) -> None:
        """_embed_lock 是 threading.Lock 实例"""
        import threading

        from src.infrastructure.external_services.embedding.embedding_api_server import _embed_lock

        assert isinstance(_embed_lock, type(threading.Lock()))
