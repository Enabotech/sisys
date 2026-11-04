"""Markdown 报告渲染器纯函数单元测试（Story 6-5a Task 1 循环 B）。

覆盖面：
- 文档结构渲染：H1 封面标题 + 元信息两列表 + 目录（H2 章级收录 + GitHub slug
  锚点）+ 章节标题 ATX 层级（# 计数 1/2/3）
- 四块型渲染：paragraph（段落）/ bullet_list（`- ` 前缀逐项）/ table（表头 +
  `| --- |` 分隔行 + 数据行 + 列对齐）/ callout（`> ` 前缀——降级与数据缺失双形态）
- 中文字符原样输出（渲染层禁转义——ensure_ascii=False 语义）
- 边界：空 items / 空 rows / toc 关闭

Run with:
    poetry run pytest tests/unit/domain/services/test_markdown_report_renderer.py -v
"""

from src.domain.services.markdown_report_renderer import render_markdown_report
from src.domain.value_objects.markdown_report import (
    MarkdownReportDocument,
    ReportBlock,
    ReportSection,
)


def _make_document(
    sections: tuple[ReportSection, ...],
    *,
    toc_enabled: bool = True,
    meta_rows: tuple[tuple[str, str], ...] = (("计划标识", "plan-1"),),
) -> MarkdownReportDocument:
    """构造测试文档（三件 helper——sections 可变参）。

    Args:
        sections: 章节元组。
        toc_enabled: 目录开关。
        meta_rows: 元信息表数据行。

    Returns:
        MarkdownReportDocument 实例。
    """
    return MarkdownReportDocument(
        plan_id="plan-1",
        title="战略规划报告（BLM 前两阶段）",
        meta_rows=meta_rows,
        sections=sections,
        toc_enabled=toc_enabled,
    )


class TestDocumentStructureRendering:
    """文档结构渲染（H1/元信息表/目录/章节标题）。"""

    def test_h1_title_first_line(self) -> None:
        """H1 封面标题是首行（ATX 单 # 前缀）。"""
        document = _make_document(())
        lines = render_markdown_report(document).splitlines()
        assert lines[0] == "# 战略规划报告（BLM 前两阶段）"

    def test_meta_table_two_columns(self) -> None:
        """元信息两列表：表头 | 项目 | 值 | + 分隔行 + 数据行。"""
        document = _make_document(())
        lines = render_markdown_report(document).splitlines()
        assert "| 项目 | 值 |" in lines
        assert "| --- | --- |" in lines
        assert "| 计划标识 | plan-1 |" in lines
        # 表头行在分隔行前（GFM 结构序）
        assert lines.index("| 项目 | 值 |") < lines.index("| --- | --- |")

    def test_section_heading_atx_levels(self) -> None:
        """章节标题 ATX 层级：level 1/2/3 分别渲染 #/##/###。"""
        document = _make_document(
            (
                ReportSection(title="第 1 章", level=2, blocks=(ReportBlock(kind="paragraph", text="正文"),)),
                ReportSection(title="小节一", level=3, blocks=(ReportBlock(kind="paragraph", text="正文"),)),
            )
        )
        lines = render_markdown_report(document).splitlines()
        assert "## 第 1 章" in lines
        assert "### 小节一" in lines

    def test_toc_renders_h2_entries_with_slug_anchors(self) -> None:
        """目录收录 H2 章级（GitHub slug 锚点——中文原样保留 + 空格转连字符）。"""
        document = _make_document(
            (
                ReportSection(title="1 业绩差距分析", level=2),
                ReportSection(title="1.1 财务差距", level=3),
                ReportSection(title="2 市场洞察", level=2),
            )
        )
        lines = render_markdown_report(document).splitlines()
        assert "## 目录" in lines
        assert "- [1 业绩差距分析](#1-业绩差距分析)" in lines
        assert "- [2 市场洞察](#2-市场洞察)" in lines
        # H3 小节不进目录（收录面冻结——两级目录足够）
        assert "- [1.1 财务差距]" not in render_markdown_report(document)

    def test_toc_disabled_omitted(self) -> None:
        """toc_enabled=False 时目录章整体省略。"""
        document = _make_document((ReportSection(title="1 章", level=2),), toc_enabled=False)
        rendered = render_markdown_report(document)
        assert "## 目录" not in rendered


