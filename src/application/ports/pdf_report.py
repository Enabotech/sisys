"""PDF 报告端口契约（Story 6-5b——双端口 + 模块常量单源）。

端口契约区（Task 0.3 规范落档的实现承载）：

**对象键与桶（OD-4）**
- ``EVIDENCE_BUCKET_TYPE = "archive-evidence"``——L4 bucket_type 单源，
  与 6-3/6-4 证据归档同桶（``strategic_archive_service.L4_BUCKET_TYPE``
  代码单源对齐：evidence_refs 上游 EVIDENCE_PACKAGE 归档即在此桶，证据
  流一桶贯通；对象键 ``reports/`` 前缀与归档键 ``{archive_id}/`` 前缀
  天然隔离零互撞）；
- ``PDF_OBJECT_KEY_TEMPLATE = "reports/{plan_id}/{report_id}.pdf"``——
  对象键逻辑路径模板（键锚 report_id 天然唯一：每 report 恰一对象，
  无同秒覆写/WORM 冲突形态；``StrategicReport.file_path`` 存此值）。

**引文三段链契约（AC-3/OD-6）**
- ①收集：``query_archive(ArchiveQuery(plan_id, archive_type=EVIDENCE_PACKAGE,
  limit=64))`` 逐行 ``assumptions.get("evidence_refs", [])``（list[str]
  chunk_id），跨步骤去重保序（首现次序即索引号；limit=64 显式传参为
  同型行扩展余量——对齐 6-4 ``_TRACE_QUERY_LIMIT=50`` 先例）；
- ②解析：每 chunk_id 经 ``L3VectorPort.get_point(collection, chunk_id)``
  取 payload（document_id/chunk_header）→ payload["document_id"]（str
  → ``uuid.UUID`` 显式转换；缺 document_id/非法 UUID 同判 ``point_missing``
  ——检索点信息缺失伞形）→ ``DocumentRepositoryPort.find(DocumentQuery(
  tenant_id=服务注入租户, document_id=...))`` 取 filename +
  ``metadata["chunks"]`` 按 chunk_id 匹配取 page_start；
- ③组装：附录 C section（H2 ``附录 C 引文索引``——标题常量
  ``APPENDIX_C_TITLE`` 单源）table 块型四列
  （``# / 文档名 / 页码 / 切片标识``——切片标识列 chunk_id 前 8 位截断
  显示，完整值入 L2 metadata）。

**解析降级三态判定（宽容——引文是增强面非阻断面）**
- ``get_point`` 无点（chunk 已删/collection 不含）→ ``point_missing``：
  条目 ``[n] [溯源不可用：检索点缺失]``；
- documents 行缺失 → ``document_missing``：条目 ``[n] [溯源不可用：
  文档记录缺失]``；
- chunks 元数据无该 chunk_id → 页码不可得：status 仍 ``resolved`` +
  page=0（渲染层 0→``-``，文档名仍可得）；
- 降级不阻断报告生成——计数入 L2 metadata ``unresolvable_citation_count``；
  **整体容错边界**：引文聚合整体 try 容错——解析链任一依赖异常
  （``query_archive``/``get_point``/``find`` 抛异常）时降级为空附录 C
  单行说明 + log warning、报告照常生成（增强面故障不炸主链——与事件
  发布宽容哲学同构）。

**CitationEntry 值域**：见 ``src/domain/value_objects/citation_entry.py``
（status 三元组冻结 resolved/point_missing/document_missing）。

**注入形态（R2 九依赖 + 两构造参数）**
- 九依赖 keyword-only：chain_archive_service / snapshot_repository /
  report_repository / event_publisher / pdf_renderer / l4_object /
  l3_vector / document_repository / archive_service；
- collection/tenant_id 是**服务构造参数**（配置态注入非依赖态）：
  collection 默认 ``"documents"``（与 chunk 索引写侧 collection 字面量
  对齐——``chunk_indexing_handler.py`` upsert 同值；非 ``BLM_SEARCH_COLLECTION``
  env 传导，env 覆写只影响检索服务侧）；tenant_id 默认 ``str(MVP_TENANT_ID)``（
  ``agent_workflow_context.py`` MVP 单租户——DocumentQuery.tenant_id
  必填且 PG find 硬过滤，数据链无租户可用注入是唯一来源；多租户归
  后续 Story）；测试经构造参数覆写注入（与 6-5a L0 tmp_path 服务实例
  层注入同款可测试性形态，不走注册表覆写）。
"""

import re
import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.domain.entities.strategic_report import StrategicReport
from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.markdown_report import MarkdownReportDocument

__all__ = [
    "APPENDIX_C_TITLE",
    "BrandRenderSpec",
    "EVIDENCE_BUCKET_TYPE",
    "PDF_OBJECT_KEY_TEMPLATE",
    "PdfRendererPort",
    "PdfReportGenerationServicePort",
]

#: L4 证据桶类型（archive-evidence——6-3/6-4 证据归档同桶单源对齐，OD-4）
EVIDENCE_BUCKET_TYPE: str = "archive-evidence"

#: PDF 对象键逻辑路径模板（键锚 report_id 天然唯一——file_path 存此值，OD-4）
PDF_OBJECT_KEY_TEMPLATE: str = "reports/{plan_id}/{report_id}.pdf"

#: 附录 C 冻结标题（增量冻结表钦定——编排层组装与渲染层锚点特判的单源常量）
APPENDIX_C_TITLE: str = "附录 C 引文索引"

