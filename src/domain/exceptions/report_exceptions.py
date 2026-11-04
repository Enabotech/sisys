"""report 子域异常（Story 6-5a 开段 + 6-5b 扩展——报告交付物域）。

开段依据：planning 段 (480,489) 中 485 预留、486-489 成文「留 6-6 恢复执行面」
不可占；报告交付物语义独立（报告 ≠ 规划流程）——按「前段满/双重成文预留不可
占/语义独立 → 开独立段」八代开段先例（data_source 410/debate 420/tool_version
430/agent 440/evaluation 450/sap 460/financial 470/planning 480）开 report 段
(490, 499)。

四类异常：
- ``ReportGenerationError``（EXCEPTION_490，404 语义）：报告数据源全缺
  （chain total==0——plan 从未跑过与归档全失败两形态同判；PlanningNotFoundError
  480 同族）
- ``ReportStorageError``（EXCEPTION_491，500 语义）：报告持久化失败（L0 写
  失败 layer="l0" / L2 落库失败 layer="l2"——二元值域；**事件发布失败不走本
  异常**：AC-5 宽容语义 warning 不回滚——上抛回滚不了已落盘 L0/L2）
- ``PdfRenderingError``（EXCEPTION_492，500 语义，6-5b）：PDF 渲染失败
  （reportlab 渲染异常/中文字体注册失败/文档模型渲染期非法/未注册锚点
  引用 save 期抛错——reportlab 原生异常的领域包装；context 携带 plan_id）
- ``ReportEvidenceStorageError``（EXCEPTION_493，500 语义，6-5b）：L4 证据
  对象归档失败（``L4ObjectPort.archive`` 抛异常/返回异常态——**开新码不复用
  491**：491 值域二元 {l0,l2} 是 6-5a 冻结面且负向测试钉死，扩值域即破坏；
  最小契约变更原则取新码）
"""

from src.domain.exceptions.business_exceptions import BusinessException

__all__ = [
    "PdfRenderingError",
    "ReportEvidenceStorageError",
    "ReportGenerationError",
    "ReportStorageError",
]


class ReportGenerationError(BusinessException):
    """报告数据源全缺（EXCEPTION_490——404 语义）。

    触发场景：ReportGenerationService 聚合 chain 归档时 total==0（plan 从未
    跑过与跑过归档全失败两形态在持久真源同形同判——报告读侧以 PG 行为准）；
    最新快照在位亦同判（时间线摘要非报告素材）。
    """

    code = "EXCEPTION_490"
    message = "该 plan_id 无思维链归档记录，无法生成报告"

    def __init__(
        self,
        plan_id: str,
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """构造报告数据源全缺异常。

        Args:
            plan_id: 无归档记录的规划任务标识。
            message: 覆写消息（缺省回落类静态文案——可观测事实口径）。
            cause: 底层异常（可选）。
            context_extra: 附加领域上下文（合并进 context）。
        """
        context: dict[str, str] = {"plan_id": plan_id}
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)


class ReportStorageError(BusinessException):
    """报告持久化失败（EXCEPTION_491——500 语义）。

    触发场景：L0 报告文件写失败（layer="l0"）或 L2 元数据行落库失败
    （layer="l2"）。layer 值域二元自有（语境借鉴 284 但值域独立——284 值域
    (l2,l3,l4,l5) 不含 l0，照抄即漏）。
    """

    code = "EXCEPTION_491"
    message = "报告持久化失败"

    #: layer 合法值域（二元——L0 文件/L2 元数据行；自有元组禁复用 284 常量）
    _VALID_LAYERS = ("l0", "l2")

    def __init__(
        self,
        layer: str,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """构造报告持久化失败异常。

        Args:
            layer: 失败存储层（"l0" 文件写 / "l2" 元数据落库——二元值域）。
            message: 覆写消息（缺省组合 layer 语境）。
            cause: 底层异常（可选——文件系统/数据库驱动异常）。

        Raises:
            EntityValidationError: layer 不在二元值域（242 守卫——家族形态
                同构 284）。
        """
        from src.domain.exceptions import EntityValidationError

        if layer not in self._VALID_LAYERS:
            raise EntityValidationError(
                message=f"layer 必须为 {self._VALID_LAYERS} 之一（二元值域）",
                context={"entity": "ReportStorageError", "field": "layer", "layer": layer},
            )
        self.layer = layer
        if message is None:
            message = f"报告持久化失败（{layer} 层）"
        super().__init__(message, cause=cause, context={"layer": layer})


class PdfRenderingError(BusinessException):
    """PDF 渲染失败（EXCEPTION_492——500 语义，Story 6-5b）。

    触发场景：reportlab 渲染异常（文档模型渲染期非法）/中文字体注册失败
    （STSong-Light）/未注册锚点引用（save 期 ``ValueError: format not
    resolved``——悬空链接天然守护路径）——reportlab 原生异常的领域包装，
    context 携带 plan_id。
    """

    code = "EXCEPTION_492"
    message = "PDF 报告渲染失败"

    def __init__(
        self,
        plan_id: str,
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """构造 PDF 渲染失败异常（领域参在前——同构 490 形态）。

        Args:
            plan_id: 渲染失败的规划任务标识。
            message: 覆写消息（缺省回落类静态文案）。
            cause: 底层异常（reportlab 原生异常——渲染包装主形态）。
            context_extra: 附加领域上下文（合并进 context）。
        """
        context: dict[str, str] = {"plan_id": plan_id}
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)


class ReportEvidenceStorageError(BusinessException):
    """L4 证据对象归档失败（EXCEPTION_493——500 语义，Story 6-5b）。

    触发场景：``L4ObjectPort.archive`` 抛异常或返回异常态（MinIO 不可达/
    WORM retention 设置失败等）——PDF bytes 归档 L4 WORM 的失败面。
    开新码不复用 491（OD-10）：491 ``_VALID_LAYERS=("l0","l2")`` 二元值域
    是 6-5a 冻结面且有负向测试钉死（"l4" 现为非法值抛 242——扩值域即破坏）。
    """

    code = "EXCEPTION_493"
    message = "PDF 报告证据归档失败"

    def __init__(
        self,
        plan_id: str,
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """构造 L4 证据归档失败异常（领域参在前——同构 490 形态）。

        Args:
            plan_id: 归档失败的规划任务标识。
            message: 覆写消息（缺省回落类静态文案）。
            cause: 底层异常（存储驱动/WORM 治理异常）。
            context_extra: 附加领域上下文（合并进 context）。
        """
        context: dict[str, str] = {"plan_id": plan_id}
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)
