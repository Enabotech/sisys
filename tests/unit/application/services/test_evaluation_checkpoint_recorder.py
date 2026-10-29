"""EvaluationCheckpointRecorder 单元测试（Story 5.10 — FR-EV-04）。

覆盖面（七场景 + 三组审查补充）：record 原子三步（累积→打包→save 委托）与
state_version 计数器递增 / 窗口滚动（101 条灌装 → 100 满窗最旧丢弃）/ restore
恢复式语义（灌回三 deque + 计数器续接 + ③b 累积延续——防纯查询式假绿锚）/
restore 快照不存在 None 语义 / restore 结构不完整 452 / save 抛 StorageError
包装 452（cause 链锚 + 内存累积保留最终一致）/ session_id 命名空间构造；
代码审查 R1 补充——多 Agent 窗口隔离（per-agent 键控——同 Recorder 交错
record 隔离断言 + restore 不串窗）/ 腐坏快照防御面收敛（越界分数与 trend
元素违规 → 452 非 201 泄漏）/ record 输入域违规收敛（predicted 越界与
agent_id 空串 → 452 invalid_input + 窗口零污染）。

存储替身：AsyncMock(spec=SnapshotRepositoryProtocol)——unit 层合法（集成/验收用
手写零 IO duck-typing 替身）。

断言纪律：浮点精确等式禁 approx；③ 构造恢复历史长度 3（< MAX_HISTORY_SIZE——
③b「长度+1/首条不变」断言在满窗恢复下数学不可满足，满窗边界归 ② 承载）。

Run with:
    poetry run pytest tests/unit/application/services/test_evaluation_checkpoint_recorder.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.domain.exceptions import EvaluationHistoryError, StorageError


def _make_evaluation_result(score: float) -> Any:
    """EvaluationResult 构造（四分数同值——真实 frozen 实例直传）。"""
    from src.application.ports.agent_evaluation import EvaluationResult

    return EvaluationResult(
        hallucination_score=score,
        context_relevance=score,
        confidence_accuracy=score,
        overall_score=score,
    )


def _make_mock_repo() -> Any:
    """AsyncMock 存储替身（spec=SnapshotRepositoryProtocol——unit 层合法）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol

    repo = AsyncMock(spec=SnapshotRepositoryProtocol)
    repo.load.return_value = None
    return repo


def _make_recorder(repo: Any) -> Any:
    """Recorder 构造 helper（延迟 import——红阶段 ModuleNotFoundError 承载）。"""
    from src.application.services.evaluation_checkpoint_recorder import EvaluationCheckpointRecorder

    return EvaluationCheckpointRecorder(snapshot_repository=repo)


async def _record_n(recorder: Any, agent_id: str, scores: list[float], predicted: float = 0.5) -> list[Any]:
    """连续 record n 次并收集快照。"""
    return [
        await recorder.record(agent_id=agent_id, evaluation_result=_make_evaluation_result(score), predicted=predicted)
        for score in scores
    ]


class TestRecordAtomicPath:
    """场景①record 单调：累积 → 打包 → save 委托 → 返回快照 + 计数器递增。"""

    async def test_record_returns_saved_snapshot(self) -> None:
        """record 返回快照（state_version == 1 首次 + save 委托调用一次）。"""
        repo = _make_mock_repo()
        recorder = _make_recorder(repo)

        snapshot = await recorder.record(
            agent_id="agent-record-001", evaluation_result=_make_evaluation_result(0.2), predicted=0.3
        )

        repo.save.assert_awaited_once_with(snapshot)
        assert snapshot.state_version == 1, "首次 record 快照 state_version 应为 1（计数器初始值）"
        assert snapshot.state_data["evaluation_history"][0]["hallucination_score"] == 0.2
        assert snapshot.state_data["evaluation_history"][0]["predicted_confidence"] == 0.3

    async def test_consecutive_record_version_increments(self) -> None:
        """连续 record 2 次：第二次快照 state_version == 2（计数器递增锚）。"""
        repo = _make_mock_repo()
        recorder = _make_recorder(repo)

        snapshots = await _record_n(recorder, "agent-record-002", [0.1, 0.3])

        assert snapshots[0].state_version == 1
        assert snapshots[1].state_version == 2, "第二次快照 state_version 应 == 2（save 成功后 +1）"
        assert len(snapshots[1].state_data["evaluation_history"]) == 2, "内存累积跨 record 保持"

    async def test_session_id_namespace(self) -> None:
        """场景⑦session_id 构造 == "agent-evaluation-{agent_id}"（DC-6 命名空间锚）。"""
        repo = _make_mock_repo()
        recorder = _make_recorder(repo)

        snapshot = await recorder.record(agent_id="agent-ns-001", evaluation_result=_make_evaluation_result(0.2), predicted=0.5)

        assert snapshot.session_id == "agent-evaluation-agent-ns-001"
        assert snapshot.stage_id == "evaluation"


