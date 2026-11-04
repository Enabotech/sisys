"""报告文档模型值对象（Story 6-5a——渲染器入参载体）。

应用层聚合服务（ReportGenerationService）将双源数据（chain 归档 payload +
latest 快照 timeline）组装为 MarkdownReportDocument，交领域渲染纯函数
（markdown_report_renderer）输出 Markdown 文本。

层级契约：domain 不得依赖 application（importlinter 方向矩阵）——故本 VO
不直接消费 ChainOfThoughtTraceView/BlmPlanningResult 等应用层 DTO，由应用
层负责 DTO → VO 的组装映射。

四块型冻结（AC-3 三要素 + callout）：paragraph（段落）/ bullet_list（无序
列表）/ table（GFM 管道表格）/ callout（降级与数据缺失标注——`> ` 前缀）。
"""

from dataclasses import dataclass, field

from src.domain.exceptions import EntityValidationError

__all__ = ["MarkdownReportDocument", "ReportBlock", "ReportSection"]

#: 块型白名单（四块型冻结——增减即渲染契约变更）
_VALID_BLOCK_KINDS: tuple[str, ...] = ("paragraph", "bullet_list", "table", "callout")

#: 标题层级值域（1-3——H1/H2/H3 严格递进不开 H4；与 AC-3 字面与校验三方对齐）
_VALID_SECTION_LEVELS: tuple[int, ...] = (1, 2, 3)


@dataclass(frozen=True)
class ReportBlock:
    """报告内容块（联合形态单类 + kind 判别——四块型冻结）。

    单类四形态而非四子类：渲染器按 kind 分派私有渲染函数，避免继承层次
    （块型是数据形态差异非行为多态——渲染逻辑单源在渲染器）。

    Attributes:
        kind: 块型（paragraph/bullet_list/table/callout——白名单校验）。
        text: paragraph 与 callout 的文本载荷。
        items: bullet_list 的列表项元组。
        headers: table 的表头元组。
        rows: table 的数据行元组（每行列数 == len(headers)——构造期守卫）。
    """

    kind: str
    text: str = ""
    items: tuple[str, ...] = ()
    headers: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()

    def __post_init__(self) -> None:
        """构造期块型守卫（违例抛 EntityValidationError 242）。

        Raises:
            EntityValidationError: kind 不在四块型白名单；或 table 块存在
                列数不一致的数据行（GFM 管道表格列对齐守卫）。
        """
        if self.kind not in _VALID_BLOCK_KINDS:
            raise EntityValidationError(
                message=f"块型必须为 {_VALID_BLOCK_KINDS} 之一（四块型冻结）",
                context={"entity_type": "ReportBlock", "field": "kind", "kind": self.kind},
            )
        if self.kind == "table":
            for row in self.rows:
                if not isinstance(row, tuple):
                    raise EntityValidationError(
                        message="表格数据行必须为 tuple 形态（str 行 len 巧合撞列数不可静默通过）",
                        context={"entity_type": "ReportBlock", "field": "rows", "row_type": type(row).__name__},
                    )
                if len(row) != len(self.headers):
                    raise EntityValidationError(
                        message="表格数据行列数必须与表头列数一致（GFM 管道表格列对齐守卫）",
                        context={
                            "entity_type": "ReportBlock",
                            "field": "rows",
                            "header_columns": str(len(self.headers)),
                            "row_columns": str(len(row)),
                        },
                    )


@dataclass(frozen=True)
class ReportSection:
    """报告章节（display_name 逐字源——标题由应用层从语义配置取值组装）。

    Attributes:
        title: 章节标题（含位置编号拼接——如 ``1 业绩差距分析`` / ``2.7 市场洞察综合``）。
        level: 标题层级（1-3——ATX ``#`` 计数；H4 不开——组内行标签用加粗
            行标签形态承载，R1 预裁定）。
        blocks: 内容块元组（缺行小节骨架形态 = 单 callout 块——R3-1 冻结）。
    """

    title: str
    level: int
    blocks: tuple[ReportBlock, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """构造期层级守卫（违例抛 EntityValidationError 242）。

        Raises:
            EntityValidationError: level 不在 1-3 值域（level=4 无渲染语法，
                放行即缺陷——R2-6 收窄）。
        """
        if self.level not in _VALID_SECTION_LEVELS:
            raise EntityValidationError(
                message="章节层级必须在 1-3 值域（H1/H2/H3 严格递进不开 H4）",
                context={"entity_type": "ReportSection", "field": "level", "level": str(self.level)},
            )


@dataclass(frozen=True)
class MarkdownReportDocument:
    """Markdown 报告文档根（应用层聚合产物 → 渲染器入参）。

    Attributes:
        plan_id: 规划任务标识（元信息表与正文锚定）。
        title: 封面 H1 标题（REPORT_TITLE_TEMPLATE 端口常量源）。
        meta_rows: 元信息表两列元组（``| 项目 | 值 |`` 表数据源）。
        sections: 章节元组（含封面后全部章节——目录由渲染器派生）。
        toc_enabled: 目录开关（True 时渲染「目录」章 + 锚点链接）。
    """

    plan_id: str
    title: str
    meta_rows: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    sections: tuple[ReportSection, ...] = field(default_factory=tuple)
    toc_enabled: bool = True

    def __post_init__(self) -> None:
        """构造期文档根守卫（CR2-F2——VO 家族守卫对称补全，违例抛 242）。

        Raises:
            EntityValidationError: title/plan_id 为空或纯空白；meta_rows 混入
                非 tuple 行或列数非 2（裸 str 行经渲染器字符级迭代静默错位
                ——ReportBlock「str 行 len 巧合」同族防呆）；sections 含
                level=1 章节（H1 单源 = document.title——渲染器 :146 自写 H1，
                sections 内 level=1 会产出第二 H1 破坏结构契约，CR1-F30(a)）。
        """
        if not self.title.strip() or not self.plan_id.strip():
            raise EntityValidationError(
                message="文档根 title/plan_id 不可为空（封面标题与标识锚定）",
                context={"entity_type": "MarkdownReportDocument", "field": "title/plan_id"},
            )
        for row in self.meta_rows:
            if not isinstance(row, tuple) or len(row) != 2:
                raise EntityValidationError(
                    message="meta_rows 每行必须为二元 tuple（| 项目 | 值 | 两列表——裸 str 行字符级迭代静默错位）",
                    context={"entity_type": "MarkdownReportDocument", "field": "meta_rows", "row_type": type(row).__name__},
                )
        for section in self.sections:
            if section.level == 1:
                raise EntityValidationError(
                    message="sections 内禁止 level=1 章节（H1 单源 = document.title——CR1-F30(a)）",
                    context={"entity_type": "MarkdownReportDocument", "field": "sections", "section_title": section.title},
                )
