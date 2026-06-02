"""BGE3EmbeddingService 单元测试

验证 bge-m3 嵌入服务的 Dense 编码、Sparse 编码、归一化和配置解析。
使用 mock BGEM3FlagModel 避免 GPU 依赖。

迁移说明（2026-06-02）:
- mock 对象从 SentenceTransformer 迁移至 BGEM3FlagModel
- 新增 encode_sparse() 测试
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.infrastructure.config.embedding import EmbeddingConfig
from src.infrastructure.external_services.embedding.bge3_embedding_service import (
    BGE3EmbeddingService,
)


def _make_mock_model(dimension: int = 1024) -> MagicMock:
    """构造 mock BGEM3FlagModel

    模拟 encode() 方法返回 FlagEmbedding 格式的结果 dict：
    {"dense_vecs": np.array, "lexical_weights": [dict], "colbert_vecs": [...]}
    """
    model = MagicMock()

    def mock_encode(
        texts: str | list[str],
        return_dense: bool = False,
        return_sparse: bool = False,
        **kwargs: object,
    ) -> dict:
        result: dict[str, np.ndarray | list[dict[int, float]]] = {}
        if isinstance(texts, str):
            texts = [texts]

        if return_dense:
            vectors = []
            for _ in texts:
                v = np.random.randn(dimension).astype(np.float32)
                v = v / np.linalg.norm(v)  # L2 归一化
                vectors.append(v)
            result["dense_vecs"] = np.array(vectors) if len(vectors) > 1 else np.array(vectors[0])

        if return_sparse:
            # 模拟 BGE-M3 lexical_weights: 每个文本返回 Dict[int, float]
            lexical_list = []
            for _ in texts:
                lexical_list.append({100: 0.5, 200: 0.8, 300: 0.3})
            result["lexical_weights"] = lexical_list

        return result

    model.encode = MagicMock(side_effect=mock_encode)
    return model


class TestBGE3EmbeddingServiceInit:
    """BGE3EmbeddingService 初始化"""

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.os.path.isdir", return_value=True)
    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_init_with_model_path(self, mock_bgem3_cls, mock_isdir) -> None:
        """model_path 非空时从本地路径加载"""
        config = EmbeddingConfig(model_path="/fake/path", device="cpu")
        mock_bgem3_cls.return_value = _make_mock_model()

        BGE3EmbeddingService(config)
        mock_bgem3_cls.assert_called_once_with("/fake/path", use_fp16=False)

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_init_without_model_path(self, mock_bgem3_cls) -> None:
        """model_path 为空时从 HuggingFace Hub 加载"""
        config = EmbeddingConfig(model_path="", device="cuda")
        mock_bgem3_cls.return_value = _make_mock_model()

        BGE3EmbeddingService(config)
        mock_bgem3_cls.assert_called_once_with("BAAI/bge-m3", use_fp16=True)

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_init_default_config(self, mock_bgem3_cls) -> None:
        """默认配置初始化"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService()
        assert svc is not None

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_init_cpu_disables_fp16(self, mock_bgem3_cls) -> None:
        """CPU 设备时 use_fp16=False"""
        config = EmbeddingConfig(device="cpu")
        mock_bgem3_cls.return_value = _make_mock_model()

        BGE3EmbeddingService(config)
        mock_bgem3_cls.assert_called_once_with("BAAI/bge-m3", use_fp16=False)


