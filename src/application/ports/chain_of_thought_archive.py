"""应用层思维链归档端口（Story 6-4 — JSON 思维链输出）

ChainOfThoughtArchiveServicePort——BLM 面思维链「确定性组装 → EVIDENCE_PACKAGE
归档 → 决策追溯查询」三职责契约。R2 规则：应用层具体应用端口组合注入既有
应用服务 StrategicArchiveService（归档编排）与 R1 基础端口 L4ObjectPort
（include_blob 深度解引用通道——R1-F6 双注入）；实现方
ChainOfThoughtArchiveService 于 application/services/ 编排注入。

组装语义（OD-2 确定性组装）：五字段从步骤执行素材（工具轨迹/检索证据/
结构化产物/降级信息/语义配置）规则组装——零新增 LLM 调用、不经
ChainOfThoughtSchema（5-3 LLM 终局合成专用资产）。

归档语义（OD-4 零改动复用）：经 StrategicArchiveService.archive_plan 落
EVIDENCE_PACKAGE 档案类型（3-10 枚举首激活——全 src 零使用实证）/ L2
强制 + L3 可降级 + L4 WORM 强制（retention_days=2555）/ 归档内 ArchiveCreated
事件随 outbox 发布（零新事件——OD-6）。

降级语义（OD-5 可观测面非流程面）：组装失败 242 捕获改写 445 → 返回
None（该步 chain 缺席——R1-F5 台账语义）；归档强制环节失败 284 捕获 →
ChainRecord(archived=False) + warning 日志 → 流程继续（领域产物/快照/事件
不受影响）。

出处：
- or.md §五.5（L480）：思维链五段式输出。
- prd.md FR-SP-04（P0）。
- 6-1 边界表 L37：「JSON 思维链输出规范化 → Story 6-4（BLM 面输出规范化）」。
- chain_of_thought.py:4-5 docstring：「供 6-4 持久化与 5.7 Phoenix 追踪消费」。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from src.domain.value_objects.chain_of_thought import ChainOfThought

#: 归档行 decision_basis.kind 语境锚常量（R8-F3「decision_basis 是 dict 自由
#: 字段，携带语境锚使读侧可精确过滤」同构先例——checkpoint_no 锚形态）
CHAIN_ARCHIVE_KIND: str = "blm_chain_of_thought"

#: synthesis 步语义常量（R1-F3：语义配置表只有 gap+六子七行，synthesis 无
#: StepSemanticConfig——钦定组装服务模块级常量，不新增 prompts.py 配置行
#: 不动 6-1 资产）
SYNTHESIS_DISPLAY_NAME: str = "市场洞察综合"
SYNTHESIS_ROLE_PREFIX: str = "CMO"


@dataclass(frozen=True)
class StepChainMaterial:
    """单步骤思维链组装素材（挂接段构造、组装服务消费——三型分列承载）。

    字段表冻结（R1-F10——Task 0.4 终稿；三型差异说明见故事数据模型节）：
    gap/六子步骤素材来自方法内执行轨迹与产物信封；synthesis 素材为
    conclusions/degraded_inputs 计数（无工具无检索——tool_slug 恒空、
    evidence_count 恒 0）。

    Attributes:
        stage: STAGE_VALUE_DOMAIN 八值之一（六子=f"market_insight_{step.value}"
            前缀拼装——R3-F7；gap="performance_gap"；synthesis="market_insight_synthesis"）。
        display_name: 步骤显示名（六子/gap=语义配置取值；synthesis=SYNTHESIS_DISPLAY_NAME）。
        role_prefix: 视角前缀（同上；synthesis=SYNTHESIS_ROLE_PREFIX）。
        task: 规划任务描述（三型同源 context.task）。
        evidence_count: 检索证据计数（gap/六子=len(evidence_texts)；synthesis 恒 0）。
        tool_slug: 实际执行工具 slug（执行轨迹第三返回值单数——可空串即空
            元组；TOOL_CATALOG 全零 slug= 定义时实值恒为中文显示名，R3-F6）。
        evidence_refs: 证据引用清单（六子=result.evidence_refs；gap=检索三元组
            第三位；synthesis=()——AC-3 assumptions.evidence_refs 源字段）。
        summary: 步骤摘要（六子=result.summary；gap=financial_gap；synthesis=""
            无该字段，reflection 用 conclusions 计数替代）。
        findings_count: 产物要点计数（统一命名承载三型：六子=len(findings)；
            gap=len(root_causes)；synthesis=len(conclusions)）。
        degraded_inputs_count: synthesis 型专用（其余 0）。
        degraded: 步骤降级标记（信封/产物字段直取；synthesis=not conclusions）。
        degrade_reason: 降级原因（降级时非空）。
        payload: 结构化产物（六子=structured_output；gap=asdict 六键；
            synthesis=asdict 两键；降级信封 dict 仅适用于产物缺席形态——R2-F2）。
        structured_ok: 约束核对素材（六子=值域守卫结果；gap=financial_gap
            非空；synthesis=conclusions 非空）。
    """

    stage: str
    display_name: str
    role_prefix: str
    task: str
    evidence_count: int
    tool_slug: str
    evidence_refs: tuple[str, ...] = ()
    summary: str = ""
    findings_count: int = 0
    degraded_inputs_count: int = 0
    degraded: bool = False
    degrade_reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    structured_ok: bool = True


@dataclass(frozen=True)
class ChainRecord:
    """单步骤思维链归档记录（Result/state 承载条目——回传通道三件套载荷）。

    Attributes:
        stage: 步骤 stage 锚（STAGE_VALUE_DOMAIN 八值之一）。
        chain: 组装产物 ChainOfThought VO（五字段经 242 校验）。
        archived: 归档终态（False=284 降级台账——失败可见可数）。
        archive_id: 归档行主键（归档成功非空；降级时空串）。
    """

    stage: str
    chain: ChainOfThought
    archived: bool
    archive_id: str = ""


@dataclass(frozen=True)
class ChainOfThoughtTraceView:
    """决策追溯查询视图（查询面 DTO——6-3 CheckpointRecoveryView 先例形态）。

    Attributes:
        plan_id: 规划任务标识（查询锚）。
        records: 追溯条目清单（按 archived_at 升序——执行序；每条 dict 五键：
            stage 锚 / chain（重构 ChainOfThought VO——round-trip 经 242 校验）
            / archive_id / degraded / blob_content（include_blob=True 且解引用
            成功时填充 JSON dict，否则 None——R2-F4））。
        total: 追溯条目总数。
        archived_count: 归档成功条目数（与 total 的差即降级台账面）。
    """

    plan_id: str
    records: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    archived_count: int = 0


@runtime_checkable
class ChainOfThoughtArchiveServicePort(Protocol):
    """思维链归档服务端口（组装+归档单步 / 追溯查询两方法）。

    实现方：ChainOfThoughtArchiveService（application/services/
    chain_of_thought_archive_service.py）；组合注入：StrategicArchiveService
    （归档编排零改动复用）+ L4ObjectPort | None（include_blob 解引用——R1-F6）。

    Raises:
        ChainOfThoughtValidationError: EXCEPTION_445——不经本端口抛出（组装
            失败在实现内捕获改写并降级返回 None——OD-5）；保留于异常契约面
            供日志与上游观测。
    """

    async def compose_and_archive_step_chain(
        self,
        plan_id: uuid.UUID,
        stage: str,
        material: StepChainMaterial,
    ) -> ChainRecord | None:
        """组装并归档单步思维链（确定性组装 + EVIDENCE_PACKAGE 归档）。

        Args:
            plan_id: 规划任务标识（UUID——归档行 plan_id 锚）。
            stage: 步骤 stage 锚（STAGE_VALUE_DOMAIN 八值之一）。
            material: 组装素材（挂接段构造——三型分列）。

        Returns:
            ChainRecord：归档成功（archived=True）/ 归档失败 284 降级台账
            （archived=False, archive_id=""）；None：组装失败 445 降级（该步
            chain 缺席——R1-F5，ChainRecord.chain 非可选无法构造缺席记录）。
        """
        ...

    async def query_chain_trace(
        self,
        plan_id: uuid.UUID,
        include_blob: bool = False,
    ) -> ChainOfThoughtTraceView:
        """决策追溯查询（按 plan_id 读回 EVIDENCE_PACKAGE 档案清单组装视图）。

        五字段从 decision_basis.chain 反序列化重构 ChainOfThought VO
        （tools_used 经 tuple() 归一——PG JSONB 读回 list 必拒 VO 守卫，R1-F9）；
        WORM blob 深度解引用为可选参数（默认读 L2 决策依据足够，深度审计时
        解 L4——object_storage 未注入时槽位置 None 不抛异常，R2-F4）。

        Args:
            plan_id: 规划任务标识（UUID）。
            include_blob: 是否深度解引用 L4 WORM blob（默认 False）。

        Returns:
            追溯视图（空档案 plan_id 返回空清单 total=0——查询面幂等读语义）。
        """
        ...


__all__ = [
    "CHAIN_ARCHIVE_KIND",
    "SYNTHESIS_DISPLAY_NAME",
    "SYNTHESIS_ROLE_PREFIX",
    "ChainOfThoughtArchiveServicePort",
    "ChainOfThoughtTraceView",
    "ChainRecord",
    "StepChainMaterial",
]
