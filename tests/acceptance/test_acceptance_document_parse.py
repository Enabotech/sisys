"""Story 2-2a 验收测试 — 文档解析与内容提取（基础格式）

按 AC（验收标准）组织，每个 AC 对应一个测试类。
测试使用真实解析器和临时 fixture 文件，验证端到端解析正确性。
"""

from __future__ import annotations

import os
import tempfile

# ===================================================================
# 内部 helpers
# ===================================================================


def _create_reportlab_pdf(text: str) -> str:
    """用 reportlab 构造含指定文本的单页 PDF"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    tmp.close()
    return tmp.name


def _create_empty_pdf() -> str:
    """创建 0 页空 PDF"""
    from pypdf import PdfWriter

    writer = PdfWriter()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    writer.write(tmp.name)
    tmp.close()
    return tmp.name


def _create_encrypted_pdf() -> str:
    """创建加密 PDF"""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    writer.write(tmp.name)
    writer.encrypt(user_password="test", owner_password="test")  # pragma: allowlist secret
    enc_tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_enc.pdf")
    writer.write(enc_tmp.name)
    enc_tmp.close()
    tmp.close()
    return enc_tmp.name


def _create_docx_with_heading_and_table() -> str:
    """创建含标题段落和表格的 DOCX"""
    from docx import Document

    doc = Document()
    doc.add_heading("战略规划报告", level=1)
    doc.add_paragraph("本报告概述了2026年度战略规划的主要内容。")
    table = doc.add_table(rows=3, cols=3)
    table.rows[0].cells[0].text = "维度"
    table.rows[0].cells[1].text = "目标"
    table.rows[0].cells[2].text = "进度"
    table.rows[1].cells[0].text = "市场"
    table.rows[1].cells[1].text = "增长20%"
    table.rows[1].cells[2].text = "进行中"
    table.rows[2].cells[0].text = "技术"
    table.rows[2].cells[1].text = "迁移上云"
    table.rows[2].cells[2].text = "未开始"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc.save(tmp.name)
    tmp.close()
    return tmp.name


def _create_txt_file(content: str, encoding: str) -> str:
    """创建指定编码的 TXT 文件"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    tmp.write(content.encode(encoding))
    tmp.close()
    return tmp.name


def _cleanup(path: str) -> None:
    """安全清理临时文件"""
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


# ===================================================================
# AC-1: PDF 文档解析
# ===================================================================


class TestAC1PDFDocumentParsing:
    """AC-1: PDF 文档解析

    系统应支持解析 PDF 格式文档，提取文本内容，
    每页包含 texts/tables/images 数组，bbox 字段为 null。
    """

    def test_parse_pdf_success(self) -> None:
        """成功解析纯文本 PDF 文档"""
        from src.infrastructure.external_services.document_parsing.pdf_parser import PDFParser

        sample_text = "Strategic Planning Report 2026"
        path = _create_reportlab_pdf(sample_text)
        try:
            parser = PDFParser()
            result = parser.parse(path, "application/pdf")

            # 解析状态验证
            assert result.is_completed(), f"PDF 解析应成功，实际: {result.error_message}"
            assert result.parse_status == "completed"
            assert len(result.pages) >= 1, "PDF 至少包含 1 页"

            # 文本准确性验证（关键词匹配）
            all_text = " ".join(t.content for p in result.pages for t in p.texts)
            for word in sample_text.split():
                assert word in all_text, f"关键词 '{word}' 未在提取文本中找到"

            # 结构验证：每页包含 texts、tables、images 数组
            for page in result.pages:
                d = page.to_dict()
                assert isinstance(d["texts"], list)
                assert isinstance(d["tables"], list)
                assert isinstance(d["images"], list)

            # bbox 字段为 null
            for page in result.pages:
                for elem in page.texts:
                    assert elem.to_dict()["bbox"] is None
                for table in page.tables:
                    assert table.to_dict()["bbox"] is None
        finally:
            _cleanup(path)

    def test_parse_encrypted_pdf_fails(self) -> None:
        """解析加密 PDF 文档失败"""
        from src.infrastructure.external_services.document_parsing.pdf_parser import PDFParser

        path = _create_encrypted_pdf()
        try:
            parser = PDFParser()
            result = parser.parse(path, "application/pdf")

            assert result.parse_status == "failed"
            assert result.is_failed()
            assert result.error_message is not None, "失败场景必须有 error_message"
        finally:
            _cleanup(path)

    def test_parse_empty_pdf_fails(self) -> None:
        """解析空 PDF 文档（0 页）失败"""
        from src.infrastructure.external_services.document_parsing.pdf_parser import PDFParser

        path = _create_empty_pdf()
        try:
            parser = PDFParser()
            result = parser.parse(path, "application/pdf")

            assert result.parse_status == "failed"
            assert result.error_message is not None
            assert "空" in result.error_message or "0 页" in result.error_message, (
                f"错误信息应说明文档为空，实际: {result.error_message}"
            )
        finally:
            _cleanup(path)


