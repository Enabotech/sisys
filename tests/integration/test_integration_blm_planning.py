"""Story 6-1 — BLM 前两阶段规划集成测试（真实服务链）。

Task 5 验证型集成测试（5-9/5-10 套件型豁免条款：以变异实证替代 TDD 红
绿——Subtask 5.5 承载）：真实 CEO Agent 实例化（Redis）+ 真实隔离守卫链 +
真实档案加载 + 真实图引擎（LangGraphEngine.submit_graph("SpBlmGraph")）+
Fake LLM（外部 SaaS 豁免替身——唯一豁免面）。

四场景（Subtask 5.1~5.4）：
- 场景① 真实实例化全链 + 顺序断言双锚 + 图身份锚
- 场景② 状态快照（执行中轮询门控构造 + 终态 8/8 + latest 写读一致）
- 场景③ 真实事件发布（PG event_outbox 落行——双预检门控动态 skip）
- 场景④ 性能基准（Fake LLM 口径 P95<30s + 受控失败注入采样 ≥95% +
  8s/温度配置传递——口径差 docstring 声明 DC-7）

测试隔离：
- TestTenant UUID 前缀租户隔离（Redis 键逐 agent_id 精确删除）
- 检索门控：embedding+Qdrant 双探测 + 租户隔离 collection 建制语料
  （3-1a 验收先例——检索不可达环境动态 skip）
- outbox 事件清理 fixture teardown 化（K8 先例——断言失败也执行）
- BDD 禁手动 delete/truncate；事件行按 event_id 精确删除

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_blm_planning.py -v
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import pytest

from src.infrastructure.storage.redis.key_builder import build_key

pytestmark = [
    pytest.mark.integration,
    pytest.mark.redis,
    pytest.mark.xdist_group("blm-planning-perf"),
]

# 六子步骤期望顺序（独立构造自 or.md——枚举序期望不经被测服务生成）
EXPECTED_ORDER: tuple[str, ...] = ("trend", "market_customer", "competition", "self", "opportunity", "opportunity_gap")

_CORPUS_TEXTS: tuple[str, ...] = (
    "新能源汽车行业战略分析：市场渗透率与增长趋势",
    "财务业绩差距：营收目标与毛利根因分析",
    "竞争对手价格战与渠道策略动态",
    "宏观政策趋势与技术路线演进",
    "内部研发能力与组织短板评估",
    "海外市场机会与增长路径",
)


# ===================================================================
# Fake LLM（集成版——失败/挂起注入 + 配置捕获）
# ===================================================================


def _make_fake_llm(
    *,
    fail_call_indices: frozenset[int] = frozenset(),
    hold_at_call: int | None = None,
    delay_sec: float = 0.0,
) -> Any:
    """BLM 面 Fake LLM（AsyncMock spec=LLMClientPort——外部 SaaS 豁免替身）。

    Args:
        fail_call_indices: 按调用序（0 基）注入 LLMAPIError。
        hold_at_call: 指定调用序挂起（asyncio.Event——场景②门控构造）。
        delay_sec: 每调用延迟（性能计时下界注入）。
    """
    from unittest.mock import AsyncMock

    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    state: dict[str, Any] = {"count": 0, "calls": [], "hold_event": asyncio.Event()}

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        call_index = state["count"]
        state["count"] += 1
        state["calls"].append(
            {
                "prompt": prompt,
                "schema": response_schema,
                "temperature": getattr(config, "temperature", None),
                "timeout": getattr(config, "timeout", None),
                "call_index": call_index,
            }
        )
        if delay_sec:
            await asyncio.sleep(delay_sec)
        if hold_at_call is not None and call_index == hold_at_call:
            await state["hold_event"].wait()
        if call_index in fail_call_indices:
            from src.domain.exceptions.llm_exceptions import LLMAPIError

            raise LLMAPIError(f"Fake 注入失败（调用序 {call_index}）")

        from src.application.services.blm_planning_prompts import (
            GapAnalysisSchema,
            InsightStepSchema,
            InsightSynthesisSchema,
        )

        if response_schema is GapAnalysisSchema:
            return GapAnalysisSchema(
                financial_gap="财务差距量化（集成）",
                operational_gap="运营差距分析（集成）",
                root_causes=["根因一", "根因二"],
                portfolio_health="组合健康度（集成）",
            )
        if response_schema is InsightStepSchema:
            return InsightStepSchema(summary=f"洞察产物-{call_index}", findings=["发现"])
        if response_schema is InsightSynthesisSchema:
            return InsightSynthesisSchema(conclusions=["综合结论（集成）"])
        raise AssertionError(f"未知 response_schema: {response_schema!r}")

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> LLMResponse:
        return LLMResponse(content='{"valid": true}', model="fake-llm")

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    fake.generate.side_effect = _generate
    fake._blm_state = state
    return fake


class _RecordingEventBus:
    """记录发布事件的发布器（4-6/4-7/5-3 先例——真实发布归场景③）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


