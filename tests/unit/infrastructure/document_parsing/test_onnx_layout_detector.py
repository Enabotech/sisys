"""Story 2-3: OnnxLayoutDetector 单元测试

使用 mock onnxruntime.InferenceSession 验证 ONNX 版面检测器逻辑。
不依赖真实 ONNX 模型文件。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.domain.value_objects.parsed_document import BoundingBoxResult


class TestOnnxLayoutDetectorInit:
    """OnnxLayoutDetector 初始化测试"""

    def test_init_with_cpu_provider(self, tmp_path: Any) -> None:
        """验证 CPUExecutionProvider 初始化"""
        import importlib

        import src.infrastructure.document_parsing.onnx_layout_detector as mod

        if mod._ort is None:
            pytest.skip("onnxruntime 未安装，跳过 init 测试")

        model_path = str(tmp_path / "model.onnx")
        with open(model_path, "wb") as f:
            f.write(b"fake_onnx_model")

        mock_session = MagicMock()
        with patch.object(mod._ort, "InferenceSession", return_value=mock_session):
            # 重新导入模块使 _ort 引用生效
            importlib.reload(mod)
            detector = mod.OnnxLayoutDetector(model_path=model_path, device="cpu")
            assert detector._session is mock_session

    def test_init_with_gpu_provider(self, tmp_path: Any) -> None:
        """验证 CUDAExecutionProvider 初始化"""
        import importlib

        import src.infrastructure.document_parsing.onnx_layout_detector as mod

        if mod._ort is None:
            pytest.skip("onnxruntime 未安装，跳过 init 测试")

        model_path = str(tmp_path / "model.onnx")
        with open(model_path, "wb") as f:
            f.write(b"fake_onnx_model")

        mock_session = MagicMock()
        with patch.object(mod._ort, "InferenceSession", return_value=mock_session) as mock_cls:
            importlib.reload(mod)
            mod.OnnxLayoutDetector(model_path=model_path, device="cuda")
            call_args = mock_cls.call_args
            assert "CUDAExecutionProvider" in str(call_args)

    def test_init_model_file_not_found(self) -> None:
        """验证模型文件缺失时抛出 FileNotFoundError"""
        from src.infrastructure.document_parsing.onnx_layout_detector import OnnxLayoutDetector

        with pytest.raises(FileNotFoundError, match="版面检测模型文件"):
            OnnxLayoutDetector(model_path="/nonexistent/model.onnx")

    def test_init_onnxruntime_not_installed(self, tmp_path: Any) -> None:
        """验证 onnxruntime 缺失时抛出 ImportError"""
        model_path = str(tmp_path / "model.onnx")
        with open(model_path, "wb") as f:
            f.write(b"fake_onnx_model")

        import src.infrastructure.document_parsing.onnx_layout_detector as mod

        original_ort = mod._ort
        try:
            mod._ort = None
            # 重新导入使局部 import 触发 ImportError
            with patch.dict("sys.modules", {"onnxruntime": None}):
                with pytest.raises((ImportError, ModuleNotFoundError)):
                    from src.infrastructure.document_parsing.onnx_layout_detector import OnnxLayoutDetector

                    OnnxLayoutDetector(model_path=model_path)
        finally:
            mod._ort = original_ort


class TestOnnxLayoutDetectorDetect:
    """OnnxLayoutDetector.detect() 推理测试"""

    def _create_detector_with_mock(self) -> tuple[Any, MagicMock]:
        """创建使用 mock session 的检测器（绕过 __init__ 直接注入 mock session）"""
        import numpy as np

        from src.infrastructure.document_parsing.onnx_layout_detector import OnnxLayoutDetector

        mock_session = MagicMock()
        detector = OnnxLayoutDetector.__new__(OnnxLayoutDetector)
        detector._session = mock_session
        detector._label_map = {
            1: "Caption",
            2: "Footnote",
            3: "Formula",
            4: "List-item",
            5: "Page-footer",
            6: "Page-header",
            7: "Picture",
            8: "Section-header",
            9: "Table",
            10: "Text",
            11: "Title",
        }
        detector._confidence_threshold = 0.5
        # mock _preprocess 返回合法 numpy array，避免 PIL 解码失败
        # 通过 object.__setattr__ 设置 mock，绕过类型检查器对方法签名的严格校验
        object.__setattr__(
            detector,
            "_preprocess",
            MagicMock(return_value=np.zeros((1, 3, 640, 640), dtype=np.float32)),
        )
        return detector, mock_session

    def test_detect_single_element(self) -> None:
        """验证单元素检测：xyxy→xywh 转换"""
        detector, mock_session = self._create_detector_with_mock()
        # ONNX 输出 xyxy 格式：[x1, y1, x2, y2]
        mock_session.run.return_value = [
            [[10.0, 20.0, 110.0, 70.0]],  # boxes: 1 个检测框
            [10],  # labels: Text (index 10)
            [0.95],  # scores
        ]

        results = detector.detect(b"fake_image", page_number=1)

        assert len(results) == 1
        result = results[0]
        assert isinstance(result, BoundingBoxResult)
        assert result.label == "Text"
        assert result.confidence == 0.95
        # xyxy [10,20,110,70] → xywh (x=10, y=20, w=100, h=50)
        assert result.bbox.x == 10.0
        assert result.bbox.y == 20.0
        assert result.bbox.width == 100.0  # 110 - 10
        assert result.bbox.height == 50.0  # 70 - 20
        assert result.bbox.page == 1

    def test_detect_multiple_elements(self) -> None:
        """验证多元素检测"""
        detector, mock_session = self._create_detector_with_mock()
        mock_session.run.return_value = [
            [
                [0.0, 0.0, 600.0, 50.0],  # Title
                [50.0, 100.0, 550.0, 300.0],  # Text
            ],
            [11, 10],  # Title, Text
            [0.98, 0.92],
        ]

        results = detector.detect(b"fake_image", page_number=2)

        assert len(results) == 2
        assert results[0].label == "Title"
        assert results[0].bbox.page == 2
        assert results[1].label == "Text"
        assert results[1].bbox.page == 2

    def test_detect_empty_result(self) -> None:
        """验证空检测结果返回空列表"""
        detector, mock_session = self._create_detector_with_mock()
        mock_session.run.return_value = [
            [],
            [],
            [],
        ]

        results = detector.detect(b"blank_image", page_number=1)
        assert results == []

    def test_detect_confidence_range(self) -> None:
        """验证置信度在阈值之上的结果被保留"""
        detector, mock_session = self._create_detector_with_mock()
        mock_session.run.return_value = [
            [[0.0, 0.0, 100.0, 100.0]],
            [10],
            [0.5],  # 恰好在阈值边界（>0.5 不行，>= 0.5 通过）
        ]

        results = detector.detect(b"image", page_number=1)
        # confidence_threshold=0.5，score=0.5 恰好等于阈值，score < threshold 过滤
        # 所以 score=0.5 不通过（< 过滤），0.51 通过
        assert len(results) == 1
        assert results[0].confidence >= detector._confidence_threshold

    def test_detect_xyxy_to_xywh_conversion(self) -> None:
        """验证 xyxy→xywh 坐标转换：width=x2-x1, height=y2-y1"""
        detector, mock_session = self._create_detector_with_mock()
        mock_session.run.return_value = [
            [[50.5, 100.3, 250.7, 200.9]],
            [10],
            [0.88],
        ]

        results = detector.detect(b"image", page_number=3)
        bbox = results[0].bbox
        assert bbox.x == 50.5
        assert bbox.y == 100.3
        assert bbox.width == pytest.approx(200.2)  # 250.7 - 50.5
        assert bbox.height == pytest.approx(100.6)  # 200.9 - 100.3
        assert bbox.page == 3

    def test_detect_filters_low_confidence(self) -> None:
        """验证低于置信度阈值的检测被过滤"""
        detector, mock_session = self._create_detector_with_mock()
        mock_session.run.return_value = [
            [
                [0.0, 0.0, 100.0, 100.0],  # 高置信度
                [0.0, 0.0, 200.0, 200.0],  # 低置信度
            ],
            [10, 10],
            [0.95, 0.02],  # 一个高一个低
        ]

        results = detector.detect(b"image", page_number=1)
        # 默认阈值 0.5，0.02 应被过滤
        assert len(results) == 1
        assert results[0].confidence == 0.95

    def test_detect_inference_failure_raises(self) -> None:
        """验证推理失败时抛出 RuntimeError"""
        detector, mock_session = self._create_detector_with_mock()
        mock_session.run.side_effect = RuntimeError("ONNX inference error")

        with pytest.raises(RuntimeError, match="版面检测推理失败"):
            detector.detect(b"corrupt_image", page_number=1)
