"""RapidOCR 本地适配器

将 RapidOCR 的同步图像推理封装为领域层的异步 OCRPort，
并通过 PDF 页面渲染端口支持扫描件 PDF。RapidOCR 只负责文字检测与识别，
版面分析、表格语义和公式理解由其他独立端口负责。
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import threading
from collections.abc import Callable
from typing import Any

from src.domain.exceptions.ocr_exceptions import OCRConnectionError, OCRProcessingError
from src.domain.ports.pdf_page_renderer import PdfPageRendererPort
from src.domain.value_objects.ocr_result import OCRPageResult
from src.domain.value_objects.parsed_document import BoundingBox, ParsedElement

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = ""
DEFAULT_MAX_CONCURRENCY = 1
DEFAULT_TEXT_SCORE = 0.5


class RapidOCRAdapter:
    """RapidOCR 本地推理适配器。

    模型按需初始化一次，并使用有界线程信号量保护同步推理。
    ``recognize`` 保持异步接口，避免阻塞应用事件循环。

    Args:
        model_dir: RapidOCR 模型目录；空值表示使用已配置的默认模型目录。
        max_concurrency: 同一适配器允许并发推理的最大数量。
        renderer: PDF 页面渲染端口；未提供时按需创建默认实现。
        engine_factory: 测试或部署场景使用的 RapidOCR 构造工厂。
    """

    def __init__(
        self,
        model_dir: str | None = None,
        max_concurrency: int | None = None,
        renderer: PdfPageRendererPort | None = None,
        engine_factory: Callable[..., Any] | None = None,
    ) -> None:
        config = self._load_config()
        self.model_dir = model_dir if model_dir is not None else config.model_dir
        configured_concurrency = max_concurrency if max_concurrency is not None else config.max_concurrency
        if configured_concurrency < 1:
            raise OCRProcessingError(message="RapidOCR 并发数必须为正整数")
        self.max_concurrency = configured_concurrency
        self._renderer = renderer
        self._engine_factory = engine_factory
        self._engine: Any | None = None
        self._engine_lock = threading.Lock()
        self._renderer_lock = threading.Lock()
        self._inference_slots = threading.BoundedSemaphore(configured_concurrency)

    @staticmethod
    def _load_config() -> Any:
        """加载 RapidOCR 配置，保持适配器可独立测试。"""
        from src.infrastructure.config.rapidocr import RapidOCRConfig

        return RapidOCRConfig.from_env()

    @staticmethod
    def _read_concurrency() -> int:
        """读取并校验并发配置。"""
        value = os.getenv("RAPIDOCR_MAX_CONCURRENCY", str(DEFAULT_MAX_CONCURRENCY))
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise OCRProcessingError(message="RAPIDOCR_MAX_CONCURRENCY 必须为整数", cause=exc) from exc

    async def recognize(
        self,
        file_path: str,
        page_numbers: list[int] | None = None,
    ) -> list[OCRPageResult]:
        """识别图像或 PDF 文件。

        Args:
            file_path: 本地图像或 PDF 路径。
            page_numbers: PDF 页码（1-indexed）；None 表示所有页面。

        Returns:
            按页面顺序排列的 OCR 结果。

        Raises:
            OCRConnectionError: 模型或运行时不可用。
            OCRProcessingError: 文件、渲染或结果处理失败。
        """
        if not os.path.isfile(file_path):
            raise OCRProcessingError(message="OCR 输入文件不存在")
        if os.path.splitext(file_path)[1].lower() == ".pdf":
            return await self._recognize_pdf(file_path, page_numbers)
        return [await self._recognize_image(file_path, 1)]

    async def _recognize_pdf(self, file_path: str, page_numbers: list[int] | None) -> list[OCRPageResult]:
        """逐页渲染并识别 PDF，保持页码和输入顺序。"""
        pages = self._resolve_pdf_pages(file_path, page_numbers)
        if not pages:
            return []
        results: list[OCRPageResult | BaseException] = []
        for page_number in pages:
            try:
                results.append(await self._recognize_pdf_page(file_path, page_number))
            except BaseException as exc:
                results.append(exc)

        failures: list[tuple[int, Exception]] = []
        successful: list[OCRPageResult] = []
        for page_number, result in zip(pages, results):
            if isinstance(result, Exception):
                failures.append((page_number, result))
            elif isinstance(result, OCRPageResult):
                successful.append(result)

        if failures:
            if successful:
                logger.warning("RapidOCR 部分页面处理失败: pages=%s", [page for page, _ in failures], exc_info=True)
                return successful
            error = failures[0][1]
            if isinstance(error, (OCRConnectionError, OCRProcessingError)):
                raise error
            raise OCRProcessingError(message="RapidOCR PDF 页面处理失败", cause=error) from error
        return successful

    @staticmethod
    def _resolve_pdf_pages(file_path: str, page_numbers: list[int] | None) -> list[int]:
        """读取 PDF 页数并规范化请求页码。"""
        try:
            from pypdf import PdfReader

            total_pages = len(PdfReader(file_path).pages)
        except Exception as exc:
            raise OCRProcessingError(message="无法读取 PDF 页面", cause=exc) from exc
        if page_numbers is None:
            return list(range(1, total_pages + 1))
        pages = sorted(set(page_numbers))
        if any(page < 1 or page > total_pages for page in pages):
            raise OCRProcessingError(message="OCR 请求页码超出 PDF 范围")
        return pages

    async def _recognize_pdf_page(self, file_path: str, page_number: int) -> OCRPageResult:
        """渲染并识别单个 PDF 页面。"""
        renderer = self._get_renderer()
        try:
            image_bytes = await asyncio.to_thread(renderer.render_page, file_path, page_number)
            return await self._recognize_image(image_bytes, page_number)
        except (OCRConnectionError, OCRProcessingError):
            raise
        except Exception as exc:
            raise OCRProcessingError(message=f"RapidOCR 第 {page_number} 页处理失败", cause=exc) from exc

    async def _recognize_image(self, source: str | bytes, page_number: int) -> OCRPageResult:
        """在线程池中执行单页同步推理。"""
        try:
            return await asyncio.to_thread(self._recognize_image_sync, source, page_number)
        except (OCRConnectionError, OCRProcessingError):
            raise
        except Exception as exc:
            raise OCRProcessingError(message="RapidOCR 图像处理失败", cause=exc) from exc

    def _recognize_image_sync(self, source: str | bytes, page_number: int) -> OCRPageResult:
        """加载图像并调用 RapidOCR。"""
        try:
            from PIL import Image
        except ImportError as exc:
            raise OCRProcessingError(message="图像运行时不可用，无法执行 RapidOCR", cause=exc) from exc

        try:
            image = Image.open(source if isinstance(source, str) else io.BytesIO(source))
            image.load()
            width, height = image.size
        except Exception as exc:
            raise OCRProcessingError(message="无法读取 OCR 图像", cause=exc) from exc

        engine = self._get_engine()
        try:
            with self._inference_slots:
                output = engine(image)
        except Exception as exc:
            raise OCRConnectionError(message="RapidOCR 推理运行时不可用", cause=exc) from exc
        return self._to_page_result(output, page_number, width, height)

    def _get_engine(self) -> Any:
        """初始化并缓存 RapidOCR 引擎。"""
        if self._engine is not None:
            return self._engine
        with self._engine_lock:
            if self._engine is not None:
                return self._engine
            try:
                if self.model_dir and not os.path.isdir(self.model_dir):
                    raise FileNotFoundError(self.model_dir)
                factory = self._engine_factory
                if factory is None:
                    from rapidocr import RapidOCR

                    factory = RapidOCR
                kwargs: dict[str, Any] = {}
                if self.model_dir:
                    kwargs["config_path"] = self.model_dir
                self._engine = factory(**kwargs)
            except ImportError as exc:
                raise OCRConnectionError(message="RapidOCR 运行时未安装", cause=exc) from exc
            except Exception as exc:
                raise OCRConnectionError(message="RapidOCR 模型初始化失败", cause=exc) from exc
        return self._engine

    async def close(self) -> None:
        """释放本地 OCR 资源。模型由进程管理，无需显式释放。"""

    async def __aenter__(self) -> RapidOCRAdapter:
        """进入异步上下文。"""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """退出异步上下文。"""
        await self.close()

    def _get_renderer(self) -> PdfPageRendererPort:
        """按需创建 PDF 渲染器。"""
        if self._renderer is None:
            with self._renderer_lock:
                if self._renderer is None:
                    try:
                        from src.infrastructure.document_parsing.pdf_page_renderer import PdfPageRenderer

                        self._renderer = PdfPageRenderer()
                    except Exception as exc:
                        raise OCRProcessingError(message="PDF 页面渲染器不可用", cause=exc) from exc
        return self._renderer

    def _to_page_result(self, output: Any, page_number: int, width: int, height: int) -> OCRPageResult:
        """将 RapidOCR 输出映射为领域页结果。"""
        boxes, texts, scores = self._extract_output(output)
        elements: list[ParsedElement] = []
        for index, text in enumerate(texts):
            content = str(text).strip()
            if not content:
                continue
            score = scores[index] if index < len(scores) else DEFAULT_TEXT_SCORE
            confidence = self._normalize_score(score)
            metadata: dict[str, Any] = {"ocr_engine": "rapidocr"}
            if index < len(boxes):
                polygon = self._normalize_polygon(boxes[index])
                if polygon:
                    metadata["ocr_polygon"] = polygon
                    metadata["ocr_coordinate_system"] = "pixel"
                    metadata["ocr_image_size"] = {"width": width, "height": height}
                    bbox = self._polygon_to_bbox(polygon, page_number, width, height)
                else:
                    bbox = None
            else:
                bbox = None
            elements.append(ParsedElement(content=content, bbox=bbox, confidence=confidence, metadata=metadata))
        return OCRPageResult(
            page_number=page_number,
            elements=elements,
            raw_response={"engine": "rapidocr", "element_count": len(elements)},
        )

    @staticmethod
    def _extract_output(output: Any) -> tuple[list[Any], list[Any], list[Any]]:
        """读取新旧 RapidOCR 返回结构。"""
        if output is None:
            return [], [], []
        if hasattr(output, "boxes"):
            return (
                list(output.boxes or []),
                list(output.txts or []),
                list(output.scores or []),
            )
        if isinstance(output, (tuple, list)):
            boxes: list[Any] = []
            texts: list[Any] = []
            scores: list[Any] = []
            for item in output:
                if not isinstance(item, (tuple, list)) or len(item) < 2:
                    continue
                boxes.append(item[0])
                texts.append(item[1])
                scores.append(item[2] if len(item) > 2 else DEFAULT_TEXT_SCORE)
            return boxes, texts, scores
        raise OCRProcessingError(message="RapidOCR 返回结果格式无效")

    @staticmethod
    def _normalize_score(score: Any) -> float:
        """将置信度限制在领域契约值域。"""
        try:
            value = float(score)
        except (TypeError, ValueError):
            value = DEFAULT_TEXT_SCORE
        return round(max(0.0, min(1.0, value)), 4)

    @staticmethod
    def _normalize_polygon(box: Any) -> list[list[float]] | None:
        """校验并复制检测框多边形，不假设固定点数。"""
        try:
            points = [[float(point[0]), float(point[1])] for point in box if len(point) >= 2]
        except (TypeError, ValueError, IndexError):
            return None
        return points if len(points) >= 3 else None

    @staticmethod
    def _polygon_to_bbox(polygon: list[list[float]], page_number: int, width: int, height: int) -> BoundingBox:
        """将像素多边形转换为项目使用的归一化边界框。"""
        xs = [point[0] for point in polygon]
        ys = [point[1] for point in polygon]
        x_min, x_max = max(0.0, min(xs)), min(float(width), max(xs))
        y_min, y_max = max(0.0, min(ys)), min(float(height), max(ys))
        return BoundingBox(
            x=x_min / width if width else 0.0,
            y=y_min / height if height else 0.0,
            width=max(0.0, x_max - x_min) / width if width else 0.0,
            height=max(0.0, y_max - y_min) / height if height else 0.0,
            page=page_number,
        )


__all__ = ["RapidOCRAdapter", "DEFAULT_MODEL_DIR", "DEFAULT_MAX_CONCURRENCY"]