# ===================================================================
# 检索门控（3-1a 验收先例——embedding+Qdrant 双探测 + 租户 collection）
# ===================================================================


async def _ensure_retrieval(env: Any) -> dict[str, Any] | None:
    """探测并建制检索语料（不可达返回 None——调用方 skip）。"""
    from qdrant_client import AsyncQdrantClient, models

    from src.infrastructure.config.embedding import EmbeddingConfig
    from src.infrastructure.external_services.embedding.embedding_api_client import EmbeddingAPIClient

    embedding = EmbeddingAPIClient(EmbeddingConfig.from_env())
    client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=30)
    try:
        await embedding.embed_query("连通性探测")
        await client.get_collections()
        collection = f"test_blm_int_{uuid.uuid4().hex[:8]}"
        await client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
        )
        vectors = await embedding.embed_documents(list(_CORPUS_TEXTS))
        await client.upsert(
            collection_name=collection,
            points=[
                models.PointStruct(id=str(uuid.uuid4()), vector=vec, payload={"text": text})
                for vec, text in zip(vectors, _CORPUS_TEXTS)
            ],
        )
        return {"collection": collection, "embedding": embedding, "client": client}
    except Exception:
        await embedding.close()
        return None


async def _dispose_retrieval(retrieval: dict[str, Any]) -> None:
    """清理检索语料 collection。"""
    try:
        await retrieval["client"].delete_collection(retrieval["collection"])
        await retrieval["client"].close()
    except Exception:
        pass
    try:
        await retrieval["embedding"].close()
    except Exception:
        pass


# ===================================================================
# 真实链装配（guard 链 + CEO 实例化 + 档案 + 服务 + 引擎 + 用例）
# ===================================================================


class _StubIsolationSwitchLogRepository:
    """零 IO 日志仓储替身（5-3 验收同款——真实链归 5-6）。"""

    def __init__(self) -> None:
        self.saved_logs: list[Any] = []

    async def save(self, log: Any) -> None:
        self.saved_logs.append(log)

    async def search(self, query: Any) -> Any:
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


