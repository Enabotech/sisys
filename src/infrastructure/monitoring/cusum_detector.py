"""基础设施层 CUSUM 漂移检测器模块（Story 5.9 — FR-EV-03 漂移检测面）

architecture.md L2594 钦定位置（monitoring/ 归口——PhoenixTracer 同目录先例）。
DriftDetectionPort（application 端口）的实现：双侧累积和 + 预热基线 + N中M
确认 + 分级 + 确认后复位 + 重校准触发（DriftDetected 事件发布）。

三阶段状态机（每 update 调用 O(1) 增量）：

1. 预热期（前 30 样本）：样本入基线窗（deque maxlen=30），返回预热统计
   （baseline_ready=False 不判定不累积——σ₀ 未稳定即判定必是噪声误报）；
   第 30 样本入窗后统计 μ₀/σ₀ 并冻结（先入窗后统计——第 30 样本返回的统计
   即冻结值）。N=1 时 baseline_std=0.0（statistics.stdev 需 ≥2 样本）。
2. 检测期（第 31 样本起）：双侧累积和增量（附录 I §29.1.1.1 钦定公式）
   Sₕ = max(0, Sₕ + (x - μ₀ - k))、Sₗ = max(0, Sₗ + (μ₀ - k - x))，
   k = 0.5σ₀、h = 5σ₀；每样本判定 detection = max(Sₕ, Sₗ) > h 记入确认窗
   （deque maxlen=5）；N中M 确认（§29.3.2.2）：窗满 5 且计数 ≥3 且当前样本
   detection=True（ISA-18.2 M-of-N 告警宣告语义——确认时刻必在告警态；该条件
   使确认时 max(Sₕ,Sₗ)>h 恒成立 → ratio/σ₀>5、level 两档域完备）。
3. 确认后复位（OD-5）：确认即 Sₕ/Sₗ 归零 + 确认窗清空（基线保持）——持续
   漂移下周期性再告警（间隔与漂移幅度反比：δ=0.4≈5 样本、δ=0.15≈8 样本）。

关键设计裁定（详见 5-9 故事 DC-2/DC-6/DC-7 + OD-2/OD-3/OD-4/OD-5）：
- 纯标准库零第三方（OD-2——statistics/collections；附录 I 参考实现的
  numpy/scipy 不采用：O(1) 增量无向量化需求，基线仅需 mean/std[ddof=1]）；
- 冻结基线（OD-3——漂移检测的前提是基线不随漂移漂移；滑动基线会掩蔽慢漂移，
  V1 按需）；单指标 overall_score（OD-4——MVP 唯一连续序列源；检测器不感知
  Agent，SINGLETON 跨 Agent 混流知悉：多 Agent 质量分布差异膨胀 σ₀——per-agent
  键控 V1）；
- severity 乘法同式比较实现（S>8σ₀ severe / 5σ₀<S≤8σ₀ moderate——与 detection
  判定同乘法系，域完备免除法舍入在 1ulp 邻域的 ratio=5.0 边界击穿；ratio 保留
  为导出语义注记）；minor 观察档（3σ<S≤5σ「记录日志不告警」）不进确认历史，
  确认前提使其不可达（OD-5②）；
- degenerate 防御（σ₀ < 1e-12 → detection 恒 False）：全同值样本下 k=h=0 恒
  触发的数学病态防线——防线缺失时确认路径 ratio=S/σ₀ 先 ZeroDivisionError
  崩溃（防线必要性强于恒触发；可观测降级非异常——样本计数继续累积）；
- 评估降级的序列缺口 = 跳过（评估失败 run 漂移块不执行，缺口不入累积——
  CUSUM 连续性假设知悉：缺口期间检测灵敏度下降是跳过策略的代价，缺口计数器
  V1-EV13 登记）；
- k/h 是 σ₀ 相对量——overall 可达域压缩（两病态角带包络 [0.475,0.65]）与六档
  锚定多峰（h 序列聚集 6 锚点值——σ₀ 估计呈多峰、累积和呈阶梯）天然适配：压缩
  只影响 σ₀ 估计值不影响检测机制；n=30 时 σ̂₀ 相对标准误 ≈1/√(2×30)≈13% →
  h 绝对值 ±13% 波动、名义 ARL₀ 可漂一个量级（合成回测 FP 主因，知悉注记）。

生命周期：SINGLETON（有状态——状态即功能：跨 run 序列累积[预热 30 + 检测期]
必须跨 execute 调用存活）；进程生命周期 = 检测序列生命周期（重启归零重新预热
——MVP 可接受，V1 Redis 持久化 V1-EV12 登记）。
"""

from __future__ import annotations

import logging
import statistics
from collections import deque

from src.application.ports.agent_drift import DriftAssessment
from src.domain.events.drift_events import DriftDetected
from src.domain.exceptions import ValidationError
from src.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger(__name__)

__all__ = [
    "CONFIRMATION_M",
    "CONFIRMATION_N",
    "H_MULTIPLIER",
    "K_MULTIPLIER",
    "METRIC_NAME",
    "WARMUP_SAMPLES",
    "CUSUMDriftDetector",
]

