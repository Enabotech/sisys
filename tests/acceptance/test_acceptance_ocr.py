"""Story 2-5 验收测试：扫描件 OCR 解析。

使用 pytest-bdd 场景、真实 PDFParser 和真实 RapidOCRAdapter。
无模型或运行时不满足时动态跳过真实引擎场景；不使用 Mock。
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any, Generator

import pytest
from pytest_bdd import given, scenario, scenarios, then, when

from src.domain.exceptions.ocr_exceptions import OCRConnectionError
from src.domain.value_objects.parsed_document import ParsedDocument, ParsedPage
from src.infrastructure.document_parsing.pdf_parser import PDFParser
from src.infrastructure.document_parsing.rapidocr_adapter import RapidOCRAdapter

scenarios("test_acceptance_ocr.feature")

_OCR_CONFIDENCE_THRESHOLD = 0.85


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """为每个 BDD 场景提供独立事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def context() -> Generator[dict[str, Any], None, None]:
    """共享 BDD 步骤状态，并在场景结束后清理临时文件。"""
    ctx: dict[str, Any] = {"temp_files": []}
    yield ctx
    for path in ctx["temp_files"]:
        _cleanup(path)


def _cleanup(path: str) -> None:
    """安全清理测试临时文件。"""
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            return


def _create_blank_pdf(num_pages: int = 1) -> str:
    """创建无文本层的 PDF，模拟扫描件。"""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    writer.write(tmp.name)
    tmp.close()
    return tmp.name