async def _assemble_chain(redis_client: Any, env: Any, retrieval: dict[str, Any], **fake_kwargs: Any) -> dict[str, Any]:
    """BLM 全链手工装配（真实服务 + Fake LLM 唯一豁免）。"""
    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.services.dense_search_service import DenseSemanticSearchService
    from src.application.services.hybrid_search_service import HybridSearchService
    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.services.retry_helpers import RetryPolicy
    from src.application.services.sparse_search_service import Bm25SparseSearchService
    from src.application.services.tool_execution_engine import ToolExecutionEngine
    from src.application.services.tool_execution_service import ToolExecutionService
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
    from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.domain.services.rrf_fusion import fuse
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository
    from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository
    from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

    redis_adapter = RedisAdapter(redis_client=redis_client)
    agent_repository = RedisAgentRepository(adapter=redis_adapter)
    isolation_repository = RedisIsolationRepository(adapter=redis_adapter)
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        agent_config_loader=resolve("agent_config_loader"),
        isolation_switch_log_repository=_StubIsolationSwitchLogRepository(),
        audit_service=None,
    )
    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=agent_repository,
        agent_config_loader=resolve("agent_config_loader"),
    )

    instantiate = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )
    agent_id = (await instantiate.execute(role=AgentRole.CEO)).agent_id

    # 真实档案加载链路验证（load 真实调用——use case 内部另行加载消费）
    await resolve("agent_profile_loader").load(role=AgentRole.CEO, agent_id=agent_id)
    await resolve("skill_selector").list_active_skills()

    fake_llm = _make_fake_llm(**fake_kwargs)
    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    # sandbox 替身纪律：spec 约束端口契约 + execute_code 显式真实 dict 返回值
    # （裸 AsyncMock 的 return_value 亦 AsyncMock 化——.get() 变协程调用泄漏
    # RuntimeWarning，且 str(协程) 垃圾文本混入工具输出注入面）
    from unittest.mock import AsyncMock

    from src.domain.ports.sandbox_executor import SandboxExecutor

    sandbox = AsyncMock(spec=SandboxExecutor)
    sandbox.execute_code.return_value = {"status": "ok", "output": '{"valid": true}', "error": None}
    engine = ToolExecutionEngine(
        llm_client=fake_llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0.01),
    )
    tool_execution_service = ToolExecutionService(registry=registry, engine=engine)

    vector_storage = QdrantVectorStorage(retrieval["client"])
    hybrid = HybridSearchService(
        dense_search=DenseSemanticSearchService(embedding_service=retrieval["embedding"], vector_storage=vector_storage),
        sparse_search=Bm25SparseSearchService(embedding_service=retrieval["embedding"], vector_storage=vector_storage),
        fuse=fuse,
        graph_search=None,
        weights=[1.0, 1.0, 0.5],
    )

    recorder = _RecordingEventBus()
    snapshot_store = RedisSnapshotStore(adapter=redis_adapter)
    service = BlmPlanningService(
        llm_client=fake_llm,
        tool_execution_service=tool_execution_service,
        tool_registry_service=registry,
        isolation_guard=guard,
        hybrid_search=hybrid,
        search_collection=retrieval["collection"],
        event_publisher=recorder,
        snapshot_repository=snapshot_store,
    )
    langgraph_engine = LangGraphEngine(
        config=LangGraphConfig.from_env(), event_publisher=recorder, blm_planning_service=service
    )
    profile_use_case = LoadAgentProfileUseCase(
        profile_loader=resolve("agent_profile_loader"),
        repository=agent_repository,
        skill_selector=resolve("skill_selector"),
        event_publisher=InMemoryEventBus(),
    )
    use_case = RunBlmPlanningUseCase(
        agent_repository=agent_repository,
        agent_profile_use_case=profile_use_case,
        agent_engine=langgraph_engine,
        blm_planning_service=service,
        isolation_guard=guard,
        event_publisher=recorder,
    )
    return {
        "agent_id": agent_id,
        "agent_repository": agent_repository,
        "guard": guard,
        "profile_use_case": profile_use_case,
        "fake_llm": fake_llm,
        "service": service,
        "snapshot_store": snapshot_store,
        "recorder": recorder,
        "use_case": use_case,
        "task": "制定新能源汽车行业五年战略规划",
    }


async def _cleanup_chain(redis_client: Any, chain: dict[str, Any]) -> None:
    """清理 Agent 状态键（agent/isolation 双 namespace 精确删除）。"""
    agent_id = chain["agent_id"]
    for namespace in ("agent", "isolation"):
        await redis_client.delete(build_key(namespace, str(agent_id)))


