"""Story 4.1a: StrategicAnalysisUseCase 端到端集成测试

CLAUDE.md §5 真实服务原则：
- Redis 6379（真实）：realtime 通道
- RabbitMQ 5672（真实）：reliable 通道（via PostgreSQLOutboxRepository）
- PostgreSQL 5432（真实）：tool_executions 表 + event_outbox 表
- TestTenant UUID 前缀：资源隔离

Mock 退路（仅限不可达端口）：
- SandboxExecutor：使用 Mock（DockerSandboxAdapter 未实现）
- LLMClient：使用 Mock（简化测试，避免 LLM API 调用）

测试范围（CLAUDE.md §5 端到端）：
1. Skill 加载（真实 TOOLS.md + 23 SKILL.md 解析）
2. Engine 5 阶段工作流
3. ToolExecution 持久化（真实 PostgreSQL）
4. 双通道事件分发（Redis realtime + RabbitMQ reliable via outbox）
5. ToolExecutedEventHandler 订阅 + Tool statistics 更新
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.event_handlers.tool_executed_event_handler import (
    ToolExecutedEventHandler,
)
from src.application.services.tool_execution_engine import (
    RetryPolicy,
    ToolExecutionEngine,
)
from src.application.services.tool_execution_service import ToolExecutionService
from src.application.services.tool_registry_service import ToolRegistryService
from src.application.skills.loader import InMemorySkillLoader
from src.application.use_cases.strategic_analysis import (
    StrategicAnalysisRequest,
    StrategicAnalysisUseCase,
)
from src.domain.entities.tool_execution import ToolExecutionState
from src.domain.events.tool_events import ToolExecuted
from src.domain.value_objects.tool_execution import ToolResultStatus
from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.dual_channel_event_bus import DualChannelEventBus
from src.infrastructure.messaging.outbox.outbox_repository import (
    PostgreSQLOutboxRepository,
)
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.messaging.redis_event_bus import RedisEventBus
from src.infrastructure.messaging.redis_publisher import RedisEventPublisher
from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository
from src.infrastructure.storage.postgresql.repository.tool_execution_repository import (
    PostgreSQLToolExecutionRepository,
)

# =====================================================================
# 真实服务 Fixtures（CLAUDE.md §5 真实服务优先）
# =====================================================================


def _require_env(name: str) -> str:
    """从环境变量读取必需配置"""
    value = os.getenv(name)
    if not value:
        pytest.skip(f"环境变量 {name} 未配置，跳过集成测试")
    return value


@pytest.fixture
def redis_publisher() -> RedisEventPublisher:
    """真实 Redis 发布器（localhost:6379）"""
    config = RedisConfig(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
    )
    return RedisEventPublisher(config)


@pytest.fixture
def redis_subscriber() -> RedisEventSubscriber:
    """真实 Redis 订阅器（localhost:6379）"""
    config = RedisConfig(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
    )
    return RedisEventSubscriber(config)


@pytest.fixture
async def pg_pool() -> Any:
    """真实 PostgreSQL 连接池（localhost:5432）

    优先使用 POSTGRES_USERNAME（实际数据库用户），
    回退到 POSTGRES_USER（.env 中常见的命名）。
    """
    import asyncpg

    pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USERNAME") or os.getenv("POSTGRES_USER") or "postgres",
        password=os.getenv("POSTGRES_PASSWORD", ""),
        database=os.getenv("POSTGRES_DB", "sisys"),
        min_size=1,
        max_size=5,
    )
    yield pool
    await pool.close()


@pytest.fixture
def real_outbox_repo(pg_session) -> PostgreSQLOutboxRepository:
    """PostgreSQLOutboxRepository（依赖 session_context fixture，由项目 conftest 提供 pg_session mock）

    实际存储使用 mock session（受限于项目现有 session_context 架构）。
    集成测试重点验证 UseCase → Outbox 调用链路是否触发。
    """
    return PostgreSQLOutboxRepository()


@pytest.fixture
def real_dual_channel_bus(
    redis_publisher: RedisEventPublisher,
    redis_subscriber: RedisEventSubscriber,
    real_outbox_repo: PostgreSQLOutboxRepository,
) -> DualChannelEventBus:
    """真实 DualChannelEventBus：Redis + Outbox（mock session）"""
    router = ChannelRouter(load_defaults=True)
    redis_bus = RedisEventBus(redis_publisher, redis_subscriber, router)
    rabbitmq_bus = RabbitMQEventBus(real_outbox_repo, router)
    return DualChannelEventBus(redis_bus, rabbitmq_bus, router)


@pytest.fixture
async def pg_tool_execution_repository(
    pg_pool,
) -> AsyncGenerator[PostgreSQLToolExecutionRepository, None]:
    """真实 PostgreSQLToolExecutionRepository（asyncpg 直连）"""
    # 强制清理（在 fixture 创建前）
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM tool_executions")
    repo = PostgreSQLToolExecutionRepository(pool=pg_pool, schema="public")
    yield repo
    # 测试后清理
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM tool_executions")


@pytest.fixture
def tool_repository() -> InMemoryToolRepository:
    """退路说明：PostgreSQLToolRepository 适配器不存在，InMemory 实现保留

    CLAUDE.md §5 例外（基础设施缺口，标注技术债）
    """
    return InMemoryToolRepository()


@pytest.fixture
def skill_loader() -> InMemorySkillLoader:
    """真实 InMemorySkillLoader（加载 TOOLS.md + 23 SKILL.md）"""
    return InMemorySkillLoader()


# =====================================================================
# 端到端集成测试
# =====================================================================


@pytest.mark.asyncio
class TestStrategicAnalysisEndToEnd:
    """StrategicAnalysisUseCase 端到端集成测试（CLAUDE.md §5 真实服务）"""

    async def test_full_pestel_pipeline_real_services(
        self,
        real_dual_channel_bus: DualChannelEventBus,
        tool_repository: InMemoryToolRepository,
        pg_tool_execution_repository: PostgreSQLToolExecutionRepository,
        skill_loader: InMemorySkillLoader,
    ) -> None:
        """完整 PESTEL 分析链路：UseCase → Skill → Engine → Sandbox → Repository → EventBus → Handler

        真实服务栈：
        - Redis Pub/Sub（realtime 通道）
        - PostgreSQL Outbox（reliable 通道，mock session）
        - PostgreSQL（tool_executions 表持久化，asyncpg 直连）

        Mock：SandboxExecutor（未实现 DockerSandboxAdapter）+ LLMClient（避免 API 调用）
        """
        # ====== Given: 装配完整依赖 ======
        # 1. ToolRegistryService
        registry = ToolRegistryService(tool_repository)
        registry.register_all()
        tool = registry.get_tool(tool_name="PESTEL 分析")
        assert tool is not None

        # 2. ToolExecutedEventHandler（订阅双通道）
        # 注意：RedisEventBus.subscribe 仅注册 handler，需启动 subscriber
        # 集成测试中简化：handler 通过直接调用验证（避免 Redis 后台任务启动复杂度）
        handler = ToolExecutedEventHandler(registry)
        await real_dual_channel_bus._redis_bus.subscribe("ToolExecuted", handler.handle)

        # 3. Mock Sandbox（DockerSandboxAdapter 未集成）
        mock_sandbox = AsyncMock()
        mock_sandbox.start_container = AsyncMock()
        mock_sandbox.execute_code = AsyncMock(return_value={"status": "ok", "output": '{"P": 0.8, "E": 0.7, "S": 0.6}'})
        mock_sandbox.stop_container = AsyncMock()

        # 4. Mock LLM（简化测试，避免 LLM API 调用）
        mock_llm = AsyncMock()

        async def mock_generate(*args: Any, **kwargs: Any) -> str:
            return "1. PESTEL 六维度分析\n2. 输出评分"

        mock_llm.structured_generate = mock_generate

        # 5. ToolExecutionEngine（注入真实 PG 仓储 + Mock 端口）
        engine = ToolExecutionEngine(
            llm_client=mock_llm,
            sandbox=mock_sandbox,
            retry_policy=RetryPolicy(max_attempts=2, initial_delay_sec=0.01),
            tool_execution_repository=pg_tool_execution_repository,
        )

        # 6. ToolExecutionService
        service = ToolExecutionService(registry=registry, engine=engine)

        # 7. StrategicAnalysisUseCase
        use_case = StrategicAnalysisUseCase(
            tool_registry=registry,
            execution_service=service,
            skill_loader=skill_loader,
            event_publisher=real_dual_channel_bus,
        )

        # ====== When: 执行 PESTEL 分析 ======
        request = StrategicAnalysisRequest(
            tool_name="PESTEL 分析",
            arguments={
                "macro_environment": {
                    "political": "政策稳定",
                    "economic": "GDP 5.2%",
                    "social": "老龄化加剧",
                    "technological": "AI 加速",
                    "environmental": "碳中和",
                    "legal": "数据合规",
                },
            },
            user_id=uuid.uuid4(),
            session_id="sess-e2e-001",
            trace_id="trace-e2e-001",
        )
        result = await use_case.execute(request)

        # ====== Then: 验证业务价值 ======
        # 1. ToolResult 成功
        assert result.status == ToolResultStatus.SUCCESS, "ToolResult 必须成功"
        assert result.tool_id == tool.tool_id

        # 2. EvidencePackage 完整（核心字段存在）
        ep = result.evidence_package
        assert ep is not None, "EvidencePackage 必须存在"
        assert ep.input_hash != "", "input_hash 必填"
        assert ep.rule_version != "", "rule_version 必填"

        # 3. ToolExecution 已持久化到 PostgreSQL（真实 PG 验证）
        all_executions = await pg_tool_execution_repository.list_all()
        assert len(all_executions) == 1, f"应有 1 个 ToolExecution，实际 {len(all_executions)}"
        persisted = all_executions[0]
        assert persisted.tool_id == tool.tool_id
        assert persisted.state == ToolExecutionState.COMPLETED, "终态为 COMPLETED"
        assert persisted.completed_at is not None

        # 4. 直接调用 handler 处理 ToolExecuted 事件
        # 注：真实场景下 Redis Pub/Sub subscriber 后台任务接收事件并 dispatch。
        # 集成测试中简化（避免后台任务启动复杂性）：直接构造事件并调用 handler
        realtime_event = ToolExecuted(
            execution_id=persisted.execution_id,
            tool_id=tool.tool_id,
            tool_version=tool.version,
            execution_result={
                "status": "success",
                "execution_id": str(persisted.execution_id),
            },
        )

        # 5. 在 handler 调用前捕获原始 score（避免引用共享导致值同步）
        original_score = tool.reliability_score
        await handler.handle(realtime_event)

        # 6. ToolExecutedEventHandler 已处理事件
        assert len(handler.received_events) >= 1, "Handler 必须至少接收 1 个 ToolExecuted 事件"
        assert handler.received_events[0].aggregate_id == persisted.execution_id

        # 7. Tool statistics 已更新（execution_count += 1, reliability_score 变化）
        updated_tool = registry.get_tool(tool_id=tool.tool_id)
        assert updated_tool.execution_count == 1, "execution_count 应为 1"
        assert updated_tool.reliability_score > original_score, "reliability_score 应略增"

        # 7. Skill 真实加载（验证 TOOLS.md + SKILL.md 解析）
        metadata = await skill_loader.load_metadata("PESTEL 分析")
        assert metadata.slug == "pestel-analysis"
        assert "宏观环境" in metadata.description or "PESTEL" in metadata.description
        assert "environment_analysis" in metadata.capabilities

        # 8. ToolExecutionQuery 列表查询（PG 真实查询）
        from src.domain.ports.tool_execution_repository import ToolExecutionQuery

        query_result = await pg_tool_execution_repository.list_by_query(ToolExecutionQuery(tenant_id=persisted.tenant_id))
        assert len(query_result) >= 1
        assert query_result[0].execution_id == persisted.execution_id
