"""集成测试 Story 5.10 - CheckpointWithEvaluation 真实 Redis 全链 + P95 双锚（FR-EV-04）。

覆盖面：真实 Redis 落键（hget latest 两层 json_loads）/ 重启恢复（新 Recorder 逐值）
/ 累积延续（restore 后 record → 历史+1）/ restore None（快照不存在正常态）/ 趋势时序
（注入序保持）/ 自清理（delete 后 exists False）；P95 双锚（save<100ms epics L1883 /
query<50ms epics L1884——委托计时 _PERF_CACHE + 验收侧 import 常量禁双真源）。

性能口径声明（五注记——防后续误读）：
1. **save 路径含 Redis RTT**：单次采样 = 完整 record 调用（内存累积 + 打包 +
   RedisSnapshotStore.save 真实 Redis 写——网络往返在栈内）；纯内存管线对照面
   （打包无 IO）不在本锚范围。本地 Redis 口径（单机 RTT <1ms——100ms 门宽松）；
   网络.Redis 部署形态 RTT 依赖知悉（远程 Redis RTT 是 V1 容量评估面）。
2. **满窗口径**：采样前 Recorder 历史预填充至 MAX_HISTORY_SIZE（100 条——经
   record 公共路径 ×100 不计时不计入调用计数）：满窗快照是最大体积形态，P95 门
   在满窗下成立才是有效锚（OD-8 窗口与性能的耦合验证）。
3. **本地 Redis 前提**：门定位是回归绊线非容量预算（5-8 DC-8④ 诚实注记同款）。
4. **门 = 回归绊线**：本地实测与门差两个数量级，劣化检出灵敏度以数量级为单位。
5. **20 样本 P95 估计量方差大知悉**：quantiles(latencies, n=20)[18] exclusive
   口径（5-8 EVALUATION_SAMPLE_ROUNDS=20 同款）——小样本分位数噪声不淹没
   数量级劣化检出。

正向锚口径：采样循环内手工递增计数（每轮恰一次 record 内一次 save / 一次
restore 内一次 load——5-9 L116-134 同款，真实 Redis 路径下循环计数即调用计数）；
warmup 轮 = 一次 record + 一次 restore（双计数同达 21——warmup 只 warm 单锚会使
另一锚计数 20≠21 假红）；预填充 100 条不计时不计入。Redis 不可达时采样前置探测
skip 而非静默零采样。

Run with:
    poetry run pytest tests/integration/test_integration_checkpoint_evaluation.py -v
"""

from __future__ import annotations

import json
import statistics
import time
import uuid
from typing import Any

import pytest

from src.infrastructure.storage.redis.key_builder import build_key

pytestmark = [
    pytest.mark.integration,
    pytest.mark.redis,
    pytest.mark.xdist_group("checkpoint-evaluation-perf"),
]

# P95 双锚阈值常量（单源定义——验收侧 import 本常量断言，禁双真源；
# epics L1883 快照创建 P95<100ms / L1884 评估历史查询 P95<50ms——本地 Redis 写
# ~1ms 量级，两门均有两个数量级裕量）
CHECKPOINT_SAVE_P95_LIMIT_SECONDS = 0.1
CHECKPOINT_QUERY_P95_LIMIT_SECONDS = 0.05

#: 采样规模（P95 = quantiles(latencies, n=20)[18] exclusive——5-8 同款 20 样本口径）
CHECKPOINT_SAMPLE_ROUNDS = 20

#: 满窗预填充条数（MAX_HISTORY_SIZE 同值——经 record 公共路径，不计时）
CHECKPOINT_PREFILL_ROUNDS = 100

#: 委托缓存（集成/验收逐字同组 loadgroup 同 worker 串行——命中或首次采样形态）
_PERF_CACHE: dict[str, dict[str, Any]] = {}


def _make_evaluation_result(score: float) -> Any:
    """EvaluationResult 构造（四分数同值——真实 frozen 实例直传）。"""
    from src.application.ports.agent_evaluation import EvaluationResult

    return EvaluationResult(
        hallucination_score=score,
        context_relevance=score,
        confidence_accuracy=score,
        overall_score=score,
    )


