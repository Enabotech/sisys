"""Agent 评估历史检查点端口族（Story 5.10 — FR-EV-04 持久化面）。

检查点族端口聚合文件：``AgentCheckpointPort``（评估历史累积+持久化+恢复契约）+
``EvaluationCheckpoint`` DTO + ``CheckpointWithEvaluation`` 聚合——与
``agent_tracing``/``agent_evaluation``/``agent_drift`` 同族命名（Agent 评估可观测族
5.7-5.10 的应用契约层第四端口，文件名=端口名先例延续）。

端口命名甄别：区别于 ``SnapshotRepositoryProtocol``（domain/ports——快照仓储基础
端口 R1，save/load/delete 通用 KV 语义）：``AgentCheckpointPort`` 是评估域具体
应用端口（R2——组合注入 SnapshotRepositoryProtocol 承载「累积→打包→持久化→恢复」
编排语义）；评估历史三序列经 ``state_data`` 四键承载（OD-3——实体零扩字段，
``evaluation_history``/``hallucination_trend``/``confidence_accuracy_trend``/
``agent_id``），``stage_id="evaluation"`` 与 BLM 阶段快照（6.3）语义分界。

设计决策（R1/R2/R3 规则落地）：
- SnapshotRepositoryProtocol（domain 基础端口 R1）被 Recorder 实现组合注入
  （R2——评估域应用端口编排存储端口，RedisSnapshotStore 是 R3 既有实现零改动）；
- record 单方法原子完成「内存累积 + 打包 + save」（OD-7——两方法形态的中间态
  无消费语义）；restore 是恢复式语义非只读查询（灌回三 deque + state_version
  续接——AC-3② 累积延续的机制承载）；
- 趋势序列由 Recorder 自持累积（OD-4——检测器窗口是算法态非历史源，
  CUSUMDriftDetector 零改动）；
- 本文件纯标准库零第三方（Protocol + dataclass——agent_tracing/agent_evaluation/
  agent_drift 同款形态；ValidationError 从 domain.exceptions import、
  CheckpointSnapshot 从 domain.entities import、EvaluationResult 从同层 import）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from src.application.ports.agent_evaluation import EvaluationResult
from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.exceptions import ValidationError

__all__ = [
    "EVALUATION_SESSION_PREFIX",
    "MAX_HISTORY_SIZE",
    "AgentCheckpointPort",
    "CheckpointWithEvaluation",
    "EvaluationCheckpoint",
]

#: 评估历史窗口上限（OD-8——deque maxlen 单源，最旧滚动丢弃，三序列同窗同步滚动；
#: 每次 record 全量重写 Redis latest（覆盖语义），无界历史会使快照体积随 run 数线性
#: 膨胀击穿 P95<100ms 门。窗口外完整序列的留存通道是 OTel span（eval.* 三键 per-run
#: 留痕——Phoenix 查询面）；DriftDetected 事件仅留存确认漂移的稀疏锚点，非历史序列
#: 通道——通道语义分述。上限值 V1 可调（配置化非本 Story 面））
MAX_HISTORY_SIZE: int = 100

#: 评估快照会话命名空间前缀（DC-6 per-agent 聚合键——``agent-evaluation-{agent_id}``；
#: record 构造落盘键与消费方 restore 查键共用单源，禁两处字面量漂移[漂移即静默错键]）
EVALUATION_SESSION_PREFIX: str = "agent-evaluation-"

#: 五分数域守卫字段闭集（[0,1] 数值域——bool 排除，域守卫形态与 EvaluationResult/
#: DriftAssessment 同款）
_SCORE_FIELDS: tuple[str, ...] = (
    "hallucination_score",
    "context_relevance",
    "confidence_accuracy",
    "overall_score",
    "predicted_confidence",
)


@dataclass(frozen=True)
class EvaluationCheckpoint:
    """单条评估历史记录（七字段 frozen DTO——V1-EV3 兑现：predicted 必存）。

    五分数域守卫 [0,1]（越界/bool/非数值抛 ValidationError 201——context 携
    ``{字段名: str(实际值)}``）；recorded_at 是 datetime、agent_id 非空守卫
    （均非 [0,1] 分数域）。评估是可观测应用面非领域概念——应用层 DTO
    （EvaluationResult 同层同论证）。

    Attributes:
        recorded_at: 记录时刻（timezone-aware datetime——生产侧保证恒
            ``datetime.now(UTC)``：record 主链路径唯一生成点；isoformat →
            fromisoformat 往返保偏移。aware 是生产侧保证而非构造期守卫——
            naive 直构被静默接受[无下游比较消费方，deque 追加序即时间序；
            naive 唯一入口是外力腐坏快照的无时区 ISO 串——知悉注记]）。
        agent_id: 评估归属的 Agent 标识（非空守卫）。
        hallucination_score: 幻觉分（[0,1]——EvaluationResult 同名透传）。
        context_relevance: 上下文相关性（[0,1]）。
        confidence_accuracy: 置信度准确性（[0,1]）。
        overall_score: 综合分（[0,1]）。
        predicted_confidence: 执行链自报置信度（[0,1]——``result.evidence.confidence``
            直传；V1-EV3 钦定必须随快照持久化的 predicted——只存 EvaluationResult
            会丢 predicted）。
    """

    recorded_at: datetime
    agent_id: str
    hallucination_score: float
    context_relevance: float
    confidence_accuracy: float
    overall_score: float
    predicted_confidence: float

    def __post_init__(self) -> None:
        """域守卫（agent_id 非空 + 五分数 [0,1] 数值域——201 三段式形态）。"""
        if not self.agent_id:
            raise ValidationError(
                message="评估记录 agent_id 必须非空",
                context={"agent_id": str(self.agent_id)},
            )
        for field_name in _SCORE_FIELDS:
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError(
                    message=f"评估分数 {field_name} 必须为数值（实际 {type(value).__name__}）",
                    context={field_name: str(value)},
                )
            if not 0.0 <= value <= 1.0:
                raise ValidationError(
                    message=f"评估分数 {field_name} 越界 [0,1]（实际 {value}）",
                    context={field_name: str(value)},
                )


@dataclass(frozen=True)
class CheckpointWithEvaluation:
    """评估历史聚合（三序列 + 元数据 + CheckpointSnapshot 纯转换）。

    聚合保持设计命名的 frozen DTO（OD-7②）：有状态累积（deque 滚动窗口）归
    ``EvaluationCheckpointRecorder`` 实现（应用服务实现应用端口——evaluation_harness
    实现 AgentEvaluationPort 同款先例）；本聚合只做结构化字段⇄state_data 的
    纯转换（``to_checkpoint_snapshot``/``from_snapshot``——OD-3 键契约）。

    Attributes:
        agent_id: 聚合归属的 Agent 标识。
        evaluation_history: 评估历史记录序列（tuple——有序，deque 追加序即时间序）。
        hallucination_trend: 幻觉分趋势序列（与 history 等长，元素 [0,1] 数值域）。
        confidence_accuracy_trend: 置信度准确性趋势序列（与 history 等长，元素 [0,1] 数值域）。
    """

    agent_id: str
    evaluation_history: tuple[EvaluationCheckpoint, ...]
    hallucination_trend: tuple[float, ...]
    confidence_accuracy_trend: tuple[float, ...]

    def __post_init__(self) -> None:
        """聚合域守卫（等长先验 + trend 元素数值域后验——均抛 201）。

        校验顺序钦定：等长守卫（O(1)）先、trend 元素扫描（O(n)）后——
        便宜先行 fail-fast；等长不齐时元素值不参与判定（双违规形态以
        等长守卫文案抛出）。trend 元素与 history 五分数守卫对称（趋势值
        语义上是已守卫分数的镜像——合法值不可能越界；NaN 经链式比较
        为 False 天然拦截：json 序列化 allow_nan=True 可使 NaN 穿越存储
        往返，恢复侧不得静默灌回[代码审查 R1]）。
        """
        history_len = len(self.evaluation_history)
        if not (history_len == len(self.hallucination_trend) == len(self.confidence_accuracy_trend)):
            raise ValidationError(
                message=(
                    "聚合三序列必须等长（"
                    f"history={history_len}, hallucination_trend={len(self.hallucination_trend)}, "
                    f"confidence_accuracy_trend={len(self.confidence_accuracy_trend)}）"
                ),
                context={"history_len": str(history_len)},
            )
        for trend_name, trend in (
            ("hallucination_trend", self.hallucination_trend),
            ("confidence_accuracy_trend", self.confidence_accuracy_trend),
        ):
            for value in trend:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
                    raise ValidationError(
                        message=f"趋势序列 {trend_name} 元素必须为 [0,1] 数值（实际 {value!r}）",
                        context={trend_name: str(value)},
                    )

    def to_checkpoint_snapshot(self, session_id: str = "", state_version: int = 1) -> CheckpointSnapshot:
        """打包为 CheckpointSnapshot（结构化字段 → state_data 四键——OD-3 键契约）。

        Args:
            session_id: 快照会话标识（``agent-evaluation-{agent_id}`` 命名空间——
                Recorder 构造传入；聚合纯转换无状态）。
            state_version: 快照版本号（默认 1——递增语义归 Recorder 内存计数器：
                record 打包传当前值后 +1、restore 续接 snapshot.state_version + 1）。

        Returns:
            CheckpointSnapshot：stage_id="evaluation" + state_data 四键
            （agent_id / evaluation_history[记录 dict 列表——recorded_at 经 isoformat
            字符串化] / hallucination_trend / confidence_accuracy_trend）。
        """
        return CheckpointSnapshot(
            session_id=session_id,
            stage_id="evaluation",
            state_version=state_version,
            state_data={
                "agent_id": self.agent_id,
                "evaluation_history": [
                    {
                        "recorded_at": checkpoint.recorded_at.isoformat(),
                        "agent_id": checkpoint.agent_id,
                        "hallucination_score": checkpoint.hallucination_score,
                        "context_relevance": checkpoint.context_relevance,
                        "confidence_accuracy": checkpoint.confidence_accuracy,
                        "overall_score": checkpoint.overall_score,
                        "predicted_confidence": checkpoint.predicted_confidence,
                    }
                    for checkpoint in self.evaluation_history
                ],
                "hallucination_trend": list(self.hallucination_trend),
                "confidence_accuracy_trend": list(self.confidence_accuracy_trend),
            },
        )

    @classmethod
    def from_snapshot(cls, snapshot: CheckpointSnapshot) -> CheckpointWithEvaluation:
        """从 CheckpointSnapshot 解包聚合（state_data 四键 → 结构化字段）。

        纯转换不做结构校验（缺键/类型不符的 KeyError/ValueError/TypeError 由
        Recorder.restore 捕获包装 EvaluationHistoryError 452——fail-loud 防御面
        归端口实现层）；recorded_at 经 fromisoformat 还原 datetime（json_loads
        不自动还原类型——调用方自行重建）。

        Args:
            snapshot: 快照实体（state_data 应含四键——正常路径快照由本聚合产出）。

        Returns:
            CheckpointWithEvaluation：三序列逐值还原的聚合。
        """
        state_data = snapshot.state_data
        history = tuple(
            EvaluationCheckpoint(
                recorded_at=datetime.fromisoformat(record["recorded_at"]),
                agent_id=record["agent_id"],
                hallucination_score=record["hallucination_score"],
                context_relevance=record["context_relevance"],
                confidence_accuracy=record["confidence_accuracy"],
                overall_score=record["overall_score"],
                predicted_confidence=record["predicted_confidence"],
            )
            for record in state_data["evaluation_history"]
        )
        return cls(
            agent_id=state_data["agent_id"],
            evaluation_history=history,
            hallucination_trend=tuple(state_data["hallucination_trend"]),
            confidence_accuracy_trend=tuple(state_data["confidence_accuracy_trend"]),
        )


@runtime_checkable
class AgentCheckpointPort(Protocol):
    """评估历史检查点端口（record + restore 两方法契约——OD-7 原子形态）。

    实现方：``EvaluationCheckpointRecorder``（application/services——组合注入
    SnapshotRepositoryProtocol）。MVP 唯一实现经组合根 ``agent_checkpoint``
    注册（SINGLETON——跨 run 累积，状态即功能）。

    窗口语义：三序列 deque maxlen=MAX_HISTORY_SIZE 同窗滚动（最旧丢弃）；
    **per-agent 键控**（代码审查 R1 修正）：累积窗口按落盘命名空间
    ``agent-evaluation-{agent_id}`` 键控——同进程多 Agent（SINGLETON 共享
    Recorder 的常态路径）各窗隔离互不混串；restore 传入非规范 session_id
    时返回聚合但内存不续接任何 Agent 窗口（键即入参——record 永不触达该
    孤儿槽）。SINGLETON 累积仍是进程内的——多 worker 部署下各进程窗口分叉
    + Redis latest 覆盖写最后写者胜（MVP 单进程前提，风险登记——跨进程
    键控/粘性路由是 V1 多进程面）。
    """

    async def record(
        self,
        agent_id: str,
        evaluation_result: EvaluationResult,
        predicted: float,
    ) -> CheckpointSnapshot:
        """累积评估记录并持久化快照（原子三步：内存累积 → 打包 → save）。

        Args:
            agent_id: 评估归属的 Agent 标识（主链 execute 形参透传）。
            evaluation_result: 评估产物（frozen 实例直传，四分数不重算）。
            predicted: 执行链自报置信度（``result.evidence.confidence`` 直传——
                V1-EV3 兑现锚）。

        Returns:
            CheckpointSnapshot：已保存的快照（调用方可断言——session_id 命名空间
            ``agent-evaluation-{agent_id}`` + state_version 递增）。

        Raises:
            EvaluationHistoryError: 存储失败（StorageError 包装 452——内存累积
            保留，最终一致语义：下次 record 打包含本条后落盘收敛）或输入域
            违规（EvaluationCheckpoint 构造守卫的 ValidationError 收敛 452
            reason=invalid_input——端口唯一异常契约；主链路径三重上游守卫下
            不可达，直调消费方触发即达）。
        """
        ...

    async def restore(self, session_id: str) -> CheckpointWithEvaluation | None:
        """从快照恢复评估历史（恢复式语义——非只读查询）。

        副作用（OD-7③——AC-3② 累积延续的机制承载）：load → 解包聚合 → 灌回内部
        三 deque（deque maxlen 同窗裁剪——恢复聚合 ≤ 窗口上限由快照产出端 maxlen
        结构保证）→ state_version 计数器续接 snapshot.state_version + 1 → 返回聚合。

        Args:
            session_id: 快照会话标识（``agent-evaluation-{agent_id}`` 命名空间——
                消费方构造键请 import ``EVALUATION_SESSION_PREFIX`` 单源拼接，
                禁手写字面量[漂移即静默错键]）。

        Returns:
            CheckpointWithEvaluation | None：恢复的聚合；快照不存在返回 None
            （正常态——首次评估前无历史；store.load 任何异常含 Redis 故障均返回
            None——故障与不存在不可区分的双义知悉，恢复后累积从空窗起步）。

        Raises:
            EvaluationHistoryError: 快照结构不完整（state_data 缺键/类型错误/
            分数值域违规/trend 元素非法/三序列等长破坏——反序列化 fail-loud
            防御面，reason=invalid_structure 收敛全部结构异常族）。
        """
        ...