class TestWindowRolling:
    """场景②窗口滚动：灌 101 条 → 100 满窗最旧丢弃 + 三序列同窗。"""

    async def test_rolling_window_drops_oldest(self) -> None:
        """灌 101 条 → history 长度 100 + 最旧丢弃（首条 == 第 2 条注入）+ 三序列同窗。"""
        from src.application.ports.agent_checkpoint import MAX_HISTORY_SIZE

        repo = _make_mock_repo()
        recorder = _make_recorder(repo)

        scores = [round(0.01 * ((i % 100) + 1), 2) for i in range(101)]
        snapshots = await _record_n(recorder, "agent-window-001", scores)

        assert len(snapshots) == 101
        last = snapshots[-1]
        assert len(last.state_data["evaluation_history"]) == 100, (
            f"满窗长度应为 100（MAX_HISTORY_SIZE），实际 {len(last.state_data['evaluation_history'])}"
        )
        assert last.state_data["hallucination_trend"][0] == scores[1], "最旧丢弃后首条应 == 第 2 条注入值"
        assert len(last.state_data["hallucination_trend"]) == 100, "三序列同窗同步滚动"
        assert len(last.state_data["confidence_accuracy_trend"]) == 100
        assert MAX_HISTORY_SIZE == 100, "窗口上限常量单源（OD-8 锚）"


class TestRestoreRecoverySemantics:
    """场景③restore 恢复式语义（灌回三 deque + 计数器续接）+ ③b 累积延续。"""

    async def test_restore_recovers_history_into_new_recorder(self) -> None:
        """③新 Recorder restore 逐值恢复（重启模拟——恢复历史长度 3 < MAX_HISTORY_SIZE）。"""
        repo = _make_mock_repo()
        original = _make_recorder(repo)
        scores = [0.1, 0.3, 0.5]
        snapshots = await _record_n(original, "agent-restore-001", scores)

        repo.load.return_value = snapshots[-1]
        restarted = _make_recorder(repo)
        restored = await restarted.restore("agent-evaluation-agent-restore-001")

        assert restored is not None
        assert len(restored.evaluation_history) == 3
        assert list(restored.hallucination_trend) == scores, "恢复历史应逐值精确相等"
        assert restored.evaluation_history[0].hallucination_score == 0.1

    async def test_restore_then_record_accumulation_continues(self) -> None:
        """③b restore 后 record 1 次 → 新快照历史 == 恢复 + 1 且首条 == 恢复首条 + version 续接。"""
        repo = _make_mock_repo()
        original = _make_recorder(repo)
        scores = [0.1, 0.3, 0.5]
        snapshots = await _record_n(original, "agent-cont-001", scores)

        repo.load.return_value = snapshots[-1]
        restarted = _make_recorder(repo)
        restored = await restarted.restore("agent-evaluation-agent-cont-001")
        assert restored is not None

        follow_up = await restarted.record(
            agent_id="agent-cont-001", evaluation_result=_make_evaluation_result(0.7), predicted=0.6
        )

        history = follow_up.state_data["evaluation_history"]
        assert len(history) == 4, f"累积延续：恢复历史 3 + 新记录 1 == 4（实际 {len(history)}）"
        assert history[0]["hallucination_score"] == 0.1, "首条应 == 恢复首条（灌回三 deque 后追加）"
        assert follow_up.state_version == snapshots[-1].state_version + 1, (
            f"state_version 应续接（快照 {snapshots[-1].state_version} + 1，实际 {follow_up.state_version}）"
        )

    async def test_restore_missing_snapshot_returns_none(self) -> None:
        """场景④restore 快照不存在（load 返 None）→ None（正常态非异常）。"""
        repo = _make_mock_repo()
        recorder = _make_recorder(repo)

        result = await recorder.restore("agent-evaluation-agent-missing-001")

        assert result is None


