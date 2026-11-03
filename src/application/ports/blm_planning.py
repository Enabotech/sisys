"""应用层 BLM 规划服务端口（Story 6-1 — BLM 前两阶段流程）

BlmPlanningServicePort——BLM 前两阶段（业绩差距分析 + 市场洞察六子步骤）
的阶段/子步骤执行契约。R2 规则：应用层具体应用端口组合注入 R1 基础端口
（LLMClientPort/工具执行/检索/EventPublisher/快照存储——实现方
BlmPlanningService 于 application/services/ 编排注入）。

快照序列化契约（SSOT——Task 2 种子与 Task 3 写入同源）：
- BlmPlanningStatus ↔ 快照存储 state_data dict 的键名/形态以本节为准：
  {"plan_id": str, "phase": str, "current_step": str, "completed_steps": int,
   "total_steps": int, "degraded_steps": list[str],
   "timeline": list[dict]}——timeline 条目六键
  （step/started_at/completed_at/status/summary_excerpt/degraded）；
  datetime 以 isoformat 字符串、枚举以 .value 字符串流转（RedisJSONEncoder
  语义；json_loads 不自动还原类型——读径 GetBlmPlanningStatusUseCase 反序列化）。
- 读径经快照存储端口 load（hget 在存储实现内部），用例只持 session_id
  （不自持 Redis 客户端）。
- 三层键形态：BLM_PLANNING_SESSION_PREFIX（本文件单源常量）→
  session_id = f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}" →
  最终键 sisys:snapshot:blm-planning-{plan_id}
  （RedisSnapshotStore.build_key("snapshot", session_id)——5-10 Recorder
  键控先例形态）。
- per-step Checkpoint 快照（6-2 新增——第三级契约，Story 6-3 Checkpoint
  完整机制的恢复点位数据面）：每个市场洞察子步骤完成时在 latest 之外
  额外写入一份独立快照，键/session_id/stage_id/state_data 契约：
  session_id = f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}:{step.value}"
  （最终键 sisys:snapshot:blm-planning-{plan_id}:{step_value}——step_value
  为 MarketInsightStep 枚举值；RedisSnapshotStore 键仅由 session_id 决定，
  内部冒号原样保留）；stage_id = f"market_insight_{step.value}"（与
  STAGE_VALUE_DOMAIN 同源）；state_data 七键
  {"step": str, "plan_id": str, "summary": str,
   "structured_output": dict[str, Any] | None, "degraded": bool,
   "degrade_reason": str, "completed_steps": list[str]}——
  structured_output 键恒存在（值为 None 当且仅当 LLM 调用/校验失败降级步；
  工具/检索面降级而 LLM 调用成功时为该步类型化产物 dict（与 summary/findings
  非空对称——代码审查 R1-F1 收窄口径）；禁"降级时键缺失"形态——
  6-3 读侧免双兼容）；completed_steps 为截至该步（含该步）的已完成
  步骤标识清单（timeline 条目 step 字段同源口径——六子步骤为裸 step
  值（trend 等），performance_gap/synthesis 为 stage 形态；自然实现
  [e.step for e in run_state.timeline]，首步快照即含 performance_gap
  ——与 latest 的 int 计数语义显式区分）；TTL 沿用 CheckpointSnapshot
  既有默认 86400（6-3 升级 30 天完整形态）；读侧判别规则 = session_id
  键后缀 + state_data 含 plan_id/step 双锚（区分 latest 与 per-step
  两契约）；写入失败容错不阻断流程（与 latest 写入同语义）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from src.application.ports.chain_of_thought_archive import ChainRecord
from src.domain.value_objects.blm_phases import (
    InsightStepResult,
    InsightSynthesis,
    MarketInsightStep,
    PerformanceGapArtifacts,
)

#: BLM 规划快照会话前缀（单源常量——读径 GetBlmPlanningStatusUseCase 与
#: 写入方 BlmPlanningService 共用拼接，禁两处字面量漂移；
#: 5-10 EVALUATION_SESSION_PREFIX 先例形态）
BLM_PLANNING_SESSION_PREFIX: str = "blm-planning-"

#: 快照 stage_id（CheckpointSnapshot.stage_id——与 evaluation 快照区分）
BLM_PLANNING_SNAPSHOT_STAGE: str = "blm_planning"


@dataclass(frozen=True)
class BlmPlanningContext:
    """BLM 规划上下文（build_planning_context 产物——图 state 的 context 键载体）。

    Attributes:
        plan_id: 规划任务标识（事件发布与快照写入的锚定字段）
        agent_id: 执行 Agent 标识（UUID——CEO 单角色 MVP）
        profile_result: 档案加载结果（AgentProfileLoadResult——六档案 VO + tools_l1）
        task: 规划任务描述
        tenant_id: 租户标识
        retrieved_evidence: 预留注入位（当前恒空——检索证据在各阶段方法内
            按步骤 query 模板异步检索，R1-12① 勘误口径）
    """

    plan_id: str
    agent_id: Any
    profile_result: Any
    task: str
    tenant_id: str = ""
    # 注：检索证据在各阶段方法内按步骤 query 模板异步检索（R1-12① 勘误——
    # 「build 时一次性检索」为旧设计表述）；本字段保留为阶段 1 证据的
    # 预留注入位，当前恒空
    retrieved_evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlmPlanningResult:
    """BLM 前两阶段执行结果 DTO（终态 state 直读组装——5-3 同构）。

    Attributes:
        plan_id: 规划任务标识
        agent_id: 执行 Agent 标识
        gap_artifacts: 阶段 1 业绩差距分析产物
        insight_steps: 六子步骤产物列表（元素携带 started_at/completed_at——
            顺序断言观测面；恒满 6 元素）
        synthesis: 综合洞察
        degraded_steps: 降级步骤清单（AC-6③）
        execution_ms: 执行耗时（毫秒）
        chain_records: 思维链归档记录（6-4——默认尾字段 () 零破坏，
            6-3 R3-2 先例；读侧 tuple 归一——R2-F5；元素 ChainRecord——
            AC-2 钦定精确类型，同层 ports 互导合法）
    """

    plan_id: str
    agent_id: Any
    gap_artifacts: PerformanceGapArtifacts
    insight_steps: tuple[InsightStepResult, ...] = ()
    synthesis: InsightSynthesis = field(default_factory=lambda: InsightSynthesis(conclusions=()))
    degraded_steps: tuple[str, ...] = ()
    execution_ms: int = 0
    chain_records: tuple[ChainRecord, ...] = ()


@runtime_checkable
class BlmPlanningServicePort(Protocol):
    """BLM 规划服务端口（阶段/子步骤执行契约）。

    实现方：BlmPlanningService（application/services/blm_planning_service.py）；
    组合注入：LLMClientPort / ToolExecutionService / 工具注册 / IsolationGuardPort /
    HybridSearchPort / EventPublisher / SnapshotRepositoryProtocol（R2）。
    """

    def build_planning_context(
        self,
        profile_result: Any,
        task: str,
        plan_id: str,
        tenant_id: str = "",
    ) -> BlmPlanningContext:
        """装配 BLM 规划上下文（同步——检索证据在各阶段方法内异步检索）。

        Args:
            profile_result: 档案加载结果。
            task: 规划任务描述。
            plan_id: 规划任务标识（事件/快照锚定）。
            tenant_id: 租户标识。

        Returns:
            BlmPlanningContext 实例。
        """
        ...

    async def run_performance_gap_analysis(self, context: BlmPlanningContext) -> PerformanceGapArtifacts:
        """执行阶段 1 业绩差距分析（四字段产物 + 步骤边界快照写 + 事件发布）。

        Args:
            context: BLM 规划上下文。

        Returns:
            PerformanceGapArtifacts 四字段产物（降级标记对称）。
        """
        ...

    async def run_insight_step(
        self,
        step: MarketInsightStep,
        context: BlmPlanningContext,
        prior_outputs: Mapping[str, Any],
    ) -> InsightStepResult:
        """执行市场洞察单子步骤（每步时序钦定 DC-3）。

        每步时序：确定性工具候选（语义配置表白名单）→ 工具先行执行（失败/
        未选 → 直接推理）→ 检索证据 + 工具输出注入 → 单次结构化 LLM 调用。

        Args:
            step: 子步骤枚举（六值之一）。
            context: BLM 规划上下文。
            prior_outputs: 上游产物（performance_gap 产物 + 已完成子步骤产物——
                降级产物以「[降级]+原因」显式标注注入）。

        Returns:
            InsightStepResult 通用信封（降级步=完整信封）。
        """
        ...

    async def synthesize_insights(
        self, step_outputs: Mapping[str, Any], context: BlmPlanningContext | None = None
    ) -> InsightSynthesis:
        """综合六子步骤产物（单次 LLM 聚合调用——计入级联）。

        Args:
            step_outputs: 六子步骤产物（含 degraded 标记——结论必须列举降级输入）。
            context: 规划上下文（事件发布锚定——服务内部状态注入时可选）。

        Returns:
            InsightSynthesis 综合结论。
        """
        ...

    def project_timeline(self, plan_id: str) -> list[dict[str, Any]]:
        """投影步骤时间线（图 state 的 timeline 键——适配器直写全量）。"""
        ...

    def project_degraded_steps(self, plan_id: str) -> list[str]:
        """投影降级步骤清单（图 state 的 degraded_steps 键）。"""
        ...

    def project_chain_records(self, plan_id: str) -> list[ChainRecord]:
        """投影思维链归档记录（图 state 的 chain_records 键——6-4 回传三件套②）。

        增量方法追加非语义变更（既有六方法零改动）；元素为 ChainRecord
        dataclass（同层 ports 互导合法——chain_of_thought_archive.py 定义，
        无循环依赖；图 state 侧 SpBlmState 承载 list[Any] 是 schemas.py
        既有惯例与本端口类型纪律分立）。
        """
        ...


__all__ = [
    "BLM_PLANNING_SESSION_PREFIX",
    "BLM_PLANNING_SNAPSHOT_STAGE",
    "BlmPlanningContext",
    "BlmPlanningResult",
    "BlmPlanningServicePort",
]
