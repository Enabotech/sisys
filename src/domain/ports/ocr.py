"""领域层 OCR 端口

定义 OCR 识别端口的 Protocol 接口，接收文件路径和页码列表，返回 OCR 识别结果。
实现类通过 HTTP 调用 PaddleOCR-VL 服务化 API 进行 OCR 识别。

置信度阈值常量定义在此文件，作为领域层契约的一部分。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.ocr_result import OCRPageResult

# OCR 置信度阈值：低于此值自动标记为"待人工复核"
# 与 AC-4 一致，使用 0.85 作为阈值
OCR_CONFIDENCE_THRESHOLD: float = 0.85

# OCR 最大文件大小：与 MAX_IMAGE_BYTES（50MB）对齐
# 超过此大小的文件跳过 OCR 步骤（基础解析不受影响）
OCR_MAX_BYTES: int = 50 * 1024 * 1024  # 50MB


@runtime_checkable
class OCRPort(Protocol):
    """OCR 识别端口协议

    统一的 OCR 识别接口，接收文件路径和可选的页码列表，
    返回指定页面的 OCR 识别结果列表。

    实现类（PaddleOCRVLAdapter）通过 HTTP 调用 PaddleOCR-VL 服务化 API，
    使用 httpx.AsyncClient 进行异步 HTTP 通信。

    Methods:
        recognize: 对指定文件执行 OCR 识别
    """

    async def recognize(
        self,
        file_path: str,
        page_numbers: list[int] | None = None,
    ) -> list[OCRPageResult]:
        """对指定文件执行 OCR 识别

        Args:
            file_path: 待识别文件的本地路径（PDF 或图像）
            page_numbers: 需要 OCR 的页码列表（1-indexed），
                None 表示对所有页面执行 OCR

        Returns:
            OCR 识别结果列表，每个元素对应一个页面的识别结果
        """
        ...


__all__ = [
    "OCRPort",
    "OCR_CONFIDENCE_THRESHOLD",
    "OCR_MAX_BYTES",
]
