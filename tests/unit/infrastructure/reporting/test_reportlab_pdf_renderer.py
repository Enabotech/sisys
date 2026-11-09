"""ReportLabPdfRenderer 单元测试（Story 6-5b Task 2）。

覆盖面：
- 渲染核心：bytes 有效（%PDF 魔数/页数≥1）/metadata Title/中文字体注册
  （STSong-Light 全程样式——Task 0.2 复验：正确 setFont 下 extract_text
  中文完美工作）
- 三态样例：正常/快照缺失（附录 A 省——目录条目非恒定敏感面）/降级
  （[数据缺失] callout + 附录 B 行）
- 结构断言（R3 实证口径）：outline 层级全等（display_name 源独立构造）/
  目录 link 注释（/Annots Subtype==/Link 且 /Dest 数组首元素有效页）/
  引文锚点（附录 C 条目行 link 自指——Task 0 裁定锚点承载形态；正文页
  零 link 负向）
- 表格全文比对（含长文件名/`-`/chunk_id 列——R3 升级口径）
- 悬空链接守护：锚点注册被破坏（monkeypatch no-op）→ save 期 ValueError
- pypdfium2 渲染冒烟（每页非空白像素——AC-8 视觉面兜底）

Run with:
    poetry run pytest tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer.py -v
"""

import io
from typing import Any

import pytest

from src.domain.value_objects.markdown_report import (
    MarkdownReportDocument,
    ReportBlock,
    ReportSection,
)

#: 附录 C 冻结标题（增量冻结表）
_APPENDIX_C_TITLE = "附录 C 引文索引"

#: 附录 C 表头四列（增量冻结表钦定）
_CITATION_HEADERS: tuple[str, ...] = ("#", "文档名", "页码", "切片标识")

#: 测试标题族（对齐 6-5a 冻结章节结构——display_name 语义源独立构造）
_GAP_TITLE = "业绩差距分析"
_TREND_TITLE = "看趋势"


def _gap_sections() -> tuple[ReportSection, ...]:
    """第 1 章四小节构造（gap 四字段块族）。"""
    return (
        ReportSection(
            title=f"1 {_GAP_TITLE}",
            level=2,
            blocks=(ReportBlock(kind="table", headers=("维度", "评估"), rows=(("财务", "营收达成率 82%"),)),),
        ),
        ReportSection(
            title="1.1 财务差距",
            level=3,
            blocks=(ReportBlock(kind="paragraph", text="财务差距量化：营收达成率 82%"),),
        ),
        ReportSection(
            title="1.2 运营差距",
            level=3,
            blocks=(ReportBlock(kind="paragraph", text="运营差距分析：交付周期延长"),),
        ),
        ReportSection(
            title="1.3 根因分析",
            level=3,
            blocks=(ReportBlock(kind="bullet_list", items=("价格竞争侵蚀毛利", "供应链成本上升")),),
        ),
        ReportSection(
            title="1.4 业务组合健康度",
            level=3,
            blocks=(ReportBlock(kind="paragraph", text="业务组合健康度：核心稳健"),),
        ),
    )


def _market_sections(*, degraded_trend: bool = False) -> tuple[ReportSection, ...]:
    """第 2 章 + 2.1 小节 + 2.7 综合（degraded_trend=True 时 2.1 为 [数据缺失] callout）。"""
    trend_blocks = (
        (ReportBlock(kind="callout", text="[数据缺失] 看趋势：该步骤归档记录不可用"),)
        if degraded_trend
        else (
            ReportBlock(
                kind="table",
                headers=("维度", "评估"),
                rows=(("政治", "政策维度：补贴退坡"), ("技术", "技术维度：固态电池演进")),
            ),
            ReportBlock(kind="bullet_list", items=("短期：平台化架构降本", "中期：固态电池量产")),
        )
    )
    return (
        ReportSection(title="2 市场洞察", level=2, blocks=()),
        ReportSection(title=f"2.1 {_TREND_TITLE}", level=3, blocks=trend_blocks),
        ReportSection(
            title="2.7 市场洞察综合",
            level=3,
            blocks=(ReportBlock(kind="bullet_list", items=("综合结论一：优先补强内部能力",)),),
        ),
    )


def _appendix_a() -> ReportSection:
    """附录 A 执行时间线（快照在位态）。"""
    return ReportSection(
        title="附录 A 执行时间线",
        level=2,
        blocks=(ReportBlock(kind="table", headers=("步骤", "完成时间"), rows=(("业绩差距分析", "2026-11-04 10:00:00"),)),),
    )