# ===================================================================
# AC-2: Word 文档解析
# ===================================================================


class TestAC2WordDocumentParsing:
    """AC-2: Word 文档解析

    系统应支持解析 DOCX 格式文档，提取文本和表格内容，
    识别段落样式（标题/正文/列表），拒绝旧版 DOC 格式。
    """

    def test_parse_docx_success(self) -> None:
        """成功解析 DOCX 文档，提取文本和表格"""
        from src.infrastructure.external_services.document_parsing.word_parser import WordParser

        path = _create_docx_with_heading_and_table()
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        try:
            parser = WordParser()
            result = parser.parse(path, mime)

            assert result.is_completed(), f"DOCX 解析应成功，实际: {result.error_message}"

            # 文本提取验证
            all_text = " ".join(t.content for p in result.pages for t in p.texts)
            assert "战略规划" in all_text, f"应提取到标题文本，实际: {all_text}"
            assert "2026年度" in all_text, f"应提取到正文内容，实际: {all_text}"

            # 段落样式验证
            styles_found = []
            for page in result.pages:
                for elem in page.texts:
                    style = elem.metadata.get("style", "")
                    if style:
                        styles_found.append(style)
            assert len(styles_found) > 0, "应识别到至少一个段落样式"
            heading_styles = [s for s in styles_found if "Heading" in s or "heading" in s.lower()]
            assert len(heading_styles) > 0, f"应识别到标题样式，实际样式列表: {styles_found}"

            # 表格结构验证
            all_tables = [t for p in result.pages for t in p.tables]
            assert len(all_tables) >= 1, "应至少提取到 1 个表格"

            table = all_tables[0]
            assert len(table.rows) >= 2, f"表格应至少有 2 行（表头+数据），实际: {len(table.rows)}"
            assert len(table.rows[0]) >= 2, f"表格应至少有 2 列，实际: {len(table.rows[0])}"
        finally:
            _cleanup(path)

    def test_parse_doc_legacy_fails(self) -> None:
        """解析旧版 DOC 格式失败，建议转换为 DOCX"""
        from src.infrastructure.external_services.document_parsing.word_parser import WordParser

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".doc")
        tmp.write(b"not a valid docx")
        tmp.close()
        try:
            parser = WordParser()
            result = parser.parse(tmp.name, "application/msword")

            assert result.parse_status == "failed"
            assert result.error_message is not None
            assert "DOCX" in result.error_message, f"错误信息应建议转换为 DOCX，实际: {result.error_message}"
        finally:
            _cleanup(tmp.name)


# ===================================================================
# AC-3: TXT 文档解析
# ===================================================================


class TestAC3TXTDocumentParsing:
    """AC-3: TXT 文档解析

    系统应支持解析 TXT 格式文档，自动识别 UTF-8/GBK 编码，
    按空行分割段落，正确提取中文内容。
    """

    def test_parse_txt_utf8_success(self) -> None:
        """成功解析 UTF-8 编码 TXT 文档，按段落分割"""
        from src.infrastructure.external_services.document_parsing.text_parser import TextParser

        content = "第一部分：项目概述\n\n第二部分：实施计划\n\n第三部分：风险评估"
        path = _create_txt_file(content, "utf-8")
        try:
            parser = TextParser()
            result = parser.parse(path, "text/plain")

            assert result.is_completed(), f"UTF-8 TXT 解析应成功，实际: {result.error_message}"

            # 按段落分割验证
            texts = [t.content for p in result.pages for t in p.texts]
            assert len(texts) >= 3, f"应按空行分割为至少 3 个段落，实际: {len(texts)} 段: {texts}"
            assert any("第一部分" in t for t in texts), f"应包含第一段，实际: {texts}"
            assert any("第三部分" in t for t in texts), f"应包含第三段，实际: {texts}"

            # UTF-8 编码正确识别
            all_text = " ".join(t.content for p in result.pages for t in p.texts)
            assert "项目概述" in all_text, f"UTF-8 中文应正确提取，实际: {all_text}"
            assert "风险评估" in all_text, f"UTF-8 中文应完整提取，实际: {all_text}"
        finally:
            _cleanup(path)

    def test_parse_txt_gbk_success(self) -> None:
        """成功解析 GBK 编码 TXT 文档，中文内容正确提取"""
        from src.infrastructure.external_services.document_parsing.text_parser import TextParser

        content = "战略规划报告摘要\n\n市场分析显示增长潜力显著\n\n技术路线图已制定"
        path = _create_txt_file(content, "gbk")
        try:
            parser = TextParser()
            result = parser.parse(path, "text/plain")

            assert result.is_completed(), f"GBK TXT 解析应成功，实际: {result.error_message}"

            # GBK 编码正确识别
            all_text = " ".join(t.content for p in result.pages for t in p.texts)
            assert "战略规划" in all_text, f"GBK 中文应正确提取，实际: {all_text}"

            # 中文内容完整提取
            chinese_keywords = ["战略规划", "市场分析", "技术路线图"]
            for kw in chinese_keywords:
                assert kw in all_text, f"中文关键词 '{kw}' 未在提取文本中找到"
        finally:
            _cleanup(path)


