"""评估历史检查点记录器（Story 5.10 — FR-EV-04 持久化面）。

``EvaluationCheckpointRecorder`` 实现 ``AgentCheckpointPort``（application 端口），
组合注入 ``SnapshotRepositoryProtocol``（domain 基础端口 R1——R2 应用端口组合注入
领域基础端口；RedisSnapshotStore 是 R3 既有存储实现零改动）。

职责边界：本类是有状态累积器（三 deque 滚动窗口 + state_version 内存计数器）；
结构化字段⇄state_data 纯转换归 ``CheckpointWithEvaluation`` 聚合（frozen DTO）；
存储序列化归 ``RedisSnapshotStore``（pipeline 原子写 + latest 覆盖语义）。

生命周期注记（DC-7）：组合根注册 SINGLETON——跨 run 累积（进程生命周期 = 历史
生命周期，「状态即功能」——5.9 检测器同款论证）；注入的 snapshot_repository 是
SCOPED 注册，但组合根 lambda 在 SINGLETON 端口首次 resolve 时执行一次并固定实例
——RedisSnapshotStore 无状态（委托 adapter，连接由 adapter 持有）固定实例安全。
**MVP 单进程前提显式声明**：多 worker 部署下各进程累积器分叉 + Redis latest 覆盖写
（最后写者胜）使其他 worker 的窗口外谱系静默丢失；同 agent 并发 record 的落盘序
竞争后果良性（打包含对方记录后落盘收敛、仅服务端到达序反转时 Redis 短暂少一条且
下次 record 自愈——内存是全窗真源）；per-agent 键控/粘性路由是 V1 多进程面。
**重启回退知悉**：单进程异常重启后未 restore 直接 record → 计数器归 1 + 空窗，
首 record 以 state_version=1/单条历史覆盖 Redis latest（历史与版本双回退——内存
计数器与 AutoExecuteService load-derived 递增[天然重启安全]的机制差异；主链不调
restore，「重启存活」的完整兑现依赖未来消费方[V1-EV12/6.3]启动时 restore）。

通道语义分述（OD-8④）：窗口外完整序列的留存通道是 OTel span（eval.* 三键
per-run 留痕——Phoenix 查询面，保留期随部署配置）；DriftDetected 事件仅在确认
漂移时发布（稀疏锚点——单确认样本 + CUSUM 统计，非历史序列通道）。

最终一致语义：record 的 save 失败（StorageError → 452）时内存累积保留——下次
record 打包含失败条目后落盘收敛（452 不阻断主链——独立降级网）。
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from src.application.ports.agent_checkpoint import (
    MAX_HISTORY_SIZE,
    AgentCheckpointPort,
    CheckpointWithEvaluation,
    EvaluationCheckpoint,
)
from src.application.ports.agent_evaluation import EvaluationResult
from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.exceptions import EvaluationHistoryError, StorageError
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol

__all__ = ["EvaluationCheckpointRecorder"]


class EvaluationCheckpointRecorder(AgentCheckpointPort):
    """评估历史累积器 + Checkpoint 快照记录器（AgentCheckpointPort 端口实现）。

    跨 run 累积三序列（deque maxlen=MAX_HISTORY_SIZE 同窗滚动——最旧丢弃），
    record 原子完成「内存累积 → to_checkpoint_snapshot 打包 → save 持久化」
    （OD-7——累积与持久化两方法形态的中间态无消费语义）；restore 是恢复式语义
    （load → 解包 → 灌回三 deque → state_version 计数器续接 → 返回聚合——
    非只读查询）。

    Attributes:
        _snapshot_repository: 快照仓储端口（R1 基础端口——存储委托）。
        _history: 评估历史滚动窗口（deque maxlen=MAX_HISTORY_SIZE）。
        _h_trend: 幻觉分趋势窗口（与 _history 同窗同步滚动）。
        _ca_trend: 置信度准确性趋势窗口（与 _history 同窗同步滚动）。
        _state_version: 快照版本内存计数器（初始 1——record 打包传当前值，
            **save 成功后 +1**[失败不消耗版本号——版本数 == 成功落盘数]；restore
            续接 snapshot.state_version + 1——重启后版本延续递增）。
    """

    def __init__(self, snapshot_repository: SnapshotRepositoryProtocol) -> None:
        """初始化记录器（组合注入快照仓储端口——R2）。

        Args:
            snapshot_repository: 快照仓储端口（组合根 snapshot_repository 注册
                resolve 注入——RedisSnapshotStore 生产实现）。
        """
        self._snapshot_repository = snapshot_repository
        self._history: deque[EvaluationCheckpoint] = deque(maxlen=MAX_HISTORY_SIZE)
        self._h_trend: deque[float] = deque(maxlen=MAX_HISTORY_SIZE)
        self._ca_trend: deque[float] = deque(maxlen=MAX_HISTORY_SIZE)
        self._state_version: int = 1

    async def record(
        self,
        agent_id: str,
        evaluation_result: EvaluationResult,
        predicted: float,
    ) -> CheckpointSnapshot:
        """累积评估记录并持久化快照（原子三步——OD-7①）。

        步骤：内存累积（三 deque 追加）→ 聚合打包（state_version 传当前计数器值）
        → save 委托 → 成功后计数器 +1 → 返回已保存快照（调用方可断言）。

        Args:
            agent_id: 评估归属的 Agent 标识（主链 execute 形参透传）。
            evaluation_result: 评估产物（frozen 实例直传，四分数不重算）。
            predicted: 执行链自报置信度（result.evidence.confidence 直传——V1-EV3 兑现）。

        Returns:
            CheckpointSnapshot: 已保存的快照（session_id 命名空间
            ``agent-evaluation-{agent_id}`` + stage_id="evaluation"）。

        Raises:
            EvaluationHistoryError: save 抛 StorageError 时包装上抛（cause 链保留；
            内存累积保留——最终一致语义，下次 record 打包含本条后落盘收敛）。
        """
        checkpoint = EvaluationCheckpoint(
            recorded_at=datetime.now(UTC),
            agent_id=agent_id,
            hallucination_score=evaluation_result.hallucination_score,
            context_relevance=evaluation_result.context_relevance,
            confidence_accuracy=evaluation_result.confidence_accuracy,
            overall_score=evaluation_result.overall_score,
            predicted_confidence=predicted,
        )
        self._history.append(checkpoint)
        self._h_trend.append(checkpoint.hallucination_score)
        self._ca_trend.append(checkpoint.confidence_accuracy)

        aggregate = CheckpointWithEvaluation(
            agent_id=agent_id,
            evaluation_history=tuple(self._history),
            hallucination_trend=tuple(self._h_trend),
            confidence_accuracy_trend=tuple(self._ca_trend),
        )
        session_id = f"agent-evaluation-{agent_id}"
        snapshot = aggregate.to_checkpoint_snapshot(session_id=session_id, state_version=self._state_version)
        try:
            await self._snapshot_repository.save(snapshot)
        except StorageError as error:
            raise EvaluationHistoryError(
                agent_id=agent_id,
                phase="record",
                reason="save_failed",
                context_extra={"session_id": session_id, "history_len": str(len(self._history))},
                cause=error,
            ) from error
        self._state_version += 1
        return snapshot

    async def restore(self, session_id: str) -> CheckpointWithEvaluation | None:
        """从快照恢复评估历史（恢复式语义——OD-7③）。

        步骤：load → None 直接返回（快照不存在是正常态）→ from_snapshot 解包
        （结构不完整抛 452——fail-loud 防御面，零部分灌回）→ **灌回三 deque**
        （deque(聚合序列, maxlen=MAX_HISTORY_SIZE) 替换式构造——恢复聚合 ≤ 窗口
        上限由快照产出端 maxlen 结构保证）→ state_version 计数器续接
        snapshot.state_version + 1 → 返回聚合。

        知悉注记：store.load 侧任何异常（含 Redis 故障）均捕获返回 None
        （redis_snapshot_store L162-164）——故障与快照不存在不可区分，restore
        返 None 双义下「故障静默为空历史」是既定行为（恢复后累积从空窗起步）。

        Args:
            session_id: 快照会话标识（``agent-evaluation-{agent_id}`` 命名空间）。

        Returns:
            CheckpointWithEvaluation | None: 恢复的聚合；快照不存在（或存储故障
            静默形态）返回 None。

        Raises:
            EvaluationHistoryError: 快照结构不完整（state_data 缺键/类型错误/
            recorded_at 反序列化失败——from_snapshot 的 KeyError/ValueError/
            TypeError 收敛包装 452）。
        """
        snapshot = await self._snapshot_repository.load(session_id)
        if snapshot is None:
            return None
        try:
            aggregate = CheckpointWithEvaluation.from_snapshot(snapshot)
        except (KeyError, ValueError, TypeError) as error:
            raise EvaluationHistoryError(
                agent_id="",
                phase="restore",
                reason="missing_keys",
                context_extra={"session_id": session_id},
                cause=error,
            ) from error
        self._history = deque(aggregate.evaluation_history, maxlen=MAX_HISTORY_SIZE)
        self._h_trend = deque(aggregate.hallucination_trend, maxlen=MAX_HISTORY_SIZE)
        self._ca_trend = deque(aggregate.confidence_accuracy_trend, maxlen=MAX_HISTORY_SIZE)
        self._state_version = snapshot.state_version + 1
        return aggregate
