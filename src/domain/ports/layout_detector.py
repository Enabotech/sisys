"""领域层 版面检测端口

定义版面检测器的 Protocol 接口，接收页面图像字节并返回 DocLayNet 标准格式的检测结果。
实现类通过 ONNX Runtime 加载 Docling Layout 模型进行推理。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.parsed_document import BoundingBoxResult


@runtime_checkable
class LayoutDetector(Protocol):
    """版面检测端口协议

    统一的版面检测接口，接收页面图像字节数据，返回检测到的版面元素列表。
    每个检测结果包含 DocLayNet 11 类标签、边界框坐标和检测置信度。
    页码信息通过 page_number 参数传入，由实现写入 BoundingBox.page 字段。

    Methods:
        detect: 检测页面图像中的版面元素
    """

    def detect(self, image_bytes: bytes, page_number: int) -> list[BoundingBoxResult]:
        """检测页面图像中的版面元素

        Args:
            image_bytes: 页面图像的二进制数据（PNG/JPEG 格式）
            page_number: 页码（用于填充 BoundingBox.page，1-indexed）

        Returns:
            检测到的版面元素列表（DocLayNet 11 类标签）
        """
        ...