class TestBlockRendering:
    """四块型渲染。"""

    def test_paragraph_block(self) -> None:
        """paragraph 块：文本原样独立成段。"""
        document = _make_document(
            (
                ReportSection(
                    title="1.1 财务差距",
                    level=3,
                    blocks=(ReportBlock(kind="paragraph", text="财务差距结论文本"),),
                ),
            )
        )
        assert "财务差距结论文本" in render_markdown_report(document)

    def test_bullet_list_block_chinese_items(self) -> None:
        """bullet_list 块：`- ` 前缀逐项 + 中文原样。"""
        document = _make_document(
            (
                ReportSection(
                    title="1.3 根因分析",
                    level=3,
                    blocks=(ReportBlock(kind="bullet_list", items=("根因一：组织能力缺口", "根因二：流程效率不足")),),
                ),
            )
        )
        rendered = render_markdown_report(document)
        assert "- 根因一：组织能力缺口" in rendered
        assert "- 根因二：流程效率不足" in rendered

    def test_bullet_list_item_count_matches_source(self) -> None:
        """列表项数与源数据项数一致（三项源数据 → 恰三条 `- ` 行）。"""
        items = ("要点一", "要点二", "要点三")
        document = _make_document(
            (
                ReportSection(
                    title="小节",
                    level=3,
                    blocks=(ReportBlock(kind="bullet_list", items=items),),
                ),
            )
        )
        lines = [line for line in render_markdown_report(document).splitlines() if line.startswith("- ")]
        assert lines == [f"- {item}" for item in items]

    def test_table_block_full_structure(self) -> None:
        """table 块：表头 + 分隔行 + 数据行（GFM 管道表格完整形态）。"""
        document = _make_document(
            (
                ReportSection(
                    title="2.1 看趋势",
                    level=3,
                    blocks=(
                        ReportBlock(
                            kind="table",
                            headers=("维度", "评估"),
                            rows=(("政治", "政策稳定"), ("经济", "温和增长")),
                        ),
                    ),
                ),
            )
        )
        lines = render_markdown_report(document).splitlines()
        assert "| 维度 | 评估 |" in lines
        assert "| 政治 | 政策稳定 |" in lines
        assert "| 经济 | 温和增长 |" in lines
        # 结构序：表头行紧邻分隔行、数据行随后（定位表头 index 防元信息表分隔行串扰）
        header_index = lines.index("| 维度 | 评估 |")
        assert lines[header_index + 1] == "| --- | --- |"
        assert lines[header_index + 2] == "| 政治 | 政策稳定 |"
        assert lines[header_index + 3] == "| 经济 | 温和增长 |"

    def test_table_empty_rows_header_only(self) -> None:
        """空数据行边界：表头 + 分隔行仍在（零数据行）。"""
        document = _make_document(
            (
                ReportSection(
                    title="小节",
                    level=3,
                    blocks=(ReportBlock(kind="table", headers=("维度", "评估"), rows=()),),
                ),
            )
        )
        lines = render_markdown_report(document).splitlines()
        assert "| 维度 | 评估 |" in lines
        assert "| --- | --- |" in lines

    def test_callout_block_degraded_form(self) -> None:
        """callout 块降级形态：`> ` 前缀（> ⚠️ [降级] {display_name}：{原因}）。"""
        document = _make_document(
            (
                ReportSection(
                    title="2.1 看趋势",
                    level=3,
                    blocks=(ReportBlock(kind="callout", text="⚠️ [降级] 看趋势：降级（原因未随归档行结构化持久化）"),),
                ),
            )
        )
        assert "> ⚠️ [降级] 看趋势：降级（原因未随归档行结构化持久化）" in render_markdown_report(document)

    def test_callout_block_missing_data_form(self) -> None:
        """callout 块数据缺失形态：`> ` 前缀唯一块（缺行小节骨架）。"""
        document = _make_document(
            (
                ReportSection(
                    title="2.1 看趋势",
                    level=3,
                    blocks=(ReportBlock(kind="callout", text="⚠️ [数据缺失] 看趋势：该步骤归档记录不可用"),),
                ),
            )
        )
        assert "> ⚠️ [数据缺失] 看趋势：该步骤归档记录不可用" in render_markdown_report(document)

    def test_empty_bullet_list_renders_no_items(self) -> None:
        """空 items 边界：无 `- ` 行输出（不产生空列表项）。"""
        document = _make_document(
            (
                ReportSection(
                    title="小节",
                    level=3,
                    blocks=(
                        ReportBlock(kind="paragraph", text="段落"),
                        ReportBlock(kind="bullet_list", items=()),
                    ),
                ),
            )
        )
        lines = render_markdown_report(document).splitlines()
        assert not any(line.startswith("- ") for line in lines)
        assert "段落" in "\n".join(lines)

    def test_table_cell_pipe_escaped(self) -> None:
        r"""表格单元格含管道符 → `\|` 结构性转义（CR1-F4——GFM 语法内在要求）。

        LLM 自由文本 payload 值（如 PESTEL 评估「政策 | 稳定」）不得破坏列对齐：
        单元格内字面管道必须转义，表头与数据行同规则。
        """
        document = _make_document(
            (
                ReportSection(
                    title="小节",
                    level=3,
                    blocks=(
                        ReportBlock(
                            kind="table",
                            headers=("维度", "评|估"),
                            rows=(("政治", "政策 | 稳定"),),
                        ),
                    ),
                ),
            )
        )
        rendered = render_markdown_report(document)
        assert "| 维度 | 评\\|估 |" in rendered
        assert "| 政治 | 政策 \\| 稳定 |" in rendered
        # 未转义的字面管道不得出现在数据单元格（表头/分隔行的 | 是语法自身）
        assert "政策 | 稳定" not in rendered

    def test_table_cell_newline_normalized_to_space(self) -> None:
        """表格单元格含换行（\\n 与 \\r\\n）→ 归一空格（CR1-F4——防拆断表格/注入行）。"""
        document = _make_document(
            (
                ReportSection(
                    title="小节",
                    level=3,
                    blocks=(
                        ReportBlock(
                            kind="table",
                            headers=("维度", "评估"),
                            rows=(("政治", "政策\n稳定"), ("经济", "温和\r\n增长")),
                        ),
                    ),
                ),
            )
        )
        rendered = render_markdown_report(document)
        assert "| 政治 | 政策 稳定 |" in rendered
        assert "| 经济 | 温和 增长 |" in rendered
        assert "政策\n稳定" not in rendered  # 换行不得原样进入单元格

    def test_callout_multiline_text_prefixes_every_line(self) -> None:
        """callout 多行文本 → 逐行 `> ` 前缀（CR1-F5——防后续行脱离 blockquote 注入块结构）。"""
        document = _make_document(
            (
                ReportSection(
                    title="小节",
                    level=3,
                    blocks=(ReportBlock(kind="callout", text="⚠️ [降级] 看趋势：原因A\n第二行不得裸奔"),),
                ),
            )
        )
        lines = render_markdown_report(document).splitlines()
        assert "> ⚠️ [降级] 看趋势：原因A" in lines
        assert "> 第二行不得裸奔" in lines
        # 脱离前缀的裸行不得存在（注入面闭合）
        assert "第二行不得裸奔" not in [line for line in lines if not line.startswith("> ")]

    def test_paragraph_multiline_text_flattened_no_heading_injection(self) -> None:
        """paragraph 多行文本 → 换行归一空格 + 段首标题窄形态转义（CR2-F1）。

        `财务差距\n### 伪造标题` 若原样输出会注入 H3；归一后单行 + 首个 #
        前插 \\ 破坏标题解析。
        """
        document = _make_document(
            (
                ReportSection(
                    title="1.1 财务差距",
                    level=3,
                    blocks=(ReportBlock(kind="paragraph", text="财务差距结论\n### 伪造标题内容"),),
                ),
            )
        )
        rendered = render_markdown_report(document)
        lines = rendered.splitlines()
        # 单行归一：换行变空格（归一后 ### 在行中非段首——标题解析向量已消除）
        assert "财务差距结论 ### 伪造标题内容" in rendered
        assert "### 伪造标题内容" not in lines  # 无独立注入标题行（精确行——章节标题 ### 1.1 不受扰）

    def test_paragraph_leading_hash_heading_escaped(self) -> None:
        """paragraph 段首 ATX 标题形态 → 首个 # 转义（CR2-F1 窄形态）。"""
        document = _make_document(
            (
                ReportSection(
                    title="小节",
                    level=3,
                    blocks=(ReportBlock(kind="paragraph", text="### 伪造标题"),),
                ),
            )
        )
        lines = render_markdown_report(document).splitlines()
        assert "\\### 伪造标题" in lines
        assert "### 伪造标题" not in lines  # 未转义标题行不得独立存在（精确行）

    def test_paragraph_leading_hash_non_heading_text_untouched(self) -> None:
        """合法 `#1 排名` 文本不被转义（CR2-F1 窄形态无误伤断言——宽形态实现下此断言红）。

        GFM 中 `#` 后非空格不构成 ATX 标题，本就原样渲染——`#` 后带数字的
        合法文本（话题标签/排名标记）零扰动。
        """
        document = _make_document(
            (
                ReportSection(
                    title="小节",
                    level=3,
                    blocks=(ReportBlock(kind="paragraph", text="#1 排名：市场渗透率第一"),),
                ),
            )
        )
        lines = render_markdown_report(document).splitlines()
        assert "#1 排名：市场渗透率第一" in lines  # 无 \ 前缀（原样）
        assert "\\#1" not in render_markdown_report(document)

    def test_bullet_item_multiline_flattened(self) -> None:
        """bullet item 含换行 → 单行归一（CR2-F1——`- {item}` 后续行裸奔可注入块结构）。"""
        document = _make_document(
            (
                ReportSection(
                    title="小节",
                    level=3,
                    blocks=(ReportBlock(kind="bullet_list", items=("根因一：组织能力缺口\n| 伪造表格行",)),),
                ),
            )
        )
        rendered = render_markdown_report(document)
        lines = rendered.splitlines()
        assert "- 根因一：组织能力缺口 | 伪造表格行" in rendered  # 换行归一空格
        assert not any(line.startswith("| 伪造") for line in lines)  # 无注入表格行