def _appendix_b(*, degraded: bool = False) -> ReportSection:
    """附录 B 降级与数据缺失记录（恒存在；degraded=True 时含一行）。"""
    rows = (("[数据缺失]", "看趋势", "该步骤归档记录不可用"),) if degraded else ()
    return ReportSection(
        title="附录 B 降级与数据缺失记录",
        level=2,
        blocks=(ReportBlock(kind="table", headers=("类型", "步骤", "原因"), rows=rows),),
    )


def _appendix_c(*, entries: tuple[tuple[str, ...], ...] | None = None) -> ReportSection:
    """附录 C 引文索引（entries None = 全空单行说明 callout）。"""
    if entries is None:
        return ReportSection(
            title=_APPENDIX_C_TITLE,
            level=2,
            blocks=(ReportBlock(kind="callout", text="本报告无检索证据引用"),),
        )
    return ReportSection(
        title=_APPENDIX_C_TITLE,
        level=2,
        blocks=(ReportBlock(kind="table", headers=_CITATION_HEADERS, rows=entries),),
    )


def _make_document(
    *,
    with_appendix_a: bool = True,
    degraded: bool = False,
    citation_entries: tuple[tuple[str, ...], ...] | None = (
        ("1", "2026年度战略复盘报告-超长文件名验证.pdf", "p.12", "a1b2c3d4"),
    ),
) -> MarkdownReportDocument:
    """构造三态可调样例文档（正常/快照缺失/降级）。"""
    sections: list[ReportSection] = [
        *_gap_sections(),
        *_market_sections(degraded_trend=degraded),
    ]
    if with_appendix_a:
        sections.append(_appendix_a())
    sections.append(_appendix_b(degraded=degraded))
    if citation_entries is None:
        sections.append(_appendix_c())
    else:
        sections.append(_appendix_c(entries=citation_entries))
    return MarkdownReportDocument(
        plan_id="0b6a6c2e-6f4e-4a3b-9c2d-1e2f3a4b5c6d",
        title="战略规划报告（BLM 前两阶段）",
        meta_rows=(("规划任务", "制定五年战略规划"), ("报告类型", "PDF")),
        sections=tuple(sections),
        toc_enabled=True,
    )


def _render(document: MarkdownReportDocument) -> bytes:
    """渲染样例文档（被测入口）。"""
    from src.infrastructure.reporting.reportlab_pdf_renderer import ReportLabPdfRenderer

    return ReportLabPdfRenderer().render(document)


def _reader(pdf_bytes: bytes) -> Any:
    """pypdf 读回。"""
    from pypdf import PdfReader

    return PdfReader(io.BytesIO(pdf_bytes))


def _full_text(reader: Any) -> str:
    """全页 extract_text 拼接。"""
    return "\n".join(page.extract_text() for page in reader.pages)


def _flatten_outline(reader: Any) -> list[tuple[int, str]]:
    """outline 展平为 (层级, 标题) 序列。"""

    def walk(items: list[Any], depth: int) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        for item in items:
            if isinstance(item, list):
                out.extend(walk(item, depth + 1))
            else:
                out.append((depth, str(item.title)))
        return out

    return walk(list(reader.outline), 0)


def _link_targets(reader: Any) -> list[tuple[int, int]]:
    """全文档 link 注释收集为 (注释页, 目标页) 序列（/Dest 数组首元素 idnum 对比）。"""
    from pypdf.generic import IndirectObject

    links: list[tuple[int, int]] = []
    for page_index, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        for annot_ref in annots.get_object():
            annot = annot_ref.get_object()
            if annot.get("/Subtype") != "/Link":
                continue
            dest = annot.get("/Dest")
            if dest is None:
                continue
            target = dest.get_object() if hasattr(dest, "get_object") else dest
            first = target[0]
            if not isinstance(first, IndirectObject):
                continue
            for target_index, candidate in enumerate(reader.pages):
                cand_ref = candidate.indirect_reference
                if cand_ref is not None and cand_ref.idnum == first.idnum:
                    links.append((page_index, target_index))
                    break
    return links


# ======================================================================
# 渲染核心
# ======================================================================


