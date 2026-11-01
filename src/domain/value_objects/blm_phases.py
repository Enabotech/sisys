"""领域层 BLM 规划值对象与枚举（Story 6-1 — BLM 前两阶段流程）

BLM（Business Leadership Model）前两阶段的概念载体：阶段/子步骤枚举与
流程状态、阶段产物四值对象。MVP 口径下阶段 1/2 由 CEO Agent 单角色承担
（FR-SP-01——完整版多角色归 Epic 9）。

出处：
- or.md §五.2（L379-415）：BLM 六阶段总纲——阶段 1 业绩差距分析 +
  阶段 2 市场洞察六子步骤（看趋势/看市场与客户/看竞争/看自己/看机会/
  机会差距分析——OD-2 口径钦定，架构稿「2.6_看风险」为过时表述不采用）。
- sisys-core-domain-design.md §17.4.2（L1803-1974）：阶段 1 产物四字段
  语义（financial_gap/operational_gap/root_causes/portfolio_health——
  OD-3 仅取流程结构与产物字段语义，多角色/Checkpoint 调用形态归 V1/6.3）。

校验语义：__post_init__ 为 VO 构造器守卫——校验失败抛 EntityValidationError
(242)；快照序列化契约（BlmPlanningStatus ↔ state_data dict 的键名/形态）
由应用层端口文件 SSOT 钦定，本文件 to_dict 仅承担条目级 JSON 可序列化。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from src.domain.exceptions import EntityValidationError

#: BLM 前两阶段流程步骤总数钦定（performance_gap + 六子步骤 + synthesis）
#: ——进度百分比分母（AC-3 total_steps=8 钦定，epics/or.md 范围权威）
BLM_TOTAL_STEPS: int = 8

#: BlmTimelineEntry 摘要截断上限（fix_attempts violations_excerpt ≤200 先例）
_TIMELINE_SUMMARY_MAX_CHARS: int = 200

#: InsightStepResult.structured_output 标量值域白名单（守卫层——刻意比六类型化
#: Schema 声明白名单 str/float/list[str] 宽一格：纵深防御，守卫是应用层值域
#: 兜底而非生成面约束，两层集合各自冻结；list[str] 以元素级检查另行校验）
_STRUCTURED_SCALAR_TYPES: tuple[type, ...] = (str, int, float, bool)


class BlmPhase(str, Enum):
    """BLM 规划阶段枚举（前两阶段）。

    六阶段完整版（战略意图/创新焦点/业务设计/执行设计）归 Epic 10
    Story 10-1（FR-SP-05）在同文件扩展——本枚举预留扩展锚。
    """

    PERFORMANCE_GAP = "performance_gap"
    MARKET_INSIGHT = "market_insight"


class MarketInsightStep(str, Enum):
    """市场洞察六子步骤枚举（or.md L385-415 钦定顺序——OD-2 口径）。

    第六步钉死为「机会差距分析」（or.md L411/PRD FR-SP-02 权威）；
    枚举声明序即执行序（顺序断言双锚的枚举序期望独立构造自本序）。
    """

    TREND = "trend"
    MARKET_CUSTOMER = "market_customer"
    COMPETITION = "competition"
    SELF = "self"
    OPPORTUNITY = "opportunity"
    OPPORTUNITY_GAP = "opportunity_gap"


#: BlmStageCompleted.stage 合法值域（8 值全集——performance_gap + 六子步骤 + synthesis）
STAGE_VALUE_DOMAIN: frozenset[str] = frozenset(
    {"performance_gap"} | {f"market_insight_{step.value}" for step in MarketInsightStep} | {"market_insight_synthesis"}
)


@dataclass(frozen=True)
class BlmTimelineEntry:
    """流程时间线条目（AC-3「各步骤摘要」载体与 AC-1 顺序断言数据源）。

    结构钦定六字段（Task 0.1 SSOT）——对齐 5-3 ExecutionResult.step_summaries
    先例；to_dict 供 BlmPlanningStatus 快照序列化（datetime→isoformat）。

    Attributes:
        step: 步骤标识（stage 值域同源——performance_gap/六子步骤/synthesis）
        started_at: 步骤开始时间（timezone-aware UTC）
        completed_at: 步骤完成时间
        status: 步骤状态（"completed"——降级步亦为 completed，降级面经 degraded 字段承载）
        summary_excerpt: 步骤摘要（≤200 截断）
        degraded: 是否降级（AC-3 摘要含降级标记）
    """

    step: str
    started_at: datetime
    completed_at: datetime
    status: str = "completed"
    summary_excerpt: str = ""
    degraded: bool = False

    def __post_init__(self) -> None:
        """自校验：step 非空 str；started_at 不晚于 completed_at；摘要截断。"""
        if not isinstance(self.step, str) or not self.step.strip():
            raise EntityValidationError(
                message="timeline 条目 step 必须为非空 str",
                context={"entity_type": "BlmTimelineEntry", "field": "step"},
            )
        if self.completed_at < self.started_at:
            raise EntityValidationError(
                message="timeline 条目 completed_at 早于 started_at",
                context={"entity_type": "BlmTimelineEntry", "field": "completed_at"},
            )
        if len(self.summary_excerpt) > _TIMELINE_SUMMARY_MAX_CHARS:
            object.__setattr__(self, "summary_excerpt", self.summary_excerpt[:_TIMELINE_SUMMARY_MAX_CHARS])

    def to_dict(self) -> dict[str, Any]:
        """JSON 可序列化形态（快照契约——datetime→isoformat、bool 原生）。"""
        return {
            "step": self.step,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "status": self.status,
            "summary_excerpt": self.summary_excerpt,
            "degraded": self.degraded,
        }


@dataclass(frozen=True)
class BlmPlanningStatus:
    """BLM 规划流程状态值对象（AC-3 流程可视化数据面真源）。

    current_step 语义钦定（DC-6）：最近完成步标识——快照写点在各步骤方法
    末尾，挂起第 N 步时轮询读到第 N-1 步；阶段 1 期间取 "performance_gap"
    （与 stage 值域同源，无 None 哨兵）。

    Attributes:
        plan_id: 规划任务标识（str——快照键拼接与事件字段同源）
        phase: 当前阶段（前两阶段枚举）
        current_step: 最近完成步标识
        completed_steps: 已完成步骤数
        total_steps: 总步骤数（恒 8——构造守卫）
        degraded_steps: 降级步骤清单（AC-6③ 可见性）
        timeline: 步骤时间线（BlmTimelineEntry 元组）
    """

    plan_id: str
    phase: BlmPhase
    current_step: str
    completed_steps: int
    total_steps: int = BLM_TOTAL_STEPS
    degraded_steps: tuple[str, ...] = ()
    timeline: tuple[BlmTimelineEntry, ...] = ()

    def __post_init__(self) -> None:
        """自校验：plan_id 非空；total_steps 恒 8；completed_steps 有界；timeline 类型守卫。"""
        if not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise EntityValidationError(
                message="BlmPlanningStatus.plan_id 必须为非空 str",
                context={"entity_type": "BlmPlanningStatus", "field": "plan_id"},
            )
        if self.total_steps != BLM_TOTAL_STEPS:
            raise EntityValidationError(
                message=f"total_steps 钦定为 {BLM_TOTAL_STEPS}（performance_gap+六子步骤+synthesis）",
                context={"entity_type": "BlmPlanningStatus", "field": "total_steps", "value": self.total_steps},
            )
        if not 0 <= self.completed_steps <= self.total_steps:
            raise EntityValidationError(
                message=f"completed_steps 越界 [0, {self.total_steps}]",
                context={"entity_type": "BlmPlanningStatus", "field": "completed_steps", "value": self.completed_steps},
            )
        if not all(isinstance(entry, BlmTimelineEntry) for entry in self.timeline):
            raise EntityValidationError(
                message="timeline 元素必须为 BlmTimelineEntry",
                context={"entity_type": "BlmPlanningStatus", "field": "timeline"},
            )

    @property
    def progress_percent(self) -> float:
        """进度百分比（completed_steps / total_steps × 100——分母恒 8）。"""
        return round(self.completed_steps / self.total_steps * 100, 2)


@dataclass(frozen=True)
class PerformanceGapArtifacts:
    """阶段 1 业绩差距分析产物（§17.4.2 四字段语义）。

    降级标记与 InsightStepResult 信封对称（VO 自身可判降级，免交叉查
    degraded_steps——R3-7 钦定）。

    Attributes:
        financial_gap: 财务差距量化结论（CFO 财务差距量化语义）
        operational_gap: 运营差距分析结论（COO 运营差距语义）
        root_causes: 根因清单（SWOT-TOWS 差距根因识别语义）
        portfolio_health: 业务组合健康度评估（GE-麦肯锡矩阵语义）
        degraded: 是否降级（步级降级标记）
        degrade_reason: 降级原因（降级时非空）
    """

    financial_gap: str
    operational_gap: str
    root_causes: tuple[str, ...]
    portfolio_health: str
    degraded: bool = False
    degrade_reason: str = ""


@dataclass(frozen=True)
class InsightStepResult:
    """市场洞察子步骤通用信封（6-2 扩展 structured_output 承载类型化产物）。

    降级步=完整信封（degraded=True + degrade_reason + 空 summary/findings）
    ——insight_steps 恒满 6 元素的前提（R3-7 钦定）。

    Attributes:
        step: 子步骤标识（MarketInsightStep 值）
        summary: 步骤结论摘要
        findings: 结构化发现清单
        tool_used: 实际执行的工具 slug（slug 缺失时回落显示名 name——
            tool.slug or tool.name 口径；直接推理时空串）
        evidence_refs: 检索证据引用清单（evidence_refs 直存——压缩循环归后续 Story）
        degraded: 是否降级
        degrade_reason: 降级原因
        started_at: 步骤开始时间（顺序断言观测面——服务方法填充）
        completed_at: 步骤完成时间（时间戳非重叠断言锚）
        structured_output: 该步类型化 Schema 校验后的扁平化结构化产物
           （model_dump 键值族——键 str、值 str/int/float/bool 或 list[str]；
            为 None 当且仅当 LLM 调用/校验失败（与 summary/findings 空同步）
            ——工具/检索面降级而 LLM 调用成功时仍为类型化产物（由服务层
            保证——代码审查 R1-F1 收窄口径）；默认 None 向后兼容 6-1 既有构造）。
            注：新增 dict 字段使 frozen dataclass 的 hash() 抛 TypeError
            （dict 不可哈希）——当前消费面不哈希信封，属潜伏性契约变化，
            若需哈希请先经 to_dict 形态转换。

    Raises:
        EntityValidationError: structured_output 值域违例（键非 str / 值非
            JSON 标量或 list[str]——pydantic 对象与嵌套 dict 渗入领域层即拒，
            domain 零依赖红线）。
    """

    step: str
    summary: str
    findings: tuple[str, ...]
    tool_used: str = ""
    evidence_refs: tuple[str, ...] = ()
    degraded: bool = False
    degrade_reason: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    structured_output: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """自校验：structured_output 值域守卫（None 短路——降级步/6-1 兼容形态）。"""
        if self.structured_output is None:
            return
        for key, value in self.structured_output.items():
            if not isinstance(key, str):
                raise EntityValidationError(
                    message="structured_output 键必须为 str",
                    context={"entity_type": "InsightStepResult", "field": "structured_output", "key": key},
                )
            if isinstance(value, list):
                if not all(isinstance(item, str) for item in value):
                    raise EntityValidationError(
                        message="structured_output 列表值元素必须全为 str（扁平化强制——OD-5）",
                        context={"entity_type": "InsightStepResult", "field": "structured_output", "key": key},
                    )
            elif not isinstance(value, _STRUCTURED_SCALAR_TYPES):
                raise EntityValidationError(
                    message="structured_output 值必须为 JSON 标量（str/int/float/bool）或 list[str]",
                    context={"entity_type": "InsightStepResult", "field": "structured_output", "key": key},
                )


@dataclass(frozen=True)
class InsightSynthesis:
    """市场洞察综合结论（synthesize_insights 产物——AC-6⑥ 规则载体）。

    synthesis 自身降级时 conclusions=空元组 + degraded_inputs 自含标记
    （"market_insight_synthesis" 自列入——R3-4 钦定）。

    Attributes:
        conclusions: 综合结论清单（聚合六子步骤产物的结构化结论）
        degraded_inputs: 降级输入列举（不可无标注吞并——⑥规则）
    """

    conclusions: tuple[str, ...]
    degraded_inputs: tuple[str, ...] = ()


#: 模块级便捷工厂：构造「当前时刻」timeline 条目（服务层步骤计时用）
def make_timeline_entry(
    step: str,
    started_at: datetime,
    summary_excerpt: str = "",
    *,
    degraded: bool = False,
) -> BlmTimelineEntry:
    """构造步骤完成时刻的 timeline 条目（completed_at 取当前 UTC）。

    Args:
        step: 步骤标识（stage 值域同源）。
        started_at: 步骤开始时间。
        summary_excerpt: 步骤摘要（≤200 截断由条目自校验承担）。
        degraded: 是否降级。

    Returns:
        BlmTimelineEntry 实例。
    """
    return BlmTimelineEntry(
        step=step,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        status="completed",
        summary_excerpt=summary_excerpt,
        degraded=degraded,
    )


__all__ = [
    "BLM_TOTAL_STEPS",
    "BlmPhase",
    "BlmPlanningStatus",
    "BlmTimelineEntry",
    "InsightStepResult",
    "InsightSynthesis",
    "MarketInsightStep",
    "PerformanceGapArtifacts",
    "STAGE_VALUE_DOMAIN",
    "make_timeline_entry",
]
