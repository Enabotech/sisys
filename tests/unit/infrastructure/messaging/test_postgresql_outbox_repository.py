"""PostgreSQLOutboxRepository 单元测试"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.outbox.outbox_repository import PostgreSQLOutboxRepository
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


@pytest.fixture
def mock_session():
    session = mock.AsyncMock(spec=AsyncSession)
    # add 是同步方法（不执行 I/O）
    session.add = mock.Mock()
    return session


@pytest.fixture
def repository(mock_session):
    token = set_session(mock_session)
    repo = PostgreSQLOutboxRepository()
    yield repo
    reset_session(token)


class TestPostgreSQLOutboxRepository:
    """PostgreSQLOutboxRepository 测试"""

    async def test_save(self, repository, mock_session):
        """测试保存事件"""
        event = DomainEvent(
            event_id=uuid4(),
            event_type="TestEvent",
            timestamp=datetime.now(UTC),
            source="test",
            payload={"key": "value"},
        )

        await repository.save(event)

        mock_session.add.assert_called_once()

    async def test_get_unpublished(self, repository, mock_session):
        """测试异步获取未发布事件"""
        # 注册测试事件类型
        DomainEvent.register("TestEvent", DomainEvent)

        model1 = mock.Mock()
        model1.event_type = "TestEvent"
        model1.payload = {
            "event_id": str(uuid4()),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "test",
            "payload": {},
        }
        model2 = mock.Mock()
        model2.event_type = "TestEvent"
        model2.payload = {
            "event_id": str(uuid4()),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "test",
            "payload": {},
        }
        models = [model1, model2]
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = models
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.get_unpublished(limit=10)

        assert len(result) == 2

    async def test_get_unpublished_poison_message_isolated(self, repository, mock_session):
        """毒消息隔离：单条畸形 payload 标 failed 跳过，不阻塞合法事件返回。"""
        DomainEvent.register("TestEvent", DomainEvent)

        poison_model = mock.Mock()
        poison_model.event_type = "TestEvent"
        poison_model.payload = {
            "event_id": "not-a-uuid",  # 畸形 UUID → from_dict 242（毒形态）
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "test",
            "payload": {},
        }
        poison_model.status = "pending"
        poison_model.retry_count = 0
        poison_model.max_retries = 3

        good_model = mock.Mock()
        good_model.event_type = "TestEvent"
        good_model.payload = {
            "event_id": str(uuid4()),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "test",
            "payload": {},
        }

        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = [poison_model, good_model]
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        # mark_failed 复用同一 execute 返回值——按 event_id 重查命中毒行
        mock_result.scalar_one_or_none.return_value = poison_model
        mock_session.execute.return_value = mock_result

        result = await repository.get_unpublished(limit=10)

        assert len(result) == 1, "合法事件必须正常返回（毒消息不得阻塞队列）"
        assert str(result[0].event_id) == good_model.payload["event_id"]
        assert poison_model.status == "failed", "毒行必须标记失败"
        assert poison_model.retry_count == 1
        assert "deserialization failed" in poison_model.error_message

    async def test_get_unpublished_poison_message_retry_bounded(self, repository, mock_session):
        """毒消息有界化：重试上限已到的毒行不再写库标记，仍返回合法事件。"""
        DomainEvent.register("TestEvent", DomainEvent)

        poison_model = mock.Mock()
        poison_model.event_type = "TestEvent"
        poison_model.payload = {
            "event_id": "not-a-uuid",
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "test",
            "payload": {},
        }
        poison_model.status = "failed"
        poison_model.retry_count = 3
        poison_model.max_retries = 3

        good_model = mock.Mock()
        good_model.event_type = "TestEvent"
        good_model.payload = {
            "event_id": str(uuid4()),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "test",
            "payload": {},
        }

        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = [poison_model, good_model]
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar_one_or_none.return_value = poison_model
        mock_session.execute.return_value = mock_result

        result = await repository.get_unpublished(limit=10)

        assert len(result) == 1, "合法事件必须正常返回"
        assert poison_model.retry_count == 3, "超限毒行不得再递增 retry_count（有界化）"
        assert poison_model.status == "failed"

    async def test_get_unpublished_excludes_retry_exhausted_rows(self, repository, mock_session):
        """SELECT 语句含 retry_count < max_retries 过滤（白盒断言——mock 模式测不到 WHERE 语义）。

        超限毒行/发布失败行必须退出选择集：否则累积至 batch_size 后
        get_unpublished 恒返回空批、合法事件静默停发（队头阻塞隐蔽复发形态）。
        """
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = []
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.get_unpublished(limit=10)

        stmt = mock_session.execute.call_args_list[0][0][0]  # 首次调用（mark_failed 可能追加调用）
        compiled = str(stmt.compile())
        assert "retry_count < event_outbox.max_retries" in compiled, "SELECT 必须以列比较过滤重试耗尽行"

    async def test_mark_published(self, repository, mock_session):
        """测试异步标记已发布"""
        event_id = uuid4()
        mock_model = mock.Mock()
        mock_model.status = "pending"
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute.return_value = mock_result

        await repository.mark_published(event_id)

        assert mock_model.status == "published"
        assert mock_model.published_at is not None

    async def test_mark_failed(self, repository, mock_session):
        """测试异步标记失败"""
        event_id = uuid4()
        mock_model = mock.Mock()
        mock_model.status = "pending"
        mock_model.retry_count = 0
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute.return_value = mock_result

        await repository.mark_failed(event_id, "Test error")

        assert mock_model.status == "failed"
        assert mock_model.retry_count == 1
        assert mock_model.error_message == "Test error"

    async def test_mark_failed_truncates_long_error(self, repository, mock_session):
        """超长错误消息按列宽截断——error_message VARCHAR(1000) 超长 PG 抛错不截断，
        未截断将使整周期事务失败（毒标记丢弃 → 永久活锁）。"""
        event_id = uuid4()
        mock_model = mock.Mock()
        mock_model.status = "pending"
        mock_model.retry_count = 0
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute.return_value = mock_result

        long_error = "x" * 2500
        await repository.mark_failed(event_id, long_error)

        assert len(mock_model.error_message) == 1000, "错误消息必须截断至列宽（防 VARCHAR 溢出炸事务）"

    async def test_internal_get_unpublished(self, repository, mock_session):
        """测试内部方法获取未发布实体"""
        models = [mock.Mock(), mock.Mock()]
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = models
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository._get_unpublished_entities(limit=10)

        assert len(result) == 2

    async def test_internal_mark_published_entity(self, repository, mock_session):
        """测试内部方法标记已发布实体"""
        model = mock.Mock()
        model.status = "pending"

        await repository._mark_published_entity(model)

        assert model.status == "published"
        assert model.published_at is not None

    async def test_internal_mark_failed_entity(self, repository, mock_session):
        """测试内部方法标记失败实体"""
        model = mock.Mock()
        model.status = "pending"
        model.retry_count = 0

        await repository._mark_failed_entity(model, "Error")

        assert model.status == "failed"
        assert model.retry_count == 1
        assert model.error_message == "Error"
