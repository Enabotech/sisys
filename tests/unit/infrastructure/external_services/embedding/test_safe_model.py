"""SafeBGE3Model 单元测试

验证线程安全 BGE-M3 模型包装器的正确行为。
SafeBGE3Model 不直接继承 BGEM3FlagModel，通过内部 _model 组合，
因此模块导入层级不触发 FlagEmbedding 加载（仅在 __init__ 实例化时触发）。
"""

from __future__ import annotations

import threading
from typing import cast
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.infrastructure.external_services.embedding.safe_model import SafeBGE3Model


def _make_model_instance() -> SafeBGE3Model:
    """构造一个不触发真实模型加载的 SafeBGE3Model 实例

    通过 patch 拦截 __init__ 中的 FlagEmbedding 导入，避免加载真实模型（~3 秒）。
    """
    m = SafeBGE3Model.__new__(SafeBGE3Model)
    # 模拟内部 _model（BGEM3FlagModel 实例）
    m._model = cast(MagicMock, MagicMock())
    m._model.target_devices = ["cuda:0"]
    m._model.model = MagicMock()
    m._model.model.to = MagicMock()
    m._model.model.eval = MagicMock()
    m._model.model.half = MagicMock()
    m._model.use_fp16 = False
    m._inference_lock = threading.Lock()
    m._device = "cuda:0"
    m._use_fp16 = False
    return m


class TestSafeBGE3ModelInit:
    """SafeBGE3Model 初始化（延迟加载 FlagEmbedding）"""

    def test_init_sets_use_fp16_false(self) -> None:
        """初始化后 _model.use_fp16 被设置为 False"""
        with patch("FlagEmbedding.BGEM3FlagModel") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.target_devices = ["cuda:0"]
            mock_cls.return_value = mock_instance

            model = SafeBGE3Model("/fake/path", use_fp16=True, device="cuda:0")
            assert model._model.use_fp16 is False

    def test_init_calls_half_when_use_fp16(self) -> None:
        """use_fp16=True 时初始化会调用 _model.model.half()"""
        with patch("FlagEmbedding.BGEM3FlagModel") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.target_devices = ["cuda:0"]
            mock_cls.return_value = mock_instance

            model = SafeBGE3Model("/fake/path", use_fp16=True, device="cuda:0")
            model._model.model.half.assert_called_once()

    def test_init_does_not_call_half_when_not_use_fp16(self) -> None:
        """use_fp16=False 时不会调用 _model.model.half()"""
        with patch("FlagEmbedding.BGEM3FlagModel") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.target_devices = ["cuda:0"]
            mock_cls.return_value = mock_instance

            model = SafeBGE3Model("/fake/path", use_fp16=False, device="cuda:0")
            model._model.model.half.assert_not_called()

    def test_init_calls_to_device_and_eval(self) -> None:
        """初始化会调用 _model.model.to(device) 和 _model.model.eval()"""
        with patch("FlagEmbedding.BGEM3FlagModel") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.target_devices = ["cuda:0"]
            mock_cls.return_value = mock_instance

            model = SafeBGE3Model("/fake/path", use_fp16=False, device="cuda:0")
            model._model.model.to.assert_called_once_with("cuda:0")
            model._model.model.eval.assert_called_once()

    def test_has_inference_lock(self) -> None:
        """初始化后存在 _inference_lock"""
        with patch("FlagEmbedding.BGEM3FlagModel") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.target_devices = ["cuda:0"]
            mock_cls.return_value = mock_instance

            model = SafeBGE3Model("/fake/path", use_fp16=False, device="cuda:0")
            assert isinstance(model._inference_lock, type(threading.Lock()))

    def test_module_import_does_not_trigger_flagembedding(self) -> None:
        """模块导入不触发 FlagEmbedding 加载（延迟导入机制）"""
        import sys

        mod = sys.modules.get("src.infrastructure.external_services.embedding.safe_model")
        assert mod is not None
        # 模块级不应包含 FlagEmbedding 引用
        assert "FlagEmbedding" not in dir(mod), "FlagEmbedding 不应在模块级导入"