async def _make_real_stack() -> tuple[Any, Any, Any]:
    """真实栈装配（场景级独立 Redis 客户端 + RedisAdapter + RedisSnapshotStore + Recorder）。

    Returns:
        (recorder, store, redis_client) 三元组；Redis 不可达时 pytest.skip。
    """
    import redis.asyncio as aioredis

    from src.application.services.evaluation_checkpoint_recorder import EvaluationCheckpointRecorder
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore
    from tests.environments import get_test_env

    config = get_test_env()
    redis_client = aioredis.Redis(
        host=config.redis.host,
        port=config.redis.port,
        password=config.redis.password,
        decode_responses=True,
    )
    try:
        await redis_client.ping()
    except Exception as exc:  # 门控专用——ping 失败一律 skip（禁写死 skip marker）
        await redis_client.close()
        pytest.skip(f"Redis not available: {exc}")
    store = RedisSnapshotStore(adapter=RedisAdapter(redis_client))
    recorder = EvaluationCheckpointRecorder(snapshot_repository=store)
    return recorder, store, redis_client


class TestRealRedisCheckpointRoundtrip:
    """真实 Redis 全链六场景（session_id UUID 前缀隔离 + 自清理只删自产键）。"""

    async def test_record_lands_key_with_two_layer_json(self) -> None:
        """①record ≥3 次落键：hget latest 非空 + 两层 json_loads + 三序列逐值 + TTL。"""
        recorder, store, redis_client = await _make_real_stack()
        try:
            agent_id = uuid.uuid4().hex
            session_id = f"agent-evaluation-{agent_id}"
            scores = [0.1, 0.3, 0.5]
            predicted = [0.2, 0.4, 0.6]
            last_snapshot = None
            for i, score in enumerate(scores):
                last_snapshot = await recorder.record(
                    agent_id=agent_id, evaluation_result=_make_evaluation_result(score), predicted=predicted[i]
                )

            raw = await redis_client.hget(build_key("snapshot", session_id), "latest")
            assert raw is not None, "真实 Redis 落键锚（latest field 非空）"
            outer = json.loads(raw)
            assert outer["stage_id"] == "evaluation"
            state_data = outer["state_data"]
            state_data = json.loads(state_data) if isinstance(state_data, str) else state_data
            assert state_data["hallucination_trend"] == scores, "三序列与 record 传入逐值相等"
            assert state_data["confidence_accuracy_trend"] == scores
            assert len(state_data["evaluation_history"]) == 3
            assert state_data["evaluation_history"][0]["predicted_confidence"] == predicted[0]
            assert last_snapshot is not None and last_snapshot.ttl_seconds == 86400, "TTL 实体默认 86400"
        finally:
            await redis_client.delete(build_key("snapshot", f"agent-evaluation-{agent_id}"))
            await redis_client.close()

    async def test_restart_restore_and_continuity(self) -> None:
        """②重启恢复 + ③累积延续：新 Recorder restore 逐值 → record → 历史+1 + version 续接。"""
        recorder, store, redis_client = await _make_real_stack()
        try:
            agent_id = uuid.uuid4().hex
            session_id = f"agent-evaluation-{agent_id}"
            scores = [0.1, 0.3, 0.5]
            snapshots = []
            for score in scores:
                snapshots.append(
                    await recorder.record(agent_id=agent_id, evaluation_result=_make_evaluation_result(score), predicted=0.5)
                )

            # 模拟重启：新实例（内存累积清零——Redis 落键仍在）
            restarted, _, _ = await _make_real_stack()
            try:
                restored = await restarted.restore(session_id)
                assert restored is not None, "重启存活锚：restore 应返回非空聚合"
                assert len(restored.evaluation_history) == 3
                assert list(restored.hallucination_trend) == scores, "恢复历史逐值精确相等"

                follow_up = await restarted.record(
                    agent_id=agent_id, evaluation_result=_make_evaluation_result(0.7), predicted=0.6
                )
                history = follow_up.state_data["evaluation_history"]
                assert len(history) == 4, "累积延续：恢复历史 3 + 新记录 1 == 4"
                assert history[0]["hallucination_score"] == 0.1, "首条 == 恢复首条（灌回三 deque）"
                assert follow_up.state_version == snapshots[-1].state_version + 1, "state_version 续接"
            finally:
                pass
        finally:
            await redis_client.delete(build_key("snapshot", f"agent-evaluation-{agent_id}"))
            await redis_client.close()

    async def test_restore_missing_snapshot_returns_none(self) -> None:
        """④restore 未 record 过的 UUID session_id → None（首次评估前正常态）。"""
        recorder, store, redis_client = await _make_real_stack()
        try:
            missing = await recorder.restore(f"agent-evaluation-{uuid.uuid4().hex}")
            assert missing is None
        finally:
            await redis_client.close()

    async def test_trend_order_preserved(self) -> None:
        """⑤趋势时序：hallucination_trend 顺序 == record 注入顺序（值序非单调性）。"""
        recorder, store, redis_client = await _make_real_stack()
        try:
            agent_id = uuid.uuid4().hex
            session_id = f"agent-evaluation-{agent_id}"
            injected_order = [0.5, 0.1, 0.3, 0.5]
            for score in injected_order:
                await recorder.record(agent_id=agent_id, evaluation_result=_make_evaluation_result(score), predicted=0.5)

            snapshot = await store.load(session_id)
            assert snapshot is not None
            assert snapshot.state_data["hallucination_trend"] == injected_order, (
                "趋势序列顺序应 == 注入顺序（deque 追加序即时间序）"
            )
        finally:
            await redis_client.delete(build_key("snapshot", f"agent-evaluation-{agent_id}"))
            await redis_client.close()

    async def test_self_cleanup_delete_and_exists_false(self) -> None:
        """⑥自清理：delete 后 exists(session_id) is False（只清自己创建的键）。"""
        recorder, store, redis_client = await _make_real_stack()
        try:
            agent_id = uuid.uuid4().hex
            session_id = f"agent-evaluation-{agent_id}"
            await recorder.record(agent_id=agent_id, evaluation_result=_make_evaluation_result(0.2), predicted=0.5)

            await store.delete(session_id)
            assert await store.exists(session_id) is False, "teardown delete 后 exists 应 False（自清理锚）"
        finally:
            await redis_client.delete(build_key("snapshot", f"agent-evaluation-{agent_id}"))
            await redis_client.close()