class TestRestoreStructureGuard:
    """场景⑤restore 结构不完整 → EvaluationHistoryError 452。"""

    async def test_restore_missing_keys_raises_452(self) -> None:
        """state_data 缺键 → 452（fail-loud 防御面——正常路径快照由本管线产出必含四键）。"""
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        repo = _make_mock_repo()
        recorder = _make_recorder(repo)
        broken = CheckpointSnapshot(
            session_id="agent-evaluation-agent-broken-001", stage_id="evaluation", state_data={"agent_id": "agent-broken-001"}
        )
        repo.load.return_value = broken

        with pytest.raises(EvaluationHistoryError) as exc_info:
            await recorder.restore("agent-evaluation-agent-broken-001")

        assert exc_info.value.code == "EXCEPTION_452"
        assert exc_info.value.context["phase"] == "restore"

    async def test_restore_no_partial_backfill_on_failure(self) -> None:
        """结构不完整时零部分灌回（事务性——三 deque 不被污染）。"""
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        repo = _make_mock_repo()
        recorder = _make_recorder(repo)
        await _record_n(recorder, "agent-tx-001", [0.2, 0.4])

        broken = CheckpointSnapshot(
            session_id="agent-evaluation-agent-tx-001",
            stage_id="evaluation",
            state_data={"agent_id": "agent-tx-001", "evaluation_history": []},
        )
        repo.load.return_value = broken
        with pytest.raises(EvaluationHistoryError):
            await recorder.restore("agent-evaluation-agent-tx-001")

        follow_up = await recorder.record(
            agent_id="agent-tx-001", evaluation_result=_make_evaluation_result(0.6), predicted=0.5
        )
        history = follow_up.state_data["evaluation_history"]
        assert len(history) == 3, "失败 restore 零部分灌回：既有累积 2 + 新记录 1 == 3（deque 未被坏快照污染）"
        assert history[0]["hallucination_score"] == 0.2, "首条应仍是失败恢复前的既有首条"


class TestStorageErrorWrapping:
    """场景⑥save 抛 StorageError → record 包装 452 上抛 + cause 链 + 内存累积保留。"""

    async def test_save_storage_error_wrapped_as_452_with_cause(self) -> None:
        """StorageError → 452 包装 + exc.__cause__ is 注入的 StorageError（包装链锚）。"""
        repo = _make_mock_repo()
        injected = StorageError(message="Failed to save snapshot: 注入故障")
        repo.save.side_effect = injected
        recorder = _make_recorder(repo)

        with pytest.raises(EvaluationHistoryError) as exc_info:
            await recorder.record(agent_id="agent-fail-001", evaluation_result=_make_evaluation_result(0.2), predicted=0.5)

        assert exc_info.value.code == "EXCEPTION_452"
        assert exc_info.value.__cause__ is injected, "cause 链应指向注入的 StorageError（AC-2 根因断言锚）"
        assert str(exc_info.value) == "评估历史持久化失败", "str(452) 恒等于静态 message（warning 文本锚）"

    async def test_failed_save_keeps_memory_accumulation(self) -> None:
        """452 后内存累积保留（最终一致）：下次 record 打包含失败条目。"""
        repo = _make_mock_repo()
        repo.save.side_effect = StorageError(message="Failed to save snapshot: 第一次注入故障")

        recorder = _make_recorder(repo)
        with pytest.raises(EvaluationHistoryError):
            await recorder.record(agent_id="agent-consist-001", evaluation_result=_make_evaluation_result(0.1), predicted=0.2)

        repo.save.side_effect = None
        follow_up = await recorder.record(
            agent_id="agent-consist-001", evaluation_result=_make_evaluation_result(0.3), predicted=0.4
        )

        history = follow_up.state_data["evaluation_history"]
        assert len(history) == 2, "内存累积保留（失败条目仍在——下次 record 打包后落盘收敛）"
        assert history[0]["hallucination_score"] == 0.1
        assert follow_up.state_version == 1, "失败不消耗版本号（版本数 == 成功落盘数）"

    async def test_recorded_at_is_recent(self) -> None:
        """recorded_at 为记录时刻（近期时刻——datetime.now(UTC)）。"""
        repo = _make_mock_repo()
        recorder = _make_recorder(repo)

        snapshot = await recorder.record(
            agent_id="agent-time-001", evaluation_result=_make_evaluation_result(0.2), predicted=0.5
        )

        recorded_at = datetime.fromisoformat(snapshot.state_data["evaluation_history"][0]["recorded_at"])
        now = datetime.now(UTC)
        assert abs((now - recorded_at).total_seconds()) < 300, "recorded_at 应为近期时刻"