#: 6 位 hex 色格式（BrandRenderSpec 五色键守卫——``^#[0-9A-Fa-f]{6}$``）
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class BrandRenderSpec:
    """白标渲染规格 VO（Story 6-11——渲染器直消费形态，7 键冻结契约）。

    「静态值域=冻结常量」单源在 application ports（COLOR_SCHEME_PRESETS/
    FONT_PRESETS 供给预设键→本 VO 的组装归应用服务 ``get_render_spec``）；
    渲染器（infrastructure）import 本 VO 合法（依赖方向矩阵 infra→application
    ✓ 允许）。**logo 是 bytes 非对象键**：L4 读取归应用服务，渲染器零 IO
    纯函数纪律保持（6-5b OD-3 同源双渲染纪律延续）。

    构造契约（R1 钦定）：五色键+font_name **必填**（缺省构造 TypeError——
    必填即判别保证：默认值不得与渲染器默认参数同值是默认态等价突变锚的
    判别前提，必填形态从根上排除同值默认风险）；logo 唯一可选默认 None。

    Attributes:
        font_name: 字体注册名（CID 名直用如 "STSong-Light"/TTF 注册名如
            "NotoSansSC"——TTF 注册通道归渲染器 ``_ensure_font`` 幂等承载）。
        title_color: H1/H2 标题文字色（6 位 hex——新能力，渲染器默认无
            textColor 即黑）。
        header_bg_color: 表头行底色（渲染器默认 #E8E8E8）。
        grid_color: 表格网格线色（渲染器默认 #BBBBBB）。
        callout_bg_color: callout 底色（渲染器默认 #F2F2F2）。
        callout_text_color: callout 文字色（渲染器默认 #444444）。
        logo: Logo 图片字节（PNG/JPEG——None 表示无 Logo[零品牌 logo 流]；
            品牌三要素中配色/字体独立生效）。

    Raises:
        EntityValidationError: 五色键任一非 6 位 hex 格式（242——application
            VO 抛 242 先例[consultant_view.py:66-91 等六文件]）。
    """

    font_name: str
    title_color: str
    header_bg_color: str
    grid_color: str
    callout_bg_color: str
    callout_text_color: str
    logo: bytes | None = None

    def __post_init__(self) -> None:
        """构造期 hex 格式守卫（五色键逐键——fail-loud）。"""
        for key in ("title_color", "header_bg_color", "grid_color", "callout_bg_color", "callout_text_color"):
            value: str = getattr(self, key)
            if not _HEX_COLOR_PATTERN.match(value):
                raise EntityValidationError(
                    message=f"{key} 必须为 6 位 hex 颜色（如 #1F4E79）",
                    context={"vo": "BrandRenderSpec", "field": key, "value": value},
                )


@runtime_checkable
class PdfRendererPort(Protocol):
    """PDF 渲染端口（R2 具体应用端口——reportlab 技术实现的抽象面）。

    同步方法（reportlab 纯 CPU 渲染无 I/O——量级评估：亚秒级 CPU 段在
    并发下互斥执行放大有限，不经 to_thread）；bytes 返回端口先例
    ``PdfPageRendererPort.render_page``；引文附录已在编排层组装进
    document VO——渲染器纯渲染，与 ``render_markdown_report`` 同
    入参对称（OD-3 同源双渲染）。

    端口版本 v1.1.0（Story 6-11）：增 keyword-only 可选参 ``brand``
    （默认 None 走既有路径——零品牌调用等价回归[invariant=1 测试前置下
    byte 级对照]；既有单参调用零破坏——兼容性元组 ("v1.0.0",)）。
    """

    def render(
        self,
        document: MarkdownReportDocument,
        *,
        brand: BrandRenderSpec | None = None,
    ) -> bytes:
        """渲染双渲染共用 IR 为 PDF bytes（品牌可选应用）。

        Args:
            document: 6-5a 聚合产物（附录 C 已组装）。
            brand: 白标渲染规格（None=默认态——字体 STSong-Light/默认四色/
                零 logo 流，产物与 v1.0.0 单参调用等价）。

        Returns:
            PDF 文件字节流。
        """
        ...


@runtime_checkable
class PdfReportGenerationServicePort(Protocol):
    """PDF 报告生成服务端口（六段编排+品牌前置小步——与 ReportGenerationServicePort 并列）。

    编排六段：①chain 归档主源聚合复用（``aggregate_report_document``——
    6-5a 聚合公开化）→ ②latest 快照辅源（容错）→ ③引文聚合（三段链）
    → ④PDF 渲染 → ⑤L4 WORM 归档 + L2 元数据行 → ⑥ReportGenerated 事件
    （report_type="pdf"）。

    端口版本 v1.1.0（Story 6-11）：增 keyword-only 可选参
    ``brand_template_name``（默认 None 零品牌路径——兼容性元组 ("v1.0.0",)；
    白标导出经 ``get_render_spec`` 组装 BrandRenderSpec 双参渲染+metadata
    品牌两键）。
    """

    async def generate_pdf_report(
        self,
        plan_id: uuid.UUID,
        *,
        brand_template_name: str | None = None,
    ) -> StrategicReport:
        """按 plan_id 生成 PDF 报告（品牌模板可选应用）。

        Args:
            plan_id: 规划任务标识。
            brand_template_name: 品牌模板名（None=默认态——v1.0.0 行为等价；
                非 None 时前置组装渲染规格，品牌失败不降级为非白标导出）。

        Returns:
            StrategicReport 实体（report_type=PDF、file_path=对象键逻辑路径）。

        Raises:
            BrandTemplateValidationError: 494——品牌模板不存在/预设键脏。
            ReportGenerationError: 490——数据源全缺（chain total==0）。
            PdfRenderingError: 492——PDF 渲染失败。
            ReportEvidenceStorageError: 493——L4 证据归档失败。
            ReportStorageError: 491（layer="l2"）——L2 元数据行落库失败。
        """
        ...