async def sample_checkpoint_perf() -> dict[str, Any]:
    """P95 双锚委托采样（cache-or-compute——_PERF_CACHE 命中或首次采样）。

    口径：满窗预填充 100 条（record 公共路径不计时）→ warmup 1 轮（一次 record +
    一次 restore——双计数同达 21 的复合构成）→ 采样 20 轮（每轮 record 计 save 延迟
    + restore 计 load 延迟）。每批次独立 session_id（UUID 前缀隔离）+ teardown 清理。

    Returns:
        {"save_p95_seconds", "query_p95_seconds", "save_call_count", "load_call_count",
         "prefill_count"} 摘要字典。
    """
    cached = _PERF_CACHE.get("checkpoint_perf")
    if cached is not None:
        return cached

    recorder, store, redis_client = await _make_real_stack()
    agent_id = uuid.uuid4().hex
    session_id = f"agent-evaluation-{agent_id}"
    try:
        # 满窗锚：预填充至 MAX_HISTORY_SIZE（record 公共路径 ×100——不计时、
        # 不计入采样轮调用计数；满窗快照是最大体积形态）
        prefill_count = 0
        for i in range(CHECKPOINT_PREFILL_ROUNDS):
            await recorder.record(
                agent_id=agent_id,
                evaluation_result=_make_evaluation_result(round(0.01 * ((i % 100) + 1), 2)),
                predicted=0.5,
            )
            prefill_count += 1

        save_call_count = 0
        load_call_count = 0

        # warmup 复合构成：一次 record + 一次 restore（双锚各计 1——只 warm 单锚
        # 会使另一锚计数 20≠21 假红）
        await recorder.record(agent_id=agent_id, evaluation_result=_make_evaluation_result(0.5), predicted=0.5)
        save_call_count += 1
        await recorder.restore(session_id)
        load_call_count += 1

        save_latencies: list[float] = []
        query_latencies: list[float] = []
        for i in range(CHECKPOINT_SAMPLE_ROUNDS):
            started = time.perf_counter()
            await recorder.record(
                agent_id=agent_id,
                evaluation_result=_make_evaluation_result(round(0.01 * ((i % 100) + 1), 2)),
                predicted=0.5,
            )
            save_latencies.append(time.perf_counter() - started)
            save_call_count += 1

            started = time.perf_counter()
            await recorder.restore(session_id)
            query_latencies.append(time.perf_counter() - started)
            load_call_count += 1

        summary = {
            "save_p95_seconds": statistics.quantiles(save_latencies, n=20)[18],  # exclusive P95（20 样本池）
            "query_p95_seconds": statistics.quantiles(query_latencies, n=20)[18],
            "save_call_count": save_call_count,
            "load_call_count": load_call_count,
            "prefill_count": prefill_count,
        }
        _PERF_CACHE["checkpoint_perf"] = summary
        return summary
    finally:
        await redis_client.delete(build_key("snapshot", session_id))
        await redis_client.close()


