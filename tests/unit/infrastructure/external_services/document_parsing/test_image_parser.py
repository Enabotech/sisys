"""图像文档解析器单元测试

TDD 红阶段：测试 ImageParser 的元数据提取、OCR 文本、GIF 第一帧、Tesseract 降级。
使用 Pillow 创建 fixture 图像文件。
"""

from __future__ import annotations

import os
import tempfile


def _create_image_file(fmt: str = "JPEG", size: tuple[int, int] = (100, 100)) -> str:
    """创建图像 fixture"""
    from PIL import Image

    ext = "jpg" if fmt.upper() == "JPEG" else fmt.lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
    img = Image.new("RGB", size, color="red")
    img.save(tmp.name, format=fmt)
    tmp.close()
    return tmp.name


def _create_gif_file() -> str:
    """创建多帧 GIF fixture"""
    from PIL import Image

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".gif")
    frame1 = Image.new("RGB", (100, 100), color="red")
    frame2 = Image.new("RGB", (100, 100), color="blue")
    frame1.save(tmp.name, format="GIF", save_all=True, append_images=[frame2], loop=0)
    tmp.close()
    return tmp.name


class TestImageParserCreation:
    """ImageParser 构造和基本功能测试"""

    def test_create_parser(self) -> None:
        from src.infrastructure.external_services.document_parsing.image_parser import ImageParser

        assert ImageParser() is not None

    def test_parser_implements_document_parser_port(self) -> None:
        from src.domain.ports.document_parser import DocumentParserPort
        from src.infrastructure.external_services.document_parsing.image_parser import ImageParser

        assert isinstance(ImageParser(), DocumentParserPort)


class TestImageParserMetadata:
    """图像元数据提取测试"""

    def test_parse_jpeg_metadata(self) -> None:
        """JPEG 元数据提取（format/size/mode）"""
        from src.infrastructure.external_services.document_parsing.image_parser import ImageParser

        path = _create_image_file("JPEG", (200, 150))
        try:
            parser = ImageParser()
            result = parser.parse(path, "image/jpeg")

            assert result.is_completed()
            images = [i for p in result.pages for i in p.images]
            assert len(images) == 1

            img_meta = images[0].metadata
            assert img_meta.get("format") == "JPEG"
            assert img_meta.get("width") == 200
            assert img_meta.get("height") == 150
            assert img_meta.get("mode") == "RGB"
            assert images[0].content == "", "image content 应为空字符串"
        finally:
            os.unlink(path)

    def test_parse_png_metadata(self) -> None:
        """PNG 元数据提取"""
        from src.infrastructure.external_services.document_parsing.image_parser import ImageParser

        path = _create_image_file("PNG")
        try:
            parser = ImageParser()
            result = parser.parse(path, "image/png")

            assert result.is_completed()
            images = [i for p in result.pages for i in p.images]
            assert len(images) == 1
            assert images[0].metadata["format"] == "PNG"
        finally:
            os.unlink(path)


class TestImageParserGif:
    """GIF 处理测试"""

    def test_gif_first_frame_only(self) -> None:
        """GIF 仅处理第一帧"""
        from src.infrastructure.external_services.document_parsing.image_parser import ImageParser

        path = _create_gif_file()
        try:
            parser = ImageParser()
            result = parser.parse(path, "image/gif")

            assert result.is_completed()
            images = [i for p in result.pages for i in p.images]
            assert len(images) == 1, f"GIF 应仅处理第一帧，实际 frames: {len(images)}"
        finally:
            os.unlink(path)


class TestImageParserTesseractFallback:
    """Tesseract 降级测试"""

    def test_tesseract_unavailable_graceful_degradation(self) -> None:
        """Tesseract 不可用时优雅降级，仅返回元数据"""
        from unittest import mock

        from src.infrastructure.external_services.document_parsing.image_parser import ImageParser

        path = _create_image_file("PNG")
        try:
            parser = ImageParser()
            with mock.patch("pytesseract.image_to_string", side_effect=ImportError("tesseract not installed")):
                result = parser.parse(path, "image/png")

            assert result.is_completed(), "即使 OCR 不可用，仍应返回元数据"
            images = [i for p in result.pages for i in p.images]
            assert len(images) >= 1, "即使 OCR 不可用，应在 images 中返回元数据"
        finally:
            os.unlink(path)
