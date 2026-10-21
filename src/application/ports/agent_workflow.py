"""应用层单 Agent 工作流端口模块（Story 5-3 — 单 Agent 标准工作流）

AgentWorkflowServicePort——六阶段标准工作流（感知→规划→执行→验证→反思→
证据打包）的应用层端口。图编排（LangGraph StateGraph）在 infrastructure 层
图工厂经本端口调用阶段逻辑（infrastructure→application 端口方向合法）。

设计决策（Task 0 规范定稿——唯一真源）：
- 六阶段每阶段一方法 + build_context 装配入口（单向装配：用例加载档案后
  传材料，服务不自行调 profile use case——防双装配，R1-F23）
- state 参数类型一律 dict[str, Any]（AgentEnginePort.parameters 同款弱类型
  先例——WorkflowAgentState 定义留 infrastructure 层仅图工厂/引擎内部使用，
  application 引它会反向依赖违反 import-linter，R1-F7）
- 阶段结果用 application 层 dataclass（非 pydantic——服务间流转不需要 LLM
  Schema）；七个多字段组合载体（WorkflowContext + 六阶段 Result）定义在
  本端口文件（多字段组合载体放端口文件先例）
- execute 是阶段级聚合（服务内部按 plan 步骤逐步执行——每步 Think→Code→
  Execute→Observe→Validate 原子循环中 Think 已由 plan 承载、Code/Execute
  走 tool_execution_service.execute、Observe 记录 ToolResult、Validate 由
  工具装饰链 OutputValidator 承载；名字→实体经 tool_registry_service.
  get_tool(tool_name=)——DC-10/DC-8）
- package_evidence 返回复合产物 PackageOutcome（evidence + chain——终局
  思维链合成在 package 阶段，适配器经 PackageOutcome 拆写两 state 键，
  R2-F1）
- 禁止在服务文件本地定义 Protocol；禁止新建语义重复端口（工具执行/LLM/
  SOP 加载全部复用既有端口）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from src.application.ports.skill_loader import ToolMetadata
from src.domain.value_objects.chain_of_thought import ChainOfThought
from src.domain.value_objects.task_evidence import TaskEvidencePackage


@dataclass(frozen=True)
class WorkflowContext:
    """工作流上下文（build_context 装配产物——五字段定稿）

    各阶段 LLM 调用共用 system_prompt；task 键供 state 初值、context 为
    装配产物键（键位分工）。

    Attributes:
        system_prompt: 五分节装配产物（IDENTITY→SOUL→CODE→核心约束→TOOLS L1
            + USER/MEMORY 尾节——HEARTBEAT 不注入，DC-3）
        tools_l1: L1 工具元数据清单（规划阶段 LLM 自主选择的素材）
        task: 任务描述原文
        tenant_id: 租户标识（MVP 固定单租户 UUID 常量，多租户扩展归后续
            ——ExecutionContext 构造的租户来源，R1-F21）
        assembled_context_tokens: 装配总计量（五档案 + L1 视图 + 核心约束
            文本的 CJK 感知估算——heartbeat 不入；弃 5-2 三件套口径，
            R2-F12/Subtask 3.3）
    """

    system_prompt: str
    tools_l1: tuple[ToolMetadata, ...]
    task: str
    tenant_id: UUID
    assembled_context_tokens: int


@dataclass(frozen=True)
class PerceptionResult:
    """感知阶段结果（任务上下文摘要）。"""

    summary: str


@dataclass(frozen=True)
class PlanResult:
    """规划阶段结果（任务分解 + 工具匹配）。"""

    steps: tuple[tuple[str, str, dict[str, Any]], ...]
    selected_tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionResult:
    """执行阶段结果（阶段级聚合——服务内部按 plan 步骤逐步执行）。

    轨迹累积语义：服务读 state 旧 execution 追加合并 tool_trace/
    artifacts_snapshot（防重试轮键覆盖丢前轮轨迹——AC-3「失败终态含全部
    已执行轨迹」的承载，R2-F5）。

    Attributes:
        tool_trace: 工具调用轨迹（含版本后缀，跨重试轮聚合）
        artifacts_snapshot: 关键中间产物快照（元组对形态）
        step_summaries: 步骤执行摘要序列（验证阶段 prompt 素材）
        citations: 引用源切片 ID 聚合（工具级证据 citations 语义）
    """

    tool_trace: tuple[str, ...] = ()
    artifacts_snapshot: tuple[tuple[str, str], ...] = ()
    step_summaries: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationResult:
    """验证阶段结果（结构化检查——含 passed/confidence）。"""

    passed: bool
    confidence: float
    rationale: str


@dataclass(frozen=True)
class ReflectionResult:
    """反思阶段结果（失败时错误分析与修正重试）。"""

    revised: bool
    error_analysis: str
    revised_plan: str


@dataclass(frozen=True)
class PackageOutcome:
    """证据打包阶段复合产物（evidence + chain——R2-F1）。

    终局思维链合成在 package 阶段（DC-2：组装覆写 + 终局单次合成）；
    图适配器经本复合产物拆写 state 的 "evidence" 与 "chain" 两键。
    """

    evidence: TaskEvidencePackage
    chain: ChainOfThought


@runtime_checkable
class AgentWorkflowServicePort(Protocol):
    """单 Agent 六阶段工作流服务端口

    六阶段方法由图节点适配器调用（节点返回 dict 部分更新——谓词键由适配器
    写入，对照表见 Story Task 0）；阶段逻辑/prompt/LLM 调用全在本端口实现
    （application 层服务），infrastructure 图工厂仅做编排。
    """

    def build_context(
        self,
        profile_result: Any,
        task: str,
    ) -> WorkflowContext:
        """装配工作流上下文（单向装配——用例加载档案后传材料）

        Args:
            profile_result: 档案加载结果（AgentProfileLoadResult——五档案
                str + tools_l1 + 计量；heartbeat 为调度心跳配置不入 prompt）
            task: 任务描述原文

        Returns:
            WorkflowContext 装配产物（五字段）
        """
        ...

    async def perceive(self, state: dict[str, Any]) -> PerceptionResult:
        """感知阶段（任务上下文摘要）

        Args:
            state: 工作流状态（dict[str, Any]——弱类型先例）

        Returns:
            感知结果（summary）
        """
        ...

    async def plan(self, state: dict[str, Any]) -> PlanResult:
        """规划阶段（任务分解与工具匹配——重试轮回灌 revised_plan）

        Args:
            state: 工作流状态（含 context 与可选 reflection 产物）

        Returns:
            规划结果（steps + selected_tools）
        """
        ...

    async def execute(self, state: dict[str, Any]) -> ExecutionResult:
        """执行阶段（阶段级聚合——按 plan 步骤逐步经工具执行服务）

        Args:
            state: 工作流状态（含 plan 产物与旧 execution 轨迹——历史聚合）

        Returns:
            执行结果（跨重试轮聚合的轨迹/快照/摘要）
        """
        ...

    async def verify(self, state: dict[str, Any]) -> VerificationResult:
        """验证阶段（结构化检查）

        Args:
            state: 工作流状态（含 execution 聚合产物）

        Returns:
            验证结果（passed/confidence/rationale）
        """
        ...

    async def reflect(self, state: dict[str, Any]) -> ReflectionResult:
        """反思阶段（验证失败时错误分析与修正计划）

        Args:
            state: 工作流状态（含 verification 失败产物）

        Returns:
            反思结果（revised/error_analysis/revised_plan）
        """
        ...

    async def package_evidence(self, state: dict[str, Any]) -> PackageOutcome:
        """证据打包阶段（终局思维链合成 + 九字段证据组装）

        Args:
            state: 工作流终态前状态（含全阶段产物与最终 verification）

        Returns:
            复合产物（evidence + chain——适配器拆写两 state 键）
        """
        ...


@dataclass(frozen=True)
class AgentWorkflowResult:
    """工作流执行结果 DTO（用例层产出——五字段）

    executed_phases 自终态 state 直读（CLI 六阶段状态行数据源）；
    workflow_status 同源于 evidence.status（"completed"/"failed"——FlowStatus
    仅系统错误通道不进业务判定，R2-F7）；置信度 CLI 输出 ← evidence.confidence；
    组装数据源 = 引擎 get_graph_result 终态 state（DC-11）。
    """

    chain: ChainOfThought
    evidence: TaskEvidencePackage
    workflow_status: str
    retry_count: int
    executed_phases: tuple[str, ...] = ()


__all__ = [
    "AgentWorkflowResult",
    "AgentWorkflowServicePort",
    "ExecutionResult",
    "PackageOutcome",
    "PerceptionResult",
    "PlanResult",
    "ReflectionResult",
    "VerificationResult",
    "WorkflowContext",
]
