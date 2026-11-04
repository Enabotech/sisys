"""reportlab PDF 渲染器（Story 6-5b——``PdfRendererPort`` 基础设施实现，reportlab 唯一宿主）。

消费 6-5a 聚合产物 ``MarkdownReportDocument``（双渲染共用 IR——名字带
Markdown 前缀但已是 PDF 链同源中间文档模型）单参渲染为 PDF bytes，与
``render_markdown_report`` 入参对称（OD-3 同源双渲染）。

层位裁定（OD-5）：渲染器依赖第三方库 reportlab（importlinter forbidden
面）必须出 domain——「渲染规则是领域知识，渲染技术是基础设施」的分界线；
markdown 渲染纯字符串拼接零依赖可进 domain，PDF 渲染不同构是必然非不一致。

三层导航结构（AC-4）：
- 书签 outline：H1 文档题（level 0）+ H2 章级含附录（level 1）+ H3 小节
  （level 2）——层级与冻结章节结构一致；
- 目录内链：目录条目 ``<link href="#sec-{i}">`` 指向章起始锚点（save 期
  统一解析命名目标——link 可前向引用 bookmarkPage，单遍渲染即可）；
- 引文锚点：附录 C 条目行序号列 link 自指（``<a name="citation-{index}"/>``
  + ``<link href="#citation-{index}">``——Task 0.2 复验裁定锚点承载形态：
  孤立 bookmarkPage 在 PDF 零留存，link 注释自指使锚点机器可寻址，6-8
  Web 阅读器可经 /Annots 定位条目行）。

中文字体（AC-8）：``UnicodeCIDFont("STSong-Light")`` 模块级注册一次——
内置 CID 字体零字体文件依赖（可移植性），全程样式统一 STSong-Light
（含表格 cell——Task 0.2 复验：extract_text 对正确 setFont 的中文完美
工作；跨 showPage 未设字体会回落 Helvetica 画 .notdef 方块）。

悬空链接天然守护：锚点注册被破坏时 reportlab save 期抛
``ValueError: format not resolved ... undefined destination``——
``PdfRenderingError``（492）的包装触发面之一（Task 3 编排层包装）。
"""

import io
import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from src.application.ports.pdf_report import APPENDIX_C_TITLE, PdfRendererPort
from src.domain.value_objects.markdown_report import (
    MarkdownReportDocument,
    ReportBlock,
    ReportSection,
)

__all__ = ["ReportLabPdfRenderer"]

#: CJK 字体名（Adobe-GB1 预定义 CMap——内置 CID 字体零字体文件依赖）
_FONT_NAME = "STSong-Light"

#: GFM 行内强调标记（``**粗体**``——markdown 渲染器原样透传、由 GFM 查看
#: 器解释；PDF 链无下游解释器且 CID 字体无 bold 变体，渲染侧剥除标记保留
#: 内容。documents 行 filename 含 ``**`` 时同被剥——概率趋零的保真度取舍）
_GFM_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")

#: 不可覆盖装饰前缀（U+26A0+U+FE0F——Adobe-GB1 无该字形，光栅化呈豆腐块；
#: 聚合产物 callout 以此为装饰前缀，语义由 ``[降级]``/``[数据缺失]`` 文字
#: 标记承载，剥除零语义损失）
_UNRENDERABLE_PREFIX = "⚠️ "


def _pdf_text(text: str) -> str:
    """PDF 文本出口净化（GFM 行内强调剥除 + 不可覆盖装饰前缀移除）。

    Args:
        text: IR 原始文本（可能夹带 GFM 行内标记/装饰字符）。

    Returns:
        净化后文本（先净化后 XML 转义——调用方衔接 ``_xml_escape``）。
    """
    return _GFM_BOLD_PATTERN.sub(r"\1", text).removeprefix(_UNRENDERABLE_PREFIX)


