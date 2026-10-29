"""CheckpointWithEvaluation 聚合与快照转换单元测试（Story 5.10 — FR-EV-04）。

覆盖面：EvaluationCheckpoint 七字段构造与五分数 [0,1] 域守卫（ValidationError 201
三段式）/ agent_id 非空守卫 / frozen 不可变 / CheckpointWithEvaluation 三序列等长
守卫 / to_checkpoint_snapshot 打包（state_data 四键契约——OD-3）/ from_snapshot
往返一致性（recorded_at isoformat 序列化边界）/ 空历史退化锚 / MAX_HISTORY_SIZE
常量单源（OD-8 窗口上限锚）。

断言纪律：浮点一律精确等式禁 approx（Python json repr 往返保真由 AC-3 真实 Redis
场景承载——本文件纯内存往返同值传递恒等）；手算锚分数取一位小数避开浮点边界。

Run with:
    poetry run pytest tests/unit/application/test_agent_checkpoint_model.py -v
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from src.domain.exceptions import ValidationError


def _make_checkpoint(agent_id: str, index: int, recorded_at: datetime | None = None) -> Any:
    """手算锚评估记录构造（七字段——分数取 0.1/0.3/0.5 一位小数）。"""
    from src.application.ports.agent_checkpoint import EvaluationCheckpoint

    scores = (0.1, 0.3, 0.5)
    predicted = (0.2, 0.4, 0.6)
    return EvaluationCheckpoint(
        recorded_at=recorded_at or datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC),
        agent_id=agent_id,
        hallucination_score=scores[index],
        context_relevance=scores[index],
        confidence_accuracy=scores[index],
        overall_score=scores[index],
        predicted_confidence=predicted[index],
    )


def _make_anchor_aggregate(agent_id: str = "agent-anchor-001") -> Any:
    """手算锚聚合（3 条记录——三序列同源一位小数）。"""
    from src.application.ports.agent_checkpoint import CheckpointWithEvaluation

    base_time = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)
    history = tuple(_make_checkpoint(agent_id, i, base_time.replace(minute=10 * i)) for i in range(3))
    return CheckpointWithEvaluation(
        agent_id=agent_id,
        evaluation_history=history,
        hallucination_trend=tuple(c.hallucination_score for c in history),
        confidence_accuracy_trend=tuple(c.confidence_accuracy for c in history),
    )


def _valid_checkpoint_kwargs() -> dict[str, Any]:
    """合法七字段构造基线（域守卫参数化的基底）。"""
    return {
        "recorded_at": datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC),
        "agent_id": "agent-guard-001",
        "hallucination_score": 0.2,
        "context_relevance": 0.3,
        "confidence_accuracy": 0.4,
        "overall_score": 0.3,
        "predicted_confidence": 0.5,
    }


class TestEvaluationCheckpointDomainGuards:
    """EvaluationCheckpoint 域守卫（五分数字段 [0,1] + agent_id 非空——201 三段式）。"""

    @pytest.mark.parametrize(
        "field",
        ["hallucination_score", "context_relevance", "confidence_accuracy", "overall_score", "predicted_confidence"],
    )
    @pytest.mark.parametrize("bad_value", [-0.01, 1.01, True, "0.5"])
    def test_score_field_domain_guard(self, field: str, bad_value: Any) -> None:
        """五分数 × 四违规值 → 201 三段式（raises → code → context 携字段名）。"""
        from src.application.ports.agent_checkpoint import EvaluationCheckpoint

        kwargs = {**_valid_checkpoint_kwargs(), field: bad_value}
        with pytest.raises(ValidationError) as exc_info:
            EvaluationCheckpoint(**kwargs)
        assert exc_info.value.code == "EXCEPTION_201", f"{field}={bad_value!r} 应抛 201（实际 {exc_info.value.code}）"
        assert field in exc_info.value.context, f"context 应携字段名 {field}（实际 {exc_info.value.context}）"
        assert exc_info.value.context[field] == str(bad_value), "context 值应为 str(实际值)"

    def test_agent_id_empty_guard(self) -> None:
        """agent_id 空串 → 201 三段式（非 [0,1] 分数域——非空字符串守卫）。"""
        from src.application.ports.agent_checkpoint import EvaluationCheckpoint

        kwargs = {**_valid_checkpoint_kwargs(), "agent_id": ""}
        with pytest.raises(ValidationError) as exc_info:
            EvaluationCheckpoint(**kwargs)
        assert exc_info.value.code == "EXCEPTION_201"
        assert exc_info.value.context["agent_id"] == ""

    def test_valid_construction_passes(self) -> None:
        """合法构造通过（七字段全合法域）。"""
        from src.application.ports.agent_checkpoint import EvaluationCheckpoint

        checkpoint = EvaluationCheckpoint(**_valid_checkpoint_kwargs())
        assert checkpoint.agent_id == "agent-guard-001"
        assert checkpoint.hallucination_score == 0.2
        assert checkpoint.predicted_confidence == 0.5

    def test_frozen_immutability(self) -> None:
        """frozen 不可变（setattr 抛 FrozenInstanceError——EvaluationResult/DriftAssessment 同款）。"""
        checkpoint = _make_checkpoint("agent-frozen-001", 0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(checkpoint, "agent_id", "mutated")

    def test_recorded_at_and_scores_at_boundaries(self) -> None:
        """[0,1] 闭区间边界值合法（0.0 与 1.0——含端点）。"""
        from src.application.ports.agent_checkpoint import EvaluationCheckpoint

        for boundary in (0.0, 1.0):
            checkpoint = EvaluationCheckpoint(**{**_valid_checkpoint_kwargs(), "hallucination_score": boundary})
            assert checkpoint.hallucination_score == boundary


class TestCheckpointWithEvaluationAggregate:
    """CheckpointWithEvaluation 聚合（三序列等长守卫 + frozen）。"""

    def test_three_sequence_equal_length_guard(self) -> None:
        """三序列等长守卫（history 3 + trend 2 → 201）。"""
        from src.application.ports.agent_checkpoint import CheckpointWithEvaluation

        anchor = _make_anchor_aggregate("agent-mismatch-001")
        with pytest.raises(ValidationError) as exc_info:
            CheckpointWithEvaluation(
                agent_id="agent-mismatch-001",
                evaluation_history=anchor.evaluation_history,
                hallucination_trend=anchor.hallucination_trend,
                confidence_accuracy_trend=anchor.confidence_accuracy_trend[:2],
            )
        assert exc_info.value.code == "EXCEPTION_201"

    @pytest.mark.parametrize("trend_field", ["hallucination_trend", "confidence_accuracy_trend"])
    @pytest.mark.parametrize("bad_element", [-0.01, 1.01, True, "0.5", float("nan")])
    def test_trend_element_domain_guard(self, trend_field: str, bad_element: Any) -> None:
        """trend 元素域守卫（代码审查 R1 补充）——两 trend × 越界/bool/字符串/NaN → 201。

        元素校验与 history 五分数守卫对称（趋势值语义上是已守卫分数的镜像）；
        bool 显式排除（JSON true 是 int 子类——naive 数值比较会放行）；NaN 经
        ``0.0 <= v <= 1.0`` 链式比较为 False 天然拦截（json allow_nan=True 可使
        NaN 穿越存储往返——恢复侧不得静默灌回）。
        """
        from src.application.ports.agent_checkpoint import CheckpointWithEvaluation

        anchor = _make_anchor_aggregate("agent-trend-guard-001")
        kwargs: dict[str, Any] = {
            "agent_id": "agent-trend-guard-001",
            "evaluation_history": anchor.evaluation_history,
            "hallucination_trend": anchor.hallucination_trend,
            "confidence_accuracy_trend": anchor.confidence_accuracy_trend,
            trend_field: (bad_element,) + anchor.hallucination_trend[1:],
        }
        with pytest.raises(ValidationError) as exc_info:
            CheckpointWithEvaluation(**kwargs)
        assert exc_info.value.code == "EXCEPTION_201", f"{trend_field}={bad_element!r} 元素应抛 201"
        assert trend_field in exc_info.value.context, f"context 应携字段名 {trend_field}"

    def test_aggregate_frozen(self) -> None:
        """聚合 frozen 不可变。"""
        aggregate = _make_anchor_aggregate()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(aggregate, "agent_id", "mutated")

    def test_aggregate_holds_sequences(self) -> None:
        """聚合三序列持有（tuple 形态）。"""
        aggregate = _make_anchor_aggregate()
        assert len(aggregate.evaluation_history) == 3
        assert aggregate.hallucination_trend == (0.1, 0.3, 0.5)
        assert aggregate.confidence_accuracy_trend == (0.1, 0.3, 0.5)


class TestToCheckpointSnapshot:
    """to_checkpoint_snapshot 打包（state_data 四键契约——OD-3）。"""

    def test_packing_structure_four_keys(self) -> None:
        """打包结构（stage_id=="evaluation" + 四键 + snapshot_id UUID + ttl 86400 + version 1）。"""
        aggregate = _make_anchor_aggregate()
        snapshot = aggregate.to_checkpoint_snapshot(session_id="agent-evaluation-agent-anchor-001", state_version=1)
        assert snapshot.stage_id == "evaluation"
        assert snapshot.state_version == 1, "state_version 形参默认 1（递增语义归 Recorder 计数器）"
        assert snapshot.ttl_seconds == 86400, "ttl_seconds 应为实体默认（评估历史 MVP 生命周期 24h）"
        assert isinstance(snapshot.snapshot_id, uuid.UUID)
        assert snapshot.session_id == "agent-evaluation-agent-anchor-001"
        for key in ("agent_id", "evaluation_history", "hallucination_trend", "confidence_accuracy_trend"):
            assert key in snapshot.state_data, f"state_data 应含四键之 {key}（实际 {list(snapshot.state_data)}）"

    def test_state_version_default_is_one(self) -> None:
        """state_version 缺省默认 1（AC-1 Then② 钦定——聚合纯转换无状态）。"""
        aggregate = _make_anchor_aggregate()
        snapshot = aggregate.to_checkpoint_snapshot(session_id="s-default-version")
        assert snapshot.state_version == 1

    def test_anchor_values_exact(self) -> None:
        """手算锚逐值（三序列长度 == 3 + 分数逐值精确相等 + recorded_at 字符串化）。"""
        aggregate = _make_anchor_aggregate()
        snapshot = aggregate.to_checkpoint_snapshot(session_id="agent-evaluation-agent-anchor-001")
        state_data = snapshot.state_data
        assert state_data["hallucination_trend"] == [0.1, 0.3, 0.5]
        assert state_data["confidence_accuracy_trend"] == [0.1, 0.3, 0.5]
        assert len(state_data["evaluation_history"]) == 3
        record = state_data["evaluation_history"][0]
        assert record["hallucination_score"] == 0.1
        assert record["context_relevance"] == 0.1
        assert record["confidence_accuracy"] == 0.1
        assert record["overall_score"] == 0.1
        assert record["predicted_confidence"] == 0.2
        assert record["agent_id"] == "agent-anchor-001"
        assert isinstance(record["recorded_at"], str), "recorded_at 应经 isoformat 字符串化（JSON 可序列化边界）"
        assert record["recorded_at"] == "2026-10-29T12:00:00+00:00"

    def test_state_data_agent_id_key(self) -> None:
        """state_data agent_id 元数据键（与聚合 agent_id 相等）。"""
        aggregate = _make_anchor_aggregate("agent-meta-001")
        snapshot = aggregate.to_checkpoint_snapshot(session_id="agent-evaluation-agent-meta-001")
        assert snapshot.state_data["agent_id"] == "agent-meta-001"


class TestFromSnapshotRoundtrip:
    """from_snapshot 解包往返（纯内存同值传递恒等——json 双程由 AC-3 承载）。"""

    def test_roundtrip_exact_equality(self) -> None:
        """往返三序列逐值精确相等 + recorded_at datetime 相等 + agent_id 相等。"""
        from src.application.ports.agent_checkpoint import CheckpointWithEvaluation

        aggregate = _make_anchor_aggregate()
        snapshot = aggregate.to_checkpoint_snapshot(session_id="agent-evaluation-agent-anchor-001")
        restored = CheckpointWithEvaluation.from_snapshot(snapshot)
        assert restored.evaluation_history == aggregate.evaluation_history, "history 应逐值精确相等"
        assert restored.hallucination_trend == aggregate.hallucination_trend
        assert restored.confidence_accuracy_trend == aggregate.confidence_accuracy_trend
        for orig, rest in zip(aggregate.evaluation_history, restored.evaluation_history):
            assert rest.recorded_at == orig.recorded_at, "recorded_at isoformat 往返应还原 datetime 相等"
        assert restored.agent_id == aggregate.agent_id

    def test_empty_history_degenerate_anchor(self) -> None:
        """空历史退化锚（零记录聚合打包空列表 + 恢复空聚合——首次评估前正常态）。"""
        from src.application.ports.agent_checkpoint import CheckpointWithEvaluation

        empty = CheckpointWithEvaluation(
            agent_id="agent-empty-001",
            evaluation_history=(),
            hallucination_trend=(),
            confidence_accuracy_trend=(),
        )
        snapshot = empty.to_checkpoint_snapshot(session_id="agent-evaluation-agent-empty-001")
        assert snapshot.state_data["evaluation_history"] == []
        assert snapshot.state_data["hallucination_trend"] == []
        assert snapshot.state_data["confidence_accuracy_trend"] == []
        restored = CheckpointWithEvaluation.from_snapshot(snapshot)
        assert restored.evaluation_history == ()
        assert restored.hallucination_trend == ()
        assert restored.agent_id == "agent-empty-001"


class TestModuleConstants:
    """模块常量单源（OD-8 窗口上限锚——防参数漂移）。"""

    def test_max_history_size_is_100(self) -> None:
        """MAX_HISTORY_SIZE == 100（模块常量单源——deque maxlen 与三序列同窗）。"""
        from src.application.ports import agent_checkpoint

        assert agent_checkpoint.MAX_HISTORY_SIZE == 100

    def test_port_protocol_runtime_checkable(self) -> None:
        """AgentCheckpointPort 是 runtime_checkable Protocol（record/restore 两方法契约）。"""
        from src.application.ports.agent_checkpoint import AgentCheckpointPort

        assert hasattr(AgentCheckpointPort, "record")
        assert hasattr(AgentCheckpointPort, "restore")
