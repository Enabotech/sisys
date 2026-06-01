"""BGE3EmbeddingService 单元测试

验证 bge-m3 嵌入服务的编码功能、归一化和配置解析
使用 mock SentenceTransformer 避免 GPU 依赖
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.infrastructure.config.embedding import EmbeddingConfig


def _make_mock_model(dimension: int = 1024) -> MagicMock:
    """构造 mock SentenceTransformer 模型"""
    model = MagicMock()
    model.get_sentence_embedding_dimension.return_value = dimension

    def mock_encode(texts, normalize_embeddings=False, **kwargs):
        if isinstance(texts, str):
            v = np.random.randn(dimension).astype(np.float32)
            if normalize_embeddings:
                v = v / np.linalg.norm(v)
            return v
        vectors = []
        for _ in texts:
            v = np.random.randn(dimension).astype(np.float32)
            if normalize_embeddings:
                v = v / np.linalg.norm(v)
            vectors.append(v)
        return np.array(vectors)

    model.encode = MagicMock(side_effect=mock_encode)
    return model


class TestBGE3EmbeddingServiceInit:
    """BGE3EmbeddingService 初始化"""

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.os.path.isdir", return_value=True)
    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_init_with_model_path(self, mock_st_cls, mock_isdir) -> None:
        """model_path 非空时从本地路径加载"""
        config = EmbeddingConfig(model_path="/fake/path", device="cpu")
        mock_st_cls.return_value = _make_mock_model()

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        BGE3EmbeddingService(config)
        mock_st_cls.assert_called_once_with("/fake/path", device="cpu")

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_init_without_model_path(self, mock_st_cls) -> None:
        """model_path 为空时从 HuggingFace Hub 加载"""
        config = EmbeddingConfig(model_path="", device="cuda")
        mock_st_cls.return_value = _make_mock_model()

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        BGE3EmbeddingService(config)
        mock_st_cls.assert_called_once_with("BAAI/bge-m3", device="cuda")

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_init_default_config(self, mock_st_cls) -> None:
        """默认配置初始化"""
        mock_st_cls.return_value = _make_mock_model()

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        svc = BGE3EmbeddingService()
        assert svc is not None


class TestBGE3EmbeddingServiceEncode:
    """BGE3EmbeddingService 编码功能"""

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_encode_text_returns_1024_dim(self, mock_st_cls) -> None:
        """单文本编码返回 1024 维向量"""
        mock_model = _make_mock_model()
        mock_st_cls.return_value = mock_model

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        result = svc.encode_text("测试文本")
        assert isinstance(result, list)
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_encode_text_normalizes(self, mock_st_cls) -> None:
        """encode_text 传递 normalize_embeddings=True"""
        mock_model = _make_mock_model()
        mock_st_cls.return_value = mock_model

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        svc.encode_text("测试文本")
        mock_model.encode.assert_called_once()
        call_kwargs = mock_model.encode.call_args
        assert call_kwargs[1].get("normalize_embeddings") is True or (
            len(call_kwargs[0]) > 1 and call_kwargs[0][1] if len(call_kwargs[0]) > 1 else False
        )

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_encode_texts_batch(self, mock_st_cls) -> None:
        """批量编码返回正确数量"""
        mock_model = _make_mock_model()
        mock_st_cls.return_value = mock_model

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        texts = ["文本一", "文本二", "文本三"]
        result = svc.encode_texts(texts)
        assert isinstance(result, list)
        assert len(result) == 3
        for emb in result:
            assert len(emb) == 1024

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_dimension_property(self, mock_st_cls) -> None:
        """dimension 属性返回正确值"""
        mock_model = _make_mock_model(1024)
        mock_st_cls.return_value = mock_model

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        assert svc.dimension == 1024

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_encode_text_empty_raises(self, mock_st_cls) -> None:
        """空文本抛出 ValueError"""
        mock_model = _make_mock_model()
        mock_st_cls.return_value = mock_model

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        with pytest.raises(ValueError, match="文本不能为空"):
            svc.encode_text("")

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_encode_texts_raises_on_empty_string_in_list(self, mock_st_cls) -> None:
        """批量编码中包含空文本时抛出 ValueError"""
        mock_model = _make_mock_model()
        mock_st_cls.return_value = mock_model

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        with pytest.raises(ValueError, match="批量编码中包含空文本"):
            svc.encode_texts(["有效文本", "", "另一个有效文本"])

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_encode_texts_raises_on_whitespace_only(self, mock_st_cls) -> None:
        """批量编码中包含纯空白字符串时抛出 ValueError"""
        mock_model = _make_mock_model()
        mock_st_cls.return_value = mock_model

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        with pytest.raises(ValueError, match="批量编码中包含空文本"):
            svc.encode_texts(["有效文本", "   ", "另一个有效文本"])

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.SentenceTransformer")
    def test_dimension_mismatch_raises(self, mock_st_cls) -> None:
        """配置维度与模型实际维度不一致时抛出 ValueError"""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_st_cls.return_value = mock_model

        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        with pytest.raises(ValueError, match="配置维度.*与模型实际维度.*不一致"):
            BGE3EmbeddingService(EmbeddingConfig(dimension=1024, device="cpu"))


class TestEmbeddingConfigFromEnv:
    """EmbeddingConfig.from_env() 配置解析"""

    def test_from_env_defaults(self) -> None:
        """默认值正确"""
        import os

        with patch.dict(os.environ, {}, clear=False):
            for key in ["EMBEDDING_MODEL_NAME", "EMBEDDING_MODEL_PATH", "EMBEDDING_MODEL_DEVICE", "EMBEDDING_MODEL_DIMENSION"]:
                os.environ.pop(key, None)
            config = EmbeddingConfig.from_env()
            assert config.model_name == "BAAI/bge-m3"
            assert config.model_path == ""
            assert config.device == "cuda"
            assert config.dimension == 1024

    def test_from_env_custom(self) -> None:
        """环境变量覆盖"""
        import os

        env = {
            "EMBEDDING_MODEL_NAME": "custom/model",
            "EMBEDDING_MODEL_PATH": "/custom/path",
            "EMBEDDING_MODEL_DEVICE": "cpu",
            "EMBEDDING_MODEL_DIMENSION": "768",
        }
        with patch.dict(os.environ, env, clear=False):
            config = EmbeddingConfig.from_env()
            assert config.model_name == "custom/model"
            assert config.model_path == "/custom/path"
            assert config.device == "cpu"
            assert config.dimension == 768