class TestRendererCore:
    """渲染核心（bytes 有效性/metadata/三态可渲染）。"""

    def test_render_returns_valid_pdf_bytes(self) -> None:
        """渲染产物为有效 PDF（%PDF 魔数 + pypdf 页数 ≥1 + bytes 非空）。"""
        pdf_bytes = _render(_make_document())
        assert isinstance(pdf_bytes, bytes) and len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")
        reader = _reader(pdf_bytes)
        assert len(reader.pages) >= 1

    def test_metadata_title_and_producer(self) -> None:
        """metadata Title=文档题（REPORT_TITLE_TEMPLATE 语义）+ Producer 非空（AC-8）。"""
        reader = _reader(_render(_make_document()))
        assert reader.metadata is not None
        assert reader.metadata.title == "战略规划报告（BLM 前两阶段）"
        assert reader.metadata.producer

    def test_three_state_documents_renderable(self) -> None:
        """三态样例（正常/快照缺失/降级）均可渲染为有效 PDF。"""
        for document in (
            _make_document(),
            _make_document(with_appendix_a=False),
            _make_document(with_appendix_a=False, degraded=True),
        ):
            pdf_bytes = _render(document)
            assert pdf_bytes.startswith(b"%PDF")
            assert len(_reader(pdf_bytes).pages) >= 1

    def test_chinese_text_extractable(self) -> None:
        """中文经 STSong-Light 渲染后 extract_text 可寻（Task 0.2 复验口径——R3 实证）。"""
        full_text = _full_text(_reader(_render(_make_document())))
        for expected in (
            "战略规划报告（BLM 前两阶段）",
            f"1 {_GAP_TITLE}",
            f"2.1 {_TREND_TITLE}",
            "财务差距量化：营收达成率 82%",
            "政策维度：补贴退坡",
        ):
            assert expected in full_text, f"中文文本层缺失: {expected}"

    def test_cjk_font_registered_module_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """STSong-Light 模块级注册一次（二次 render 恰一次注册——spy 委托真实注册）。"""
        import src.infrastructure.reporting.reportlab_pdf_renderer as renderer_module

        calls: list[str] = []
        real_register = renderer_module.pdfmetrics.registerFont

        def _spy_register(font: object) -> None:
            calls.append(type(font).__name__)
            real_register(font)

        monkeypatch.setattr(renderer_module.pdfmetrics, "registerFont", _spy_register)
        # 6-11 哨兵字典化机械适配（Story 6-11 AC-4 carve out 钦定唯一例外行：
        # _FONT_REGISTERED 单布尔→按名字典——monkeypatch 值 False→空 dict）
        monkeypatch.setattr(renderer_module, "_FONT_REGISTERED", {})
        first = _render(_make_document())
        second = _render(_make_document())
        assert first.startswith(b"%PDF") and second.startswith(b"%PDF")
        # reportlab build 期内部另有默认字体注册（'Font' 族）——仅计数目标 CID 字体
        assert calls.count("UnicodeCIDFont") == 1, f"STSong-Light 注册次数漂移（应恰一次）: {calls}"

    def test_bullet_list_ascii_prefix_and_payload(self) -> None:
        """bullet 前缀 ASCII 连字符 + 载荷可寻（CR1-F3——Adobe-GB1 无 U+2022 字形）。"""
        full_text = _full_text(_reader(_render(_make_document())))
        assert "- 价格竞争侵蚀毛利" in full_text, "bullet 前缀+载荷连续序列缺失"
        assert "- 短期：平台化架构降本" in full_text
        assert "•" not in full_text, "豆腐块字符 U+2022 残留"

    def test_gfm_bold_markers_stripped(self) -> None:
        """paragraph 内 GFM 行内强调标记剥除（内容保留——CR1-F8/F9）。"""
        document = MarkdownReportDocument(
            plan_id="plan-x",
            title="战略规划报告（BLM 前两阶段）",
            meta_rows=(),
            sections=(
                ReportSection(
                    title="1 业绩差距分析",
                    level=2,
                    blocks=(ReportBlock(kind="paragraph", text="**能力概览**：内部能力评估"),),
                ),
            ),
            toc_enabled=False,
        )
        full_text = _full_text(_reader(_render(document)))
        assert "能力概览：内部能力评估" in full_text
        assert "**" not in full_text, "GFM 强调标记残留（PDF 无解释器应剥除）"

    def test_unrenderable_warning_prefix_stripped(self) -> None:
        """callout 不可覆盖装饰前缀（U+26A0+VS16）剥除——文字标记保留语义（CR1-F8/F9）。"""
        document = MarkdownReportDocument(
            plan_id="plan-x",
            title="战略规划报告（BLM 前两阶段）",
            meta_rows=(),
            sections=(
                ReportSection(
                    title="1 业绩差距分析",
                    level=2,
                    blocks=(ReportBlock(kind="callout", text="⚠️ [降级] 看趋势：LLM 调用失败"),),
                ),
            ),
            toc_enabled=False,
        )
        full_text = _full_text(_reader(_render(document)))
        assert "[降级] 看趋势：LLM 调用失败" in full_text
        assert "⚠" not in full_text, "不可覆盖装饰字符残留（Adobe-GB1 无该字形）"


