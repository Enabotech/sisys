"""Outbox 终态机制集成测试（Story 91-2 — 真实 PG 5432 全链路）

验证 archived 终态迁移 / requeue 重放 / count_by_status 巡检三链路：
- 超限行经 get_unpublished 应用层分流迁移 archived（终态 + 不进正常发布批）
- requeue：archived → pending（计数清零）后重新进入选择集
- 隔离：独立 PG schema + savepoint rollback（真实服务 Schema 隔离先例）

Run with:
    poetry run pytest tests/integration/test_integration_outbox_termination.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.outbox.outbox_repository import PostgreSQLOutboxRepository
from src.infrastructure.storage.postgresql.models import OutboxModel
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

pytestmark = [pytest.mark.integration, pytest.mark.database]

DomainEvent.register("TestEvent", DomainEvent)  # to_domain_event 注册表要求（合法行路径）


def _make_model(retry_count: int = 0, status: str = "pending") -> OutboxModel:
    """构造 OutboxModel 行（91-2 终态链路测试数据）。

    model.event_id 与 payload["event_id"] 必须同源（to_domain_event 经 payload
    重建事件——断言「行进入 events」以 event_id 比对，两 id 不同则恒 False）；
    created_at 钉在 2020 年——FIFO 排序确保本行位于批首（并发 worker
    同刻写入时 limit 窗口必含本行，防竞态漏处理）。
    """
    event_id = uuid.uuid4()
    return OutboxModel(
        id=uuid.uuid4(),
        event_id=event_id,
        event_type="TestEvent",
        payload={
            "event_id": str(event_id),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "test",
            "payload": {},
        },
        status=status,
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
        retry_count=retry_count,
        max_retries=3,
    )


class TestOutboxTerminationIntegration:
    """91-2 终态机制三链路集成验证（真实 PG）。"""

    async def test_exhausted_row_archived_not_published(self, pg_session: AsyncSession) -> None:
        """AC-1：超限行经 get_unpublished 分流迁移 archived，不进正常发布批。"""
        exhausted = _make_model(retry_count=3, status="failed")
        pg_session.add(exhausted)
        await pg_session.flush()

        token = set_session(pg_session)
        try:
            repo = PostgreSQLOutboxRepository()
            events = await repo.get_unpublished(limit=10)
        finally:
            reset_session(token)

        assert all(e.event_id != exhausted.event_id for e in events), "超限行不得进入正常发布批"
        await pg_session.refresh(exhausted)
        assert exhausted.status == "archived", "超限行必须迁移 archived 终态"
        assert "retries exhausted" in (exhausted.error_message or "")

    async def test_requeue_archived_roundtrip(self, pg_session: AsyncSession) -> None:
        """AC-2：requeue archived → pending（计数清零），行重新进入选择集。"""
        DomainEvent.register("TestEvent", DomainEvent)  # 行内注册（防模块级注册被会话级快照撤销）
        archived = _make_model(retry_count=3, status="failed")
        pg_session.add(archived)
        await pg_session.flush()

        token = set_session(pg_session)
        try:
            repo = PostgreSQLOutboxRepository()
            await repo.archive(archived.event_id)
            await pg_session.flush()
            await pg_session.refresh(archived)
            assert archived.status == "archived"

            await repo.requeue(archived.event_id)
            await pg_session.flush()
            await pg_session.refresh(archived)
            assert archived.status == "pending", "requeue 后必须回到 pending"
            assert archived.retry_count == 0, "重试预算须清零"

            # 共用 dev 库存在真实存量行——limit 窗口断言天然脆弱，用大窗口验证
            # 「requeue 后行重新进入选择集」（pending + 预算内即可见）
            events = await repo.get_unpublished(limit=500)
        finally:
            reset_session(token)
        assert any(e.event_id == archived.event_id for e in events), "requeue 后重新进入选择集"

    async def test_count_by_status_reflects_archived(self, pg_session: AsyncSession) -> None:
        """AC-3：count_by_status 巡检——archived 终态计数可见。"""
        row = _make_model(retry_count=3, status="failed")
        pg_session.add(row)
        await pg_session.flush()

        token = set_session(pg_session)
        try:
            repo = PostgreSQLOutboxRepository()
            await repo.archive(row.event_id)
            await pg_session.flush()
            counts = await repo.count_by_status()
        finally:
            reset_session(token)

        assert counts.get("archived", 0) >= 1, "archived 终态经巡检面可见"
