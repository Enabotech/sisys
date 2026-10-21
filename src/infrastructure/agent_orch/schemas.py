"""基础设施层 Agent 编排 Schema 模块

定义 LangGraph 状态图的状态 TypedDict，供 Engine 和 Graph 共享
"""

from __future__ import annotations

from typing import Any, TypedDict


class BasicAgentState(TypedDict, total=False):
    """BasicAgent 状态图状态定义

    MVP 阶段最小状态，验证编排架构而非业务逻辑

    Attributes:
        task_description: 任务描述
        agent_role: Agent 角色
        analysis_result: 分析结果
        synthesis_result: 综合结果
    """

    task_description: str
    agent_role: str
    analysis_result: str
    synthesis_result: str


class WorkflowAgentState(TypedDict, total=False):
    """SingleAgentWorkflow 六阶段状态定义（Story 5-3）

    仅图工厂/引擎内部使用——application 端口签名一律 dict[str, Any]
    （.importlinter「Application must not depend on infrastructure」契约，
    端口方法注解引用本 TypedDict 即 CI 红——R1-F7）。

    谓词键↔写入者对照表（DC-1）：
    - verification_passed / confidence ← verify 节点适配器
    - revised / retry_count ← reflect 节点适配器（reflect 执行一次=消耗一次重试）
    - executed_phases ← 各节点适配器 append 阶段名（末元素钉死 "package"——
      对齐 444 phase 枚举）
    - evidence / chain ← package_evidence 适配器自 PackageOutcome 拆写

    键合并语义：纯 TypedDict 无 reducer，LangGraph 默认键覆盖——plan/
    verification/reflection 键覆盖是正确行为（终局读末值）；execution 键是
    轨迹累积语义（execute 服务聚合历史——服务读旧值追加合并后适配器直写
    全量，R2-F5/R3-F10）。

    Attributes:
        agent_id: Agent 实体标识（str 形态——parameters 透传，引擎收敛位写入）
        task: 任务描述原文（parameters 初值）
        context: WorkflowContext 装配产物（dataclass 实例直存——InMemorySaver
            无序列化，R2-F15 直读 VO 实例同款理由）
        perception: PerceptionResult（perceive 产物）
        plan: PlanResult（plan 产物——重试轮覆盖）
        execution: ExecutionResult（execute 产物——跨重试轮聚合）
        verification: VerificationResult（verify 产物——重试轮覆盖）
        reflection: ReflectionResult（reflect 产物）
        retry_count: 已消耗重试次数（reflect 适配器递增）
        revised: 反思判定是否可修正（reflect 适配器写入）
        verification_passed: 验证是否通过（verify 适配器写入——条件边谓词键）
        confidence: 验证置信度（verify 适配器写入——事件真实化数据源）
        executed_phases: 阶段执行轨迹（各适配器 append）
        evidence: TaskEvidencePackage（package_evidence 产物拆写）
        chain: ChainOfThought（package_evidence 产物拆写）
    """

    agent_id: str
    task: str
    context: Any
    perception: Any
    plan: Any
    execution: Any
    verification: Any
    reflection: Any
    retry_count: int
    revised: bool
    verification_passed: bool
    confidence: float
    executed_phases: list[str]
    evidence: Any
    chain: Any
