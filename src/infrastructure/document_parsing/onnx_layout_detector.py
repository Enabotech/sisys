"""基础设施层 ONNX 版面检测器实现

基于 onnxruntime 的 DocLayNet 版面检测实现，封装模型加载、推理和后处理逻辑。
模型文件通过环境变量 SISYS_LAYOUT_MODEL_PATH 或构造函数参数指定。
"""

from __future__ import annotations

import logging
import os
from types import ModuleType
from typing import Any

from src.domain.exceptions import ValidationError
from src.domain.value_objects.parsed_document import BoundingBox, BoundingBoxResult

logger = logging.getLogger(__name__)

# 延迟导入 onnxruntime（仅在 __init__ 时检查可用性）
# 测试通过 patch 此属性模拟 onnxruntime 行为
_ort: ModuleType | None = None
try:
    import onnxruntime as _ort_impl

    _ort = _ort_impl
except ImportError:
    pass

# DocLayNet 11 类标签映射（index → label）
_DOCLAYNET_LABELS: dict[int, str] = {
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

# 默认置信度过滤阈值
_DEFAULT_CONFIDENCE_THRESHOLD = 0.5

# ONNX 模型输入尺寸（_preprocess 统一 resize 到此尺寸）
_MODEL_INPUT_SIZE = 640


class OnnxLayoutDetector:
    """基于 onnxruntime 的版面检测实现

    使用 Docling Layout ONNX 模型（docling-layout-heron-onnx）进行版面元素检测。
    支持 CPU（CPUExecutionProvider）和 GPU（CUDAExecutionProvider）推理。

    Args:
        model_path: ONNX 模型文件路径
        device: 推理设备，"cpu" 或 "cuda"
        confidence_threshold: 置信度过滤阈值，低于此值的结果被丢弃

    Raises:
        FileNotFoundError: 模型文件不存在
        ImportError: onnxruntime 未安装
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        """初始化 ONNX 推理会话

        Args:
            model_path: ONNX 模型文件路径
            device: 推理设备，"cpu" 或 "cuda"
            confidence_threshold: 置信度过滤阈值

        Raises:
            FileNotFoundError: 模型文件不存在
            ImportError: onnxruntime 未安装
        """
        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"版面检测模型文件不存在: {model_path}。"
                f"请下载 docling-layout-heron-onnx 模型: "
                f"https://huggingface.co/docling-project/docling-layout-heron-onnx"
            )

        if _ort is None:
            raise ImportError("onnxruntime 未安装。请执行: pip install onnxruntime")

        provider = "CUDAExecutionProvider" if device == "cuda" else "CPUExecutionProvider"
        logger.info("加载版面检测模型: %s (provider=%s)", model_path, provider)
        self._session = _ort.InferenceSession(model_path, providers=[provider])
        self._label_map = _DOCLAYNET_LABELS
        self._confidence_threshold = confidence_threshold

        # 动态发现输入/输出张量名称，避免硬编码不匹配真实模型
        self._input_name: str = self._session.get_inputs()[0].name
        self._output_names: list[str] = [o.name for o in self._session.get_outputs()]
        logger.info(
            "ONNX 模型输入: %s, 输出: %s",
            self._input_name,
            self._output_names,
        )

        # 记录原始图像尺寸（在 _preprocess 中设置），用于 Letterbox 归一化
        self._orig_width: int = 0
        self._orig_height: int = 0

    def close(self) -> None:
        """释放 ONNX InferenceSession 资源

        在 composition_root shutdown 时调用，显式释放模型权重和推理引擎资源。
        onnxruntime InferenceSession 没有标准 close() 方法，
        但通过删除引用允许 GC 回收内存。
        """
        if hasattr(self, "_session") and self._session is not None:
            logger.info("释放 ONNX 版面检测模型资源")
            self._session = None

    def detect(self, image_bytes: bytes, page_number: int) -> list[BoundingBoxResult]:
        """检测页面图像中的版面元素

        Args:
            image_bytes: 页面图像的二进制数据（PNG/JPEG 格式）
            page_number: 页码（用于填充 BoundingBox.page，1-indexed）

        Returns:
            检测到的版面元素列表（经过置信度过滤和坐标转换）

        Raises:
            ValidationError: page_number 不合法（< 1）或 image_bytes 为空
            RuntimeError: ONNX 推理失败
        """
        if page_number < 1:
            raise ValidationError(f"页码必须为正整数（1-indexed），实际值: {page_number}")
        if not image_bytes:
            raise ValidationError("image_bytes 不能为空")

        try:
            # 预处理：将图像字节转为 numpy array
            input_array = self._preprocess(image_bytes)
            outputs = self._session.run(None, {self._input_name: input_array})
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"版面检测推理失败: {e}") from e

        # 后处理：解析输出并转换为 BoundingBoxResult
        return self._postprocess(outputs, page_number)

    def _preprocess(self, image_bytes: bytes) -> Any:
        """预处理图像字节为模型输入格式（Letterbox 保持宽高比）

        将原始图像等比缩放至 _MODEL_INPUT_SIZE 边界内，剩余空间使用均值填充，
        避免直接拉伸导致宽高比失真。记录原始尺寸供 _postprocess 坐标反归一化使用。

        Args:
            image_bytes: 原始图像字节

        Returns:
            模型输入的 numpy array
        """
        import io

        import numpy as np
        from PIL import Image

        pil_image: Image.Image = Image.open(io.BytesIO(image_bytes))
        pil_image = pil_image.convert("RGB")
        self._orig_width, self._orig_height = pil_image.size

        # Letterbox: 等比缩放至 640 边界内，保持宽高比（避免拉伸失真）
        width, height = pil_image.size
        if width == 0 or height == 0:
            # 退化图像：直接缩放到目标尺寸
            pil_image = pil_image.resize((_MODEL_INPUT_SIZE, _MODEL_INPUT_SIZE))
        else:
            scale = min(_MODEL_INPUT_SIZE / width, _MODEL_INPUT_SIZE / height)
            new_w, new_h = max(1, round(width * scale)), max(1, round(height * scale))
            pil_image = pil_image.resize((new_w, new_h))

            # 创建均值填充画布并居中粘贴，保持输入尺寸恒定
            canvas = Image.new("RGB", (_MODEL_INPUT_SIZE, _MODEL_INPUT_SIZE), (114, 114, 114))
            offset_x = (_MODEL_INPUT_SIZE - new_w) // 2
            offset_y = (_MODEL_INPUT_SIZE - new_h) // 2
            canvas.paste(pil_image, (offset_x, offset_y))
            pil_image = canvas

        img_array = np.array(pil_image, dtype=np.float32) / 255.0
        # NCHW 格式: [1, 3, H, W]
        img_array = np.transpose(img_array, (2, 0, 1))
        img_array = np.expand_dims(img_array, axis=0)
        return img_array

    def _postprocess(self, outputs: list[Any], page_number: int) -> list[BoundingBoxResult]:
        """后处理模型输出，转换为 BoundingBoxResult 列表

        将 ONNX 输出的 xyxy 像素坐标转换为 BoundingBox 的 xywh 格式。

        坐标反归一化策略（Letterbox 反变换）：
        - 模型输出坐标位于 640x640 的填充画布坐标系
        - 需先裁剪掉填充偏移（offset_x/offset_y），再除以缩放比例 scale
        - 还原到原始图像像素坐标后，除以原始宽/高归一化到 [0, 1]
        该逻辑保证与 PDFParser 的 bbox 页面坐标空间一致，不受宽高比影响。

        Args:
            outputs: ONNX 模型原始输出 [boxes, labels, scores]
            page_number: 页码

        Returns:
            过滤后的 BoundingBoxResult 列表（坐标已归一化到 [0, 1]）
        """
        results: list[BoundingBoxResult] = []

        if len(outputs) < 3:
            return results

        boxes = outputs[0]
        labels = outputs[1]
        scores = outputs[2]

        # 防御性校验：确保三个输出数组长度一致
        n = min(len(boxes), len(labels), len(scores))
        if n != len(scores) and len(scores) > 0:
            logger.warning(
                "ONNX 输出数组长度不一致: boxes=%d, labels=%d, scores=%d，按最短数组截断",
                len(boxes),
                len(labels),
                len(scores),
            )

        # Letterbox 反变换参数（与 _preprocess 保持一致）
        orig_w = max(self._orig_width, 1)
        orig_h = max(self._orig_height, 1)
        scale = min(_MODEL_INPUT_SIZE / orig_w, _MODEL_INPUT_SIZE / orig_h)
        new_w = max(1, round(orig_w * scale))
        new_h = max(1, round(orig_h * scale))
        offset_x = (_MODEL_INPUT_SIZE - new_w) / 2.0
        offset_y = (_MODEL_INPUT_SIZE - new_h) / 2.0

        for i in range(n):
            score = float(scores[i])
            if score < self._confidence_threshold:
                continue

            box = boxes[i]
            x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])

            # Letterbox 反向映射到原始图像像素坐标
            x1_orig = (x1 - offset_x) / scale
            y1_orig = (y1 - offset_y) / scale
            x2_orig = (x2 - offset_x) / scale
            y2_orig = (y2 - offset_y) / scale

            # xyxy → xywh 转换，防御性 clamp 防止负值与越界
            width = max(0.0, x2_orig - x1_orig)
            height = max(0.0, y2_orig - y1_orig)
            if width == 0.0 or height == 0.0:
                logger.warning("检测坐标异常 (x1=%.2f, y1=%.2f, x2=%.2f, y2=%.2f)，跳过", x1, y1, x2, y2)
                continue

            # 归一化到 [0, 1] 页面坐标空间（与 PDFParser bbox 坐标系一致）
            bbox = BoundingBox(
                x=max(0.0, min(1.0, x1_orig / orig_w)),
                y=max(0.0, min(1.0, y1_orig / orig_h)),
                width=max(0.0, min(1.0, width / orig_w)),
                height=max(0.0, min(1.0, height / orig_h)),
                page=page_number,
            )

            label_idx = int(labels[i])
            label = self._label_map.get(label_idx, f"Unknown-{label_idx}")

            results.append(
                BoundingBoxResult(
                    label=label,
                    bbox=bbox,
                    confidence=score,
                )
            )

        logger.debug("页 %d: 检测到 %d 个版面元素（阈值 %.2f）", page_number, len(results), self._confidence_threshold)
        return results