class TestMultiAgentWindowIsolation:
    """代码审查 R1 补充：per-agent 键控窗口隔离（全局单窗口跨 Agent 混串缺陷的回归锁）。

    组合根 agent_checkpoint 是 SINGLETON 且 use case 亦 SINGLETON——同进程多
    Agent（七角色平台常态路径）共享同一 Recorder 实例。窗口必须按落盘命名空间
    （agent-evaluation-{agent_id}）键控：B 键快照不得混入 A 的记录，版本计数器
    各窗独立。
    """

    async def test_two_agents_interleaved_windows_isolated(self) -> None:
        """交错 record(A,B,A)：各快照仅含自身 Agent 记录 + 版本各窗独立。"""
        repo = _make_mock_repo()
        recorder = _make_recorder(repo)

        snapshot_a1 = await recorder.record(
            agent_id="agent-iso-a", evaluation_result=_make_evaluation_result(0.1), predicted=0.2
        )
        snapshot_b1 = await recorder.record(
            agent_id="agent-iso-b", evaluation_result=_make_evaluation_result(0.9), predicted=0.8
        )
        snapshot_a2 = await recorder.record(
            agent_id="agent-iso-a", evaluation_result=_make_evaluation_result(0.3), predicted=0.4
        )

        # B 键快照只含 B 的记录（全局单窗口缺陷形态：len==2 且混入 agent-iso-a）
        b_history = snapshot_b1.state_data["evaluation_history"]
        assert len(b_history) == 1, f"B 窗应仅 1 条（实际 {len(b_history)}）——跨 Agent 混串回归锁"
        assert b_history[0]["agent_id"] == "agent-iso-b"
        assert snapshot_b1.state_data["hallucination_trend"] == [0.9]
        assert snapshot_b1.session_id == "agent-evaluation-agent-iso-b"

        # A 第三次打包只含 A 的两条记录
        a_history = snapshot_a2.state_data["evaluation_history"]
        assert len(a_history) == 2, f"A 窗应 2 条（实际 {len(a_history)}）"
        assert {record["agent_id"] for record in a_history} == {"agent-iso-a"}
        assert snapshot_a2.state_data["hallucination_trend"] == [0.1, 0.3]

        # 版本计数器各窗独立（B 首条 v1——不受 A 已 v2 牵连）
        assert snapshot_a1.state_version == 1
        assert snapshot_a2.state_version == 2
        assert snapshot_b1.state_version == 1, "B 窗版本应独立从 1 起（全局计数器错配回归锁）"

    async def test_restore_agent_a_does_not_disturb_agent_b_window(self) -> None:
        """restore(A) 仅替换 A 窗——B 窗既有累积不受扰（restore 不串窗锚）。"""
        repo = _make_mock_repo()
        recorder = _make_recorder(repo)
        await _record_n(recorder, "agent-iso-a", [0.1, 0.3])
        await recorder.record(agent_id="agent-iso-b", evaluation_result=_make_evaluation_result(0.9), predicted=0.5)

        # restore A：加载 A 最后快照（全局 deque 缺陷形态：灌回会整体替换共享窗口殃及 B）
        loaded = await recorder.record(agent_id="agent-iso-a", evaluation_result=_make_evaluation_result(0.5), predicted=0.5)
        repo.load.return_value = loaded
        restored = await recorder.restore("agent-evaluation-agent-iso-a")
        assert restored is not None

        # restore 后 B 再 record：B 历史仍是 B 自己的两条（0.9 + 新 0.7），首条不变
        follow_up_b = await recorder.record(
            agent_id="agent-iso-b", evaluation_result=_make_evaluation_result(0.7), predicted=0.5
        )
        b_history = follow_up_b.state_data["evaluation_history"]
        assert len(b_history) == 2, f"B 窗 restore(A) 后应仍是 2 条（实际 {len(b_history)}）"
        assert b_history[0]["hallucination_score"] == 0.9, "B 窗首条应不被 A 的 restore 替换"
        assert b_history[1]["hallucination_score"] == 0.7


