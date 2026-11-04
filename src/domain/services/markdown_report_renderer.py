"""Markdown 报告渲染器纯函数（Story 6-5a——BLM 报告章节结构领域知识）。

渲染规则 = BLM 方法论领域知识的一部分（报告章节结构/基础格式化冻结表）：
- ATX 标题（``#``/``##``/``###`` 严格 1-3 递进；禁 Setext——组内行标签用
  加粗行标签承载不开 H4）
- GFM 管道表格（表头 + ``| --- |`` 分隔行 + 数据行，列数严格一致）
- 无序列表 ``- `` 前缀；callout ``> `` 前缀（降级/数据缺失标注；多行文本
  逐行补前缀——合法多行 blockquote，CR1-F5）
- 中文与特殊字符原样输出（渲染层禁 **unicode/中文语义**转义——
  ``ensure_ascii=False`` 语义）；**GFM 结构性字符处理例外（CR1-F4 限定）**：
  表格单元格内 ``|`` 转义为 ``\\|``、换行归一空格——GFM 语法内在要求（防
  LLM 自由文本 payload 值破坏列对齐/注入表格行），不属「禁转义」条款范围
- 目录锚点算法：GitHub 风格 slug（标题小写化 + 空格→连字符 + 去除标点、
  中文原样保留）；收录面 = H2 章级 + 附录（H3 小节不进目录——两级目录足够）

纯函数零副作用：入参 MarkdownReportDocument，返回 str 文本；不做任何 I/O。
"""

import re

from src.domain.value_objects.markdown_report import (
    MarkdownReportDocument,
    ReportBlock,
    ReportSection,
)

__all__ = ["render_markdown_report"]

#: 元信息表表头（两列表冻结——| 项目 | 值 |）
_META_TABLE_HEADERS: tuple[str, str] = ("项目", "值")

#: 目录章标题（固定——toc_enabled 时渲染）
_TOC_TITLE: str = "目录"

#: 标题层级 → ATX 前缀映射（1-3 冻结）
_ATX_PREFIXES: dict[int, str] = {1: "#", 2: "##", 3: "###"}

#: GitHub slug 标点清除正则（保留 Unicode 字母/数字/下划线/空格/连字符——中文原样）
_SLUG_PUNCTUATION_PATTERN = re.compile(r"[^\w\s-]", flags=re.UNICODE)


def _github_slug(title: str) -> str:
    """GitHub 风格标题 slug（目录锚点算法冻结）。

    标题小写化 + 去除标点（中文原样保留）+ 空格转连字符——如
    ``1 业绩差距分析`` → ``1-业绩差距分析``。

    Args:
        title: 章节标题。

    Returns:
        slug 字符串（目录锚点 ``#`` 后缀用）。
    """
    lowered = title.strip().lower()
    cleaned = _SLUG_PUNCTUATION_PATTERN.sub("", lowered)
    return cleaned.replace(" ", "-")


#: 段首 ATX 标题形态（窄转义判别——0-3 前导空格 + 1-6 个 # + 空白/行尾；
#: `#` 后非空格的合法文本如 ``#1 排名`` 不命中零误伤——CR2-F1 评审窄形态）
_ATX_HEADING_PATTERN = re.compile(r" {0,3}#{1,6}(?:\s|$)")


def _flatten_inline(text: str) -> str:
    """行内文本换行归一（CR2-F1——``\\r\\n``/``\\r``/``\\n`` → 空格）。

    paragraph/bullet 出口归一：多行文本拆行会注入任意块结构（标题/表格/
    列表）。与表格单元格归一同链（``_escape_cell`` 组合消费）。

    Args:
        text: 原始行内文本。

    Returns:
        单行文本。
    """
    return text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def _escape_leading_hash(text: str) -> str:
    """段首 ATX 标题形态的行首 ``#`` 转义（CR2-F1 窄形态——仅首个 ``#``）。

    在首个 ``#`` 前插入 ``\\`` 破坏标题解析（``\\###`` 渲染回 ``###`` 原文）；
    保留 0-3 前导空格原位。

    Args:
        text: 已判定命中标题形态的单行文本。

    Returns:
        转义后文本。
    """
    index = len(text) - len(text.lstrip(" "))
    return text[:index] + "\\" + text[index:]