class TestChineseAndSpecialCharacters:
    """中文与特殊字符原样输出（渲染层禁转义）。"""

    def test_chinese_and_special_chars_verbatim(self) -> None:
        """中文/全角括号/⚠️ emoji 原样（无 \\u 转义、无 HTML 实体）。"""
        special_text = "评估要点：政策稳定（≥85 分）＆ 监管友好 ⚠️"
        document = _make_document(
            (
                ReportSection(
                    title="小节",
                    level=3,
                    blocks=(ReportBlock(kind="paragraph", text=special_text),),
                ),
            )
        )
        rendered = render_markdown_report(document)
        assert special_text in rendered
        assert "\\u" not in rendered
        assert "&#" not in rendered

    def test_document_ends_with_newline(self) -> None:
        """文档以换行结尾（POSIX 文本文件惯例——L0 落盘可读性）。"""
        document = _make_document(())
        assert render_markdown_report(document).endswith("\n")


class TestMultipleSectionsAndBlocks:
    """多章节多块型组合渲染。"""

    def test_section_blocks_separated_by_blank_lines(self) -> None:
        """章节内多块间以空行分隔（Markdown 块语法边界）。"""
        document = _make_document(
            (
                ReportSection(
                    title="2.1 看趋势",
                    level=3,
                    blocks=(
                        ReportBlock(kind="paragraph", text="摘要段落"),
                        ReportBlock(kind="bullet_list", items=("发现一", "发现二")),
                    ),
                ),
            )
        )
        rendered = render_markdown_report(document)
        assert "摘要段落\n\n- 发现一" in rendered

    def test_full_document_rendering_pipeline(self) -> None:
        """全文档冒烟：H1+元信息+目录+两章三块型齐备渲染无异常。"""
        document = _make_document(
            (
                ReportSection(title="1 业绩差距分析", level=2),
                ReportSection(
                    title="1.1 财务差距",
                    level=3,
                    blocks=(ReportBlock(kind="paragraph", text="财务结论"),),
                ),
                ReportSection(
                    title="2.7 市场洞察综合",
                    level=3,
                    blocks=(ReportBlock(kind="bullet_list", items=("结论一", "结论二")),),
                ),
            )
        )
        rendered = render_markdown_report(document)
        assert rendered.startswith("# 战略规划报告（BLM 前两阶段）")
        assert "## 目录" in rendered
        assert "## 1 业绩差距分析" in rendered
        assert "### 1.1 财务差距" in rendered
        assert "### 2.7 市场洞察综合" in rendered