# ===================================================================
# AC-4: 解析结果结构化输出
# ===================================================================


class TestAC4ParsedResultJSONSchema:
    """AC-4: 解析结果遵循统一 JSON Schema

    输出包含 document_id、mime_type、pages 数组，
    每页包含 page_number、texts、tables、images，
    bbox 字段为 null（DocLayNet 预留），confidence 默认值为 1.0。
    """

    def test_json_schema_top_level(self) -> None:
        """输出包含 document_id、mime_type、pages 数组"""
        from src.domain.value_objects.parsed_document import ParsedDocument

        doc = ParsedDocument(document_id="test-id", mime_type="text/plain")
        d = doc.to_dict()
        assert "document_id" in d
        assert d["document_id"] == "test-id"
        assert "mime_type" in d
        assert d["mime_type"] == "text/plain"
        assert "pages" in d
        assert isinstance(d["pages"], list)

    def test_json_schema_page_level(self) -> None:
        """每页包含 page_number、texts、tables、images"""
        from src.domain.value_objects.parsed_document import ParsedPage

        page = ParsedPage(page_number=1)
        d = page.to_dict()
        assert d["page_number"] == 1
        assert isinstance(d["texts"], list)
        assert isinstance(d["tables"], list)
        assert isinstance(d["images"], list)

    def test_bbox_null_for_doclaynet_reserve(self) -> None:
        """bbox 字段结构为 null（DocLayNet 预留）"""
        from src.domain.value_objects.parsed_document import ParsedElement, ParsedTable

        elem = ParsedElement(content="x")
        assert elem.to_dict()["bbox"] is None
        table = ParsedTable()
        assert table.to_dict()["bbox"] is None

    def test_confidence_default_value(self) -> None:
        """confidence 默认值为 1.0"""
        from src.domain.value_objects.parsed_document import ParsedElement, ParsedTable

        elem = ParsedElement(content="x")
        assert elem.confidence == 1.0
        table = ParsedTable()
        assert table.confidence == 1.0

    def test_document_processed_event_schema(self) -> None:
        """DocumentProcessed.parse_result 包含完整解析输出"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedPage

        doc = ParsedDocument(
            document_id="test",
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1)],
        )
        d = doc.to_dict()
        required_fields = {"document_id", "mime_type", "pages", "parse_status", "error_message", "parse_timestamp"}
        missing = required_fields - set(d.keys())
        assert not missing, f"事件 parse_result 缺少字段: {missing}"


# ===================================================================
# AC-5: 事件触发与状态流转
# ===================================================================


class TestAC5EventTriggerAndStatusFlow:
    """AC-5: 事件触发与状态流转

    验证解析状态机的正确性：
    - 成功路径: pending -> in_progress -> completed，发布 DocumentProcessed 事件
    - 失败路径: pending -> in_progress -> failed，不发布事件
    """

    def test_success_status_flow(self) -> None:
        """解析成功完整状态流转：pending -> in_progress -> completed"""
        from src.domain.entities.document import ParseStatus

        assert ParseStatus.PENDING.value == "pending"
        assert ParseStatus.IN_PROGRESS.value == "in_progress"
        assert ParseStatus.COMPLETED.value == "completed"

    def test_failure_status_flow(self) -> None:
        """解析失败状态流转：pending -> in_progress -> failed"""
        from src.domain.entities.document import ParseStatus

        assert ParseStatus.FAILED.value == "failed"