def _escape_cell(text: str) -> str:
    """GFM 表格单元格结构性字符归一（CR1-F4——语法内在要求非 unicode 转义）。

    ``|`` 转义为 ``\\|``（GFM 字面管道标准形态）；换行归一空格（单元格内
    本就无法存在换行——防注入拆断表格）。中文原样。

    Args:
        text: 单元格原始文本。

    Returns:
        归一后单元格文本。
    """
    return _flatten_inline(text.replace("|", "\\|"))


def _render_table(headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> list[str]:
    """渲染 GFM 管道表格（表头 + 分隔行 + 数据行；单元格结构性转义）。

    Args:
        headers: 表头元组。
        rows: 数据行元组（列数已由 VO 构造期守卫保证一致）。

    Returns:
        表格文本行列表（空表头时返回空列表——零列表格无 Markdown 语法）。
    """
    if not headers:
        return []
    lines = [f"| {' | '.join(_escape_cell(header) for header in headers)} |"]
    lines.append(f"| {' | '.join('---' for _ in headers)} |")
    for row in rows:
        lines.append(f"| {' | '.join(_escape_cell(cell) for cell in row)} |")
    return lines


def _render_block(block: ReportBlock) -> list[str]:
    """渲染单个内容块（四块型分派）。

    Args:
        block: 内容块（kind 白名单已由 VO 构造期守卫保证）。

    Returns:
        块文本行列表（空 items 边界返回空列表——无空列表项）。
    """
    if block.kind == "paragraph":
        if not block.text:
            return []
        flattened = _flatten_inline(block.text)
        # 段首标题注入防护（CR2-F1 窄形态）：命中 ATX 标题形态时仅转义首个 #
        # ——合法文本（# 后非空格如「#1 排名」）不命中零误伤；bullet 渲染形态
        # `- {item}` 中 # 非行首本无向量，不在此处理
        if _ATX_HEADING_PATTERN.match(flattened):
            flattened = _escape_leading_hash(flattened)
        return [flattened]
    if block.kind == "bullet_list":
        return [f"- {_flatten_inline(item)}" for item in block.items]
    if block.kind == "table":
        return _render_table(block.headers, block.rows)
    # callout（降级/数据缺失标注——`> ` 前缀；多行文本逐行补前缀防后续行
    # 脱离 blockquote 注入块结构，CR1-F5）
    return [f"> {line}" for line in block.text.splitlines()] if block.text else []


def _render_section(section: ReportSection) -> list[str]:
    """渲染章节（ATX 标题行 + 块内容，块间空行分隔）。

    Args:
        section: 章节VO。

    Returns:
        章节文本行列表（标题与首块间空行；空块过滤不产生空段）。
    """
    prefix = _ATX_PREFIXES[section.level]
    lines = [f"{prefix} {section.title}"]
    block_line_groups = [block_lines for block in section.blocks if (block_lines := _render_block(block))]
    for block_lines in block_line_groups:
        lines.append("")
        lines.extend(block_lines)
    return lines


def render_markdown_report(document: MarkdownReportDocument) -> str:
    """渲染 Markdown 报告文本（纯函数——领域渲染规则单源）。

    结构序：H1 封面标题 → 元信息两列表 → 目录（toc_enabled 时，收录 H2
    章级 + 附录）→ 正文章节逐个渲染。中文与特殊字符原样输出（GFM 结构性
    字符转义限定见模块 docstring——CR1-F4）。

    Args:
        document: 报告文档 VO（应用层聚合产物）。

    Returns:
        Markdown 文本（以换行结尾）。
    """
    sections_out: list[list[str]] = []
    # H1 封面标题
    sections_out.append([f"# {document.title}"])
    # 元信息两列表（| 项目 | 值 | 冻结表头）
    sections_out.append(_render_table(_META_TABLE_HEADERS, document.meta_rows))
    # 目录（收录面冻结：H2 章级 + 附录；H3 不进）
    if document.toc_enabled:
        toc_entries = [section for section in document.sections if section.level == 2]
        if toc_entries:
            toc_lines = [f"## {_TOC_TITLE}"]
            for section in toc_entries:
                toc_lines.append(f"- [{section.title}](#{_github_slug(section.title)})")
            sections_out.append(toc_lines)
    # 正文章节
    for section in document.sections:
        sections_out.append(_render_section(section))
    # 章节间空行拼接 + 文末换行（空段落过滤——空元信息/零章节形态不产生空块）
    body = "\n\n".join("\n".join(lines) for lines in sections_out if lines)
    return f"{body}\n" if body else "\n"
