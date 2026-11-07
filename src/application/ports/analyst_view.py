"""分析师视图端口契约（Story 6-9）——七 VO + PhaseStatus 三值枚举 + BLM_SIX_PHASES 静态清单 + AnalystViewPort.

读侧 CQRS 投影 DTO（读侧 DTO 归应用层——6-6 CheckpointSummaryView/6-7 五 VO/6-8 七 VO
先例族；零 domain VO——OD-12 纯三零裁定）。三段聚合：
    - 专业工具箱段（toolbox）：SkillSelectorPort.list_active_skills 的 ACTIVE 清单
      投影（ToolSummary 五键投影白名单——ToolMetadata 18 字段面其余 13 字段
      [input_schema/output_schema/when_to_use/when_not_to_use/capabilities/tags/version/
      rule_version/token_budget_l1/token_budget_l2/depends_on/triggers/data_sources]
      禁入视图——执行面载荷防扩散，OD-4）+ 分类分组计数；
    - BLM 进度段（progress）：latest 快照 state_data 七键直读（步级计数）+ 六阶段
      全景派生（stages——前两阶段 timeline 派生+后四阶段规划态 not_started）；
    - 溯源摘要段（traceability）：溯源树四层规模统计（三层有效计数[stage/chunk/
      document]+jump_ready 计数+degraded_stage 计数+树顶层哨兵透传——结论层恒
      单根节点[root 即唯一 ConclusionNode，空树同构造]不计入统计面，R1-F1）。

PhaseStatus 是全仓首个三值进度态枚举（completed/in_progress/not_started——进度态
语义域，与 6-8 ExecutiveHealth 健康分级域[green/amber/red]正交分立）。

BLM_SIX_PHASES 是应用层静态呈现清单（阶段序 or.md L379 权威——非 BlmPhase 枚举
扩展：六阶段完整版归 Epic 10 Story 10-1 在 domain 同文件扩展，本枚举预留扩展锚
钦定不可僭越——OD-5）。

端口版本：(v1.0.0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.blm_phases import MarketInsightStep


class PhaseStatus(str, Enum):
    """BLM 阶段进度状态（三值进度态枚举——completed/in_progress/not_started）.

    进度态语义域与 ExecutiveHealth 健康分级域（green/amber/red）正交分立：
    前者刻画「流程走到哪」，后者刻画「数据可信度如何」——两枚举各自独立演进。
    """

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"


#: BLM 六阶段静态呈现清单（(phase_key, phase_name) 六元组——阶段序 or.md L379 权威：
#: 「业绩差距分析、市场洞察(包括六个子步骤)、战略意图与目标、创新焦点、业务设计、
#: 执行设计六个阶段」）。应用层常量非 BlmPhase 枚举扩展（扩展锚归 Epic 10 Story
#: 10-1 钦定——OD-5）；后四阶段 V1 归 Epic 10-1（FR-SP-05），本清单仅呈现框架
#: （「V1 交付」注记归 CLI 呈现，不进 status 值域）。
BLM_SIX_PHASES: tuple[tuple[str, str], ...] = (
    ("performance_gap", "业绩差距分析"),
    ("market_insight", "市场洞察"),
    ("strategic_intent", "战略意图与目标"),
    ("innovation_focus", "创新焦点"),
    ("business_design", "业务设计"),
    ("execution_design", "执行设计"),
)

#: 六阶段 step 值域映射（AC-3 派生规则输入面单源——三阶段值域两两不相交
#: [{performance_gap}/六子裸值+synthesis 七值/∅]是 derive_stage_status 单集合参数
#: 可判别三规则的依据；后四阶段空值域=step_total 0 规划态）。
PHASE_STEP_DOMAINS: dict[str, frozenset[str]] = {
    "performance_gap": frozenset({"performance_gap"}),
    "market_insight": frozenset({step.value for step in MarketInsightStep} | {"market_insight_synthesis"}),
    "strategic_intent": frozenset(),
    "innovation_focus": frozenset(),
    "business_design": frozenset(),
    "execution_design": frozenset(),
}

#: 六阶段步数规划值（值域基数派生——1/7/0/0/0/0；「框架恒在」=阶段名+步数规划
#: 恒在，数据缺席仅影响 status/step_completed——P-empty 语义）
PHASE_STEP_TOTALS: dict[str, int] = {phase_key: len(domain) for phase_key, domain in PHASE_STEP_DOMAINS.items()}


def _not_started_stages() -> tuple[PhaseProgress, ...]:
    """构造六阶段全 not_started 框架（ProgressSection 空态默认值——AC-3「框架恒在」）.

    静态清单+步数规划值不依赖快照——空 plan/段降级共用默认值（R3-F2 钦定）。
    """
    return tuple(
        PhaseProgress(
            phase_key=phase_key,
            phase_name=phase_name,
            status=PhaseStatus.NOT_STARTED,
            step_completed=0,
            step_total=PHASE_STEP_TOTALS[phase_key],
        )
        for phase_key, phase_name in BLM_SIX_PHASES
    )


@dataclass(frozen=True)
class ToolSummary:
    """工具摘要（5 键——L1 元数据投影白名单）.

    投影白名单五键从 ToolMetadata（18 字段）直传零变形；白名单外 13 字段
    （input/output schema、when_to_use/when_not_to_use、token 预算等执行面载荷）
    禁入视图——展示面与执行面载荷分立（OD-4，6-8 审计 15 键投影白名单同款）。
    """

    slug: str
    tool_name: str
    category: str
    description: str
    status: str


@dataclass(frozen=True)
class ToolCategorySummary:
    """工具分类分组计数（2 键——按 category 分组）.

    组序钦定 slug 清单稳定序去重序（selector 返回序派生，禁字母序重排——OD-10）；
    分组和恒等式 sum(tool_count) == total_tools 是分组完备性断言锚（AC-2）。
    """

    category: str
    tool_count: int

    def __post_init__(self) -> None:
        """构造守卫：tool_count 非负（违例抛 242）."""
        if self.tool_count < 0:
            raise EntityValidationError(
                message="工具分类计数不得为负",
                context={"vo": "ToolCategorySummary", "category": self.category, "tool_count": self.tool_count},
            )


@dataclass(frozen=True)
class ToolboxSection:
    """专业工具箱段（4 键——ACTIVE 工具清单+分类分组计数）.

    静态真源与 plan 正交（TOOLS.md 打包文件内存读——三段中唯一恒数据段）；
    段降级（selector 异常）时清单降空 tuple+计数降 0（键恒在纪律）。
    """

    degraded: bool = False
    total_tools: int = 0
    tools: tuple[ToolSummary, ...] = ()
    categories: tuple[ToolCategorySummary, ...] = ()

    def __post_init__(self) -> None:
        """构造守卫：total_tools 非负."""
        if self.total_tools < 0:
            raise EntityValidationError(
                message="工具箱工具总数不得为负",
                context={"vo": "ToolboxSection", "total_tools": self.total_tools},
            )


@dataclass(frozen=True)
class PhaseProgress:
    """BLM 单阶段进度（5 键——六阶段全景的元素）.

    status 派生自 timeline step 集合（derive_stage_status 纯函数——AC-3 规则表）；
    step_completed 与 status 同源派生自同一 stage_steps 集合基数（set 去重口径
    ——R1-F3，计数天然有界于阶段值域基数，脏 timeline 重复形态结构不可触发
    越界）；后四阶段 step_total==0 规划态（「未启动」非「不可用」）。
    """

    phase_key: str
    phase_name: str
    status: PhaseStatus
    step_completed: int = 0
    step_total: int = 0

    def __post_init__(self) -> None:
        """构造守卫：枚举成员校验（裸 str 拒绝）+计数非负+step_completed ≤ step_total."""
        if not isinstance(self.status, PhaseStatus):
            raise EntityValidationError(
                message="status 必须为 PhaseStatus 枚举成员（裸字符串拒绝）",
                context={"vo": "PhaseProgress", "phase_key": self.phase_key, "status": self.status},
            )
        if self.step_completed < 0 or self.step_total < 0:
            raise EntityValidationError(
                message="阶段步数计数不得为负",
                context={
                    "vo": "PhaseProgress",
                    "phase_key": self.phase_key,
                    "step_completed": self.step_completed,
                    "step_total": self.step_total,
                },
            )
        if self.step_completed > self.step_total:
            raise EntityValidationError(
                message="step_completed 不得大于 step_total（进度不变量）",
                context={
                    "vo": "PhaseProgress",
                    "phase_key": self.phase_key,
                    "step_completed": self.step_completed,
                    "step_total": self.step_total,
                },
            )


@dataclass(frozen=True)
class ProgressSection:
    """BLM 进度段（9 键——步级计数直读+六阶段全景）.

    步级计数（completed_steps/total_steps/progress_percent/degraded_step_count）
    是快照 state_data int 直读口径（写侧 min 钳制 ≤8）；stages 是 timeline 派生
    口径——两口径分立（timeline 含值域外脏值时可不一致，属「快照计数 vs 派生
    计数」预期语义非 bug——AC-3 注记）。progress_percent 为整数口径
    （int(completed/total*100) 向下取整，与 6-8 PlanningSection 同口径——VO 侧
    int 截断，与 BlmPlanningStatus.progress_percent 实体 property float 口径分立）。

    空态/段降级共用默认值钦定（R3-F2）：phase=None/current_step=None/计数全 0
    /stages=六阶段 not_started 框架——total_steps 默认 0 非 8（与 6-8 默认 8 分立
    注记：本 Story 总数语义由 stages 框架承载，空态 0 是「没有数据」诚实语义）。
    """

    available: bool = False
    degraded: bool = False
    phase: str | None = None
    current_step: str | None = None
    completed_steps: int = 0
    total_steps: int = 0
    progress_percent: int = 0
    degraded_step_count: int = 0
    stages: tuple[PhaseProgress, ...] = field(default_factory=_not_started_stages)

    def __post_init__(self) -> None:
        """构造守卫：三计数非负."""
        negative_fields = {
            "completed_steps": self.completed_steps,
            "total_steps": self.total_steps,
            "degraded_step_count": self.degraded_step_count,
        }
        if any(value < 0 for value in negative_fields.values()):
            raise EntityValidationError(
                message="BLM 进度段计数不得为负",
                context={"vo": "ProgressSection", **negative_fields},
            )


@dataclass(frozen=True)
class TraceabilitySection:
    """溯源摘要段（8 键——四层树规模统计+jump_ready 计数）.

    两层哨兵分立：degraded（本段编排异常——build_trace_tree 调用抛异常）与
    tree_build_degraded（6-7 树顶层哨兵透传——query_archive 顶层降级）语义正交
    （「本段拿不到」vs「树内拿不到」）。五计数派生自树遍历单源：stage_count=
    分析层 StageNode 数（synthesis 行不计入）/chunk_count=切片层节点实例数（跨
    stage 重复引用按实例计）/document_count=文档层节点实例数/jump_ready_count=
    jump_ready True 文档节点数（「30 秒溯源」可达性观测锚）/degraded_stage_count=
    stage 级降级上卷——结论层恒单根节点（root 自身）不计入统计面（R1-F1）。
    """

    available: bool = False
    degraded: bool = False
    stage_count: int = 0
    chunk_count: int = 0
    document_count: int = 0
    jump_ready_count: int = 0
    degraded_stage_count: int = 0
    tree_build_degraded: bool = False

    def __post_init__(self) -> None:
        """构造守卫：五计数非负."""
        negative_fields = {
            "stage_count": self.stage_count,
            "chunk_count": self.chunk_count,
            "document_count": self.document_count,
            "jump_ready_count": self.jump_ready_count,
            "degraded_stage_count": self.degraded_stage_count,
        }
        if any(value < 0 for value in negative_fields.values()):
            raise EntityValidationError(
                message="溯源摘要段计数不得为负",
                context={"vo": "TraceabilitySection", **negative_fields},
            )


@dataclass(frozen=True)
class AnalystView:
    """分析师视图（6 键——三段聚合 + 顶层降级哨兵）.

    build_degraded 是顶层哨兵（任一段 degraded 即 True——「拿不到数据不得报绿」
    读模型诚实性，6-7/6-8 哲学延续）。generated_at 是视图生成锚（ISO 字符串——
    服务入口单时间锚取一次 now，6-8 R1-F2 单锚派生直系）。
    """

    plan_id: str
    generated_at: str = ""
    build_degraded: bool = False
    toolbox: ToolboxSection = field(default_factory=ToolboxSection)
    progress: ProgressSection = field(default_factory=ProgressSection)
    traceability: TraceabilitySection = field(default_factory=TraceabilitySection)

    def __post_init__(self) -> None:
        """构造守卫：plan_id 非空字符串（违例抛 242——畸形守卫归用例层单源）."""
        if not isinstance(self.plan_id, str) or not self.plan_id:
            raise EntityValidationError(
                message="plan_id 必须为非空字符串",
                context={"vo": "AnalystView", "field": "plan_id", "plan_id": self.plan_id},
            )


@runtime_checkable
class AnalystViewPort(Protocol):
    """分析师视图端口（读侧聚合 CQRS 投影——R2 应用层具体端口组合注入三既有依赖）.

    消费方：GetAnalystViewUseCase（用例守卫+透传）+ CLI analyst-view 子命令
    （经组合根 analyst_view_use_case 注册名 resolve）。
    端口版本：(v1.0.0)
    """

    async def build_analyst_view(self, *, plan_id: str) -> AnalystView:
        """按 plan_id 构建三段聚合视图.

        Args:
            plan_id: 规划任务标识（UUID 字符串——畸形守卫归用例层 242，服务层不守卫）.

        Returns:
            AnalystView 六键冻结视图（空 plan 幂等读返回空态视图不抛异常——AC-5）.
        """
        ...