# ======================================================================
# 表格与附录 C 值级（AC-8/AC-3 渲染面）
# ======================================================================


class TestTableRendering:
    """表格渲染（列完整/长文件名/降级 `-` 列/chunk_id 列——全文比对口径）。"""

    def test_appendix_c_entry_full_text(self) -> None:
        """附录 C 引文条目四列全文可提取（含超长文件名/chunk_id 列）。"""
        full_text = _full_text(_reader(_render(_make_document())))
        assert _APPENDIX_C_TITLE in full_text
        assert "2026年度战略复盘报告-超长文件名验证.pdf" in full_text
        assert "p.12" in full_text
        assert "a1b2c3d4" in full_text

    def test_appendix_c_page_dash_cell(self) -> None:
        """页码列 `-` 值经渲染层透传（dash 决策在服务层——CR1-F4 docstring 口径）。"""
        full_text = _full_text(
            _reader(_render(_make_document(citation_entries=(("1", "无页码元数据文档.pdf", "-", "b2c3d4e5"),))))
        )
        assert "无页码元数据文档.pdf" in full_text

    def test_appendix_c_empty_note(self) -> None:
        """全空引文 → 附录 C 单行说明（恒存在哲学）。"""
        full_text = _full_text(_reader(_render(_make_document(citation_entries=None))))
        assert _APPENDIX_C_TITLE in full_text
        assert "本报告无检索证据引用" in full_text

    def test_pestel_table_full_text(self) -> None:
        """PESTEL 表格中文全文比对（表头+数据行）。"""
        full_text = _full_text(_reader(_render(_make_document())))
        assert "维度" in full_text and "评估" in full_text
        assert "政治" in full_text and "政策维度：补贴退坡" in full_text

    def test_meta_table_rendered(self) -> None:
        """元信息表渲染（项目/值二列）。"""
        full_text = _full_text(_reader(_render(_make_document())))
        assert "规划任务" in full_text
        assert "制定五年战略规划" in full_text


# ======================================================================
# 导航结构（AC-4——outline/目录内链/引文锚点）
# ======================================================================


