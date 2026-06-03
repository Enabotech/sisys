"""EmbeddingAPIClient 单元测试

验证 HTTP API 客户端的编码功能、错误处理和参数校验。
使用 mock httpx.Client 避免真实网络调用。
EmbeddingAPIClient 方法签名使用同步 def，测试无需 asyncio。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

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
    return EmbeddingConfig(api_url="http://localhost:8000", device="cpu")


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
        """dimension 属性返回 config.dimension"""
        client = EmbeddingAPIClient(api_config)
        assert client.dimension == 1024


class TestEmbeddingAPIClientEncodeDense:
    """EmbeddingAPIClient Dense 编码（同步方法，patch httpx.Client.post）"""

    def test_encode_text_returns_1024_dim(self, api_config: EmbeddingConfig) -> None:
        """encode_text 返回 1024 维向量"""
        mock_resp = _make_mock_response(_fake_dense_response())

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            result = client.encode_text("测试文本")

            assert isinstance(result, list)
            assert len(result) == 1024
            assert all(isinstance(x, float) for x in result)

    def test_encode_text_sends_correct_payload(self, api_config: EmbeddingConfig) -> None:
        """encode_text 发送正确的请求体"""
        mock_resp = _make_mock_response(_fake_dense_response())

        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            client = EmbeddingAPIClient(api_config)
            client.encode_text("测试文本")

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["texts"] == ["测试文本"]
            assert call_kwargs["json"]["return_sparse"] is False

    def test_encode_texts_batch(self, api_config: EmbeddingConfig) -> None:
        """encode_texts 批量编码返回正确数量"""
        batch_response = {
            "dense": [[0.1] * 1024, [0.2] * 1024, [0.3] * 1024],
            "sparse": None,
        }
        mock_resp = _make_mock_response(batch_response)

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            result = client.encode_texts(["文本一", "文本二", "文本三"])

            assert len(result) == 3
            for emb in result:
                assert len(emb) == 1024

    def test_encode_texts_empty_list(self, api_config: EmbeddingConfig) -> None:
        """空列表不发送 HTTP 请求"""
        with patch("httpx.Client.post") as mock_post:
            client = EmbeddingAPIClient(api_config)
            result = client.encode_texts([])
            assert result == []
            mock_post.assert_not_called()


class TestEmbeddingAPIClientEncodeSparse:
    """EmbeddingAPIClient Sparse 编码"""

    def test_encode_sparse_returns_correct_format(self, api_config: EmbeddingConfig) -> None:
        """encode_sparse 返回 indices/values dict"""
        mock_resp = _make_mock_response(_fake_sparse_response())

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            result = client.encode_sparse("测试文本")

            assert isinstance(result, dict)
            assert "indices" in result
            assert "values" in result
            assert result["indices"] == [100, 200, 300]
            assert result["values"] == [0.5, 0.3, 0.2]

    def test_encode_sparse_sends_return_sparse_true(self, api_config: EmbeddingConfig) -> None:
        """encode_sparse 发送 return_sparse=True"""
        mock_resp = _make_mock_response(_fake_sparse_response())

        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            client = EmbeddingAPIClient(api_config)
            client.encode_sparse("测试文本")

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["return_sparse"] is True

    def test_encode_sparse_empty_response_returns_empty(self, api_config: EmbeddingConfig) -> None:
        """API 返回空 sparse 列表时返回空 dict"""
        mock_resp = _make_mock_response({"dense": [[0.1] * 1024], "sparse": []})

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            result = client.encode_sparse("测试文本")
            assert result == {"indices": [], "values": []}


class TestEmbeddingAPIClientValidation:
    """EmbeddingAPIClient 参数校验"""

    def test_encode_text_empty_raises(self, api_config: EmbeddingConfig) -> None:
        """空文本抛出 ValueError（不发送 HTTP）"""
        with patch("httpx.Client.post") as mock_post:
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(ValueError, match="文本不能为空"):
                client.encode_text("")
            mock_post.assert_not_called()

    def test_encode_text_whitespace_raises(self, api_config: EmbeddingConfig) -> None:
        """纯空白文本抛出 ValueError"""
        with patch("httpx.Client.post") as mock_post:
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(ValueError, match="文本不能为空"):
                client.encode_text("   ")
            mock_post.assert_not_called()

    def test_encode_sparse_empty_raises(self, api_config: EmbeddingConfig) -> None:
        """空文本 encode_sparse 抛出 ValueError"""
        with patch("httpx.Client.post") as mock_post:
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(ValueError, match="文本不能为空"):
                client.encode_sparse("")
            mock_post.assert_not_called()


class TestEmbeddingAPIClientErrorHandling:
    """EmbeddingAPIClient 错误处理"""

    def test_http_error_propagates(self, api_config: EmbeddingConfig) -> None:
        """HTTP 5xx 异常传播"""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_resp)

        with patch("httpx.Client.post", return_value=mock_resp):
            client = EmbeddingAPIClient(api_config)
            with pytest.raises(httpx.HTTPStatusError):
                client.encode_text("测试文本")