# ===================================================================
# 场景① 真实实例化全链 + 顺序双锚 + 图身份锚（Subtask 5.1）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_1_real_chain_full_flow(real_redis: Any) -> None:
    """场景①：真实链全流程（阶段 1 四字段 + 六子步骤 + 综合 + 图身份锚）。

    顺序断言双锚：①枚举序独立构造（insight_steps[i].step == EXPECTED_ORDER[i]）
    ②时间戳非重叠（started_at[i] >= completed_at[i-1]——证伪并行）。
    """
    from tests.environments import get_test_env

    retrieval = await _ensure_retrieval(get_test_env())
    if retrieval is None:
        pytest.skip("检索服务（embedding/Qdrant）不可用")
    redis_client = real_redis
    try:
        chain = await _assemble_chain(redis_client, get_test_env(), retrieval)
        result = await chain["use_case"].execute(agent_id=chain["agent_id"], task=chain["task"])

        # 阶段 1 四字段
        assert result.gap_artifacts.financial_gap
        assert result.gap_artifacts.operational_gap
        assert result.gap_artifacts.root_causes
        assert result.gap_artifacts.portfolio_health
        # 顺序锚 1：枚举序（独立构造期望）
        actual_steps = tuple(s.step for s in result.insight_steps)
        assert actual_steps == EXPECTED_ORDER, f"顺序错乱: {actual_steps}"
        # 顺序锚 2：时间戳非重叠（证伪并行）
        steps = result.insight_steps
        for prev, curr in zip(steps, steps[1:]):
            assert curr.started_at and prev.completed_at
            assert curr.started_at >= prev.completed_at
        # 综合与图身份锚
        assert result.synthesis.conclusions
        assert len(result.insight_steps) == 6
        # 图身份锚：经真实引擎 submit_graph——agent_id 全程单一
        assert str(result.agent_id) == str(chain["agent_id"])
        await _cleanup_chain(redis_client, chain)
    finally:
        await _dispose_retrieval(retrieval)


# ===================================================================
# 场景② 状态快照（Subtask 5.2——门控构造执行中轮询 + 终态 + 写读一致）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_2_status_snapshot_lifecycle(real_redis: Any) -> None:
    """场景②：执行中轮询（挂起第 2 步门控）→ 终态 8/8 → latest 写读一致。"""
    from src.application.use_cases.get_blm_planning_status import GetBlmPlanningStatusUseCase
    from src.domain.value_objects.blm_phases import BlmPlanningStatus
    from tests.environments import get_test_env

    retrieval = await _ensure_retrieval(get_test_env())
    if retrieval is None:
        pytest.skip("检索服务（embedding/Qdrant）不可用")
    redis_client = real_redis
    try:
        # 挂起第 2 次调用（TREND——performance_gap 完成后）制造执行中窗口
        chain = await _assemble_chain(redis_client, get_test_env(), retrieval, hold_at_call=1)
        status_use_case = GetBlmPlanningStatusUseCase(snapshot_repository=chain["snapshot_store"])

        task = asyncio.create_task(chain["use_case"].execute(agent_id=chain["agent_id"], task=chain["task"]))
        mid_status: BlmPlanningStatus | None = None
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            await asyncio.sleep(0.02)
            if task.done():
                break
            try:
                # plan_id 未知（用例内铸造）——经服务内存 run 键探测
                plan_ids = list(chain["service"].active_plan_ids)
                if plan_ids:
                    mid_status = await status_use_case.execute(plan_id=plan_ids[0])
                    if mid_status.completed_steps >= 1:
                        break
            except Exception:
                continue
        assert mid_status is not None, "执行中窗口未捕获快照"
        assert 1 <= mid_status.completed_steps < 8, "挂起第 2 步时应读到 1~7 步完成"
        assert mid_status.phase
        assert 0 < mid_status.progress_percent < 100

        chain["fake_llm"]._blm_state["hold_event"].set()  # 释放挂起
        result = await task

        final_status = await status_use_case.execute(plan_id=result.plan_id)
        assert final_status.completed_steps == 8
        assert final_status.total_steps == 8
        assert final_status.progress_percent == 100.0
        assert len(final_status.timeline) == 8
        # latest 写读一致（二次读回同值）
        again = await status_use_case.execute(plan_id=result.plan_id)
        assert again.completed_steps == final_status.completed_steps
        assert again.plan_id == final_status.plan_id
        await _cleanup_chain(redis_client, chain)
    finally:
        await _dispose_retrieval(retrieval)