class TestCheckpointPerformance:
    """P95 双锚（委托采样——与验收 AC-5 同 _PERF_CACHE 同 xdist_group 同 worker 串行）。"""

    async def test_save_p95_below_100ms(self) -> None:
        """save P95<100ms（epics L1883——record 全路径含真实 Redis 写）。"""
        summary = await sample_checkpoint_perf()
        assert summary["save_p95_seconds"] < CHECKPOINT_SAVE_P95_LIMIT_SECONDS, (
            f"快照创建 P95 应 < {CHECKPOINT_SAVE_P95_LIMIT_SECONDS}s（实测 {summary['save_p95_seconds']}s）"
        )

    async def test_query_p95_below_50ms(self) -> None:
        """query P95<50ms（epics L1884——restore 全路径 load+解包）。"""
        summary = await sample_checkpoint_perf()
        assert summary["query_p95_seconds"] < CHECKPOINT_QUERY_P95_LIMIT_SECONDS, (
            f"评估历史查询 P95 应 < {CHECKPOINT_QUERY_P95_LIMIT_SECONDS}s（实测 {summary['query_p95_seconds']}s）"
        )

    async def test_positive_anchor_call_counts(self) -> None:
        """正向锚：save/load 调用计数 == warmup + 采样数（21——防静默跳过假绿）。"""
        summary = await sample_checkpoint_perf()
        assert summary["save_call_count"] == 21, f"save 调用计数应 21（实际 {summary['save_call_count']}）"
        assert summary["load_call_count"] == 21, f"load 调用计数应 21（实际 {summary['load_call_count']}）"

    async def test_full_window_prefill_anchor(self) -> None:
        """满窗锚：预填充 100 条经 record 公共路径（MAX_HISTORY_SIZE 耦合注记）。"""
        summary = await sample_checkpoint_perf()
        assert summary["prefill_count"] == 100, f"预填充应 100 条（实际 {summary['prefill_count']}）"

    async def test_xdist_group_unique(self) -> None:
        """xdist 组互异：checkpoint-evaluation-perf 与既有 14 组不冲突（全仓扫描）。"""
        import re
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        existing_groups: set[str] = set()
        for py_file in (repo_root / "tests").rglob("*.py"):
            existing_groups.update(re.findall(r'xdist_group\("([^"]+)"\)', py_file.read_text(encoding="utf-8")))
        expected_existing = {
            "agent-workflow-perf",
            "agent-isolation-perf",
            "agent-triple-isolation-perf",
            "isolation-switch-log-perf",
            "phoenix-tracer-perf",
            "agent-evaluation-perf",
            "drift-detection-perf",
            "agent-instantiation",
            "agent-profile-loading",
            "data-source-cache",
            "sandbox-daemon",
            "tool-executions-pg",
            "tool-versions-pg",
            "validation-feedback-pg",
        }
        assert expected_existing <= existing_groups, f"既有 14 组应全在位（缺失 {expected_existing - existing_groups}）"
        assert "checkpoint-evaluation-perf" in existing_groups