class TestRestoreCorruptSnapshotConvergence:
    """代码审查 R1 补充：腐坏快照防御面收敛（ValidationError 不得泄漏——452 唯一异常契约）。

    from_snapshot 内 EvaluationCheckpoint/CheckpointWithEvaluation 守卫抛
    ValidationError（DomainError 体系——非 ValueError 子类）：restore 的收敛面
    必须覆盖之（端口契约承诺「结构不完整 → 452 fail-loud」）。
    """

    @staticmethod
    def _make_snapshot_with_history(history_record: dict[str, Any]) -> Any:
        """构造含指定 history 记录的快照（四键齐备——仅注入字段值腐坏）。"""
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        return CheckpointSnapshot(
            session_id="agent-evaluation-agent-corrupt-001",
            stage_id="evaluation",
            state_data={
                "agent_id": "agent-corrupt-001",
                "evaluation_history": [history_record],
                "hallucination_trend": [0.5],
                "confidence_accuracy_trend": [0.5],
            },
        )

    @staticmethod
    def _valid_history_record(**overrides: Any) -> dict[str, Any]:
        """合法 history 记录模板（仅覆写注入的腐坏字段）。"""
        record: dict[str, Any] = {
            "recorded_at": "2026-10-29T12:00:00+00:00",
            "agent_id": "agent-corrupt-001",
            "hallucination_score": 0.5,
            "context_relevance": 0.5,
            "confidence_accuracy": 0.5,
            "overall_score": 0.5,
            "predicted_confidence": 0.5,
        }
        record.update(overrides)
        return record

    async def test_restore_out_of_range_score_raises_452_not_201(self) -> None:
        """history 分数越界（1.5）→ 452（非 ValidationError 201 泄漏——契约收敛锚）。"""
        repo = _make_mock_repo()
        recorder = _make_recorder(repo)
        repo.load.return_value = self._make_snapshot_with_history(self._valid_history_record(hallucination_score=1.5))

        with pytest.raises(EvaluationHistoryError) as exc_info:
            await recorder.restore("agent-evaluation-agent-corrupt-001")

        assert exc_info.value.code == "EXCEPTION_452"
        assert exc_info.value.context["reason"] == "invalid_structure"
        assert isinstance(exc_info.value.__cause__, Exception)

    async def test_restore_bool_score_raises_452(self) -> None:
        """history 分数为 bool（JSON true——int 子类陷阱）→ 452。"""
        repo = _make_mock_repo()
        recorder = _make_recorder(repo)
        repo.load.return_value = self._make_snapshot_with_history(self._valid_history_record(overall_score=True))

        with pytest.raises(EvaluationHistoryError) as exc_info:
            await recorder.restore("agent-evaluation-agent-corrupt-001")

        assert exc_info.value.code == "EXCEPTION_452"

    async def test_restore_corrupt_trend_element_raises_452(self) -> None:
        """trend 元素字符串（"0.1"）→ 452（元素数值校验——静默灌回缺陷回归锁）。"""
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        repo = _make_mock_repo()
        recorder = _make_recorder(repo)
        repo.load.return_value = CheckpointSnapshot(
            session_id="agent-evaluation-agent-corrupt-002",
            stage_id="evaluation",
            state_data={
                "agent_id": "agent-corrupt-002",
                "evaluation_history": [self._valid_history_record()],
                "hallucination_trend": ["0.1"],
                "confidence_accuracy_trend": [0.5],
            },
        )

        with pytest.raises(EvaluationHistoryError) as exc_info:
            await recorder.restore("agent-evaluation-agent-corrupt-002")

        assert exc_info.value.code == "EXCEPTION_452"
        assert exc_info.value.context["reason"] == "invalid_structure"

    async def test_restore_unequal_sequences_raises_452(self) -> None:
        """三序列长度不齐（history 1 + trend 2）→ 452（等长守卫经收敛面非泄漏）。"""
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        repo = _make_mock_repo()
        recorder = _make_recorder(repo)
        repo.load.return_value = CheckpointSnapshot(
            session_id="agent-evaluation-agent-corrupt-003",
            stage_id="evaluation",
            state_data={
                "agent_id": "agent-corrupt-003",
                "evaluation_history": [self._valid_history_record()],
                "hallucination_trend": [0.5, 0.7],
                "confidence_accuracy_trend": [0.5],
            },
        )

        with pytest.raises(EvaluationHistoryError) as exc_info:
            await recorder.restore("agent-evaluation-agent-corrupt-003")

        assert exc_info.value.code == "EXCEPTION_452"


