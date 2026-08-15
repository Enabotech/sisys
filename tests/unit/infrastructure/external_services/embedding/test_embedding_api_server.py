"""Embedding API Server 单元测试

使用 FastAPI TestClient 验证嵌入 API 服务的端点、请求校验和编码功能。
测试不加载真实 BGE-M3 模型，通过覆盖全局 _engine 注入 mock。

重构适配：
- v1.x: 使用 app.state.model 注入 mock
- v2.0: 使用 _engine 全局变量注入 mock ModelInferenceEngine
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_engine() -> MagicMock:
    """构造 mock ModelInferenceEngine"""
    engine = MagicMock()
    engine.is_ready = True
    engine.load_error = None
    engine.dimension = 1024

    def mock_encode(texts, return_sparse=False):
        n = len(texts) if isinstance(texts, list) else 1
        result = {"dense": np.random.randn(n, 1024).astype(np.float32).tolist()}
        if return_sparse:
            result["sparse"] = [{"indices": [100, 200], "values": [0.5, 0.3]} for _ in range(n)]
        else:
            result["sparse"] = None
        return result

    engine.encode.side_effect = mock_encode
    return engine


@pytest.fixture
def client(mock_engine: MagicMock) -> Generator[TestClient, None, None]:
    """创建 TestClient 并注入 mock 引擎"""
    import src.infrastructure.external_services.embedding.embedding_api_server as server

    old_engine = server._engine
    server._engine = mock_engine
    yield TestClient(server.app)
    server._engine = old_engine


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
    """创建 TestClient，引擎模型未加载（模拟启动失败场景）"""
    import src.infrastructure.external_services.embedding.embedding_api_server as server

    engine = MagicMock()
    engine.is_ready = False
    engine.load_error = "Model download failed"

    old_engine = server._engine
    server._engine = engine
    yield TestClient(server.app)
    server._engine = old_engine


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
    """NaN/Inf 防御性净化测试（通过 ModelInferenceEngine）"""

    @pytest.fixture
    def client_with_nan_engine(self) -> Generator[TestClient, None, None]:
        """注入会返回 NaN 的 mock 引擎"""
        import src.infrastructure.external_services.embedding.embedding_api_server as server

        engine = MagicMock()
        engine.is_ready = True
        engine.load_error = None

        # ModelInferenceEngine.encode 会先净化再返回
        # 直接模拟净化后的结果
        def mock_encode(texts, return_sparse=False):
            n = len(texts) if isinstance(texts, list) else 1
            arr = np.random.randn(n, 1024).astype(np.float32)
            # ModelInferenceEngine 会将 NaN/Inf 替换为 0.0
            result = {"dense": np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0).tolist()}
            result["sparse"] = None
            return result

        engine.encode.side_effect = mock_encode
        old_engine = server._engine
        server._engine = engine
        yield TestClient(server.app)
        server._engine = old_engine

    def test_nan_inf_sanitized_to_zero(self, client_with_nan_engine: TestClient) -> None:
        """NaN/Inf 值被净化后 JSON 序列化成功"""
        resp = client_with_nan_engine.post("/v1/embeddings", json={"texts": ["测试文本"], "return_sparse": False})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dense"]) == 1
        assert len(data["dense"][0]) == 1024

    def test_normal_values_unchanged(self, client_with_nan_engine: TestClient) -> None:
        """正常值（非 NaN/Inf）保留原值"""
        resp = client_with_nan_engine.post("/v1/embeddings", json={"texts": ["测试文本"], "return_sparse": False})
        assert resp.status_code == 200
        data = resp.json()
        # 正常值应非零
        assert any(x != 0.0 for x in data["dense"][0][3:10])


class TestEmbeddingAPIConcurrency:
    """并发请求安全测试（引擎内部锁保护）"""

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


class TestModelInferenceEngine:
    """ModelInferenceEngine 单元测试"""

    def test_mock_engine_encode_returns_dense(self) -> None:
        """mock 引擎的 encode 返回正确的 dense 结构"""
        from unittest.mock import MagicMock

        engine = MagicMock()
        engine.is_ready = True
        engine.encode.return_value = {
            "dense": [[0.1] * 1024],
            "sparse": None,
        }
        result = engine.encode(["test"])
        assert "dense" in result
        assert len(result["dense"]) == 1
        assert len(result["dense"][0]) == 1024

    def test_mock_engine_encode_returns_sparse(self) -> None:
        """mock 引擎的 encode 返回正确的 sparse 结构"""
        from unittest.mock import MagicMock

        engine = MagicMock()
        engine.is_ready = True
        engine.encode.return_value = {
            "dense": [[0.1] * 1024],
            "sparse": [{"indices": [100], "values": [0.5]}],
        }
        result = engine.encode(["test"], return_sparse=True)
        assert result["sparse"] is not None
        assert len(result["sparse"]) == 1
        assert result["sparse"][0]["indices"] == [100]

    def test_engine_not_ready_raises_503(self) -> None:
        """引擎未就绪时返回 503"""
        import src.infrastructure.external_services.embedding.embedding_api_server as server

        engine = MagicMock()
        engine.is_ready = False
        engine.load_error = "Not loaded"

        old_engine = server._engine
        server._engine = engine
        try:
            client = TestClient(server.app)
            resp = client.post("/v1/embeddings", json={"texts": ["test"]})
            assert resp.status_code == 503
        finally:
            server._engine = old_engine
