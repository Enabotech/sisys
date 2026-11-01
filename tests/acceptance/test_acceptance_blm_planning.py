"""Story 6-1 — BLM 前两阶段规划流程验收测试（BDD 场景步骤实现）。

模板基准: test_acceptance_postgresql_relational_layer.py（R6——多行 @scenario
字面量路径 + 场景绑定与步骤实现交替排列 + AC 横幅分组）；装配形态对齐
test_acceptance_agent_workflow.py（5-3——真实服务链 + Fake LLM 唯一豁免替身）。

14 场景三属性分档表（Subtask 0.3 钦定——层级/LLM 依赖/服务门控）：

| #  | 场景             | 层级                 | LLM          | 服务门控        |
|----|------------------|----------------------|--------------|-----------------|
| 1  | AC-1.1 完整流程  | 用例级（全链装配）   | Fake         | Redis+检索(R)   |
| 2  | AC-1.2 顺序双锚  | 用例级               | Fake         | R               |
| 3  | AC-1.3 综合洞察  | 用例级               | Fake 捕获    | R               |
| 4  | AC-2.1 单角色    | 用例级+静态 grep     | Fake         | R               |
| 5  | AC-2.2 守卫链    | 用例级（守卫触发）   | 不触         | Redis           |
| 6  | AC-3.1 执行中    | 门控构造（挂起轮询） | Fake 挂起    | R               |
| 7  | AC-3.2 终态快照  | 用例级               | Fake         | R               |
| 8  | AC-4.1 事件发布  | 用例级（记录总线）   | Fake         | R               |
| 9  | AC-4.2 outbox   | 用例级（真实发布）   | Fake         | R+PG            |
| 10 | AC-5.1 性能采样  | 用例级（benchmark）  | Fake 延迟    | R               |
| 11 | AC-6.1 步级降级  | 用例级               | Fake 失败注  | R               |
| 12 | AC-6.2 全/部分降 | 用例级（双比例）     | Fake 失败注  | R               |
| 13 | AC-6.3 449 降级  | 用例级（受限白名单） | Fake         | R               |
| 14 | 收尾完成清单     | 静态完成清单         | 无           | 无              |

检索门控档位（R = embedding+Qdrant 双探测 + 租户隔离 collection 建制语料
upsert，3-1a 验收先例；检索不可达环境逐场景动态 skip；PG = event_outbox
连接+表存在双预检，5-4 R1-F07 先例）。

新模块延迟 import 纪律：本 Story 交付的模块（blm_phases VO / planning_events
扩展 / planning_exceptions / blm_planning 端口 / blm_planning_service /
prompts / sp_blm_graph / use_cases）一律在步骤函数体内延迟 import——模块
顶部 import 会使 pytest 收集期整文件 collection error，已实现/未实现场景
一起炸，无法逐 Task 转绿（Task 0 预期红因 = ModuleNotFoundError）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_blm_planning.py -v

测试隔离:
    - 场景级独立 Redis 客户端 + 同循环关闭（跨循环 "Event loop is closed" 存档教训）
    - Agent 状态键逐 agent_id 精确删除（agent/isolation 双 namespace；禁 flush）
    - 检索 collection 场景级唯一命名 + teardown 精确删除
    - BDD 步骤禁 @pytest.mark.asyncio（context 数据丢失红线），统一 _run_async
    - Fake LLM 端口替身是外部 SaaS 豁免面（分派键 = response_schema 身份）
    - outbox 事件清理走 fixture teardown（K8 先例——断言失败也执行；CLI 无
      poller 残留知悉归 L170 锚）
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Coroutine, Generator
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

from src.infrastructure.storage.redis.key_builder import build_key

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# 文件名不含服务关键词，acceptance conftest 不会自动添加 marker——显式声明；
# xdist_group 性能采样场景同 worker 串行化
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.redis,
    pytest.mark.xdist_group("blm-planning-perf"),
]

# 六子步骤期望顺序（独立构造自 or.md 六步序——枚举序期望不经被测服务生成，
# 循环自证红线；string 值与 MarketInsightStep 枚举 value 同源对齐）
EXPECTED_INSIGHT_ORDER: tuple[str, ...] = (
    "trend",
    "market_customer",
    "competition",
    "self",
    "opportunity",
    "opportunity_gap",
)

# 真实检索语料（背景建制——与任务主题相关，保证 dense 命中）
_CORPUS_TEXTS: tuple[str, ...] = (
    "新能源汽车行业进入战略分析报告：市场增速放缓但渗透率持续提升",
    "财务业绩差距分析：营收目标达成率与毛利率下滑根因",
    "竞争对手动态：头部厂商价格战与渠道下沉策略",
    "宏观趋势：政策补贴退坡与技术路线演进（固态电池）",
    "内部能力评估：研发投入占比与组织能力短板",
    "市场机会：海外新兴市场增长路径与机会差距量化",
)

# Fake LLM 各步骤产出语料（步骤可判别标记——顺序断言的产物侧观测锚）
_FAKE_STEP_SUMMARY_PREFIX = "市场洞察产物"

#: 六子步骤显示名字面量（or.md 钦定序——Fake 步骤标识提取与断言期望共源）
_STEP_DISPLAY_NAMES: tuple[str, ...] = (
    "看趋势",
    "看市场与客户",
    "看竞争",
    "看自己",
    "看机会",
    "机会差距分析",
)


def _extract_step_display_name(prompt: str) -> str:
    """从 prompt 提取子步骤显示名（完整句式锚——与调用计数解耦，R1-7）。

    失败注入场景下重试同占调用序——按计数注入标识会错位；prompt 中的
    「执行 BLM 市场洞察子步骤「X」」句式在正常/注入场景均唯一可判别。
    """
    for name in _STEP_DISPLAY_NAMES:
        if f"执行 BLM 市场洞察子步骤「{name}」" in prompt:
            return name
    return "未知步骤"


# ===================================================================
# 共享基建：三件套（context fixture / 模块级 event_loop / _run_async）
# ===================================================================


@pytest.fixture(scope="module")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """模块级事件循环（BDD 步骤禁 @pytest.mark.asyncio——同循环三件套）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """BDD 步骤间共享状态容器（场景级独立 Redis 客户端 + 同循环 teardown）。

    teardown 顺序：恢复端口覆写 → 删 outbox 事件行（真实发布场景）→ 删检索
    collection → 删 Agent 状态键 → 关闭 Redis 客户端（全部 _run_async 同循环；
    K8 先例——断言失败也执行）。
    """
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(
        host=acceptance_env_config.redis.host,
        port=acceptance_env_config.redis.port,
        password=acceptance_env_config.redis.password,
        decode_responses=True,
    )
    ctx: dict[str, Any] = {
        "_tenant": uuid.uuid4(),
        "_loop": event_loop,
        "_env_config": acceptance_env_config,
        "_redis_client": redis_client,
        "_agent_ids": [],
        "_restorers": [],
        "_created_collections": [],
        "_outbox_event_ids": [],
    }
    yield ctx

    # 1) 端口覆写还原（真实发布链路场景注册的替身）
    for restore in ctx["_restorers"]:
        restore()
    # 2) outbox 事件清理（真实发布场景按 event_id 精确删除——K8 teardown 先例）
    if ctx["_outbox_event_ids"]:
        _cleanup_outbox_rows(ctx)
    # 3) 检索 collection 精确删除
    for name in list(ctx["_created_collections"]):
        try:
            _run_async(event_loop, _delete_collection(ctx, name))
        except Exception:
            pass
    # 4) Agent 状态键精确删除（agent/isolation 双 namespace）
    for agent_id in ctx["_agent_ids"]:
        for namespace in ("agent", "isolation"):
            _run_async(event_loop, redis_client.delete(build_key(namespace, str(agent_id))))
    # 5) 同循环关闭客户端
    _run_async(event_loop, redis_client.close())


def _run_async(event_loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, Any]) -> Any:
    """在模块级共享事件循环上同步调度协程（BDD 步骤禁 @pytest.mark.asyncio）。"""
    return event_loop.run_until_complete(coro)


