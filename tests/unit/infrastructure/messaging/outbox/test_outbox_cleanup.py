"""Outbox 清理策略 + RetryPolicy 集成测试

验证 AC-5: Outbox 清理策略 + RetryPolicy 集成
对应 Task 5 的 TDD 测试
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.infrastructure.messaging.outbox.outbox import OutboxEntity


class TestOutboxCleanupStrategy:
    """验证 InMemoryOutboxRepository 清理策略"""

    async def test_cleanup_removes_old_published_records(self) -> None:
        """cleanup_old_published_records() 应移除超过保留期的已发布记录"""
        from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository

        repo = InMemoryOutboxRepository()

        old_entity = OutboxEntity(
            event_id=uuid4(),
            event_type="test",
            payload={},
            status="published",
            published_at=datetime.now(UTC) - timedelta(days=31),
        )
        recent_entity = OutboxEntity(
            event_id=uuid4(),
            event_type="test",
            payload={},
            status="published",
            published_at=datetime.now(UTC) - timedelta(days=1),
        )
        repo._entities.extend([old_entity, recent_entity])

        removed = await repo.cleanup_old_published_records(older_than_days=30)

        assert removed == 1
        assert len(repo._entities) == 1
        assert repo._entities[0].event_id == recent_entity.event_id

    async def test_cleanup_does_not_remove_pending_records(self) -> None:
        """cleanup_old_published_records() 不应移除 pending 记录"""
        from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository

        repo = InMemoryOutboxRepository()

        pending_entity = OutboxEntity(
            event_id=uuid4(),
            event_type="test",
            payload={},
            status="pending",
            created_at=datetime.now(UTC) - timedelta(days=60),
        )
        repo._entities.append(pending_entity)

        removed = await repo.cleanup_old_published_records(older_than_days=30)

        assert removed == 0
        assert len(repo._entities) == 1

    async def test_cleanup_does_not_remove_failed_records(self) -> None:
        """cleanup_old_published_records() 不应移除 failed 记录"""
        from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository

        repo = InMemoryOutboxRepository()

        failed_entity = OutboxEntity(
            event_id=uuid4(),
            event_type="test",
            payload={},
            status="failed",
            created_at=datetime.now(UTC) - timedelta(days=60),
        )
        repo._entities.append(failed_entity)

        removed = await repo.cleanup_old_published_records(older_than_days=30)

        assert removed == 0
        assert len(repo._entities) == 1

    async def test_cleanup_respects_retention_period(self) -> None:
        """cleanup_old_published_records() 应遵守保留期"""
        from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository

        repo = InMemoryOutboxRepository()

        within_period = OutboxEntity(
            event_id=uuid4(),
            event_type="test",
            payload={},
            status="published",
            published_at=datetime.now(UTC) - timedelta(days=29),
        )
        repo._entities.append(within_period)

        removed = await repo.cleanup_old_published_records(older_than_days=30)

        assert removed == 0
        assert len(repo._entities) == 1


class TestRetryPolicyIntegration:
    """验证 AsyncOutboxPoller 集成 RetryPolicy"""

    def test_retry_policy_get_delay_increases(self) -> None:
        """RetryPolicy.get_delay() 返回值应随 retry_count 增长"""
        from src.infrastructure.messaging.retry.retry_policy import RetryPolicy

        policy = RetryPolicy(base_delay=1.0, max_delay=60.0)
        delays = [policy.get_delay(i) for i in range(4)]

        for i in range(1, len(delays)):
            assert delays[i] > delays[i - 1] * 0.5  # 考虑 jitter

    def test_retry_policy_should_retry(self) -> None:
        """RetryPolicy.should_retry() 应在 max_retries 内返回 True"""
        from src.infrastructure.messaging.retry.retry_policy import RetryPolicy

        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(0) is True
        assert policy.should_retry(2) is True
        assert policy.should_retry(3) is False
