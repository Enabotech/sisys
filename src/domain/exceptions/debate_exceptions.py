"""领域层红蓝辩论异常模块

红蓝辩论机制（单 Agent 多视角 MVP，Story 4.5）专属异常，包含视角生成失败、
风险视图合成失败与红蓝分化不足三类异常。

异常编码范围：EXCEPTION_420 ~ EXCEPTION_429（预留 10 个码）

设计理由（继承链选择）：
- DebateGenerationError(420) 继承 ExternalException：红/蓝视角生成的根因是外部 LLM
  服务调用失败，与 RelevanceEvaluationError(360) 继承链先例完全一致；HTTP 映射至
  500 Internal Server Error（精确注册避免 isinstance 回退到 ExternalException 基类 502）
- DebateSynthesisError(421) 继承 ExternalException：风险视图合成同为 LLM 调用失败，
  独立成类以区分"视角生成失败"与"合成失败"两个监控面（无法精确区分则监控无法精确告警）；
  HTTP 映射至 500（同 420 精确注册理由）
- DebateLowDivergenceError(422) 继承 BusinessException：红蓝视角重叠率 ≥ 0.95 表示两视角
  实质相同、辩论失去意义，属业务规则违反（LLM 调用本身成功，非外部故障）；HTTP 映射至
  422 Unprocessable Entity（与 RelevanceEvaluationBlockedError(361)→422 先例一致，
  精确注册避免回退到 BusinessException 基类 400）
- 不设 DebateError 子域基类：420/421 继承 ExternalException、422 继承 BusinessException，
  无法共享同一基类（项目规范必须继承三大抽象分层之一）；relevance 子域平铺无基类先例
  支持此设计

消息安全性：错误消息面向调用方可理解，不泄露 prompt 模板全文与内部实现细节。

结构化输出校验失败的包装链（2026-10-01 实测定谳）：小模型违反 json_schema 约束时，
pydantic ValidationError（继承 ValueError）被 LitellmLLMClient 外层 except 捕获，
重试耗尽统一抛 LLMResponseError，本模块将其经 cause 链入包装——裸 ValidationError
不会逃逸到调用方。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException
from src.domain.exceptions.external_exceptions import ExternalException


class DebateGenerationError(ExternalException):
    """红/蓝视角 LLM 生成调用失败

    当辩论任一视角（激进派红/保守派蓝）的 LLM 结构化生成调用出现不可恢复错误
    （如 API 调用失败、超时、结构化解析失败）时，由 RedBlueDebateService 包装抛出。
    LLM 底层异常经 cause 参数链入，不吞异常、不直接向调用方透传。

    继承 ExternalException，HTTP 映射至 500 Internal Server Error
    （精确注册避免 isinstance 回退到 ExternalException 基类 502）。

    Attributes:
        code: EXCEPTION_420
        message: 默认消息
        debate_id: 辩论会话 ID
        perspective: 失败视角（"red_aggressive" / "blue_conservative"）
        topic_title: 议题标题（截断至 100 字符）
    """

    code = "EXCEPTION_420"
    message = "红蓝辩论视角生成失败"

    def __init__(
        self,
        debate_id: str,
        perspective: str,
        topic_title: str,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化辩论视角生成失败错误

        Args:
            debate_id: 辩论会话 ID（字符串形式）
            perspective: 失败视角标识（"red_aggressive" / "blue_conservative"）
            topic_title: 议题标题（截断至 100 字符）
            message: 错误描述
            cause: 原始 LLM 底层异常
        """
        context: dict[str, str] = {
            "debate_id": debate_id,
            "perspective": perspective,
            "topic_title": topic_title[:100],
        }
        super().__init__(message=message, cause=cause, context=context)


class DebateSynthesisError(ExternalException):
    """风险视图合成 LLM 调用失败

    当红蓝视角生成成功后、风险全景视图（共识/分歧合成）的 LLM 结构化调用出现
    不可恢复错误时，由 RedBlueDebateService 包装抛出。与 DebateGenerationError
    分立两类以精确区分"视角生成失败"与"合成失败"监控面。

    继承 ExternalException，HTTP 映射至 500 Internal Server Error
    （精确注册避免 isinstance 回退到 ExternalException 基类 502）。

    Attributes:
        code: EXCEPTION_421
        message: 默认消息
        debate_id: 辩论会话 ID
        topic_title: 议题标题（截断至 100 字符）
    """

    code = "EXCEPTION_421"
    message = "红蓝辩论风险视图合成失败"

    def __init__(
        self,
        debate_id: str,
        topic_title: str,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化辩论风险视图合成失败错误

        Args:
            debate_id: 辩论会话 ID（字符串形式）
            topic_title: 议题标题（截断至 100 字符）
            message: 错误描述
            cause: 原始 LLM 底层异常
        """
        context: dict[str, str] = {
            "debate_id": debate_id,
            "topic_title": topic_title[:100],
        }
        super().__init__(message=message, cause=cause, context=context)


class DebateLowDivergenceError(BusinessException):
    """红蓝视角分化不足

    当红蓝两视角论点重叠率 ≥ 0.95（硬阈值）时抛出——两视角论点几乎完全相同，
    辩论失去对抗意义，属业务规则违反（LLM 调用本身成功，非外部故障）。
    注意：0.80 ≤ 重叠率 < 0.95 为分化偏弱警告（RiskView.warnings 正常输出），
    不抛异常——质量问题硬失败会损害可用性，重试机制属 Story 4.7 体系。

    继承 BusinessException，HTTP 映射至 422 Unprocessable Entity
    （与 RelevanceEvaluationBlockedError(361) 先例一致，精确注册避免回退 400）。

    Attributes:
        code: EXCEPTION_422
        message: 默认消息
        debate_id: 辩论会话 ID
        overlap_rate: 红蓝重叠率（触发时 ≥ 0.95）
        red_summary: 红方论点摘要（截断至 100 字符）
        blue_summary: 蓝方论点摘要（截断至 100 字符）
    """

    code = "EXCEPTION_422"
    message = "红蓝辩论视角分化不足"

    def __init__(
        self,
        debate_id: str,
        overlap_rate: float,
        red_summary: str,
        blue_summary: str,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化辩论分化不足错误

        Args:
            debate_id: 辩论会话 ID（字符串形式）
            overlap_rate: 红蓝重叠率（触发时 ≥ 0.95）
            red_summary: 红方论点摘要（截断至 100 字符）
            blue_summary: 蓝方论点摘要（截断至 100 字符）
            message: 错误描述
            cause: 原始异常
        """
        context: dict[str, str | float] = {
            "debate_id": debate_id,
            "overlap_rate": overlap_rate,
            "red_summary": red_summary[:100],
            "blue_summary": blue_summary[:100],
        }
        super().__init__(message=message, cause=cause, context=context)


__all__ = [
    "DebateGenerationError",
    "DebateSynthesisError",
    "DebateLowDivergenceError",
]