async def _delete_collection(ctx: dict[str, Any], name: str) -> None:
    from qdrant_client import AsyncQdrantClient

    from src.infrastructure.config.qdrant import QdrantConfig

    env = ctx["_env_config"]
    config = QdrantConfig(
        host=env.qdrant.host, port=env.qdrant.port, grpc_port=env.qdrant.grpc_port, api_key=env.qdrant.api_key
    )
    client = AsyncQdrantClient(url=f"http://{config.host}:{config.port}", timeout=10)
    try:
        await client.delete_collection(name)
    finally:
        await client.close()


def _cleanup_outbox_rows(ctx: dict[str, Any]) -> None:
    """按 event_id 精确删除本场景落库的 outbox 事件行（真实发布场景清理）。"""
    import sqlalchemy as sa

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    env = ctx["_env_config"]

    async def _delete() -> None:
        manager = PostgreSQLManager(
            PostgreSQLConfig(
                host=env.postgres.host,
                port=env.postgres.port,
                username=env.postgres.username,
                password=env.postgres.password,
                database=env.postgres.database,
            )
        )
        try:
            engine = manager.get_async_engine()
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text("DELETE FROM event_outbox WHERE event_id = ANY(:ids)"),
                    {"ids": [str(e) for e in ctx["_outbox_event_ids"]]},
                )
            await engine.dispose()
        except Exception:
            pass  # 清理尽力而为（PG 不可达时跳过——生产残留归 L170 锚知悉）

    try:
        _run_async(ctx["_loop"], _delete())
    except Exception:
        pass


# ===================================================================
# 共享基建：Fake LLM（BLM 面三 Schema 分派 + 失败/挂起注入 + 配置捕获）
# ===================================================================


def _make_fake_llm(
    *,
    fail_call_indices: frozenset[int] = frozenset(),
    hold_at_call: int | None = None,
    delay_sec: float = 0.0,
) -> Any:
    """BLM 面 Fake LLM 端口替身（外部 SaaS 豁免面——分派键 = response_schema 身份）。

    分派键 = GapAnalysisSchema / InsightStepSchema / InsightSynthesisSchema 三者
    身份互斥。注入控制：
    - fail_call_indices: 按调用序（0 基）注入 LLMAPIError——AC-6 受控失败采样
    - hold_at_call: 指定调用序挂起（await asyncio.Event——AC-3.1 门控构造）
    - delay_sec: 每调用延迟（AC-5 计时下界注入）

    calls 记录每次 structured_generate 的 prompt/schema/temperature/timeout
    实参（AC-5 配置传递断言锚 + AC-2 prompt 前缀断言锚）。
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
            await state["hold_event"].wait()  # 门控挂起（场景 teardown 前 set 释放）
        if call_index in fail_call_indices:
            raise __import__("src.domain.exceptions.llm_exceptions", fromlist=["LLMAPIError"]).LLMAPIError(
                f"Fake 注入失败（调用序 {call_index}）"
            )

        from src.application.services.blm_planning_prompts import (
            GapAnalysisSchema,
            InsightStepSchema,
            InsightSynthesisSchema,
        )

        if response_schema is GapAnalysisSchema:
            return GapAnalysisSchema(
                financial_gap="财务差距量化：营收达成率 82%，毛利率 -3.2pct",
                operational_gap="运营差距分析：交付周期延长与产能利用率不足",
                root_causes=["价格竞争侵蚀毛利", "供应链成本上升", "组织响应迟缓"],
                portfolio_health="业务组合健康度：核心业务稳健，新兴业务双低",
            )
        if response_schema is InsightStepSchema:
            step_marker = _extract_step_display_name(prompt)
            return InsightStepSchema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:{step_marker}（结构化要点）",
                findings=["发现一：趋势信号明确", "发现二：竞争压力上升"],
            )
        if response_schema is InsightSynthesisSchema:
            return InsightSynthesisSchema(conclusions=["综合结论一：优先补强内部能力", "综合结论二：把握海外机会窗口"])
        raise AssertionError(f"未知 response_schema: {response_schema!r}")

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> LLMResponse:
        if delay_sec:
            await asyncio.sleep(delay_sec)
        return LLMResponse(content='{"valid": true, "confidence": 0.9}', model="fake-llm")

    async def _close() -> None:
        return None

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    fake.generate.side_effect = _generate
    fake.close.side_effect = _close
    fake_probe: Any = fake  # 测试探针挂载（Any 收窄——动态属性断言锚）
    fake_probe._blm_state = state
    return fake


# ===================================================================
# 共享基建：记录总线 + 真实链装配
# ===================================================================


class _RecordingEventBus:
    """记录发布事件的发布器（手写 EventPublisher 协议实现——4-6/4-7/5-3 先例）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


def _ensure_qdrant_retrieval(ctx: dict[str, Any]) -> None:
    """检索门控 + 租户隔离 collection 建制语料 upsert（3-1a 验收先例）。

    embedding 客户端构造 + Qdrant health 双探测，任一不可达 pytest.skip；
    建制语料 upsert 后返回（collection 名经 ctx["retrieval_collection"] 共享）。
    """
    if "retrieval_collection" in ctx:
        return

    from qdrant_client import AsyncQdrantClient

    from src.infrastructure.config.embedding import EmbeddingConfig
    from src.infrastructure.config.qdrant import QdrantConfig
    from src.infrastructure.external_services.embedding.embedding_api_client import EmbeddingAPIClient

    env = ctx["_env_config"]
    loop = ctx["_loop"]

    async def _setup() -> tuple[str, EmbeddingAPIClient, AsyncQdrantClient]:
        embedding = EmbeddingAPIClient(EmbeddingConfig.from_env())
        qconfig = QdrantConfig(
            host=env.qdrant.host, port=env.qdrant.port, grpc_port=env.qdrant.grpc_port, api_key=env.qdrant.api_key
        )
        client = AsyncQdrantClient(url=f"http://{qconfig.host}:{qconfig.port}", timeout=30)
        await embedding.embed_query("连通性探测")  # embedding 服务不可达即抛
        await client.get_collections()  # Qdrant 不可达即抛

        collection = f"test_blm_{uuid.uuid4().hex[:8]}"
        from qdrant_client import models

        await client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
        )
        vectors = await embedding.embed_documents(list(_CORPUS_TEXTS))
        points = [
            models.PointStruct(id=str(uuid.uuid4()), vector=vec, payload={"text": text})
            for vec, text in zip(vectors, _CORPUS_TEXTS)
        ]
        await client.upsert(collection_name=collection, points=points)
        return collection, embedding, client

    try:
        collection, embedding, qclient = _run_async(loop, _setup())
    except Exception as exc:  # 探测失败——检索不可达环境动态 skip
        pytest.skip(f"检索服务（embedding/Qdrant）不可用: {exc}")

    ctx["retrieval_collection"] = collection
    ctx["_created_collections"].append(collection)
    ctx["_embedding_client"] = embedding
    ctx["_qdrant_client"] = qclient


def _make_real_hybrid_search(ctx: dict[str, Any]) -> Any:
    """真实 hybrid 检索服务（场景级实例——dense+sparse 双路，graph 路豁免注记）。

    全真实组件手动构造（EmbeddingAPIClient/QdrantVectorStorage/
    DenseSemanticSearchService/Bm25SparseSearchService/HybridSearchService/rrf fuse）；
    graph_search=None（Neo4j 路非本 Story 检索依赖面——HybridSearchService 构造
    签名可选项；部分路激活时权重自动过滤）。场景级实例避免 SINGLETON 缓存跨
    loop 死连接。
    """
    _ensure_qdrant_retrieval(ctx)

    from src.application.services.dense_search_service import DenseSemanticSearchService
    from src.application.services.hybrid_search_service import HybridSearchService
    from src.application.services.sparse_search_service import Bm25SparseSearchService
    from src.domain.services.rrf_fusion import fuse
    from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage

    vector_storage = QdrantVectorStorage(ctx["_qdrant_client"])
    dense = DenseSemanticSearchService(embedding_service=ctx["_embedding_client"], vector_storage=vector_storage)
    sparse = Bm25SparseSearchService(embedding_service=ctx["_embedding_client"], vector_storage=vector_storage)
    return HybridSearchService(dense_search=dense, sparse_search=sparse, fuse=fuse, graph_search=None, weights=[1.0, 1.0, 0.5])


class _StubIsolationSwitchLogRepository:
    """手写 duck-typing 日志仓储替身（5-3 验收同款——零 IO 替身，真实链归 5-6）。"""

    def __init__(self) -> None:
        self.saved_logs: list[Any] = []

    async def save(self, log: Any) -> None:
        self.saved_logs.append(log)

    async def search(self, query: Any) -> Any:
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


