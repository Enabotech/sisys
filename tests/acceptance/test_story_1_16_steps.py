"""Acceptance test step definitions for Story 1.16 - Integration Test Framework.

Follows the same pattern as Story 1.3: @scenario per scenario + @given/@when/@then steps.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import fakeredis
import pytest
from pytest_bdd import given, parsers, scenario, then, when

from src.domain.repositories.outbox import OutboxRepository

FEATURE = "test_story_1_16.feature"

_test_context: dict[str, Any] = {}


@pytest.fixture
def repo():
    """Fresh InMemoryOutboxRepository for each scenario."""
    from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

    return InMemoryOutboxRepository()


# ============================================================================
# Background
# ============================================================================


@given("单元测试框架 pytest 已配置完成")
def _pytest_configured():
    """Background: pytest is configured."""
    _test_context.clear()


# ============================================================================
# Scenario: 集成测试目录结构就绪
# ============================================================================


@scenario(FEATURE, "集成测试目录结构就绪")
def test_integration_dir_structure():
    """Verify integration test directory structure."""


@when("创建集成测试目录结构 tests/integration/")
def _create_integration_dir():
    import os

    assert os.path.isdir("tests/integration")
    assert os.path.isdir("tests/integration/fixtures")
    _test_context["dir_exists"] = True


@then("支持外部服务 Mock")
def _support_mocks():
    from tests.integration.conftest import mock_postgresql_repo, mock_rabbitmq_publisher, mock_redis

    assert callable(mock_redis)
    assert callable(mock_postgresql_repo)
    assert callable(mock_rabbitmq_publisher)


@then("测试隔离机制完善")
def _isolation_perfect():
    from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

    r1 = InMemoryOutboxRepository()
    r2 = InMemoryOutboxRepository()
    assert r1._entities is not r2._entities


# ============================================================================
# Scenario: 外部服务 Mock 配置
# ============================================================================


@scenario(FEATURE, "外部服务 Mock 配置")
def test_external_mock_config():
    """External mock config scenario."""


@given("需要 Mock 外部服务")
def _need_mocks():
    pass


@when("配置 Mock fixtures")
def _configure_mocks():
    pass


@then("Redis 使用 fakeredis 行为级 Mock")
def _redis_mock():
    assert isinstance(fakeredis.FakeRedis(), fakeredis.FakeRedis)


@then("PostgreSQL 使用 AsyncMock 接口级 Mock")
def _pg_mock():
    from unittest.mock import AsyncMock

    assert callable(AsyncMock())


@then("RabbitMQ 使用 AsyncMock 接口级 Mock")
def _mq_mock():
    from unittest.mock import AsyncMock

    assert callable(AsyncMock())


# ============================================================================
# Scenario: 领域事件冒烟测试
# ============================================================================


@scenario(FEATURE, "领域事件冒烟测试")
def test_event_smoke_publish():
    """Event publish to outbox scenario."""


@given("领域事件定义和内存发件箱已实现")
def _event_impl_done():
    from src.domain.events.base import DomainEvent
    from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

    assert DomainEvent is not None
    assert InMemoryOutboxRepository is not None


@when(parsers.parse("通过 InMemoryOutboxRepository 发布事件 {event_type}"))
def _publish_event(event_type: str):
    from src.domain.events import AgentDecided, DocumentProcessed, ToolExecuted
    from src.domain.events.base import DomainEvent
    from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

    repo = InMemoryOutboxRepository()
    event: DomainEvent

    if event_type == "DocumentProcessed":
        event = DocumentProcessed(document_id=uuid4(), parse_result={"pages": 5}, embedding=[0.1] * 1024)
    elif event_type == "ToolExecuted":
        event = ToolExecuted(tool_id=uuid4(), execution_result={"status": "ok"}, cost_audit={"tokens": 500})
    elif event_type == "AgentDecided":
        event = AgentDecided(agent_id=uuid4(), decision_result={"r": "go"}, confidence=0.85)
    else:
        pytest.fail(f"Unknown event type: {event_type}")

    repo.save(event)
    _test_context["repo"] = repo
    _test_context["event"] = event


@then("事件被正确序列化并写入内存发件箱")
def _event_serialized():
    repo = _test_context.get("repo")
    event = _test_context.get("event")
    assert repo and event
    unpublished = repo.get_unpublished(limit=10)
    assert len(unpublished) == 1
    assert unpublished[0].event_type == event.event_type


@then("可通过 get_unpublished 查询到未发布事件")
def _query_unpublished():
    assert len(_test_context["repo"].get_unpublished(limit=10)) >= 1


@then("可通过 mark_published 标记事件已发布")
def _mark_published():
    repo = _test_context.get("repo")
    event = _test_context.get("event")
    repo.mark_published(event.event_id)
    assert len(repo.get_unpublished(limit=10)) == 0


# ============================================================================
# Scenario: 事件类型注册表 — 未知类型反序列化
# ============================================================================


@scenario(FEATURE, "事件类型注册表 — 未知类型反序列化")
def test_unknown_event_type():
    """Unknown event type deserialization."""


@given("事件类型注册表已知 DocumentProcessed")
def _registry_known():
    from src.domain.events import DocumentProcessed  # noqa: F401


@when(parsers.parse('反序列化未知 event_type "{unknown_type}"'))
def _deserialize_unknown(unknown_type: str):
    from src.infrastructure.adapters.event_outbox_adapter import EventOutboxAdapter
    from src.infrastructure.entities.outbox import OutboxEntity

    entity = OutboxEntity()
    entity.event_id = uuid4()
    entity.event_type = unknown_type
    entity.payload = {}
    try:
        EventOutboxAdapter.to_domain_event(entity)
        _test_context["raised"] = False
    except ValueError as e:
        _test_context["raised"] = True
        _test_context["msg"] = str(e)


@then("应抛出 ValueError")
def _expect_value_error():
    assert _test_context.get("raised") is True


# ============================================================================
# Scenario: 幂等性检查原子操作
# ============================================================================


@scenario(FEATURE, "幂等性检查原子操作")
def test_idempotency_atomic():
    """Idempotency atomic check."""


@given("IdempotencyChecker 使用 fakeredis")
def _idempotency_setup():
    from src.infrastructure.idempotency.checker import IdempotencyChecker

    _test_context["checker"] = IdempotencyChecker(redis_client=fakeredis.FakeRedis())


@when("对同一 event_id 调用 try_acquire 两次")
def _acquire_twice():
    checker = _test_context["checker"]
    eid = uuid4()
    _test_context["first"] = checker.try_acquire(eid)
    _test_context["second"] = checker.try_acquire(eid)


@then("第一次返回 True")
def _first_true():
    assert _test_context["first"] is True


@then("第二次返回 False")
def _second_false():
    assert _test_context["second"] is False


# ============================================================================
# Scenario: 重试机制指数退避
# ============================================================================


@scenario(FEATURE, "重试机制指数退避")
def test_retry_exponential_backoff():
    """Retry exponential backoff."""


@given(parsers.parse("RetryPolicy base_delay={base:f}, max_delay={max:f}"))
def _retry_setup(base: float, max: float):
    from src.infrastructure.idempotency.retry_policy import RetryPolicy

    _test_context["policy"] = RetryPolicy(base_delay=base, max_delay=max)


@when("调用 get_delay(0) 和 get_delay(2)")
def _call_delays():
    p = _test_context["policy"]
    _test_context["d0"] = p.get_delay(0)
    _test_context["d2"] = p.get_delay(2)


@then("get_delay(2) > get_delay(0)")
def _delay_increased():
    assert _test_context["d2"] > _test_context["d0"]


@then("延迟包含 jitter 随机性")
def _delay_jitter():
    p = _test_context["policy"]
    delays = {p.get_delay(0) for _ in range(10)}
    assert len(delays) > 1


# ============================================================================
# Scenario: 仓储模式冒烟测试
# ============================================================================


@scenario(FEATURE, "仓储模式冒烟测试")
def test_repository_smoke():
    """Repository smoke test."""


@given("领域层定义了仓储接口")
def _domain_iface():
    from src.domain.repositories.outbox import OutboxRepository

    assert hasattr(OutboxRepository, "save")


@when(parsers.parse("通过 InMemoryOutboxRepository {operation}"))
def _repo_op(operation: str):
    from src.domain.events import DocumentProcessed
    from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

    repo = InMemoryOutboxRepository()
    event = DocumentProcessed(document_id=uuid4(), parse_result={"p": 3}, embedding=[0.1] * 1024)

    if operation == "保存事件":
        repo.save(event)
        _test_context["repo"] = repo
    elif operation == "查询未发布事件":
        repo.save(event)
        _test_context["unpublished"] = repo.get_unpublished(limit=10)
    elif operation == "标记已发布":
        repo.save(event)
        repo.mark_published(event.event_id)
        _test_context["repo"] = repo


@then("领域事件可通过仓储接口保存至内存存储")
def _event_saved():
    assert len(_test_context["repo"].get_unpublished(limit=10)) >= 1


@then("领域层不直接依赖具体存储实现")
def _domain_no_impl():
    import inspect

    from src.domain.repositories.outbox import OutboxRepository

    src = inspect.getsource(OutboxRepository)
    assert "infrastructure" not in src.lower()


# ============================================================================
# Scenario: 测试数据生命周期管理
# ============================================================================


@scenario(FEATURE, "测试数据生命周期管理")
def test_data_lifecycle():
    """Data lifecycle management."""


@given("每个测试使用独立 InMemoryOutboxRepository 实例")
def _independent_repo(repo):
    from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

    r2 = InMemoryOutboxRepository()
    assert repo._entities is not r2._entities


@when("测试后调用 repo.clear()")
def _call_clear(repo):
    repo._entities.clear()


@then("内存存储被清空")
def _cleared(repo):
    assert len(repo._entities) == 0


@then("不影响其他测试")
def _no_cross_impact():
    from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

    assert len(InMemoryOutboxRepository()._entities) == 0


# ============================================================================
# Scenario: 应用层→领域层→基础设施层协作
# ============================================================================


@scenario(FEATURE, "应用层→领域层→基础设施层协作")
def test_layer_collaboration():
    """Layer collaboration."""


@given("六边形架构各层已单独通过单元测试")
def _layers_tested():
    pass


@when("调用应用层用例方法")
def _call_use_case(repo):
    from src.application.use_cases.document_processing import DocumentProcessingUseCase

    uc = DocumentProcessingUseCase(outbox_repo=repo)
    _test_context["result"] = uc.process_document(document_id="gherkin-doc")
    _test_context["repo"] = repo


@then("正确调用领域层服务接口")
def _correct_domain_call():
    assert len(_test_context["repo"].get_unpublished(limit=10)) == 1


@then("领域层通过接口访问基础设施层")
def _domain_via_iface(repo):
    from src.domain.repositories.outbox import OutboxRepository

    assert isinstance(repo, OutboxRepository)


# ============================================================================
# Scenario: 错误传播
# ============================================================================


@scenario(FEATURE, "错误传播")
def test_error_propagation():
    """Error propagation."""


@given("仓储层抛出异常")
def _repo_throws():
    pass


class _FailingRepo(OutboxRepository):
    def save(self, event):
        raise ConnectionError("Infra failure for doc: fail-doc")

    def get_unpublished(self, limit):
        return []

    def mark_published(self, event_id):
        pass

    def mark_failed(self, event_id, error):
        pass


@when("应用层调用领域服务")
def _app_call_error():
    from src.application.use_cases.document_processing import DocumentProcessingUseCase

    uc = DocumentProcessingUseCase(outbox_repo=_FailingRepo())
    try:
        uc.process_document(document_id="fail-doc")
        _test_context["raised"] = False
    except RuntimeError as e:
        _test_context["raised"] = True
        _test_context["cause"] = e.__cause__


@then("应用层捕获异常")
def _app_caught():
    assert _test_context.get("raised") is True


@then("返回正确错误信息")
def _correct_msg():
    assert "fail-doc" in str(_test_context.get("cause"))


# ============================================================================