class TestRecordInputValidationConvergence:
    """代码审查 R1 补充：record 输入域违规收敛 452（端口「唯一异常」契约成立锚）。

    record 的 Raises 契约只列 EvaluationHistoryError——EvaluationCheckpoint
    构造守卫的 ValidationError 必须在实现层收敛（451「理论不可达的防御层」同款
    哲学：主链内层 catch 无需扩、直调消费方只见 452 一族）。
    """

    async def test_record_predicted_out_of_range_wrapped_as_452(self) -> None:
        """predicted 越界（1.5）→ 452 invalid_input + cause 链 + 窗口零污染。"""
        from src.domain.exceptions import ValidationError

        repo = _make_mock_repo()
        recorder = _make_recorder(repo)

        with pytest.raises(EvaluationHistoryError) as exc_info:
            await recorder.record(agent_id="agent-input-001", evaluation_result=_make_evaluation_result(0.2), predicted=1.5)

        assert exc_info.value.code == "EXCEPTION_452"
        assert exc_info.value.context["phase"] == "record"
        assert exc_info.value.context["reason"] == "invalid_input"
        assert isinstance(exc_info.value.__cause__, ValidationError), "cause 链应指向被收敛的 ValidationError"
        repo.save.assert_not_awaited(), "输入违规不得触达存储"

        # 窗口零污染：同 agent 合法 record 后历史仅 1 条（违规条目未入窗）
        follow_up = await recorder.record(
            agent_id="agent-input-001", evaluation_result=_make_evaluation_result(0.3), predicted=0.4
        )
        history = follow_up.state_data["evaluation_history"]
        assert len(history) == 1, f"违规 record 零入窗（实际 {len(history)} 条）"
        assert history[0]["hallucination_score"] == 0.3

    async def test_record_empty_agent_id_wrapped_as_452(self) -> None:
        """agent_id 空串 → 452 invalid_input（非 201 泄漏）。"""
        repo = _make_mock_repo()
        recorder = _make_recorder(repo)

        with pytest.raises(EvaluationHistoryError) as exc_info:
            await recorder.record(agent_id="", evaluation_result=_make_evaluation_result(0.2), predicted=0.5)

        assert exc_info.value.code == "EXCEPTION_452"
        assert exc_info.value.context["reason"] == "invalid_input"