class TestSafeBGE3ModelEncode:
    """SafeBGE3Model.encode 线程安全"""

    @pytest.fixture
    def model(self) -> SafeBGE3Model:
        """创建已初始化的 mock SafeBGE3Model 实例"""
        return _make_model_instance()

    def test_encode_returns_dense_vecs(self, model: SafeBGE3Model) -> None:
        """encode 返回包含 dense_vecs 的 dict"""
        mock_result = {"dense_vecs": np.random.randn(2, 1024).astype(np.float32)}
        model._model.encode.return_value = mock_result
        result = model.encode(["文本1", "文本2"], return_dense=True)
        assert "dense_vecs" in result
        assert len(result["dense_vecs"]) == 2

    def test_encode_uses_lock(self, model: SafeBGE3Model) -> None:
        """encode 使用锁保护，确保线程安全"""
        mock_lock = MagicMock()
        model._inference_lock = mock_lock
        model._model.encode.return_value = {"dense_vecs": np.random.randn(1, 1024).astype(np.float32)}
        model.encode(["test"], return_dense=True)
        mock_lock.__enter__.assert_called_once()

    def test_concurrent_encode_safe(self, model: SafeBGE3Model) -> None:
        """并发 encode 调用不抛出异常"""
        model._model.encode.return_value = {
            "dense_vecs": np.random.randn(1, 1024).astype(np.float32),
        }
        results = []
        errors = []

        def do_encode():
            try:
                r = model.encode(["测试"], return_dense=True)
                results.append(r)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=do_encode) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发异常: {errors}"
        assert len(results) == 10

    def test_encode_passes_kwargs_to_model(self, model: SafeBGE3Model) -> None:
        """encode 将参数传递给内部 _model.encode"""
        model._model.encode.return_value = {
            "dense_vecs": np.random.randn(1, 1024).astype(np.float32),
        }
        model.encode(["test"], return_dense=True, return_sparse=False, batch_size=64)
        model._model.encode.assert_called_once_with(
            ["test"],
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
            batch_size=64,
            max_length=8192,
        )