# ===================================================================
# 场景③ 真实事件发布（Subtask 5.3——PG event_outbox 落行，双预检门控）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_3_real_publish_outbox_rows(real_redis: Any) -> None:
    """场景③：真实 event_publisher 落行（8 stage 全集各恰一次 + PlanningStarted 恰一行）。

    PG 门控双预检（连接 + event_outbox 表存在——5-4 R1-F07 先例）。
    """
    import sqlalchemy as sa

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from tests.environments import get_test_env

    retrieval = await _ensure_retrieval(get_test_env())
    if retrieval is None:
        pytest.skip("检索服务（embedding/Qdrant）不可用")
    env = get_test_env()
    manager = PostgreSQLManager(
        PostgreSQLConfig(
            host=env.postgres.host,
            port=env.postgres.port,
            username=env.postgres.username,
            password=env.postgres.password,
            database=env.postgres.database,
        )
    )
    engine = manager.get_async_engine()
    try:
        async with engine.connect() as probe:
            await probe.execute(sa.text("SELECT event_id FROM event_outbox LIMIT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL 不可达或 event_outbox 表未初始化: {exc}")

    redis_client = real_redis
    event_ids: list[str] = []
    try:
        from src.application.services.blm_planning_service import BlmPlanningService
        from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
        from src.domain.ports.resolver import get_resolver, resolve
        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
        from src.infrastructure.config.langgraph import LangGraphConfig

        chain = await _assemble_chain(redis_client, env, retrieval)
        # 覆写：记录总线 → 真实 publisher（SINGLETON 跨 loop 防线——5-3 场景⑤先例）
        get_resolver().clear_singleton()
        real_publisher = resolve("event_publisher")
        service = BlmPlanningService(
            llm_client=chain["fake_llm"],
            tool_execution_service=chain["service"].tool_execution_service,
            tool_registry_service=chain["service"].tool_registry_service,
            isolation_guard=chain["service"].isolation_guard,
            hybrid_search=chain["service"].hybrid_search,
            search_collection=retrieval["collection"],
            event_publisher=real_publisher,
            snapshot_repository=chain["snapshot_store"],
        )
        engine_real = LangGraphEngine(
            config=LangGraphConfig.from_env(), event_publisher=real_publisher, blm_planning_service=service
        )
        use_case = RunBlmPlanningUseCase(
            agent_repository=chain["agent_repository"],
            agent_profile_use_case=chain["profile_use_case"],
            agent_engine=engine_real,
            blm_planning_service=service,
            isolation_guard=chain["guard"],
            event_publisher=real_publisher,
        )
        result = await use_case.execute(agent_id=chain["agent_id"], task=chain["task"])
        agent_id_str = str(chain["agent_id"])

        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT event_id, event_type, payload->'payload'->>'stage' AS stage, COUNT(*) OVER "
                        "(PARTITION BY event_type, payload->'payload'->>'stage') AS cnt "
                        "FROM event_outbox "
                        "WHERE event_type IN ('PlanningStarted', 'BlmStageCompleted') "
                        "AND payload->>'aggregate_id' = :agent_id "
                        "AND created_at >= NOW() - INTERVAL '2 minutes'"
                    ),
                    {"agent_id": agent_id_str},
                )
            ).fetchall()
        await engine.dispose()

        assert rows, "event_outbox 未落 BLM 事件行（真实发布链路断裂）"
        by_type: dict[tuple[str, str | None], int] = {}
        for row in rows:
            event_ids.append(str(row[0]))
            key = (row[1], row[2] if row[1] == "BlmStageCompleted" else None)
            by_type[key] = by_type.get(key, 0) + 1

        assert by_type.get(("PlanningStarted", None)) == 1, (
            f"PlanningStarted 落行 {by_type.get(('PlanningStarted', None))} != 1"
        )
        expected_stages = {"performance_gap"} | {f"market_insight_{s}" for s in EXPECTED_ORDER} | {"market_insight_synthesis"}
        actual_stages = {stage for (etype, stage) in by_type if etype == "BlmStageCompleted"}
        assert actual_stages == expected_stages, f"stage 全集不一致: {actual_stages ^ expected_stages}"
        assert all(count == 1 for count in by_type.values()), f"存在重复落行: {by_type}"
        assert result.plan_id
        await _cleanup_chain(redis_client, chain)
    finally:
        # teardown：按 event_id 精确清理本场景落行（K8 先例）
        if event_ids:
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        sa.text("DELETE FROM event_outbox WHERE event_id = ANY(:ids)"),
                        {"ids": event_ids},
                    )
                await engine.dispose()
            except Exception:
                await engine.dispose()
        await _dispose_retrieval(retrieval)