#: 检测器绑定指标名（OD-4——单指标收窄：MVP 唯一连续序列源是评估块内存返回的
#: overall_score；多指标逐键归因 V1-EV9）
METRIC_NAME = "overall_score"

#: 容许度 k 乘数（附录 I §29.3.1.1 标准 CUSUM 参数 + §29.3.3.2 质量指标 accuracy
#: 行——overall 是合成质量分取标准档；k=δ/2=0.5σ 对 1σ 移位最优）
K_MULTIPLIER = 0.5

#: 决策阈值 h 乘数（§29.3.1.1——h=5σ₀ ↔ ARL₀≈465 保守档）
H_MULTIPLIER = 5.0

#: N中M 确认阈值 N（§29.3.2.2 警告级 3中5——单点异常误报抑制）
CONFIRMATION_N = 3

#: N中M 确认窗长 M（§29.3.2.2）
CONFIRMATION_M = 5

#: 预热样本量（§29.2.3.2 正态性检验最小样本量下限锚——OD-3：附录 I 的 14 天
#: 采集期 ≥1000 样本在 MVP 验收窗口不可满足，30 样本 ≈ per-run 频率下可达量级）
WARMUP_SAMPLES = 30

#: σ₀ 退化防线阈值（全同值样本 σ₀=0 → k=h=0 恒触发的数学病态——detection 恒 False）
_DEGENERATE_STD_EPSILON = 1e-12

#: severity 判定乘数（与 detection 判定同乘法系——moderate/severe 分界 8σ₀）
_SEVERE_MULTIPLIER = 8.0


