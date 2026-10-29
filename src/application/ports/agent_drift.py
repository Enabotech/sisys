"""Agent 漂移检测端口族（Story 5.9 — FR-EV-03 漂移检测面）。

漂移族端口聚合文件：``DriftDetectionPort``（检测+重校准触发契约）+
``DriftAssessment`` DTO——与 ``agent_tracing``/``agent_evaluation`` 同族命名
（Agent 评估可观测族 5.7-5.9 的应用契约层第三端口，文件名=端口名先例延续）。

端口命名甄别：区别于 ``MetricsPort``（Prometheus 计量导出——计量收集面）与
``ExceptionMetricsPort``（异常计量）——本端口是漂移判定面（时序统计检测），
三者语义分立。drift 检测消费评估产物（5.8 下游）但独立成端口——检测状态
生命周期与评估编排解耦（评估无状态[5.8 DC-9] vs 检测器有状态[5.9 DC-6——
状态即功能：跨 run 序列累积]）。

设计决策（R1/R2/R3 规则落地）：
- EventPublisher（domain 基础端口 R1）被检测器实现组合注入（R2——事件发布是
  重校准触发的组成部分）；
- CUSUM 状态管理（进程内累积/预热/复位生命周期）是技术实现面（R3）——
  CUSUMDriftDetector 在 infrastructure/monitoring 实现（architecture.md L2594
  钦定位置），可替换（Redis 持久化实现/多指标扩展——V1 演化轴）；
- 本文件纯标准库零第三方（Protocol + dataclass——agent_tracing/
  agent_evaluation 同款形态；ValidationError 从 domain.exceptions import）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.domain.exceptions import ValidationError

__all__ = ["DriftAssessment", "DriftDetectionPort"]

#: drift_direction 合法域（"none" 仅未确认态——确认语义锁 level 但方向可带探测值）
_DRIFT_DIRECTIONS = ("up", "down", "none")

#: drift_level 合法域（minor 观察档不可达——OD-5：确认前提含当前样本 detection
#: → max(Sₕ,Sₗ)>h=5σ₀ 恒成立 → ratio>5，仅 moderate/severe 可达）
_DRIFT_LEVELS = ("moderate", "severe", "none")


@dataclass(frozen=True)
class DriftAssessment:
    """漂移检测评估结果（十字段——应用层 DTO，与 EvaluationResult 同层同风格）。

    字段语义对照表（OD-7——单方法 update 的原子返回值，is_drifted() 判定语义
    由返回值字段承载）：

    - ``is_drifted``：本样本是否确认漂移（N中M 确认含当前样本 detection 条件）。
    - ``baseline_ready``：基线是否就绪（前 30 样本预热期 False——预热态可观测）。
    - ``drift_direction``：漂移方向探测值（"up"/"down"；未确认态可带探测值——
      Sₕ==Sₗ 平局归 "none"，确认语义只锁 level）。
    - ``drift_level``：漂移级别（确认态 "moderate"/"severe"；未确认态恒 "none"）。
    - ``cusum_high``/``cusum_low``：双侧累积和当前值（≥0——max(0,·) 语义）。
    - ``baseline_mean``/``baseline_std``：预热期当前统计或冻结基线（N=1 时
      baseline_std=0.0——statistics.stdev 需 ≥2 样本）。
    - ``observed_value``：本样本值（[0,1]——overall_score 语义）。
    - ``sample_count``：累计样本数（≥1，含预热期）。

    可观测性注记：逐样本 detection 布尔不进 DTO——detection 断言经
    ``cusum_high/low 与 h=5×baseline_std 同式比较`` 推导承载。
    """

    is_drifted: bool
    baseline_ready: bool
    drift_direction: str
    drift_level: str
    cusum_high: float
    cusum_low: float
    baseline_mean: float
    baseline_std: float
    observed_value: float
    sample_count: int

    def __post_init__(self) -> None:
        """字段域守卫（[0,1] + 非负 + Literal 域 + 确认一致性——应用层输入校验）。

        Raises:
            ValidationError: EXCEPTION_201——observed_value 越界/类型非数值/bool、
                cusum 负值、sample_count < 1、direction/level 域外、is_drifted 与
                direction/level 一致性违反（context 携 ``{字段名: 实际值}``——
                242 惯例形态）。
        """
        value = self.observed_value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(
                message=f"漂移检测 observed_value 必须为数值（实际 {type(value).__name__}）",
                context={"observed_value": str(value)},
            )
        if not 0.0 <= value <= 1.0:
            raise ValidationError(
                message=f"漂移检测 observed_value 越界 [0,1]（实际 {value}）",
                context={"observed_value": str(value)},
            )
        if self.cusum_high < 0:
            raise ValidationError(
                message=f"漂移检测 cusum_high 必须非负（实际 {self.cusum_high}）",
                context={"cusum_high": str(self.cusum_high)},
            )
        if self.cusum_low < 0:
            raise ValidationError(
                message=f"漂移检测 cusum_low 必须非负（实际 {self.cusum_low}）",
                context={"cusum_low": str(self.cusum_low)},
            )
        if self.sample_count < 1:
            raise ValidationError(
                message=f"漂移检测 sample_count 必须 ≥1（实际 {self.sample_count}）",
                context={"sample_count": str(self.sample_count)},
            )
        if self.drift_direction not in _DRIFT_DIRECTIONS:
            raise ValidationError(
                message=f"漂移检测 drift_direction 域外（实际 {self.drift_direction!r}，合法 {_DRIFT_DIRECTIONS}）",
                context={"drift_direction": str(self.drift_direction)},
            )
        if self.drift_level not in _DRIFT_LEVELS:
            raise ValidationError(
                message=f"漂移检测 drift_level 域外（实际 {self.drift_level!r}，合法 {_DRIFT_LEVELS}）",
                context={"drift_level": str(self.drift_level)},
            )
        if self.is_drifted:
            if self.drift_direction == "none" or self.drift_level == "none":
                raise ValidationError(
                    message="确认漂移 assessment 的 drift_direction/drift_level 不可为 none（事件语义污染防线）",
                    context={"is_drifted": str(self.is_drifted)},
                )
        elif self.drift_level != "none":
            raise ValidationError(
                message="未确认 assessment 的 drift_level 必须为 none（确认语义只锁 level）",
                context={"is_drifted": str(self.is_drifted)},
            )


@runtime_checkable
class DriftDetectionPort(Protocol):
    """Agent 漂移检测端口（R2 具体应用端口——Agent 评估可观测族应用契约）。

    检测编排：双侧累积和增量更新 + N中M 确认（含当前样本 detection 条件）+
    确认后复位 + 重校准触发（DriftDetected 领域事件发布）。实现方：
    ``CUSUMDriftDetector``（infrastructure/monitoring/cusum_detector.py——
    architecture.md L2594 钦定；EventPublisher 组合注入——事件发布是重校准
    触发的组成部分）。
    """

    async def update(self, score: float) -> DriftAssessment:
        """灌入单个评估分数并执行漂移检测（原子——累积+判定+确认一次调用完成）。

        OD-7：伪码 update + is_drifted() 两方法形态的单方法原子化——两方法形态
        在并发/异常路径下存在中间态（update 成功 is_drifted 未调）语义模糊；
        is_drifted 判定语义由返回值字段承载。

        三阶段管线：①预热期（前 30 样本入基线窗，baseline_ready=False 不判定
        不累积）→ ②检测期（双侧累积和 O(1) 增量 + 每样本 detection 判定记入
        确认窗 + N中M 确认）→ ③确认后复位（Sₕ/Sₗ 归零 + 确认窗清空——基线
        保持，OD-5）。

        Args:
            score: 本次评估 overall_score（[0,1] 闭区间）。

        Returns:
            DriftAssessment: 本次检测评估（十字段——事件构造、span 判定、
            测试断言的统一数据源）。

        Raises:
            ValidationError: EXCEPTION_201——score 域校验（越界/bool/非数值）。
            DriftDetectionError: EXCEPTION_451——检测管线状态异常防御面
                （理论不可达态——主链降级网捕获）。
        """
        ...

    async def trigger_recalibration(self, assessment: DriftAssessment, agent_id: str | None = None) -> None:
        """触发重校准（确认漂移后：构造并发布 DriftDetected 事件 + logger.warning）。

        未确认守卫（与调用方守卫双保险——R1 裁定）：is_drifted=False 的
        assessment 直接 return None 零发布（防 level="none" 泄入事件语义污染）。
        OD-6：MVP「提示人工介入」单通道（reliable 事件——人工介入通知），
        自动配置变更 V1。

        Args:
            assessment: 确认漂移的检测评估（事件字段数据源）。
            agent_id: 漂移监控对象 Agent 标识（execute 形参透传；None=未知——
                SINGLETON 跨 Agent 混流知悉）。

        Raises:
            无（发布失败内部 logger.error 降级不上抛——可观测附加面：
            agent_profile_loading L151-169 先例，事件失败不阻断主链也不阻断
            已确认的检测语义）。
        """
        ...