# ===================================================================
# 场景④ 性能基准（Subtask 5.4——DC-7 Fake LLM 口径 + 受控注入采样）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_4_performance_and_success_rate(real_redis: Any) -> None:
    """场景④：Fake LLM 口径 P95<30s + 受控注入采样成功率≥95% + 8s/温度配置传递。

    口径差声明（DC-7）：P95 以 Fake LLM 管线自身开销计量——真实 LLM 延迟
    显式出栈（单次结构化调用真实环境 30s+ 量级——8 次串行级联真实口径归
    部署验证）；受控失败注入采样（≥20 次轮转单步注入——降级成功计入，
    零注入恒 100% 零鉴别力——R1-11 裁定）。
    """
    from tests.environments import get_test_env

    retrieval = await _ensure_retrieval(get_test_env())
    if retrieval is None:
        pytest.skip("检索服务（embedding/Qdrant）不可用")
    redis_client = real_redis
    try:
        from src.application.services.blm_planning_prompts import BLM_TEMPERATURE_PROFILE

        durations: list[float] = []
        success_steps = 0
        total_steps = 0
        all_temperatures: list[float | None] = []
        all_timeouts: list[float | None] = []
        for i in range(20):
            chain = await _assemble_chain(
                redis_client,
                get_test_env(),
                retrieval,
                fail_call_indices=frozenset({1 + (i % 6), 2 + (i % 6)}),  # 六子步骤内单步双杀（首调+重试皆败→真降级）
            )
            start = time.monotonic()
            result = await chain["use_case"].execute(agent_id=chain["agent_id"], task=chain["task"])
            durations.append(time.monotonic() - start)
            degraded_in_insight = sum(1 for s in result.insight_steps if s.degraded)
            # 鉴别锚（R1-8）：双杀注入下每轮恰 1 步真降级——重试机制删除→2 红 /
            # 降级标记丢失→0 红 / 降级捕获删除→异常穿透 execute 抛 481 该轮炸
            assert degraded_in_insight == 1, f"第 {i} 轮双杀注入应恰 1 步真降级（实测 {degraded_in_insight}）"
            # 成功口径（epics L2061 统一钦定「降级信封完整即计入成功」——逐位判定）
            for s in result.insight_steps:
                envelope_complete = bool(s.summary) or (s.degraded and bool(s.degrade_reason))
                assert envelope_complete, f"步骤 {s.step} 信封不完整"
                if envelope_complete:
                    success_steps += 1
            total_steps += 6
            all_temperatures.extend(c["temperature"] for c in chain["fake_llm"]._blm_state["calls"])
            all_timeouts.extend(c["timeout"] for c in chain["fake_llm"]._blm_state["calls"])
            await _cleanup_chain(redis_client, chain)

        durations.sort()
        p95 = durations[max(0, int(len(durations) * 0.95) - 1)]
        assert p95 < 30.0, f"Fake LLM 口径 P95={p95:.2f}s >= 30s（DC-7 口径）"
        rate = success_steps / total_steps * 100
        assert rate >= 95.0, f"受控注入下六子步骤成功率 {rate:.1f}% < 95%"
        assert all(t == 8.0 for t in all_timeouts), "单调用超时 8s 配置传递断裂"
        assert all(t in BLM_TEMPERATURE_PROFILE.values() for t in all_temperatures), "温度档越配置表值域"
    finally:
        await _dispose_retrieval(retrieval)