def _make_real_guard_chain(ctx: dict[str, Any], *, restricted_tools: bool = False) -> Any:
    """真实隔离守卫链（5-3 验收同款三依赖注入——场景级 Redis 仓储）。

    restricted_tools=True 时以 L2 白名单形态写入隔离状态（工具白名单仅含
    pestel-analysis——449 降级场景的受限真实锚：白名单外工具子步骤在预检时
    拒绝，伪造真实 449 路径而非 Mock 抛错）。
    """
    if "isolation_guard_chain" in ctx and not restricted_tools:
        return ctx["isolation_guard_chain"]["guard"]

    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    loop = ctx["_loop"]
    redis_client = ctx["_redis_client"]
    config_loader = resolve("agent_config_loader")
    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        agent_config_loader=config_loader,
        isolation_switch_log_repository=_StubIsolationSwitchLogRepository(),
        audit_service=None,
    )
    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=agent_repository,
        agent_config_loader=config_loader,
    )
    ctx["isolation_guard_chain"] = {
        "guard": guard,
        "agent_repository": agent_repository,
        "isolation_service": isolation_service,
    }
    _run_async(loop, redis_client.ping())
    return guard


class _RestrictedConfigLoader:
    """受限配置加载器（真实加载后收窄 allowed_tools——449 真实锚构造）。

    白名单真源经 AgentConfigLoader（L4 tool_isolation 严格模式）——本包装
    保持真实加载链路，仅收窄白名单至「PESTEL 分析」单项（duck-typing 注入
    guard 构造位；L2/L3 是共享池全放行不触发 449——isolation_access 纯函数
    语义），使白名单外工具候选在预检被拒（真实 449 路径）。
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    async def load(self, role: Any, **kwargs: Any) -> Any:
        import dataclasses

        config = await self._inner.load(role, **kwargs)
        return dataclasses.replace(config, allowed_tools=("PESTEL 分析",))


def _make_restricted_guard_chain(ctx: dict[str, Any]) -> Any:
    """构造受限白名单 guard 链（场景 13——449 降级真实路径）。"""
    import dataclasses

    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    _ = dataclasses
    loop = ctx["_loop"]
    redis_client = ctx["_redis_client"]
    restricted_loader = _RestrictedConfigLoader(resolve("agent_config_loader"))
    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        agent_config_loader=restricted_loader,
        isolation_switch_log_repository=_StubIsolationSwitchLogRepository(),
        audit_service=None,
    )
    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=agent_repository,
        agent_config_loader=restricted_loader,
    )
    ctx["isolation_guard_chain"] = {
        "guard": guard,
        "agent_repository": agent_repository,
        "isolation_service": isolation_service,
    }
    _run_async(loop, redis_client.ping())
    return guard


def _instantiate_real_agent(ctx: dict[str, Any], *, restricted_tools: bool = False) -> uuid.UUID:
    """经真实实例化用例构造 CEO Agent（5-3 同步形态先例）。

    restricted_tools=True 时由装配方先行构造受限白名单 guard 链
    （_make_restricted_guard_chain——白名单收窄至 PESTEL 分析单项，
    L4 严格模式下其余工具预检 449）。
    """
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

    chain = ctx["isolation_guard_chain"]
    config_loader = (
        _RestrictedConfigLoader(resolve("agent_config_loader")) if restricted_tools else resolve("agent_config_loader")
    )
    use_case = InstantiateAgentUseCase(
        config_loader=config_loader,
        repository=chain["agent_repository"],
        event_publisher=InMemoryEventBus(),
        isolation_service=chain["isolation_service"],
    )
    result = _run_async(ctx["_loop"], use_case.execute(role=AgentRole.CEO))
    agent_id: uuid.UUID = result.agent_id
    ctx["_agent_ids"].append(agent_id)
    return agent_id


def _make_registry() -> Any:
    """手工组装工具注册服务（InMemoryToolRepository + register_all——5-3 同款）。"""
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    return registry


def _build_tool_execution_service(fake_llm: Any) -> Any:
    """真实工具执行装饰链（Fake LLM 注入——5-3 集成/验收同款）。

    sandbox 替身纪律：AsyncMock(spec=SandboxExecutor) + execute_code 显式
    return_value 真实 dict 形态——裸 AsyncMock 的 return_value 与子属性均
    AsyncMock 化，被测代码同步调用 result.get("output") 时返回协程无人
    await（RuntimeWarning 泄漏）且 str(协程) 垃圾文本混入工具输出注入面。
    """
    from unittest.mock import AsyncMock

    from src.application.services.retry_helpers import RetryPolicy
    from src.application.services.tool_execution_engine import ToolExecutionEngine
    from src.application.services.tool_execution_service import ToolExecutionService
    from src.domain.ports.sandbox_executor import SandboxExecutor

    sandbox = AsyncMock(spec=SandboxExecutor)
    sandbox.execute_code.return_value = {"status": "ok", "output": '{"valid": true}', "error": None}
    engine = ToolExecutionEngine(
        llm_client=fake_llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0.01),
    )
    return ToolExecutionService(registry=_make_registry(), engine=engine)


def _assemble_blm_chain(ctx: dict[str, Any], **fake_kwargs: Any) -> None:
    """BLM 全链手工装配（真实服务 + Fake LLM 唯一豁免）。

    装配面：真实 guard 链 + 真实 CEO 实例化 + 真实档案加载 + 真实工具链/注册表 +
    真实 hybrid 检索（R 门控）+ 真实快照存储（RedisSnapshotStore）+ Fake LLM +
    BlmPlanningService + LangGraphEngine（blm_planning_service 注入）+
    RunBlmPlanningUseCase。
    """
    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult, LoadAgentProfileUseCase
    from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

    loop = ctx["_loop"]
    restricted = fake_kwargs.pop("restricted_tools", False)

    # 1) 真实 guard 链 + CEO 实例化 + 档案加载
    if restricted:
        _make_restricted_guard_chain(ctx)
    else:
        _make_real_guard_chain(ctx)
    agent_id = _instantiate_real_agent(ctx, restricted_tools=restricted)
    profile_loader = resolve("agent_profile_loader")
    profile = _run_async(loop, profile_loader.load(role=AgentRole.CEO, agent_id=agent_id))
    skill_selector = resolve("skill_selector")
    tools_l1 = _run_async(loop, skill_selector.list_active_skills())
    profile_result = AgentProfileLoadResult(
        agent_id=agent_id,
        role=AgentRole.CEO,
        profile=profile,
        tools_l1=tools_l1,
        startup_context_tokens=0,
    )
    if restricted:
        # 受限白名单：档案面 tools_l1 收窄（system 面注入受限——449 真实锚构造）
        profile_result = AgentProfileLoadResult(
            agent_id=agent_id,
            role=AgentRole.CEO,
            profile=profile,
            tools_l1=tuple(t for t in tools_l1 if t.slug == "pestel-analysis"),
            startup_context_tokens=0,
        )
    ctx["agent_id"] = agent_id
    ctx["profile_result"] = profile_result

    # 2) Fake LLM + 真实工具链
    fake_llm = _make_fake_llm(**fake_kwargs)
    ctx["fake_llm"] = fake_llm
    tool_execution_service = _build_tool_execution_service(fake_llm)

    # 3) BlmPlanningService（真实检索 + 真实快照存储 + 记录总线）
    hybrid = _make_real_hybrid_search(ctx)
    snapshot_store = RedisSnapshotStore(adapter=RedisAdapter(redis_client=ctx["_redis_client"]))
    recorder = _RecordingEventBus()
    ctx["recorder"] = recorder
    service = BlmPlanningService(
        llm_client=fake_llm,
        tool_execution_service=tool_execution_service,
        tool_registry_service=_make_registry(),
        isolation_guard=ctx["isolation_guard_chain"]["guard"],
        hybrid_search=hybrid,
        search_collection=ctx["retrieval_collection"],
        event_publisher=recorder,
        snapshot_repository=snapshot_store,
    )
    ctx["blm_service"] = service

    # 4) 图引擎 + 用例
    ctx["engine"] = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=recorder,
        blm_planning_service=service,
    )
    profile_use_case = LoadAgentProfileUseCase(
        profile_loader=resolve("agent_profile_loader"),
        repository=ctx["isolation_guard_chain"]["agent_repository"],
        skill_selector=resolve("skill_selector"),
        event_publisher=InMemoryEventBus(),
    )
    ctx["use_case"] = RunBlmPlanningUseCase(
        agent_repository=ctx["isolation_guard_chain"]["agent_repository"],
        agent_profile_use_case=profile_use_case,
        agent_engine=ctx["engine"],
        blm_planning_service=service,
        isolation_guard=ctx["isolation_guard_chain"]["guard"],
        event_publisher=recorder,
    )
    ctx["profile_use_case"] = profile_use_case
    ctx["task"] = "制定新能源汽车行业五年战略规划"


def _run_planning(ctx: dict[str, Any], **execute_kwargs: Any) -> Any:
    """执行 BLM 规划（默认 task 经 ctx 注入；plan_id 缺省新铸）。"""
    kwargs = {"agent_id": ctx["agent_id"], "task": ctx["task"]}
    kwargs.update(execute_kwargs)
    return _run_async(ctx["_loop"], ctx["use_case"].execute(**kwargs))


def _release_holds(ctx: dict[str, Any]) -> None:
    """释放 Fake LLM 挂起（挂起场景收尾防悬挂）。"""
    fake = ctx.get("fake_llm")
    state = getattr(fake, "_blm_state", None)
    if state is not None:
        state["hold_event"].set()


# ===================================================================
# Background Steps
# ===================================================================


@given("Redis 服务可用")
def redis_service_available(context: dict[str, Any]) -> None:
    """验证 Redis 服务可用（场景级客户端 ping——不可达 skip）。"""
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
    except Exception as exc:
        pytest.skip(f"Redis 不可用: {exc}")


@given("检索服务可用且语料已索引")
def retrieval_service_available(context: dict[str, Any]) -> None:
    """检索门控（embedding+Qdrant 双探测 + 租户隔离 collection 语料 upsert）。"""
    _ensure_qdrant_retrieval(context)


# ===================================================================
# AC-1: BLM 前两阶段流程执行
# ===================================================================


@scenario("test_acceptance_blm_planning.feature", "BLM 前两阶段完整流程执行")
def test_blm_full_flow_execution() -> None:
    """AC-1.1 完整流程（阶段 1 四字段 + 六子步骤 + 综合 + DTO）。"""
    pass


@given("CEO Agent 已实例化且档案已加载")
def ceo_agent_instantiated_and_profile_loaded(context: dict[str, Any]) -> None:
    """真实 CEO Agent 实例化 + 档案加载 + BLM 全链装配。"""
    _assemble_blm_chain(context)


@when("启动 BLM 规划")
def start_blm_planning(context: dict[str, Any]) -> None:
    """执行 RunBlmPlanningUseCase（全链真实 + Fake LLM）。"""
    context["result"] = _run_planning(context)


@then("阶段 1 业绩差距分析产出四字段产物")
def stage1_gap_artifacts_four_fields(context: dict[str, Any]) -> None:
    """阶段 1 产物含 financial_gap/operational_gap/root_causes/portfolio_health。"""
    result = context["result"]
    gap = result.gap_artifacts
    assert gap.financial_gap, "financial_gap 产物非空"
    assert gap.operational_gap, "operational_gap 产物非空"
    assert gap.root_causes, "root_causes 产物非空"
    assert gap.portfolio_health, "portfolio_health 产物非空"
    assert gap.degraded is False, "正常路径阶段 1 不降级"


@then("市场洞察六子步骤依次执行")
def market_insight_six_steps_executed(context: dict[str, Any]) -> None:
    """六子步骤产物恒满 6 元素（降级步=完整信封）。"""
    steps = context["result"].insight_steps
    assert len(steps) == 6, f"六子步骤恒满 6 元素，实际 {len(steps)}"
    for step_result in steps:
        assert step_result.summary, f"{step_result.step} summary 非空"


@then("综合洞察报告已生成")
def synthesis_generated(context: dict[str, Any]) -> None:
    """synthesize_insights 综合结论生成（聚合结构化结论）。"""
    synthesis = context["result"].synthesis
    assert synthesis.conclusions, "综合结论非空"


@then("结果 DTO 返回阶段 1 与阶段 2 全部产物")
def result_dto_contains_all_artifacts(context: dict[str, Any]) -> None:
    """结果 DTO 含 gap_artifacts + insight_steps(6) + synthesis + plan_id/agent_id。"""
    result = context["result"]
    assert result.gap_artifacts is not None
    assert len(result.insight_steps) == 6
    assert result.synthesis is not None
    assert result.plan_id
    assert str(result.agent_id) == str(context["agent_id"])
    assert result.execution_ms >= 0


@then("全链在单一 CEO Agent 实例上执行")
def single_agent_execution(context: dict[str, Any]) -> None:
    """agent_id 全程单一（结果 agent_id 与装配锚一致）。"""
    assert str(context["result"].agent_id) == str(context["agent_id"])


@scenario("test_acceptance_blm_planning.feature", "市场洞察六子步骤按序执行")
def test_blm_step_order_dual_anchor() -> None:
    """AC-1.2 顺序断言双锚（枚举序独立构造 + 时间戳非重叠）。"""
    pass


@then("六子步骤顺序与 or.md 钦定顺序一致")
def six_steps_match_ormd_order(context: dict[str, Any]) -> None:
    """锚 1：枚举序独立构造自 or.md（不经被测服务生成期望——循环自证红线）。"""
    actual = tuple(step_result.step for step_result in context["result"].insight_steps)
    assert actual == EXPECTED_INSIGHT_ORDER, f"六子步骤顺序错乱: {actual}"


@then("六子步骤时间戳无重叠")
def six_steps_timestamps_non_overlapping(context: dict[str, Any]) -> None:
    """锚 2：started_at[i] >= completed_at[i-1]（证伪并行——运行期观测值）。"""
    steps = context["result"].insight_steps
    for step_result in steps:
        assert step_result.started_at is not None and step_result.completed_at is not None, (
            f"步骤 {step_result.step} 时间戳缺失（前置检查——None 会以 TypeError 形态掩盖断言）"
        )
    for prev, curr in zip(steps, steps[1:]):
        assert curr.started_at >= prev.completed_at, f"步骤 {curr.step} 与前步 {prev.step} 时间戳重叠（并行执行嫌疑）"


@scenario("test_acceptance_blm_planning.feature", "综合洞察聚合六子步骤产物")
def test_blm_synthesis_injection() -> None:
    """AC-1.3 综合洞察双锚（注入侧 prompt 含六步摘要 + degraded_inputs 空）。"""
    pass


@then("综合提示词包含六子步骤产物摘要")
def synthesis_prompt_contains_six_step_summaries(context: dict[str, Any]) -> None:
    """注入侧锚：synthesis prompt 六步产物摘要**逐一可判别**（R1-7）。

    Fake summary 按步骤 display_name 携带标识（prompt 提取判定——与调用
    计数解耦，失败注入场景不错位）；断言六标识逐一出现（漏传任一步即红）。"""
    from src.application.services.blm_planning_prompts import InsightStepSchema

    calls = context["fake_llm"]._blm_state["calls"]
    synthesis_calls = [c for c in calls if c["schema"].__name__ == "InsightSynthesisSchema"]
    assert synthesis_calls, "未捕获 synthesize_insights 的 LLM 调用"
    prompt = synthesis_calls[-1]["prompt"]
    # 六显示名字面量独立构造（or.md 钦定序——不经被测枚举/Fake 生成期望）
    for display_name in ("看趋势", "看市场与客户", "看竞争", "看自己", "看机会", "机会差距分析"):
        assert f"{_FAKE_STEP_SUMMARY_PREFIX}:{display_name}" in prompt, (
            f"综合 prompt 缺「{display_name}」产物摘要（漏传即红——R1-7）"
        )
    insight_call_count = sum(1 for c in calls if c["schema"] is InsightStepSchema)
    assert insight_call_count == 6, f"六子步骤 LLM 调用计数 {insight_call_count} != 6"


@then("正常路径下降级输入清单为空")
def degraded_inputs_empty_on_normal_path(context: dict[str, Any]) -> None:
    """正常路径 synthesis.degraded_inputs 为空（全部输入未降级）。"""
    assert context["result"].synthesis.degraded_inputs == ()


# ===================================================================
# AC-2: CEO Agent 单角色替代（MVP）
# ===================================================================


@scenario("test_acceptance_blm_planning.feature", "CEO Agent 单角色承担全部阶段")
def test_ceo_single_role_substitution() -> None:
    """AC-2.1 单角色替代（agent_id 单一 + prompt 视角前缀 + 零非 CEO 实例化）。"""
    pass


@then("全程仅使用 CEO Agent 单角色实例")
def single_ceo_role_instance(context: dict[str, Any]) -> None:
    """agent_id 全程单一（同 AC-1 断言面——角色面经 Agent 实体 role=CEO 锚定）。"""
    from src.domain.entities.agent import AgentRole

    chain = context["isolation_guard_chain"]
    agent = _run_async(context["_loop"], chain["agent_repository"].get_by_id(context["agent_id"]))
    assert agent.role is AgentRole.CEO


@then("阶段提示词含角色视角前缀与工具候选白名单")
def prompts_contain_role_prefix_and_tool_whitelist(context: dict[str, Any]) -> None:
    """每步 prompt 含视角前缀句与该步工具候选白名单（语义配置表钦定面）。

    断言锚：六子步骤 prompt 含「以 … 视角」前缀 + 候选工具 slug 至少其一。
    期望表独立构造（or.md 主导角色映射），不经被测服务生成。"""
    from src.application.services.blm_planning_prompts import MARKET_INSIGHT_STEP_CONFIG

    calls = context["fake_llm"]._blm_state["calls"]
    step_calls = [c for c in calls if c["schema"].__name__ == "InsightStepSchema"]
    assert len(step_calls) == 6
    for call, (step_key, config) in zip(step_calls, MARKET_INSIGHT_STEP_CONFIG.items()):
        assert "视角" in call["prompt"], f"{step_key} prompt 缺角色视角前缀"
        assert any(slug in call["prompt"] for slug in config.tool_candidates), (
            f"{step_key} prompt 缺工具候选白名单（期望含 {config.tool_candidates} 之一）"
        )


@then("没有新增非 CEO 角色实例化")
def no_non_ceo_role_instantiation() -> None:
    """静态断言：SUPPORTED_ROLES 不扩展（全仓 grep 零新增非 CEO 角色）。"""
    from src.application.use_cases.agent_instantiation import SUPPORTED_ROLES

    assert set(SUPPORTED_ROLES) == {__import__("src.domain.entities.agent", fromlist=["AgentRole"]).AgentRole.CEO}, (
        f"SUPPORTED_ROLES 被扩展: {SUPPORTED_ROLES}（AC-2 红线——MVP 单 CEO 角色）"
    )


@scenario("test_acceptance_blm_planning.feature", "BLM 入口守卫链生效")
def test_blm_guard_chain() -> None:
    """AC-2.2 守卫链（443 存在 → 441 角色 → 447 隔离 fail-closed）。"""
    pass


@given("存在不满足守卫条件的 Agent 入口")
def invalid_agent_entrypoints(context: dict[str, Any]) -> None:
    """构造三类守卫触发入口（不存在 id / 非 CEO 角色 / 未初始化隔离状态）。"""
    _assemble_blm_chain(context)  # 正常链装配（守卫链复用其仓储与 guard）
    context["guard_cases"] = [
        {"name": "existence_443", "agent_id": uuid.uuid4()},  # 不存在 Agent
        {"name": "role_441", "agent_id": uuid.uuid4()},
        {"name": "isolation_447", "agent_id": uuid.uuid4()},
    ]


@then("存在性守卫与角色守卫与隔离守卫依次生效")
def guard_chain_triggers_in_order(context: dict[str, Any]) -> None:
    """三类守卫异常按序触发（443 → 441 → 447——5.3 守卫链复用）。"""
    from src.domain.exceptions.agent_exceptions import (
        AgentNotFoundError,
        AgentRoleNotSupportedError,
        IsolationStateNotInitializedError,
    )

    loop = context["_loop"]
    use_case = context["use_case"]

    # 443：不存在 Agent
    try:
        _run_async(loop, use_case.execute(agent_id=uuid.uuid4(), task="t"))
        pytest.fail("存在性守卫未触发（443）")
    except AgentNotFoundError:
        pass

    # 441：非 CEO 角色（直接落一个 CTO Agent 实体——绕过实例化守卫构造守卫触发面）
    from src.domain.entities.agent import Agent, AgentRole

    chain = context["isolation_guard_chain"]
    cto_agent = Agent(agent_id=context["guard_cases"][1]["agent_id"], role=AgentRole.CTO, name="cto-guard-probe")
    _run_async(loop, chain["agent_repository"].save(cto_agent, ttl=3600))
    context["_agent_ids"].append(cto_agent.agent_id)
    try:
        _run_async(loop, use_case.execute(agent_id=cto_agent.agent_id, task="t"))
        pytest.fail("角色守卫未触发（441）")
    except AgentRoleNotSupportedError:
        pass

    # 447：未初始化隔离状态（真实 CEO 实例化正常初始化隔离——绕开经裸实体构造）
    bare_agent = Agent(agent_id=context["guard_cases"][2]["agent_id"], role=AgentRole.CEO, name="bare-guard-probe")
    _run_async(loop, chain["agent_repository"].save(bare_agent, ttl=3600))
    context["_agent_ids"].append(bare_agent.agent_id)
    try:
        _run_async(loop, use_case.execute(agent_id=bare_agent.agent_id, task="t"))
        pytest.fail("隔离守卫未触发（447）")
    except IsolationStateNotInitializedError:
        pass


# ===================================================================
# AC-3: 流程可视化数据面
# ===================================================================


@scenario("test_acceptance_blm_planning.feature", "执行中状态可查询")
def test_status_queryable_during_execution() -> None:
    """AC-3.1 执行中状态（门控构造：挂起第 2 步 + 后台执行 + 轮询快照）。"""
    pass


@given("Fake LLM 在第 2 步挂起")
def fake_llm_holds_at_second_call(context: dict[str, Any]) -> None:
    """装配挂起链（hold_at_call=2——序 2 为 market_customer 首调（正常序 pg=0/trend=1），挂起时前两步已完成）。

    挂起步骤须 >= 第 2 步：首步完成前无快照可轮询（use case 轮询会 480）。"""
    _assemble_blm_chain(context, hold_at_call=2)


@when("后台启动 BLM 规划并轮询状态快照")
def background_planning_and_poll_status(context: dict[str, Any]) -> None:
    """asyncio.create_task 后台执行 + 主协程窗口内真实读快照（R1-6——集成②先例形态）。"""
    from src.application.use_cases.get_blm_planning_status import GetBlmPlanningStatusUseCase
    from src.domain.exceptions.planning_exceptions import PlanningNotFoundError

    loop = context["_loop"]

    async def _poll_during_execution() -> None:
        task = asyncio.create_task(context["use_case"].execute(agent_id=context["agent_id"], task=context["task"]))
        try:
            status_use_case = GetBlmPlanningStatusUseCase(
                snapshot_repository=context["blm_service"].snapshot_repository,
            )
            mid_status = None
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                if task.done():
                    break  # 挂起构造失效防死循环（集成②先例）
                plan_ids = list(context["blm_service"].active_plan_ids)
                if plan_ids:
                    try:
                        status = await status_use_case.execute(plan_id=plan_ids[0])
                    except PlanningNotFoundError:
                        await asyncio.sleep(0.01)  # 首步快照未落盘的 480 窗口容错
                        continue
                    if 0 < status.completed_steps < 8:
                        mid_status = status  # 挂起窗口内真实读到执行中快照
                        break
                await asyncio.sleep(0.01)
            assert not task.done(), "挂起构造失效（流程提前完成——门控红）"
            assert mid_status is not None, "挂起窗口内未轮询到执行中快照（轮询空转退化——R1-6）"
            context["mid_status"] = mid_status
            _release_holds(context)
            result = await task
            context["polled_result"] = result
            context["final_status"] = await status_use_case.execute(plan_id=result.plan_id)
        finally:
            if not task.done():
                _release_holds(context)
                await task

    _run_async(loop, _poll_during_execution())


@then("执行中状态含当前阶段与子步骤与进度百分比")
def mid_execution_status_fields(context: dict[str, Any]) -> None:
    """执行中窗口真实读到的快照断言（R1-6——非终态退化）。

    挂起位=第 2 步（market_customer 首调）→ 窗口内 completed_steps∈[1,8)、
    progress∈(0,100)、current_step=最近完成步（trend）。"""
    mid = context["mid_status"]
    assert mid.phase, "执行中 phase 非空"
    assert 1 <= mid.completed_steps < 8, f"执行中 completed_steps 应 <8（实测 {mid.completed_steps}——终态退化即红）"
    assert 0 < mid.progress_percent < 100, "执行中进度百分比应 <100%"
    assert mid.current_step, "current_step 非空（最近完成步语义）"
    assert mid.total_steps == 8


@scenario("test_acceptance_blm_planning.feature", "执行完成后状态为终态")
def test_final_status_terminal_state() -> None:
    """AC-3.2 终态（total_steps=8 全 completed + 快照读写一致）。"""
    pass


@then("状态为 8 步全部完成的终态")
def terminal_status_all_completed(context: dict[str, Any]) -> None:
    """终态：completed_steps == 8，timeline 全 completed。"""
    from src.application.use_cases.get_blm_planning_status import GetBlmPlanningStatusUseCase

    status_use_case = GetBlmPlanningStatusUseCase(
        snapshot_repository=context["blm_service"].snapshot_repository,
    )
    status = _run_async(context["_loop"], status_use_case.execute(plan_id=context["result"].plan_id))
    assert status.completed_steps == 8, f"终态 completed_steps={status.completed_steps} != 8"
    assert status.total_steps == 8
    assert status.progress_percent == 100.0
    assert all(entry.status == "completed" for entry in status.timeline), "timeline 存在非 completed 条目"
    assert len(status.timeline) == 8


@then("Redis latest 快照读写一致")
def redis_latest_snapshot_roundtrip(context: dict[str, Any]) -> None:
    """写后读回断言（真实 RedisSnapshotStore——hget latest 读回与状态查询一致）。"""
    from src.application.use_cases.get_blm_planning_status import GetBlmPlanningStatusUseCase
    from src.domain.value_objects.blm_phases import BlmPlanningStatus

    status_use_case = GetBlmPlanningStatusUseCase(
        snapshot_repository=context["blm_service"].snapshot_repository,
    )
    status = _run_async(context["_loop"], status_use_case.execute(plan_id=context["result"].plan_id))
    assert isinstance(status, BlmPlanningStatus)
    # 二次读回一致（latest 覆盖写语义——同 plan_id 两次读取结果一致）
    status_again = _run_async(context["_loop"], status_use_case.execute(plan_id=context["result"].plan_id))
    assert status_again.completed_steps == status.completed_steps
    assert status_again.plan_id == status.plan_id


# ===================================================================
# AC-4: 领域事件发布（通道登记与投递）
# ===================================================================


@scenario("test_acceptance_blm_planning.feature", "领域事件按通道发布")
def test_domain_events_published() -> None:
    """AC-4.1 事件发布（PlanningStarted 1 + BlmStageCompleted 8 全集）。"""
    pass


@given("事件通道已双登记")
def event_channels_dual_registered() -> None:
    """守护断言：event_channels.yaml + ChannelRouter.DEFAULT_MAPPINGS 双登记。"""
    import yaml

    from src.infrastructure.messaging.channel_router import ChannelRouter

    names = ("PlanningStarted", "BlmStageCompleted")
    channels = yaml.safe_load((REPO_ROOT / "configs" / "event_channels.yaml").read_text(encoding="utf-8"))["event_channels"]
    for name in names:
        assert name in channels, f"{name} 未登记 event_channels.yaml"
        assert name in ChannelRouter.DEFAULT_MAPPINGS, f"{name} 未登记 DEFAULT_MAPPINGS"
        assert channels[name]["delivery_mode"] == "reliable", f"{name} 应钦定 reliable"
        assert ChannelRouter.DEFAULT_MAPPINGS[name].delivery_mode.value == "reliable"


@then("规划启动事件恰发布一次")
def planning_started_published_once(context: dict[str, Any]) -> None:
    """PlanningStarted 恰一次（use case 三守卫通过后、submit_graph 前发布）。"""
    events = [e for e in context["recorder"].published_events if type(e).__name__ == "PlanningStarted"]
    assert len(events) == 1, f"PlanningStarted 发布 {len(events)} 次 != 1"


@then("八个阶段完成事件各恰发布一次")
def eight_stage_completed_events(context: dict[str, Any]) -> None:
    """BlmStageCompleted 8 个 stage 值全集各恰一次（独立构造期望）。"""
    expected_stages = (
        {"performance_gap"} | {f"market_insight_{s}" for s in EXPECTED_INSIGHT_ORDER} | {"market_insight_synthesis"}
    )
    events = [e for e in context["recorder"].published_events if type(e).__name__ == "BlmStageCompleted"]
    actual_counts: dict[str, int] = {}
    for event in events:
        actual_counts[event.stage] = actual_counts.get(event.stage, 0) + 1
    assert set(actual_counts) == expected_stages, (
        f"stage 全集不一致: 缺 {expected_stages - set(actual_counts)} 多 {set(actual_counts) - expected_stages}"
    )
    assert all(count == 1 for count in actual_counts.values()), f"存在重复发布: {actual_counts}"
    assert len(events) == 8


@then("CheckpointReached 事件未发布")
def checkpoint_reached_not_published(context: dict[str, Any]) -> None:
    """负向断言：CheckpointReached 不发布（6.3 语义分立）。"""
    checkpoint_events = [e for e in context["recorder"].published_events if type(e).__name__ == "CheckpointReached"]
    assert checkpoint_events == [], f"CheckpointReached 不应发布（6.3 语义分立）: {checkpoint_events}"


@scenario("test_acceptance_blm_planning.feature", "事件经 outbox 落行")
def test_events_outbox_persisted() -> None:
    """AC-4.2 outbox 落行（真实发布链路 + PG 双预检门控）。"""
    pass


@given("PostgreSQL 事件外发表可用")
def postgres_outbox_available(context: dict[str, Any]) -> None:
    """PG 门控双预检（连接 + event_outbox 表存在——5-4 R1-F07 先例）。"""
    import sqlalchemy as sa

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    env = context["_env_config"]

    async def _probe() -> Any:
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
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT event_id FROM event_outbox LIMIT 1"))
        await engine.dispose()
        return manager

    try:
        context["_pg_manager"] = _run_async(context["_loop"], _probe())
    except Exception as exc:
        pytest.skip(f"PostgreSQL 不可达或 event_outbox 表未初始化: {exc}")


@when("启动 BLM 规划并经真实发布链路投递")
def planning_with_real_publish_chain(context: dict[str, Any]) -> None:
    """真实 event_publisher 装配执行（SINGLETON 跨 loop 防线——clear_singleton）。"""
    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
    from src.domain.ports.resolver import get_resolver, resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig

    _assemble_blm_chain(context)
    # 覆写：记录总线 → 真实 publisher（clear_singleton 防跨 loop 死连接——5-3 场景⑤先例）
    get_resolver().clear_singleton()
    real_publisher = resolve("event_publisher")
    service = BlmPlanningService(
        llm_client=context["fake_llm"],
        tool_execution_service=context["blm_service"].tool_execution_service,
        tool_registry_service=context["blm_service"].tool_registry_service,
        isolation_guard=context["isolation_guard_chain"]["guard"],
        hybrid_search=context["blm_service"].hybrid_search,
        search_collection=context["retrieval_collection"],
        event_publisher=real_publisher,
        snapshot_repository=context["blm_service"].snapshot_repository,
    )
    engine = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=real_publisher,
        blm_planning_service=service,
    )
    context["use_case"] = RunBlmPlanningUseCase(
        agent_repository=context["isolation_guard_chain"]["agent_repository"],
        agent_profile_use_case=context["profile_use_case"],
        agent_engine=engine,
        blm_planning_service=service,
        isolation_guard=context["isolation_guard_chain"]["guard"],
        event_publisher=real_publisher,
    )
    context["result"] = _run_planning(context)
    # 登记 event_id 供 teardown 精确清理（_collect 返回 event_id 列表）
    context["_outbox_event_ids"].extend(str(e) for e in _collect_published_events(context))


def _collect_published_events(ctx: dict[str, Any]) -> list[Any]:
    """经 outbox 反查本 run 事件行（真实发布下 event_id 无内存锚——按聚合查询）。"""
    import sqlalchemy as sa

    async def _query() -> list[Any]:
        engine = ctx["_pg_manager"].get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT event_id FROM event_outbox "
                        "WHERE event_type IN ('PlanningStarted', 'BlmStageCompleted') "
                        "AND payload->>'aggregate_id' = :agent_id "
                        "AND created_at >= NOW() - INTERVAL '5 minutes'"
                    ),
                    {"agent_id": str(ctx["agent_id"])},
                )
            ).fetchall()
        await engine.dispose()
        return [row[0] for row in rows]

    return list(_run_async(ctx["_loop"], _query()))


@then("事件外发表含规划启动事件与八个阶段完成事件")
def outbox_contains_full_event_set(context: dict[str, Any]) -> None:
    """outbox 全集断言：PlanningStarted 恰一行 + BlmStageCompleted 8 stage 恰一次。"""
    import sqlalchemy as sa

    async def _query() -> dict[tuple[str, str | None], int]:
        engine = context["_pg_manager"].get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT event_type, payload->'payload'->>'stage' AS stage, COUNT(*) "
                        "FROM event_outbox "
                        "WHERE event_type IN ('PlanningStarted', 'BlmStageCompleted') "
                        "AND payload->>'aggregate_id' = :agent_id "
                        "AND created_at >= NOW() - INTERVAL '5 minutes' "
                        "GROUP BY event_type, stage"
                    ),
                    {"agent_id": str(context["agent_id"])},
                )
            ).fetchall()
        await engine.dispose()
        return {(r[0], r[1]): r[2] for r in rows}

    counts = _run_async(context["_loop"], _query())
    planning = counts.get(("PlanningStarted", None), 0)
    assert planning == 1, f"outbox PlanningStarted {planning} 行 != 1"
    expected_stages = (
        {"performance_gap"} | {f"market_insight_{s}" for s in EXPECTED_INSIGHT_ORDER} | {"market_insight_synthesis"}
    )
    actual_stages = {stage for (etype, stage), _ in counts.items() if etype == "BlmStageCompleted"}
    assert actual_stages == expected_stages, f"stage 全集不一致: {actual_stages ^ expected_stages}"
    assert all(count == 1 for (etype, _), count in counts.items() if etype == "BlmStageCompleted"), "存在重复落行"


# ===================================================================
# AC-5: 性能与成功率
# ===================================================================


@scenario("test_acceptance_blm_planning.feature", "Fake LLM 口径性能与成功率")
def test_fake_llm_performance_and_success_rate() -> None:
    """AC-5 性能（P95<30s Fake 口径 + 受控注入采样≥95% + 配置传递）。"""
    pass


@when("执行 BLM 前两阶段完整流程并计量")
def execute_and_measure(context: dict[str, Any]) -> None:
    """性能计量（Fake LLM 管线自身开销口径——真实 LLM 延迟显式出栈）。

    口径差声明：P95 以 Fake LLM 管线开销计量（DC-7——真实 LLM 全链计时归
    部署验证）；受控失败注入采样 ≥20 次（零注入恒 100% 零鉴别力——R1-11 裁定）。"""
    context["result"] = _run_planning(context)
    # 标准链（无注入）调用面——温度/超时断言锚（与采样注入解耦防序偏移）
    context["base_calls"] = list(context["fake_llm"]._blm_state["calls"])
    durations: list[float] = []
    success_count = 0
    total_insight_steps = 0
    degraded_per_round: list[int] = []
    for i in range(20):
        # 六子步骤内单步双杀注入（首调+重试皆败→真降级）
        _assemble_blm_chain(context, fail_call_indices=frozenset({1 + (i % 6), 2 + (i % 6)}))
        start = time.monotonic()
        result = _run_planning(context)
        durations.append(time.monotonic() - start)
        # 成功口径（epics L2061——AC-5 统一钦定「降级信封完整即计入成功」）：
        # 各步按信封完整性逐位判定（summary 非空，或 degraded 且 degrade_reason
        # 非空——完整降级信封），非无条件计入；鉴别力三面（R1-8）：
        # 重试机制删除→每轮降级 2 断言红 / 降级标记丢失→0 红 / 降级捕获删除
        # →异常穿透 execute 抛 481 该轮炸
        assert len(result.insight_steps) == 6, "恒满 6 元素（降级步=完整信封）"
        round_degraded = sum(1 for s in result.insight_steps if s.degraded)
        assert round_degraded == 1, f"第 {i} 轮双杀注入应恰 1 步真降级（实测 {round_degraded}——重试/降级机制异常）"
        degraded_per_round.append(round_degraded)
        for s in result.insight_steps:
            envelope_complete = bool(s.summary) or (s.degraded and bool(s.degrade_reason))
            assert envelope_complete, f"步骤 {s.step} 信封不完整（summary 与降级原因均空）"
            if envelope_complete:
                success_count += 1
        total_insight_steps += 6
        # P95 口径含降级轮（降级流程完成耗时真实计入）
    context["perf_durations"] = durations
    context["perf_success_count"] = success_count
    context["perf_total_steps"] = total_insight_steps


@then("全流程延迟 P95 小于 30 秒")
def p95_latency_under_30s(context: dict[str, Any]) -> None:
    """P95<30s 分级断言（4-6/4-7 基准先例形态——Fake LLM 口径）。"""
    durations = sorted(context["perf_durations"])
    assert durations, "无采样"
    p95_index = max(0, int(len(durations) * 0.95) - 1)
    p95 = durations[p95_index]
    assert p95 < 30.0, f"Fake LLM 口径 P95={p95:.2f}s >= 30s"


@then("受控失败注入下六子步骤成功率不低于 95 百分比")
def success_rate_at_least_95_percent(context: dict[str, Any]) -> None:
    """六子步骤成功率 ≥95%（降级成功计入——受控注入采样口径）。"""
    rate = context["perf_success_count"] / context["perf_total_steps"] * 100
    assert rate >= 95.0, f"六子步骤成功率 {rate:.1f}% < 95%"
    # 受控注入下的期望：单步注入→该步降级（成功计入）→每轮 6/6 成功（降级成功口径）
    # 若降级未被捕获（异常穿透）则该轮流程失败——成功率显著跌落，断言鉴别力成立


@then("单调用超时与温度按语义配置表传递")
def timeout_and_temperature_passed(context: dict[str, Any]) -> None:
    """配置传递断言：timeout==8.0 且温度==语义配置表钦定档（8 步逐一）。"""
    from src.application.services.blm_planning_prompts import BLM_TEMPERATURE_PROFILE

    calls = context["base_calls"]
    assert len(calls) == 8, f"标准链 8 步调用计数 {len(calls)} != 8"
    for call in calls:
        assert call["timeout"] == 8.0, f"调用 {call['call_index']} timeout={call['timeout']} != 8.0"
    expected_temps = tuple(BLM_TEMPERATURE_PROFILE.values())
    actual_temps = tuple(call["temperature"] for call in calls)
    assert actual_temps == expected_temps, f"温度档与语义配置表不一致: actual={actual_temps} expected={expected_temps}"


# ===================================================================
# AC-6: 异常与步级降级
# ===================================================================


@scenario("test_acceptance_blm_planning.feature", "步级降级继续推进")
def test_step_level_degradation() -> None:
    """AC-6.1 步级降级（单步 LLM 失败→降级续行+下游标注）。"""
    pass


@given("Fake LLM 对指定子步骤注入失败")
def fake_llm_fails_on_specific_step(context: dict[str, Any]) -> None:
    """单步失败注入（TREND 子步骤——调用序 1：performance_gap 后第一步）。"""
    _assemble_blm_chain(context, fail_call_indices=frozenset({1, 2}))
    context["injected_step"] = "trend"


@then("流程完成且降级步骤清单恰含该步")
def flow_completes_with_single_degraded_step(context: dict[str, Any]) -> None:
    """流程完成 + degraded_steps 恰含注入步（单元素）。"""
    result = context["result"]
    assert result.degraded_steps == (context["injected_step"],), (
        f"degraded_steps={result.degraded_steps} 应恰含 [{context['injected_step']}]"
    )
    injected = next(s for s in result.insight_steps if s.step == context["injected_step"])
    assert injected.degraded is True
    assert injected.degrade_reason, "降级步骤须记录失败原因"


@then("下游产物含降级标注")
def downstream_contains_degradation_marker(context: dict[str, Any]) -> None:
    """⑥ 规则：下游 prompt 或 synthesis 含降级步骤标注（不可无标注吞并）。"""
    synthesis = context["result"].synthesis
    assert context["injected_step"] in synthesis.degraded_inputs, (
        f"synthesis.degraded_inputs={synthesis.degraded_inputs} 未列举降级输入"
    )
    # 下游 prompt 标注：注入步之后的首个 LLM 调用 prompt 含降级标记
    calls = context["fake_llm"]._blm_state["calls"]
    downstream_calls = calls[2:]  # 注入步（序 1）之后的调用
    assert any("降级" in c["prompt"] or context["injected_step"] in c["prompt"] for c in downstream_calls), (
        "下游 prompt 未含降级标注（⑥规则：'[降级]+原因' 显式注入）"
    )


@scenario("test_acceptance_blm_planning.feature", "全降级顶层异常与部分降级成功")
def test_full_vs_partial_degradation() -> None:
    """AC-6.2 全降级 481 + 部分降级 7/8 成功 DTO。"""
    pass


@when("注入不同降级比例并启动 BLM 规划")
def inject_varying_degradation_ratios(context: dict[str, Any]) -> None:
    """双比例执行：8/8 全降级（全部调用注入）→ 481；7/8（仅漏 synthesis）→ 成功。"""
    from src.domain.exceptions.planning_exceptions import PlanningExecutionError

    # 8/8 全降级：全部 16 次调用注入（8 步×首次+重试——序 0-15）
    _assemble_blm_chain(context, fail_call_indices=frozenset(range(16)))
    try:
        result = _run_planning(context)
        pytest.fail(f"全降级应抛 PlanningExecutionError(481)，实际返回 {result!r}")
    except PlanningExecutionError:
        context["full_degradation_raised"] = True

    # 7/8 部分降级：注入序 0-13（漏 synthesis 两调——序 14-15 正常）
    _assemble_blm_chain(context, fail_call_indices=frozenset(range(14)))
    context["result"] = _run_planning(context)


@then("全部 8 步降级时抛出规划执行失败异常")
def full_degradation_raises_481(context: dict[str, Any]) -> None:
    """全降级 → PlanningExecutionError(481)（抛出点=终态组装处）。"""
    assert context.get("full_degradation_raised") is True, "全降级未抛 PlanningExecutionError"
    from src.domain.exceptions.planning_exceptions import PlanningExecutionError

    assert PlanningExecutionError.code == "EXCEPTION_481"


@then("7/8 部分降级时返回成功 DTO 与降级清单")
def partial_degradation_returns_success_dto(context: dict[str, Any]) -> None:
    """部分降级（7/8，含仅 synthesis 未降级）→ 成功 DTO + degraded_steps=7。"""
    result = context["result"]
    assert len(result.degraded_steps) == 7, f"7/8 降级 degraded_steps={len(result.degraded_steps)} != 7"
    assert result.synthesis is not None
    assert result.synthesis.conclusions, "synthesis 未降级（序 7 未注入）——conclusions 非空"
    assert len(result.synthesis.degraded_inputs) == 7, (
        "synthesis 须列举全部降级输入（六子步骤 + performance_gap 阶段 1 源——R1-4 规则 3 跨阶段传导）"
    )
    assert "performance_gap" in result.synthesis.degraded_inputs, "综合报告须携带阶段 1 降级标记（规则 3）"


@scenario("test_acceptance_blm_planning.feature", "隔离预检 449 降级续行")
def test_isolation_preflight_449_degradation() -> None:
    """AC-6.3 449 降级（tools_l1 受限真实 CEO Agent——真实路径锚）。"""
    pass


@given("隔离白名单受限的 CEO Agent 已实例化且档案已加载")
def restricted_ceo_agent_instantiated(context: dict[str, Any]) -> None:
    """受限白名单链装配（tools_l1 收窄至 pestel-analysis——449 真实锚）。"""
    _assemble_blm_chain(context, restricted_tools=True)
    # 受限面：白名单仅「PESTEL 分析」——阶段 1 四候选与五子步骤候选全被拒，
    # MARKET_CUSTOMER 等步骤候选白名单与受限面交集为空 → 预检 449 → 步级降级续行
    context["expected_restricted_steps"] = (
        "performance_gap",
        "market_customer",
        "competition",
        "self",
        "opportunity",
        "opportunity_gap",
    )


@then("受限工具子步骤降级并以直接推理续行")
def restricted_steps_degraded_with_direct_reasoning(context: dict[str, Any]) -> None:
    """受限步骤产物=完整信封（degraded=True+原因），未受限步骤正常产出。"""
    result = context["result"]
    by_step = {s.step: s for s in result.insight_steps}
    for step_key in context["expected_restricted_steps"]:
        if step_key == "performance_gap":
            # 阶段 1 降级经 gap_artifacts 判定（不在 insight_steps 序列）
            assert result.gap_artifacts.degraded is True, "阶段 1 应降级（四候选全被 449 拒）"
            assert "449" in result.gap_artifacts.degrade_reason or "隔离" in result.gap_artifacts.degrade_reason
            continue
        step_result = by_step[step_key]
        assert step_result.degraded is True, f"{step_key} 应降级（449 预检拒绝）"
        assert "449" in step_result.degrade_reason or "隔离" in step_result.degrade_reason, (
            f"{step_key} 降级原因应含 449/隔离语义: {step_result.degrade_reason}"
        )
    assert by_step["trend"].degraded is False, "trend（PESTEL 分析在白名单）不应降级"


@then("流程完成且降级步骤清单恰含受限步")
def degraded_steps_exactly_restricted(context: dict[str, Any]) -> None:
    """degraded_steps 恰含全部受限步（5 步——449 步级捕获+直接推理续行语义）。"""
    result = context["result"]
    assert tuple(sorted(result.degraded_steps)) == tuple(sorted(context["expected_restricted_steps"])), (
        f"degraded_steps={result.degraded_steps} 应恰含受限 5 步"
    )
    assert len(result.insight_steps) == 6, "流程完成（insight_steps 恒满 6）"


# ===================================================================
# 收尾: 开发完成清单
# ===================================================================


@scenario("test_acceptance_blm_planning.feature", "开发完成清单收尾")
def test_development_completion_checklist() -> None:
    """收尾：src 交付清单 + 四测试目录完成清单逐项确认。"""
    pass


@given("扫描源码交付清单与测试目录")
def scan_delivery_checklist() -> None:
    """静态扫描（零服务依赖——src/交付件与 tests/ 四目录文件存在性）。"""
    pass


@then("BLM 规划交付件全部就位")
def src_delivery_files_present() -> None:
    """src 交付清单（★新建文件全部在位）。"""
    expected = [
        "src/domain/value_objects/blm_phases.py",
        "src/domain/events/planning_events.py",
        "src/domain/exceptions/planning_exceptions.py",
        "src/application/ports/blm_planning.py",
        "src/application/use_cases/run_blm_planning.py",
        "src/application/use_cases/get_blm_planning_status.py",
        "src/application/services/blm_planning_service.py",
        "src/application/services/blm_planning_prompts.py",
        "src/infrastructure/agent_orch/graphs/sp_blm_graph.py",
    ]
    missing = [str(p) for p in expected if not (REPO_ROOT / p).is_file()]
    assert not missing, f"src 交付件缺失: {missing}"


@then("四测试目录完成清单全部就位")
def delivery_files_in_four_test_dirs_present() -> None:
    """四测试目录交付清单（unit/integration/acceptance/contracts 全部在位）。"""
    expected = [
        "tests/unit/domain/test_blm_domain_models.py",
        "tests/unit/domain/exceptions/test_planning_exceptions.py",
        "tests/unit/application/test_blm_planning_service.py",
        "tests/unit/application/test_run_blm_planning.py",
        "tests/unit/architecture/test_blm_planning_arch.py",
        "tests/integration/test_integration_blm_planning.py",
        "tests/contracts/test_port_contract_blm_planning.py",
        "tests/contracts/test_event_channel_mapping_blm_planning.py",
        "tests/acceptance/test_acceptance_blm_planning.feature",
        "tests/acceptance/test_acceptance_blm_planning.py",
    ]
    missing = [str(p) for p in expected if not (REPO_ROOT / p).is_file()]
    assert not missing, f"测试交付件缺失: {missing}"