class CUSUMDriftDetector:
    """CUSUM 双侧累积和漂移检测器（DriftDetectionPort 实现——纯内存 O(1) 增量）。

    状态即功能（DC-6）：基线窗/Sₕ/Sₗ/确认窗/样本计数跨 update 调用存活——
    SINGLETON 生命周期由组合根管理；测试全形态手工构造新实例（不走 resolve——
    跨测试序列污染防线）。
    """

    def __init__(self, event_publisher: EventPublisher | None = None) -> None:
        """初始化检测器。

        Args:
            event_publisher: 事件发布端口（domain 基础端口——R2 组合注入：事件
                发布是重校准触发的组成部分；None 允许[纯检测消费面]）。
        """
        self._event_publisher = event_publisher
        self._baseline_window: deque[float] = deque(maxlen=WARMUP_SAMPLES)
        self._baseline_frozen = False
        self._baseline_mean = 0.0
        self._baseline_std = 0.0
        self._cusum_high = 0.0
        self._cusum_low = 0.0
        self._confirmation_window: deque[bool] = deque(maxlen=CONFIRMATION_M)
        self._sample_count = 0

    async def update(self, score: float) -> DriftAssessment:
        """灌入单个评估分数并执行漂移检测（原子——累积+判定+确认一次调用）。

        Args:
            score: 本次评估 overall_score（[0,1] 闭区间）。

        Returns:
            DriftAssessment: 本次检测评估（预热期返回预热统计不判定）。

        Raises:
            ValidationError: EXCEPTION_201——score 域校验（越界/bool/非数值，
                context 携 ``{"score": 实际值}``；守卫失败不消耗样本计数）。
        """
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValidationError(
                message=f"漂移检测 score 必须为数值（实际 {type(score).__name__}）",
                context={"score": str(score)},
            )
        if not 0.0 <= score <= 1.0:
            raise ValidationError(
                message=f"漂移检测 score 越界 [0,1]（实际 {score}）",
                context={"score": str(score)},
            )
        self._sample_count += 1
        observed = float(score)

        # 阶段 1：预热期（前 30 样本入窗——先入窗后统计，第 30 样本返回满窗统计）
        if not self._baseline_frozen:
            self._baseline_window.append(observed)
            window_size = len(self._baseline_window)
            if window_size >= WARMUP_SAMPLES:
                self._baseline_mean = statistics.mean(self._baseline_window)
                self._baseline_std = statistics.stdev(self._baseline_window)
                self._baseline_frozen = True
            return DriftAssessment(
                is_drifted=False,
                baseline_ready=False,
                drift_direction=self._probe_direction(),
                drift_level="none",
                cusum_high=0.0,
                cusum_low=0.0,
                baseline_mean=statistics.mean(self._baseline_window),
                baseline_std=statistics.stdev(self._baseline_window) if window_size >= 2 else 0.0,
                observed_value=observed,
                sample_count=self._sample_count,
            )

        # 阶段 2：检测期（双侧累积和 O(1) 增量——附录 I §29.1.1.1 钦定公式）
        k = K_MULTIPLIER * self._baseline_std
        h = H_MULTIPLIER * self._baseline_std
        self._cusum_high = max(0.0, self._cusum_high + (observed - self._baseline_mean - k))
        self._cusum_low = max(0.0, self._cusum_low + (self._baseline_mean - k - observed))
        # degenerate 防线：σ₀ 退化（全同值基线）时 k=h=0 恒触发 → detection 恒 False
        detection = self._baseline_std >= _DEGENERATE_STD_EPSILON and max(self._cusum_high, self._cusum_low) > h
        self._confirmation_window.append(detection)

        # N中M 确认（§29.3.2.2 + 当前样本条件——ISA-18.2 M-of-N 告警宣告语义）
        confirmed = (
            len(self._confirmation_window) >= CONFIRMATION_M and sum(self._confirmation_window) >= CONFIRMATION_N and detection
        )
        if confirmed:
            assessment = DriftAssessment(
                is_drifted=True,
                baseline_ready=True,
                drift_direction=self._determine_direction(),
                drift_level=self._determine_severity(),
                cusum_high=self._cusum_high,
                cusum_low=self._cusum_low,
                baseline_mean=self._baseline_mean,
                baseline_std=self._baseline_std,
                observed_value=observed,
                sample_count=self._sample_count,
            )
            # 阶段 3：确认后复位（OD-5——S 归零 + 窗清空，基线保持）
            self._cusum_high = 0.0
            self._cusum_low = 0.0
            self._confirmation_window.clear()
            return assessment

        return DriftAssessment(
            is_drifted=False,
            baseline_ready=True,
            drift_direction=self._probe_direction(),
            drift_level="none",
            cusum_high=self._cusum_high,
            cusum_low=self._cusum_low,
            baseline_mean=self._baseline_mean,
            baseline_std=self._baseline_std,
            observed_value=observed,
            sample_count=self._sample_count,
        )

    async def trigger_recalibration(self, assessment: DriftAssessment, agent_id: str | None = None) -> None:
        """触发重校准（确认漂移后：构造并发布 DriftDetected 事件 + warning 日志）。

        未确认守卫（与调用方守卫双保险）：is_drifted=False 直接 return None 零发布
        ——防 level="none" 泄入事件语义污染。发布失败 logger.error 降级不上抛
        （可观测附加面——agent_profile_loading L151-169 先例：事件失败不阻断主链
        也不阻断已确认的检测语义）。

        Args:
            assessment: 确认漂移的检测评估（事件字段数据源）。
            agent_id: 漂移监控对象 Agent 标识（execute 形参透传；None=未知——
                SINGLETON 跨 Agent 混流知悉）。
        """
        if not assessment.is_drifted:
            return None
        event = DriftDetected(
            agent_id=agent_id,
            metric_name=METRIC_NAME,
            drift_direction=assessment.drift_direction,
            drift_level=assessment.drift_level,
            cusum_high=assessment.cusum_high,
            cusum_low=assessment.cusum_low,
            baseline_mean=assessment.baseline_mean,
            baseline_std=assessment.baseline_std,
            observed_value=assessment.observed_value,
            sample_count=assessment.sample_count,
        )
        logger.warning(
            "CUSUM 漂移确认（触发重校准——人工介入通道）: metric=%s direction=%s level=%s agent_id=%s sample_count=%s",
            METRIC_NAME,
            assessment.drift_direction,
            assessment.drift_level,
            agent_id,
            assessment.sample_count,
        )
        if self._event_publisher is None:
            return None
        try:
            publish_result = await self._event_publisher.publish(event)
            if publish_result is not None and not publish_result.is_success:
                logger.error(
                    "DriftDetected 事件发布未成功: agent_id=%s channels=%s",
                    agent_id,
                    publish_result.results,
                )
        except Exception as exc:
            # 事件发布失败不阻断检测语义（对齐 agent_profile_loading 先例）
            logger.error("DriftDetected 事件发布失败（降级不阻断）: %s", exc, exc_info=True)
        return None

    def _probe_direction(self) -> str:
        """方向探测值（未确认态——Sₕ vs Sₗ 大者，平局归 none）。"""
        if self._cusum_high > self._cusum_low:
            return "up"
        if self._cusum_low > self._cusum_high:
            return "down"
        return "none"

    def _determine_direction(self) -> str:
        """确认态方向判定（§29.7.1 _determine_direction——Sₕ vs Sₗ 大者）。

        确认前提含当前样本 detection → max(Sₕ,Sₗ)>h>0；增长侧 S 与衰减侧 S 的
        平局在确认时刻不可达（通往平局的路径必先满足确认条件被复位——棘轮论证，
        R3 时间线 T5 推演）。
        """
        if self._cusum_high >= self._cusum_low:
            return "up"
        return "down"

    def _determine_severity(self) -> str:
        """确认态级别判定（§29.3.2.1 两档——乘法同式比较实现）。

        severe（S>8σ₀）/ moderate（5σ₀<S≤8σ₀）；minor 观察档（3σ<S≤5σ「记录
        日志不告警」）不进确认历史——确认前提使 S>5σ₀ 恒成立，minor 不可达
        （OD-5②；ratio = S/σ₀ 是导出语义注记）。
        """
        peak = max(self._cusum_high, self._cusum_low)
        if peak > _SEVERE_MULTIPLIER * self._baseline_std:
            return "severe"
        return "moderate"