def _xml_escape(text: str) -> str:
    """XML 文本节点转义（&/</> 三字符——生成侧纯字符串替换）。

    与 ``xml.sax.saxutils.escape(text)`` 无 entities 形态逐字符等价；不经
    xml.sax 模块（bandit B406 import 黑名单——escape 本是生成侧替换非 XML
    解析攻击面，本地实现消除模块依赖；& 必须最先替换防二次转义）。

    Args:
        text: 原始文本。

    Returns:
        转义后文本（reportlab Paragraph 文本节点安全形态）。
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


#: 元信息表头（6-5a markdown 渲染器同款冻结口径）
_META_TABLE_HEADERS: tuple[str, ...] = ("项目", "值")

#: 附录 C 四列宽度占比（首列窄序号 + 文档名列自适应 + 页码/标识列定宽——AC-8 列宽策略）
_CITATION_COL_RATIOS: tuple[float, ...] = (0.08, 0.52, 0.14, 0.26)

#: 字体注册幂等标记（模块级一次——多实例 render 不重复注册）
_FONT_REGISTERED = False


def _ensure_font() -> None:
    """注册 CJK 字体（模块级一次——幂等；注册失败属 492 包装面由编排层包装）。"""
    global _FONT_REGISTERED
    if not _FONT_REGISTERED:
        pdfmetrics.registerFont(UnicodeCIDFont(_FONT_NAME))
        _FONT_REGISTERED = True


def _register_section_anchor(canvas: Any, name: str, title: str, level: int) -> None:
    """注册命名锚点 + outline 条目（章节导航锚定位——悬空守护的注册面）。

    Args:
        canvas: reportlab canvas（Flowable.draw 传入）。
        name: 命名锚点名（``sec-{i}`` / ``doc-title``）。
        title: outline 显示标题。
        level: outline 层级（0=H1 题级 / 1=H2 章级 / 2=H3 小节）。
    """
    canvas.bookmarkPage(name)
    canvas.addOutlineEntry(title, name, level=level, closed=False)


def _anchor_name(section_index: int) -> str:
    """章节锚点名（``sec-{i}``——序号锚定避免中文/特殊字符名不稳定）。

    Args:
        section_index: section 序号（0 起）。

    Returns:
        锚点名。
    """
    return f"sec-{section_index}"


class _OutlineMarker(Flowable):
    """零尺寸 Flowable：在绘制点注册章节命名锚点 + outline 条目。

    与标题 Paragraph 经 KeepTogether 绑定（防分页边界锚点错页）；
    引用的锚点名被目录 ``<link>`` 前向消费——save 期统一解析。
    """

    def __init__(self, name: str, title: str, level: int) -> None:
        """初始化标记。

        Args:
            name: 命名锚点名。
            title: outline 显示标题。
            level: outline 层级。
        """
        super().__init__()
        self._name = name
        self._title = title
        self._level = level
        self.width = 0
        self.height = 0

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        """零尺寸（不占布局空间——位置绑定兼容 Flowable.wrap 驼峰签名）。"""
        return (0, 0)

    def draw(self) -> None:
        """绘制点注册锚点 + outline 条目（悬空守护的注册面）。"""
        _register_section_anchor(self.canv, self._name, self._title, self._level)


class ReportLabPdfRenderer(PdfRendererPort):
    """reportlab PDF 渲染器（``PdfRendererPort`` 实现——reportlab 唯一宿主）。

    同步纯 CPU 渲染（无 I/O）：块型分派（paragraph/bullet_list/table/callout
    四块型——与 markdown_report_renderer 对称）+ 三层导航 + CJK 字体 +
    Table 列宽策略（cell 全 Paragraph 自动换行不溢出——AC-8）。
    """

    def render(self, document: MarkdownReportDocument) -> bytes:
        """渲染文档模型为 PDF bytes。

        Args:
            document: 双渲染共用 IR（6-5a 聚合产物，附录 C 已由编排层组装）。

        Returns:
            PDF 文件字节流。

        Raises:
            ValueError: save 期锚点未解析（悬空链接天然守护——编排层包装 492）。
        """
        _ensure_font()
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            title=document.title,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=20 * mm,
            bottomMargin=18 * mm,
        )
        story: list[Any] = []
        story.extend(self._build_cover(document))
        story.extend(self._build_meta_table(document, doc.width))
        story.extend(self._build_toc(document))
        for index, section in enumerate(document.sections):
            story.extend(self._build_section(section, index, doc.width))
        doc.build(story)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # 封面 / 元信息 / 目录
    # ------------------------------------------------------------------

    def _build_cover(self, document: MarkdownReportDocument) -> list[Any]:
        """H1 封面（文档题大字 + doc-title 锚点 + level 0 outline）。"""
        title_style = self._style("cover", fontSize=18, leading=26, spaceAfter=12)
        clean_title = _pdf_text(document.title)
        marker = _OutlineMarker("doc-title", clean_title, 0)
        return [KeepTogether([Paragraph(_xml_escape(clean_title), title_style), marker])]

    def _build_meta_table(self, document: MarkdownReportDocument, width: float) -> list[Any]:
        """元信息表（项目/值二列——markdown 渲染器同款表头）。"""
        if not document.meta_rows:
            return []
        table = self._build_table(_META_TABLE_HEADERS, tuple(document.meta_rows), width, col_ratios=(0.3, 0.7))
        return [table]

    def _build_toc(self, document: MarkdownReportDocument) -> list[Any]:
        """目录（H2 章级收录 + link 内链——附录 A 可选使条目数非恒定）。

        目录收录面 = level==2 sections（markdown 渲染器同款口径）；
        条目 ``<link href="#sec-{i}">`` 前向引用章起始锚点（save 期解析）。
        """
        if not document.toc_enabled:
            return []
        toc_title_style = self._style("toc_title", fontSize=14, leading=20, spaceBefore=14, spaceAfter=8)
        entry_style = self._style("toc_entry", fontSize=11, leading=18)
        flows: list[Any] = [Paragraph("目录", toc_title_style)]
        for index, section in enumerate(document.sections):
            if section.level != 2:
                continue
            flows.append(
                Paragraph(f'<link href="#{_anchor_name(index)}">{_xml_escape(_pdf_text(section.title))}</link>', entry_style)
            )
        return flows

    # ------------------------------------------------------------------
    # 章节与块渲染
    # ------------------------------------------------------------------

    def _build_section(self, section: ReportSection, index: int, width: float) -> list[Any]:
        """单章节（标题 + outline 锚点 + 块序列——空块仍渲染标题防目录悬空）。

        Args:
            section: 章节 VO。
            index: section 序号（锚点名派生源）。
            width: 可用宽度。

        Returns:
            Flowable 序列。
        """
        font_size = 14 if section.level == 2 else 12
        heading_style = self._style(
            f"h{section.level}", fontSize=font_size, leading=font_size + 6, spaceBefore=12, spaceAfter=6
        )
        clean_title = _pdf_text(section.title)
        marker = _OutlineMarker(_anchor_name(index), clean_title, section.level - 1)
        flows: list[Any] = [KeepTogether([Paragraph(_xml_escape(clean_title), heading_style), marker])]
        is_citation = section.title == APPENDIX_C_TITLE
        for block in section.blocks:
            flows.extend(self._build_block(block, width, citation_table=is_citation))
        return flows

    def _build_block(self, block: ReportBlock, width: float, *, citation_table: bool = False) -> list[Any]:
        """块型分派（四块型——paragraph/bullet_list/table/callout）。

        Args:
            block: 报告块 VO。
            width: 可用宽度。
            citation_table: 当前 section 是否附录 C（引文行锚点特判）。

        Returns:
            Flowable 序列。
        """
        if block.kind == "paragraph":
            if not block.text:
                return []
            return [Paragraph(_xml_escape(_pdf_text(block.text)), self._style("body", fontSize=10, leading=16))]
        if block.kind == "bullet_list":
            item_style = self._style("bullet", fontSize=10, leading=15, leftIndent=12)
            # ASCII 连字符前缀（markdown 渲染器 "- {item}" 同款对称——Adobe-GB1
            # 无 U+2022 字形，`•` 光栅化呈豆腐块）
            return [Paragraph(f"- {_xml_escape(_pdf_text(item))}", item_style) for item in block.items]
        if block.kind == "table":
            if not block.headers:
                return []
            return [self._build_table(block.headers, block.rows, width, citation_links=citation_table)]
        # callout：单格浅灰底表（视觉区分——CID 无 italic/bold 变体）
        callout_style = self._style("callout", fontSize=10, leading=15, textColor=colors.HexColor("#444444"))
        rows = [[Paragraph(_xml_escape(_pdf_text(line)), callout_style)] for line in block.text.splitlines() if line]
        if not rows:
            return []
        table = Table(rows, colWidths=[width])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F2F2")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return [table]

    def _build_table(
        self,
        headers: tuple[str, ...],
        rows: tuple[tuple[str, ...], ...],
        width: float,
        col_ratios: tuple[float, ...] | None = None,
        citation_links: bool = False,
    ) -> Table:
        """表格（cell 全 Paragraph 自动换行不溢出 + 表头浅灰底 + 附录 C 列宽策略）。

        Args:
            headers: 表头行。
            rows: 数据行。
            width: 可用宽度。
            col_ratios: 列宽占比（None=按附录 C 四列钦定占比或均分）。
            citation_links: 附录 C 特判（序号列 link 自指锚点注册）。

        Returns:
            reportlab Table。
        """
        ncols = len(headers)
        if col_ratios is None:
            col_ratios = _CITATION_COL_RATIOS if citation_links else (1.0 / ncols,) * ncols
        col_widths = [width * ratio for ratio in col_ratios]
        header_style = self._style("th", fontSize=9.5, leading=13)
        cell_style = self._style("td", fontSize=9.5, leading=13)
        data: list[list[Any]] = [[Paragraph(_xml_escape(_pdf_text(str(header))), header_style) for header in headers]]
        for row in rows:
            cells: list[Any] = []
            for col_index, cell in enumerate(row):
                text = _pdf_text(str(cell))
                if citation_links and col_index == 0:
                    anchor = f"citation-{text}"
                    cells.append(
                        Paragraph(
                            f'<a name="{anchor}"/><link href="#{anchor}">{_xml_escape(text)}</link>',
                            cell_style,
                        )
                    )
                else:
                    cells.append(Paragraph(_xml_escape(text), cell_style))
            data.append(cells)
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return table

    # ------------------------------------------------------------------
    # 样式
    # ------------------------------------------------------------------

    def _style(self, name: str, **overrides: Any) -> ParagraphStyle:
        """构造段落样式（fontName 恒 STSong-Light——全程 CJK 字体纪律）。

        Args:
            name: 样式名。
            **overrides: 尺寸/间距覆写项。

        Returns:
            ParagraphStyle 实例。
        """
        base: dict[str, Any] = {"fontName": _FONT_NAME, "fontSize": 10, "leading": 15}
        base.update(overrides)
        return ParagraphStyle(name, **base)