class TestModelInferenceEngine:
    """ModelInferenceEngine 单元测试"""

    @pytest.fixture
    def engine(self):
        """创建推理引擎实例（不加载真实模型）"""
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        eng = ModelInferenceEngine(
            model_path="/fake/path",
            device="cpu",
            use_fp16=False,
        )
        return eng

    def test_init_not_ready(self, engine) -> None:
        """未加载模型时不就绪"""
        assert not engine.is_ready
        assert engine.load_error is None

    def test_dimension_is_1024(self, engine) -> None:
        """dimension 返回 1024"""
        assert engine.dimension == 1024

    def test_encode_not_ready_raises(self, engine) -> None:
        """未加载模型时 encode 抛出 ModelInferenceError"""
        from src.domain.exceptions import ModelInferenceError

        with pytest.raises(ModelInferenceError, match="模型未加载"):
            engine.encode(["测试文本"])

    def test_encode_ready_returns_dense(self) -> None:
        """加载 mock 模型后 encode 返回正确结果"""
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        mock_model = MagicMock()
        mock_model.encode.return_value = {
            "dense_vecs": np.random.randn(2, 1024).astype(np.float32),
        }
        engine._model = mock_model
        engine._load_error = None

        result = engine.encode(["文本1", "文本2"])
        assert "dense" in result
        assert len(result["dense"]) == 2
        assert len(result["dense"][0]) == 1024
        assert result["sparse"] is None

    def test_encode_with_sparse(self) -> None:
        """return_sparse=True 时返回 sparse 权重"""
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        mock_model = MagicMock()
        mock_model.encode.return_value = {
            "dense_vecs": np.random.randn(1, 1024).astype(np.float32),
            "lexical_weights": [{"100": 0.5, "200": 0.3}],
        }
        engine._model = mock_model
        engine._load_error = None

        result = engine.encode(["测试文本"], return_sparse=True)
        assert result["sparse"] is not None
        assert len(result["sparse"]) == 1
        assert result["sparse"][0]["indices"] == [100, 200]
        assert result["sparse"][0]["values"] == [0.5, 0.3]

    def test_encode_model_raises(self) -> None:
        """模型推理抛出异常时包装为 ModelInferenceError"""
        from src.domain.exceptions import ModelInferenceError
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("GPU OOM")
        engine._model = mock_model
        engine._load_error = None

        with pytest.raises(ModelInferenceError, match="GPU OOM"):
            engine.encode(["测试文本"])

    def test_encode_missing_dense_vecs(self) -> None:
        """模型输出缺少 dense_vecs 时抛出 ModelInferenceError"""
        from src.domain.exceptions import ModelInferenceError
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        mock_model = MagicMock()
        mock_model.encode.return_value = {"wrong_key": "value"}
        engine._model = mock_model
        engine._load_error = None

        with pytest.raises(ModelInferenceError, match="缺少 'dense_vecs' 键"):
            engine.encode(["测试文本"])

    def test_encode_count_mismatch(self) -> None:
        """向量数与输入数不匹配时抛出 ModelInferenceError"""
        from src.domain.exceptions import ModelInferenceError
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        mock_model = MagicMock()
        mock_model.encode.return_value = {
            "dense_vecs": np.random.randn(1, 1024).astype(np.float32),
        }
        engine._model = mock_model
        engine._load_error = None

        with pytest.raises(ModelInferenceError, match="向量数不匹配"):
            engine.encode(["文本1", "文本2"])

    def test_load_twice_is_idempotent(self) -> None:
        """重复 load 是幂等的"""
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        engine._model = cast(SafeBGE3Model, MagicMock())
        engine._load_error = None
        engine.load()
        assert engine._model is not None

    def test_unload_clears_model(self) -> None:
        """unload 清除模型实例"""
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        engine._model = cast(SafeBGE3Model, MagicMock())
        engine._load_error = None
        engine.unload()
        assert engine._model is None

    def test_sanitize_dense_vectors_cleans_nan(self) -> None:
        """_sanitize_dense_vectors 将 NaN 替换为 0.0"""
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        arr = np.array([[np.nan, np.inf, 1.0, 2.0]], dtype=np.float32)
        result = engine._sanitize_dense_vectors(arr)
        assert result[0][0] == 0.0
        assert result[0][1] == 0.0
        assert result[0][2] == 1.0
        assert result[0][3] == 2.0

    def test_parse_sparse_weights_sorts_by_index(self) -> None:
        """_parse_sparse_weights 按 indices 升序排列"""
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        lexical_weights = [{"200": 0.3, "100": 0.5}]
        result = engine._parse_sparse_weights(lexical_weights)
        assert result[0]["indices"] == [100, 200]
        assert result[0]["values"] == [0.5, 0.3]

    def test_parse_sparse_weights_skips_invalid_keys(self) -> None:
        """_parse_sparse_weights 跳过非法 token ID"""
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        lexical_weights = [{"abc": 0.5, "100": 0.3}]
        result = engine._parse_sparse_weights(lexical_weights)
        assert result[0]["indices"] == [100]
        assert result[0]["values"] == [0.3]

    def test_parse_sparse_weights_empty_returns_empty(self) -> None:
        """空输入返回空列表"""
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        result = engine._parse_sparse_weights([])
        assert result == []


class TestModelInferenceEngineConcurrency:
    """ModelInferenceEngine 并发安全测试"""

    def test_concurrent_encode_returns_all_results(self) -> None:
        """并发 encode 调用正常返回所有结果"""
        from src.infrastructure.external_services.embedding.model_inference_engine import (
            ModelInferenceEngine,
        )

        engine = ModelInferenceEngine("/fake/path", device="cpu", use_fp16=False)
        mock_model = MagicMock()
        mock_model.encode.return_value = {
            "dense_vecs": np.random.randn(1, 1024).astype(np.float32),
        }
        engine._model = mock_model
        engine._load_error = None

        results = []
        errors = []

        def do_encode():
            try:
                r = engine.encode(["测试"])
                results.append(r)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=do_encode) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发异常: {errors}"
        assert len(results) == 10
        for r in results:
            assert "dense" in r