class TestNavigationStructure:
    """三层导航结构（书签 outline/目录内链/引文锚点）。"""

    def test_outline_hierarchy_full(self) -> None:
        """outline 层级全等（正常态——含 H1 题级/附录 A/B/C）。"""
        flat = _flatten_outline(_reader(_render(_make_document())))
        expected: list[tuple[int, str]] = [
            (0, "战略规划报告（BLM 前两阶段）"),
            (1, f"1 {_GAP_TITLE}"),
            (2, "1.1 财务差距"),
            (2, "1.2 运营差距"),
            (2, "1.3 根因分析"),
            (2, "1.4 业务组合健康度"),
            (1, "2 市场洞察"),
            (2, f"2.1 {_TREND_TITLE}"),
            (2, "2.7 市场洞察综合"),
            (1, "附录 A 执行时间线"),
            (1, "附录 B 降级与数据缺失记录"),
            (1, _APPENDIX_C_TITLE),
        ]
        assert flat == expected, f"outline 漂移: 实测={flat} 期望={expected}"

    def test_outline_without_appendix_a(self) -> None:
        """快照缺失态 outline 无附录 A（目录条目非恒定敏感面）。"""
        flat = _flatten_outline(_reader(_render(_make_document(with_appendix_a=False))))
        titles = [title for _, title in flat]
        assert "附录 A 执行时间线" not in titles
        assert _APPENDIX_C_TITLE in titles

    def test_outline_targets_resolvable(self) -> None:
        """outline 每条目目标页可解析（锚点可解析——get_destination_page_number）。"""
        reader = _reader(_render(_make_document()))

        def walk(items: list[Any]) -> list[Any]:
            leaves: list[Any] = []
            for item in items:
                if isinstance(item, list):
                    leaves.extend(walk(item))
                else:
                    leaves.append(item)
            return leaves

        for leaf in walk(list(reader.outline)):
            page_index = reader.get_destination_page_number(leaf)
            assert 0 <= page_index < len(reader.pages)

    def test_toc_link_annotations_valid(self) -> None:
        """目录 link 注释（/Annots Subtype==/Link + /Dest 数组首元素有效页）。"""
        reader = _reader(_render(_make_document()))
        links = _link_targets(reader)
        page_texts = [page.extract_text() for page in reader.pages]
        toc_pages = {page for page, _ in links if "目录" in page_texts[page]}
        assert toc_pages, "目录 link 未锚定目录页"
        toc_links = [(page, target) for page, target in links if page in toc_pages]
        # 目录收录面：H2 章级 5 条（1 章/2 章/附录 A/B/C）——不含附录 C 自指锚点
        assert len(toc_links) == 5, f"目录 link 数漂移: {len(toc_links)}"
        for _, target in links:
            assert 0 <= target < len(reader.pages)

    def test_toc_links_without_appendix_a(self) -> None:
        """快照缺失态目录条目数 4（附录 A 可选——收录面非恒定）。"""
        reader = _reader(_render(_make_document(with_appendix_a=False)))
        page_texts = [page.extract_text() for page in reader.pages]
        links = _link_targets(reader)
        toc_pages = {page for page, _ in links if "目录" in page_texts[page]}
        toc_links = [(page, target) for page, target in links if page in toc_pages]
        assert len(toc_links) == 4

    def test_citation_anchors_appendix_only(self) -> None:
        """引文锚点承载形态（Task 0 裁定）：附录 C 条目行 link 自指 + 正文页零 link。"""
        reader = _reader(_render(_make_document()))
        links = _link_targets(reader)
        page_texts = [page.extract_text() for page in reader.pages]
        toc_pages = {page for page, _ in links if "目录" in page_texts[page]}
        assert toc_pages, "目录 link 未锚定目录页"
        # 非目录页 link = 引文锚点（正文页零 link + 附录 C 页恰引文条目数的自指锚点）
        non_toc_links = [(page, target) for page, target in links if page not in toc_pages]
        assert len(non_toc_links) == 1, f"非目录页 link 数漂移: {non_toc_links}"
        for page, target in non_toc_links:
            assert target == page  # 自指（条目行锚点在本页）
            assert _APPENDIX_C_TITLE in page_texts[page]  # 锚定附录 C 页

    def test_citation_anchors_count_matches_entries(self) -> None:
        """附录 C 锚点数随条目数（2 条引文 → 2 个自指 link）。"""
        reader = _reader(
            _render(
                _make_document(
                    citation_entries=(
                        ("1", "报告甲.pdf", "p.3", "aaaabbbb"),
                        ("2", "[溯源不可用：检索点缺失]", "-", "ccccdddd"),
                    )
                )
            )
        )
        links = _link_targets(reader)
        page_texts = [page.extract_text() for page in reader.pages]
        toc_pages = {page for page, _ in links if "目录" in page_texts[page]}
        non_toc_links = [(page, target) for page, target in links if page not in toc_pages]
        assert len(non_toc_links) == 2
        for page, target in non_toc_links:
            assert target == page
            assert _APPENDIX_C_TITLE in page_texts[page]

    def test_dangling_link_save_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """悬空链接守护（锚点注册被破坏 → save 期 ValueError——R3 实证形态）。"""
        from src.infrastructure.reporting import reportlab_pdf_renderer as renderer_module

        monkeypatch.setattr(renderer_module, "_register_section_anchor", lambda *args, **kwargs: None)
        with pytest.raises(ValueError, match="format not resolved|destination"):
            _render(_make_document())


# ======================================================================
# pypdfium2 渲染冒烟（AC-8 视觉面兜底）
# ======================================================================


class TestRasterizationSmoke:
    """pypdfium2 光栅化冒烟（每页渲染非空白——渲染异常即红）。"""

    def test_every_page_non_blank(self) -> None:
        """每页光栅化非纯白像素（中文渲染不炸 + 视觉面非空白）。"""
        import pypdfium2 as pdfium

        pdf_bytes = _render(_make_document())
        pdf_doc = pdfium.PdfDocument(pdf_bytes)
        assert len(pdf_doc) >= 1
        for page in pdf_doc:
            grayscale_values = list(page.render().to_pil().convert("L").getdata())
            non_white = sum(1 for value in grayscale_values if value < 250)
            assert non_white > 0, "页面光栅化后纯白（渲染内容缺失）"
