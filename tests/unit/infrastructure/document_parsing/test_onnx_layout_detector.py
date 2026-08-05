"""Story 2-3: OnnxLayoutDetector 单元测试

使用 mock onnxruntime.InferenceSession 验证 ONNX 版面检测器逻辑。
不依赖真实 ONNX 模型文件。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.domain.exceptions import ValidationError
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
    """OnnxLayoutDetector.detect() 推理测试

    坐标已归一化到 [0, 1] 页面坐标空间（除以 _MODEL_INPUT_SIZE=640）。
    """

    # 归一化缩放因子
    _INPUT_SIZE = 640.0

    def _create_detector_with_mock(self) -> tuple[Any, MagicMock]:
        """创建使用 mock session 的检测器（绕过 __init__ 直接注入 mock session）"""
        import numpy as np

        from src.infrastructure.document_parsing.onnx_layout_detector import OnnxLayoutDetector

        mock_session = MagicMock()
        # mock get_inputs/get_outputs 返回值，支持动态输入/输出名发现
        mock_input = MagicMock()
        mock_input.name = "images"  # 模拟 docling-layout-heron-onnx 输入名
        mock_session.get_inputs.return_value = [mock_input]
        mock_output_box = MagicMock()
        mock_output_box.name = "boxes"
        mock_output_label = MagicMock()
        mock_output_label.name = "labels"
        mock_output_score = MagicMock()
        mock_output_score.name = "scores"
        mock_session.get_outputs.return_value = [mock_output_box, mock_output_label, mock_output_score]

        detector = OnnxLayoutDetector.__new__(OnnxLayoutDetector)
        detector._session = mock_session
        detector._input_name = "images"  # 动态发现的输入名
        detector._output_names = ["boxes", "labels", "scores"]  # 动态发现的输出名
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
        """验证单元素检测：xyxy→xywh→归一化 [0,1]"""
        detector, mock_session = self._create_detector_with_mock()
        s = self._INPUT_SIZE
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
        # xyxy [10,20,110,70] → xywh → /640: x=10/640, y=20/640, w=100/640, h=50/640
        assert result.bbox.x == pytest.approx(10.0 / s)
        assert result.bbox.y == pytest.approx(20.0 / s)
        assert result.bbox.width == pytest.approx(100.0 / s)  # (110-10)/640
        assert result.bbox.height == pytest.approx(50.0 / s)  # (70-20)/640
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
        """验证 xyxy→xywh→归一化 [0,1]：width=x2-x1, height=y2-y1，除以 640"""
        detector, mock_session = self._create_detector_with_mock()
        s = self._INPUT_SIZE
        mock_session.run.return_value = [
            [[50.5, 100.3, 250.7, 200.9]],
            [10],
            [0.88],
        ]

        results = detector.detect(b"image", page_number=3)
        bbox = results[0].bbox
        assert bbox.x == pytest.approx(50.5 / s)
        assert bbox.y == pytest.approx(100.3 / s)
        assert bbox.width == pytest.approx(200.2 / s)  # (250.7-50.5)/640
        assert bbox.height == pytest.approx(100.6 / s)  # (200.9-100.3)/640
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

    def test_detect_outputs_less_than_3_returns_empty(self) -> None:
        """验证 ONNX 输出张量不足 3 个时返回空列表（防御性处理）"""
        detector, mock_session = self._create_detector_with_mock()
        mock_session.run.return_value = [
            [[10.0, 20.0, 110.0, 70.0]],  # 仅有 boxes
            [10],  # 仅有 labels（缺少 scores）
        ]

        results = detector.detect(b"image", page_number=1)
        assert results == []

    def test_detect_unknown_label_index_generates_unknown_label(self) -> None:
        """验证不在 _label_map 中的 label index 生成 'Unknown-X' 标签"""
        detector, mock_session = self._create_detector_with_mock()
        mock_session.run.return_value = [
            [[10.0, 20.0, 110.0, 70.0]],
            [99],  # label index 99 不在 _label_map 中
            [0.95],
        ]

        results = detector.detect(b"image", page_number=1)
        assert len(results) == 1
        assert results[0].label == "Unknown-99"
        assert results[0].confidence == 0.95

    def test_detect_page_number_zero_raises_validation_error(self) -> None:
        """验证页码为 0 时抛出 ValidationError（1-indexed 约束）"""
        detector, _ = self._create_detector_with_mock()
        with pytest.raises(ValidationError, match="页码必须为正整数"):
            detector.detect(b"fake_image", page_number=0)

    def test_detect_negative_page_number_raises_validation_error(self) -> None:
        """验证负页码时抛出 ValidationError"""
        detector, _ = self._create_detector_with_mock()
        with pytest.raises(ValidationError, match="页码必须为正整数"):
            detector.detect(b"fake_image", page_number=-1)

    def test_detect_empty_image_bytes_raises_validation_error(self) -> None:
        """验证空图像字节时抛出 ValidationError"""
        detector, _ = self._create_detector_with_mock()
        with pytest.raises(ValidationError, match="image_bytes 不能为空"):
            detector.detect(b"", page_number=1)

    def test_detect_mismatched_output_lengths_truncates(self) -> None:
        """验证 ONNX 输出数组长度不一致时按最短截断（防御性校验）"""
        detector, mock_session = self._create_detector_with_mock()
        mock_session.run.return_value = [
            [[10.0, 20.0, 110.0, 70.0]],  # boxes: 1 个
            [10, 11],  # labels: 2 个（不一致）
            [0.95, 0.8],  # scores: 2 个（不一致）
        ]

        results = detector.detect(b"image", page_number=1)
        # min(1, 2, 2) = 1，只迭代第一个
        assert len(results) == 1
        assert results[0].label == "Text"

    def test_detect_inverted_coordinates_skipped(self) -> None:
        """验证 xyxy 坐标反转（x2<x1）时跳过该检测（防御性 clamp）"""
        detector, mock_session = self._create_detector_with_mock()
        s = self._INPUT_SIZE
        mock_session.run.return_value = [
            [
                [100.0, 200.0, 50.0, 150.0],  # x2<x1, y2<y1 → width=0, height=0
                [10.0, 20.0, 110.0, 70.0],  # 正常坐标
            ],
            [10, 10],
            [0.95, 0.8],
        ]

        results = detector.detect(b"image", page_number=1)
        # 第一个因 width=0 被跳过，只保留第二个
        assert len(results) == 1
        assert results[0].bbox.x == pytest.approx(10.0 / s)

    def test_close_releases_session(self) -> None:
        """验证 close() 释放 ONNX session 资源"""
        detector, mock_session = self._create_detector_with_mock()
        assert detector._session is not None
        detector.close()
        assert detector._session is None