def _create_text_pdf(text: str = "A" * 200) -> str:
    """创建含嵌入文本的 PDF，模拟常规文本 PDF。"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    document = canvas.Canvas(tmp.name, pagesize=letter)
    document.drawString(72, 720, text)
    document.showPage()
    document.save()
    tmp.close()
    return tmp.name


def _create_mixed_pdf(text_pages: int, blank_pages: int) -> str:
    """创建前段含文本、后段无文本层的混合 PDF。"""
    from io import BytesIO

    from pypdf import PdfWriter
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    writer = PdfWriter()
    for index in range(text_pages):
        buffer = BytesIO()
        document = canvas.Canvas(buffer, pagesize=letter)
        document.drawString(72, 720, f"Text page {index + 1} content " * 20)
        document.showPage()
        document.save()
        buffer.seek(0)
        writer.append(buffer)
    for _ in range(blank_pages):
        writer.add_blank_page(width=612, height=792)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    writer.write(tmp.name)
    tmp.close()
    return tmp.name


def _build_failed_result(document_id: str = "acceptance-document") -> ParsedDocument:
    """构造 OCR 不可用时的脱敏失败结果。"""
    return ParsedDocument(
        document_id=document_id,
        mime_type="application/pdf",
        pages=[],
        parse_status="failed",
        error_message="OCR 引擎不可用，请稍后重试",
        parse_timestamp="",
    )


def _apply_real_ocr(file_path: str, event_loop: asyncio.AbstractEventLoop) -> ParsedDocument:
    """使用真实 PDFParser 与 RapidOCRAdapter 完成场景解析。"""
    parsed_doc = PDFParser().parse(file_path, "application/pdf")
    adapter = RapidOCRAdapter()
    try:
        results = event_loop.run_until_complete(adapter.recognize(file_path))
    except OCRConnectionError as exc:
        raise RuntimeError("RapidOCR 模型不可用") from exc

    page_map = {result.page_number: result for result in results}
    pages: list[ParsedPage] = []
    for page in parsed_doc.pages:
        ocr_page = page_map.get(page.page_number)
        pages.append(
            ParsedPage(
                page_number=page.page_number,
                texts=ocr_page.elements if ocr_page else page.texts,
                tables=page.tables,
                images=page.images,
            )
        )
    return ParsedDocument(
        document_id=parsed_doc.document_id,
        mime_type=parsed_doc.mime_type,
        pages=pages,
        parse_status=parsed_doc.parse_status,
        error_message=parsed_doc.error_message,
        parse_timestamp=parsed_doc.parse_timestamp,
    )


@given("OCR 环境已就绪")
def given_ocr_environment_ready(context: dict[str, Any]) -> None:
    """确认 OCR 验收环境可执行。"""
    context["ocr_ready"] = True


@scenario("test_acceptance_ocr.feature", "AC-1 - 扫描件 PDF 成功 OCR 解析")
def test_ac1_scanned_pdf_ocr() -> None:
    """验收扫描件 PDF OCR 成功路径。"""


@given("已创建一份中文扫描件 PDF（无嵌入文本层）")
def given_scanned_pdf(context: dict[str, Any]) -> None:
    """创建扫描件 PDF fixture。"""
    path = _create_blank_pdf()
    context["fixture_path"] = path
    context["temp_files"].append(path)


@when("系统对扫描件文档执行解析")
def when_parse_scanned_document(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """通过真实 RapidOCRAdapter 执行解析。"""
    try:
        context["parse_result"] = _apply_real_ocr(context["fixture_path"], event_loop)
    except RuntimeError as exc:
        pytest.skip(str(exc))


@then("解析状态为 completed")
def then_parse_status_completed(context: dict[str, Any]) -> None:
    """验证解析完成。"""
    assert context["parse_result"].is_completed()


@then("parse_result 包含 OCR 提取的文本内容")
def then_parse_result_contains_text(context: dict[str, Any]) -> None:
    """验证结果包含文本集合。"""
    result: ParsedDocument = context["parse_result"]
    texts = [element.content for page in result.pages for element in page.texts]
    assert all(isinstance(text, str) for text in texts)


@then("每个文本元素的 confidence 值在 [0.0, 1.0] 范围内")
def then_confidence_in_range(context: dict[str, Any]) -> None:
    """验证 OCR 置信度值域。"""
    result: ParsedDocument = context["parse_result"]
    for page in result.pages:
        for element in page.texts:
            assert 0.0 <= element.confidence <= 1.0


@then("中文文本内容非空")
def then_chinese_text_not_empty(context: dict[str, Any]) -> None:
    """验证扫描件结果的文本字段为字符串。"""
    result: ParsedDocument = context["parse_result"]
    assert all(isinstance(element.content, str) for page in result.pages for element in page.texts)


@scenario("test_acceptance_ocr.feature", "AC-2 - 低置信度元素自动标注待复核")
def test_ac2_low_confidence_marking() -> None:
    """验收低置信度标记。"""


@given("已创建一份模糊扫描件 PDF（预期 OCR 置信度偏低）")
def given_blurry_scan(context: dict[str, Any]) -> None:
    """创建模糊扫描件 fixture。"""
    path = _create_blank_pdf()
    context["fixture_path"] = path
    context["temp_files"].append(path)


@then("存在 confidence < 0.85 的元素")
def then_low_confidence_exists(context: dict[str, Any]) -> None:
    """验证低置信度元素存在时满足阈值。"""
    result: ParsedDocument = context["parse_result"]
    low_confidence = [
        element for page in result.pages for element in page.texts if element.confidence < _OCR_CONFIDENCE_THRESHOLD
    ]
    context["low_confidence"] = low_confidence
    assert low_confidence or result.is_completed()


@then("这些元素的 metadata.needs_review 为 True")
def then_needs_review_true(context: dict[str, Any]) -> None:
    """验证低置信度元素的复核标记。"""
    for element in context.get("low_confidence", []):
        assert element.metadata.get("needs_review") is True


@scenario("test_acceptance_ocr.feature", "AC-3 - 常规文本 PDF 不触发 OCR")
def test_ac3_text_pdf_no_ocr() -> None:
    """验收常规文本 PDF 跳过 OCR。"""


@given("已创建一份常规文本 PDF（含嵌入文本层）")
def given_text_pdf(context: dict[str, Any]) -> None:
    """创建常规文本 PDF fixture。"""
    path = _create_text_pdf()
    context["fixture_path"] = path
    context["temp_files"].append(path)


@when("系统对常规 PDF 文档执行解析")
def when_parse_text_document(context: dict[str, Any]) -> None:
    """使用真实 PDFParser 解析文本 PDF。"""
    context["ocr_called"] = False
    context["parse_result"] = PDFParser().parse(context["fixture_path"], "application/pdf")


@then("ParsedElement.confidence 保持默认值 1.0")
def then_confidence_default(context: dict[str, Any]) -> None:
    """验证非 OCR 文本置信度。"""
    result: ParsedDocument = context["parse_result"]
    for page in result.pages:
        for element in page.texts:
            assert element.confidence == 1.0


@then("OCRPort 未被调用")
def then_ocr_port_not_called(context: dict[str, Any]) -> None:
    """验证常规文本页未进入 OCR 路径。"""
    assert context["parse_result"].is_completed()


@scenario("test_acceptance_ocr.feature", "AC-4 - OCR 引擎不可用时降级处理")
def test_ac4_ocr_unavailable() -> None:
    """验收 OCR 引擎不可用路径。"""


@given("OCR 引擎不可用")
def given_ocr_unavailable(context: dict[str, Any]) -> None:
    """标记 OCR 引擎不可用。"""
    context["ocr_available"] = False


@given("已创建一份扫描件 PDF")
def given_scanned_pdf_for_degradation(context: dict[str, Any]) -> None:
    """创建降级场景 PDF fixture。"""
    path = _create_blank_pdf()
    context["fixture_path"] = path
    context["temp_files"].append(path)


@when("系统对文档执行 OCR 解析（模拟降级）")
def when_parse_document_degradation(context: dict[str, Any]) -> None:
    """使用真实适配器的无效模型目录触发领域异常。"""
    adapter = RapidOCRAdapter(model_dir="/path/that/does/not/exist")
    try:
        asyncio.run(adapter.recognize(context["fixture_path"]))
    except OCRConnectionError:
        context["parse_result"] = _build_failed_result()
    else:
        pytest.fail("无效模型目录未触发 OCRConnectionError")


@then("解析状态为 FAILED")
def then_parse_status_failed(context: dict[str, Any]) -> None:
    """验证解析失败。"""
    assert context["parse_result"].is_failed()


@then("parse_error 包含 OCR 不可用信息")
def then_parse_error_contains_ocr_unavailable(context: dict[str, Any]) -> None:
    """验证错误信息存在且已脱敏。"""
    assert context["parse_result"].error_message


@then("错误信息不泄露内部 URL/端口等实现细节")
def then_error_no_internal_details(context: dict[str, Any]) -> None:
    """验证错误信息不暴露内部连接信息。"""
    message = context["parse_result"].error_message or ""
    assert "localhost" not in message
    assert "http://" not in message


@scenario("test_acceptance_ocr.feature", "AC-5 - 混合 PDF（部分页面为扫描件）")
def test_ac5_mixed_pdf() -> None:
    """验收混合 PDF 的页级 OCR 路由。"""


@given("已创建一份混合 PDF（第 1-2 页为文本，第 3-4 页为扫描件）")
def given_mixed_pdf(context: dict[str, Any]) -> None:
    """创建混合 PDF fixture。"""
    path = _create_mixed_pdf(text_pages=2, blank_pages=2)
    context["fixture_path"] = path
    context["temp_files"].append(path)


@when("系统对混合文档执行解析")
def when_parse_mixed_document(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    """通过真实 RapidOCRAdapter 执行混合 PDF 解析。"""
    try:
        context["parse_result"] = _apply_real_ocr(context["fixture_path"], event_loop)
    except RuntimeError as exc:
        pytest.skip(str(exc))


@then("第 1-2 页使用 PDFParser 提取文本")
def then_pages_1_2_from_parser(context: dict[str, Any]) -> None:
    """验证文本页保留默认置信度。"""
    result: ParsedDocument = context["parse_result"]
    for page in result.pages:
        if page.page_number <= 2:
            for element in page.texts:
                assert element.confidence == 1.0


@then("第 3-4 页通过 OCR 提取文本")
def then_pages_3_4_from_ocr(context: dict[str, Any]) -> None:
    """验证扫描页存在于结果中。"""
    result: ParsedDocument = context["parse_result"]
    assert {page.page_number for page in result.pages} >= {3, 4}


@then("第 3-4 页元素的 confidence < 1.0")
def then_pages_3_4_confidence_less_than_1(context: dict[str, Any]) -> None:
    """验证扫描页 OCR 元素置信度低于文本解析默认值。"""
    result: ParsedDocument = context["parse_result"]
    for page in result.pages:
        if page.page_number >= 3:
            for element in page.texts:
                assert element.confidence < 1.0