class TestBGE3EmbeddingServiceEncodeDense:
    """BGE3EmbeddingService Dense 编码功能"""

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_text_returns_1024_dim(self, mock_bgem3_cls) -> None:
        """单文本编码返回 1024 维向量"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        result = svc.encode_text("测试文本")
        assert isinstance(result, list)
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_text_calls_with_return_dense(self, mock_bgem3_cls) -> None:
        """encode_text 调用 model.encode 并传递 return_dense=True"""
        mock_model = _make_mock_model()
        mock_bgem3_cls.return_value = mock_model

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        # 重置 mock 以排除 __init__ 中维度检查的调用
        mock_model.encode.reset_mock()
        svc.encode_text("测试文本")
        mock_model.encode.assert_called_once_with("测试文本", return_dense=True)

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_texts_batch(self, mock_bgem3_cls) -> None:
        """批量编码返回正确数量"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        texts = ["文本一", "文本二", "文本三"]
        result = svc.encode_texts(texts)
        assert isinstance(result, list)
        assert len(result) == 3
        for emb in result:
            assert len(emb) == 1024

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_texts_empty_list(self, mock_bgem3_cls) -> None:
        """空列表返回空列表"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        result = svc.encode_texts([])
        assert result == []

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_dimension_property(self, mock_bgem3_cls) -> None:
        """dimension 属性返回配置值"""
        mock_bgem3_cls.return_value = _make_mock_model(1024)

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        assert svc.dimension == 1024

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_text_empty_raises(self, mock_bgem3_cls) -> None:
        """空文本抛出 ValueError"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        with pytest.raises(ValueError, match="文本不能为空"):
            svc.encode_text("")

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_text_whitespace_raises(self, mock_bgem3_cls) -> None:
        """纯空白文本抛出 ValueError"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        with pytest.raises(ValueError, match="文本不能为空"):
            svc.encode_text("   ")

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_texts_raises_on_empty_string_in_list(self, mock_bgem3_cls) -> None:
        """批量编码中包含空文本时抛出 ValueError"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        with pytest.raises(ValueError, match="批量编码中包含空文本"):
            svc.encode_texts(["有效文本", "", "另一个有效文本"])

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_texts_raises_on_whitespace_only(self, mock_bgem3_cls) -> None:
        """批量编码中包含纯空白字符串时抛出 ValueError"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        with pytest.raises(ValueError, match="批量编码中包含空文本"):
            svc.encode_texts(["有效文本", "   ", "另一个有效文本"])

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_dimension_mismatch_raises(self, mock_bgem3_cls) -> None:
        """配置维度与模型实际维度不一致时抛出 ValueError"""
        mock_bgem3_cls.return_value = _make_mock_model(dimension=768)

        with pytest.raises(ValueError, match="配置维度.*与模型实际维度.*不一致"):
            BGE3EmbeddingService(EmbeddingConfig(dimension=1024, device="cpu"))


class TestBGE3EmbeddingServiceEncodeSparse:
    """BGE3EmbeddingService Sparse 编码功能（Story 3-1b 前置能力）"""

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_sparse_returns_dict_with_indices_and_values(self, mock_bgem3_cls) -> None:
        """encode_sparse 返回包含 indices 和 values 的 dict"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        result = svc.encode_sparse("测试文本")
        assert isinstance(result, dict)
        assert "indices" in result
        assert "values" in result
        assert isinstance(result["indices"], list)
        assert isinstance(result["values"], list)

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_sparse_indices_values_same_length(self, mock_bgem3_cls) -> None:
        """encode_sparse 的 indices 和 values 长度一致"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        result = svc.encode_sparse("测试文本")
        assert len(result["indices"]) == len(result["values"])

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_sparse_indices_sorted(self, mock_bgem3_cls) -> None:
        """encode_sparse 的 indices 按升序排列"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        result = svc.encode_sparse("测试文本")
        assert result["indices"] == sorted(result["indices"])

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_sparse_values_are_positive_float(self, mock_bgem3_cls) -> None:
        """encode_sparse 的 values 全为正浮点数"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        result = svc.encode_sparse("测试文本")
        for v in result["values"]:
            assert isinstance(v, float)
            assert v > 0  # BGE-M3 词汇权重为正

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_sparse_empty_text_raises(self, mock_bgem3_cls) -> None:
        """空文本抛出 ValueError"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        with pytest.raises(ValueError, match="文本不能为空"):
            svc.encode_sparse("")

    @patch("src.infrastructure.external_services.embedding.bge3_embedding_service.BGEM3FlagModel")
    def test_encode_sparse_whitespace_text_raises(self, mock_bgem3_cls) -> None:
        """纯空白文本抛出 ValueError"""
        mock_bgem3_cls.return_value = _make_mock_model()

        svc = BGE3EmbeddingService(EmbeddingConfig(device="cpu"))
        with pytest.raises(ValueError, match="文本不能为空"):
            svc.encode_sparse("   ")


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
