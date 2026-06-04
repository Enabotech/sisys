"""EmbeddingAPIClient 单元测试

验证 HTTP API 客户端的嵌入功能、错误处理和参数校验。
使用 mock httpx.Client 避免真实网络调用。
EmbeddingAPIClient 方法签名使用同步 def，测试无需 asyncio。
异常规范: sisys-uni-exception-design.md — 使用统一异常层次结构
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.domain.exceptions import (
    EmbeddingAPIError,
    EmbeddingResponseError,
    NetworkError,
    ServiceUnavailableError,
    TimeoutError,
)
from src.infrastructure.config.embedding import EmbeddingConfig
from src.infrastructure.external_services.embedding.embedding_api_client import (
    EmbeddingAPIClient,
)


def _fake_dense_response() -> dict:
    """构造 mock Dense 编码响应"""
    return {"dense": [[0.1] * 1024], "sparse": None}


def _fake_sparse_response() -> dict:
    """构造 mock Sparse 编码响应"""
    return {
        "dense": [[0.2] * 1024],
        "sparse": [{"indices": [100, 200, 300], "values": [0.5, 0.3, 0.2]}],
    }


def _make_mock_response(json_body: dict) -> MagicMock:
    """构造 mock httpx.Response"""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = json_body
    return resp


@pytest.fixture
def api_config() -> EmbeddingConfig:
    """API 模式 EmbeddingConfig"""
    return EmbeddingConfig(api_url="http://localhost:8000")


class TestEmbeddingAPIClientInit:
    """EmbeddingAPIClient 初始化"""

    def test_api_url_empty_raises(self) -> None:
        """api_url 为空时构造抛出 ValueError"""
        config = EmbeddingConfig(api_url="")
        with pytest.raises(ValueError, match="API 模式"):
            EmbeddingAPIClient(config)

    def test_init_with_api_url(self, api_config: EmbeddingConfig) -> None:
        """api_url 非空时正常初始化"""
        client = EmbeddingAPIClient(api_config)
        assert client is not None

    def test_dimension_property(self, api_config: EmbeddingConfig) -> None:
        """dimension 属性返回 1024"""
        client = EmbeddingAPIClient(api_config)
        assert client.dimension == 1024


class TestEmbeddingAPIClientEmbedQuery:
    """embed_query — 查询文本 Dense 嵌入（对标 LangChain embed_query）"""

    def test_embed_query_returns_1024_dim(self, api_config: EmbeddingConfig) -> None:
        """embed_query 返回 1024 维向量"""
        mock_resp = _make_mock_response(_fake_dense_response())

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            result = client.embed_query("测试文本")

            assert isinstance(result, list)
            assert len(result) == 1024
            assert all(isinstance(x, float) for x in result)

    def test_embed_query_sends_correct_payload(self, api_config: EmbeddingConfig) -> None:
        """embed_query 发送正确的请求体（单文本包装为列表）"""
        mock_resp = _make_mock_response(_fake_dense_response())

        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            client = EmbeddingAPIClient(api_config)
            client.embed_query("测试文本")

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["texts"] == ["测试文本"]
            assert call_kwargs["json"]["return_sparse"] is False


class TestEmbeddingAPIClientEmbedDocuments:
    """embed_documents — 文档批量 Dense 嵌入（对标 LangChain embed_documents）"""

    def test_embed_documents_batch(self, api_config: EmbeddingConfig) -> None:
        """embed_documents 批量编码返回正确数量"""
        batch_response = {
            "dense": [[0.1] * 1024, [0.2] * 1024, [0.3] * 1024],
            "sparse": None,
        }
        mock_resp = _make_mock_response(batch_response)

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            result = client.embed_documents(["文本一", "文本二", "文本三"])

            assert len(result) == 3
            for emb in result:
                assert len(emb) == 1024

    def test_embed_documents_empty_list(self, api_config: EmbeddingConfig) -> None:
        """空列表不发送 HTTP 请求"""
        with patch("httpx.Client.post") as mock_post:
            client = EmbeddingAPIClient(api_config)
            result = client.embed_documents([])
            assert result == []
            mock_post.assert_not_called()

    def test_embed_documents_mixed_invalid_raises(self, api_config: EmbeddingConfig) -> None:
        """批量中包含空文本时抛出 ValueError"""
        with patch("httpx.Client.post") as mock_post:
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(ValueError, match="文本列表"):
                client.embed_documents(["有效文本", "", "另一个有效文本"])
            mock_post.assert_not_called()

    def test_embed_documents_whitespace_item_raises(self, api_config: EmbeddingConfig) -> None:
        """批量中包含纯空白项时抛出 ValueError"""
        with patch("httpx.Client.post") as mock_post:
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(ValueError, match="文本列表"):
                client.embed_documents(["有效文本", "   "])
            mock_post.assert_not_called()


class TestEmbeddingAPIClientEmbedSparse:
    """embed_sparse — Sparse 词汇权重嵌入（批量化接口）"""

    def test_embed_sparse_returns_correct_format(self, api_config: EmbeddingConfig) -> None:
        """embed_sparse 返回 list[SparseEmbedding]"""
        mock_resp = _make_mock_response(_fake_sparse_response())

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            result = client.embed_sparse(["测试文本"])

            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], dict)
            assert result[0]["indices"] == [100, 200, 300]
            assert result[0]["values"] == [0.5, 0.3, 0.2]

    def test_embed_sparse_sends_return_sparse_true(self, api_config: EmbeddingConfig) -> None:
        """embed_sparse 发送 return_sparse=True"""
        mock_resp = _make_mock_response(_fake_sparse_response())

        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            client = EmbeddingAPIClient(api_config)
            client.embed_sparse(["测试文本"])

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["return_sparse"] is True

    def test_embed_sparse_empty_response_returns_empty_list(self, api_config: EmbeddingConfig) -> None:
        """API 返回空 sparse 列表时返回空 SparseEmbedding 列表"""
        mock_resp = _make_mock_response({"dense": [[0.1] * 1024], "sparse": []})

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            result = client.embed_sparse(["测试文本"])
            assert result == [{"indices": [], "values": []}]


class TestEmbeddingAPIClientValidation:
    """EmbeddingAPIClient 参数校验"""

    def test_embed_query_empty_raises(self, api_config: EmbeddingConfig) -> None:
        """空文本 embed_query 抛出 ValueError（不发送 HTTP）"""
        with patch("httpx.Client.post") as mock_post:
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(ValueError, match="文本不能为空"):
                client.embed_query("")
            mock_post.assert_not_called()

    def test_embed_query_whitespace_raises(self, api_config: EmbeddingConfig) -> None:
        """纯空白文本 embed_query 抛出 ValueError"""
        with patch("httpx.Client.post") as mock_post:
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(ValueError, match="文本不能为空"):
                client.embed_query("   ")
            mock_post.assert_not_called()

    def test_embed_sparse_empty_raises(self, api_config: EmbeddingConfig) -> None:
        """空文本 embed_sparse 抛出 ValueError"""
        with patch("httpx.Client.post") as mock_post:
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(ValueError, match="文本列表"):
                client.embed_sparse([""])
            mock_post.assert_not_called()


class TestEmbeddingAPIClientErrorHandling:
    """EmbeddingAPIClient 错误处理 — 统一异常体系"""

    def test_http_error_raises_embedding_api_error(self, api_config: EmbeddingConfig) -> None:
        """HTTP 5xx 包装为 EmbeddingAPIError (EXCEPTION_306)"""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_resp)

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(EmbeddingAPIError, match="HTTP 500"):
                client.embed_query("测试文本")

    def test_timeout_raises_timeout_error(self, api_config: EmbeddingConfig) -> None:
        """httpx.TimeoutException 包装为 TimeoutError (EXCEPTION_302)"""
        with patch("httpx.Client.post", side_effect=httpx.TimeoutException("timeout")):
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(TimeoutError, match="超时"):
                client.embed_query("测试文本")

    def test_network_error_raises_network_error(self, api_config: EmbeddingConfig) -> None:
        """httpx.NetworkError 包装为 NetworkError (EXCEPTION_102)"""
        with patch("httpx.Client.post", side_effect=httpx.NetworkError("connection refused")):
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(NetworkError, match="网络错误"):
                client.embed_query("测试文本")

    def test_invalid_json_raises_embedding_response_error(self, api_config: EmbeddingConfig) -> None:
        """响应 JSON 解析失败包装为 EmbeddingResponseError (EXCEPTION_307)"""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.side_effect = ValueError("Invalid JSON")

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(EmbeddingResponseError, match="响应格式异常"):
                client.embed_query("测试文本")

    def test_closed_client_raises_service_unavailable(self, api_config: EmbeddingConfig) -> None:
        """已关闭客户端调用抛出 ServiceUnavailableError (EXCEPTION_303)"""
        client = EmbeddingAPIClient(api_config)
        client.close()
        with pytest.raises(ServiceUnavailableError, match="已关闭"):
            client.embed_query("测试文本")
