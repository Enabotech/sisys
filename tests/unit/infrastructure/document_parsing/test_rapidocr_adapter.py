"""RapidOCR 适配器单元测试。

使用可注入的 engine factory 和 PDF renderer 验证基础设施边界，
不下载模型、不依赖 GPU 或外部 OCR 服务。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.domain.exceptions.ocr_exceptions import OCRConnectionError, OCRProcessingError
from src.infrastructure.document_parsing.rapidocr_adapter import RapidOCRAdapter


class _FakeEngine:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.calls = 0

    def __call__(self, image: object) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(
            boxes=[[[10, 10], [90, 10], [90, 30], [10, 30]]],
            txts=("经营计划",),
            scores=(0.96,),
        )


class _FakeRenderer:
    def render_page(self, file_path: str, page_number: int) -> bytes:
        from io import BytesIO

        from PIL import Image

        stream = BytesIO()
        Image.new("RGB", (100, 50), "white").save(stream, format="PNG")
        return stream.getvalue()


def _engine_factory(created: list[_FakeEngine]):
    def factory(**kwargs: object) -> _FakeEngine:
        engine = _FakeEngine(**kwargs)
        created.append(engine)
        return engine

    return factory


@pytest.mark.asyncio
async def test_image_output_maps_text_confidence_and_normalized_bbox(tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    from PIL import Image

    Image.new("RGB", (100, 50), "white").save(image_path)
    created: list[_FakeEngine] = []
    adapter = RapidOCRAdapter(engine_factory=_engine_factory(created))

    results = await adapter.recognize(str(image_path))

    element = results[0].elements[0]
    assert element.content == "经营计划"
    assert element.confidence == 0.96
    assert element.bbox is not None
    assert element.bbox.to_dict() == {"x": 0.1, "y": 0.2, "width": 0.8, "height": 0.4, "page": 1}
    assert element.metadata["ocr_engine"] == "rapidocr"
    assert created[0].calls == 1


@pytest.mark.asyncio
async def test_engine_is_initialized_once(tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    from PIL import Image

    Image.new("RGB", (10, 10), "white").save(image_path)
    created: list[_FakeEngine] = []
    adapter = RapidOCRAdapter(engine_factory=_engine_factory(created))

    await adapter.recognize(str(image_path))
    await adapter.recognize(str(image_path))

    assert len(created) == 1
    assert created[0].calls == 2


@pytest.mark.asyncio
async def test_pdf_renders_all_pages_and_preserves_page_numbers(tmp_path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    with pdf_path.open("wb") as stream:
        writer.write(stream)
    created: list[_FakeEngine] = []
    adapter = RapidOCRAdapter(renderer=_FakeRenderer(), engine_factory=_engine_factory(created))

    results = await adapter.recognize(str(pdf_path))

    assert [result.page_number for result in results] == [1, 2]
    assert created[0].calls == 2


@pytest.mark.asyncio
async def test_invalid_engine_output_is_processing_error(tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    from PIL import Image

    Image.new("RGB", (10, 10), "white").save(image_path)

    class InvalidEngine:
        def __call__(self, image: object) -> object:
            return object()

    adapter = RapidOCRAdapter(engine_factory=InvalidEngine)
    with pytest.raises(OCRProcessingError):
        await adapter.recognize(str(image_path))


@pytest.mark.asyncio
async def test_engine_failure_is_connection_error(tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    from PIL import Image

    Image.new("RGB", (10, 10), "white").save(image_path)

    class FailingEngine:
        def __call__(self, image: object) -> object:
            raise RuntimeError("runtime unavailable")

    adapter = RapidOCRAdapter(engine_factory=FailingEngine)
    with pytest.raises(OCRConnectionError):
        await adapter.recognize(str(image_path))
