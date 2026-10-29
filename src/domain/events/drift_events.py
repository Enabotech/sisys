"""领域层 漂移检测事件模块（Story 5.9 — FR-EV-03 漂移检测面）

CUSUM 漂移检测确认事件——双侧累积和越线且 N中M 确认（含当前样本 detection 条件）
时经检测器 trigger_recalibration 构造发布。数值告警事件（StrategicDeviationWarning
同族先例：数值+级别字段 + reliable 投递）；与 5.8「评估非领域概念」的分界——
评估结果服务单 run 应用观测（span 属性即载体），漂移确认是跨 run 聚合的领域级
质量状态变迁（事件是载体）。

通道治理：reliable 单通道（RabbitMQ + Outbox——告警不可丢；realtime Redis
pub/sub 对告警消费方无订阅面，不双通道）——event_channels.yaml 与
ChannelRouter.DEFAULT_MAPPINGS 双登记（CLAUDE.md 硬约束）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .base import DomainEvent


@dataclass(frozen=True)
class DriftDetected(DomainEvent):
    """CUSUM 漂移检测确认事件（确认漂移时发布——人工介入通知载体）

    触发语义：检测器 update 返回 is_drifted=True 的确认样本（N中M 确认含当前样本
    detection 条件——ISA-18.2 M-of-N 告警宣告语义）；确认即复位（OD-5——持续漂移
    下周期性再告警，重复告警间隔与漂移幅度反比）。

    MVP 唯一「提示人工介入」通道（OD-6）：recommended_action 固定 "manual_review"
    ——自动配置变更 V1（依赖漂移归因 + UDMR 运行时配置面）。

    direction 语义注记：up 可能是真实改进（重校准成功信号）或评估器漂移（judge
    变更/自评偏差）——消费方勿默认当系统故障处理；manual_review 是中性人工复核。

    Attributes:
        drift_id: 警告唯一标识符（uuid4 自动生成——aggregate 锚）
        agent_id: 漂移监控对象 Agent 标识（调用方 execute 形参透传；
            None=未知/混合——SINGLETON 检测器跨 Agent 混流知悉：多 Agent 质量
            分布差异膨胀 σ₀，per-agent 键控是 V1 形态）
        metric_name: 漂移检测指标名（检测器绑定常量——"overall_score"）
        drift_direction: 漂移方向（"up" 上漂/"down" 下漂）
        drift_level: 漂移级别（"moderate" 5σ<S≤8σ / "severe" S>8σ——minor 观察
            档不可达注记 OD-5：确认前提含当前样本 detection → ratio>5 恒成立）
        cusum_high: 确认时上侧累积和（≥0）
        cusum_low: 确认时下侧累积和（≥0）
        baseline_mean: 冻结基线均值 μ₀
        baseline_std: 冻结基线标准差 σ₀（样本标准差 ddof=1 语义）
        observed_value: 确认样本值（[0,1]——overall_score 语义）
        sample_count: 确认时累计样本数（含预热期）
        recommended_action: 建议动作（固定 "manual_review"——OD-6）
        event_type: 事件类型，固定为 "DriftDetected"（init=False——自动注册）
    """

    drift_id: uuid.UUID = field(default_factory=uuid.uuid4)
    agent_id: str | None = field(kw_only=True, default=None)
    metric_name: str = field(kw_only=True)
    drift_direction: str = field(kw_only=True)
    drift_level: str = field(kw_only=True)
    cusum_high: float = field(kw_only=True)
    cusum_low: float = field(kw_only=True)
    baseline_mean: float = field(kw_only=True)
    baseline_std: float = field(kw_only=True)
    observed_value: float = field(kw_only=True)
    sample_count: int = field(kw_only=True)
    recommended_action: str = "manual_review"
    event_type: str = field(default="DriftDetected", init=False)

    def __post_init__(self) -> None:
        """设置 aggregate_id 和 aggregate_type（漂移的监控对象是 Agent 评估质量）。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.drift_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "AgentEvaluation")
