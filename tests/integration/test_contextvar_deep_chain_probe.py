"""技术债清偿实证探针：ContextVar 在集成测试深链的存活验证（保留为回归防线）

背景（4.1a 遗留技术债，2026-09-30 清偿）：test_integration_strategic_tool_e2e.py 的
pg_tool_execution_repository fixture docstring 曾声称「pytest-xdist 多进程测试中，
asyncio ContextVar 跨 await 边界会丢失」，因此弃用 SQLAlchemy ContextVar 模式、
改用 asyncpg 直连 + 全表 DELETE（违反「集成测试禁止手动 delete/truncate」纪律，
且是 xdist 并发竞态根源）。

本探针在 integration 侧复现 acceptance 模式（conftest 共享 pg_session + 同步
fixture set_session）并做深链验证，证伪上述判断——改造后保留为回归防线：

- 同步 fixture 内 set_session(token) → 异步测试方法读（跨 fixture/测试边界）
- save → get_by_id → list_by_query 多次独立 await 调用（跨 await 边界）
- 事务隔离：begin + rollback（无 DELETE——合规模式的最小实证）
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest

from src.domain.entities.tool_execution import ToolExecution, ToolExecutionState
from src.domain.ports.tool_execution_repository import ToolExecutionQuery
from src.infrastructure.storage.postgresql.repository.tool_execution_repository import (
    PostgreSQLToolExecutionRepository,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

_PROBE_TENANT_A = uuid.uuid4()  # 测试一写入（rollback 后应无残留）
_PROBE_TENANT_B = uuid.uuid4()  # 测试二查询基线


@pytest.fixture
def probe_repo(pg_session) -> Generator[PostgreSQLToolExecutionRepository, None, None]:
    """同步 fixture 内 set_session（acceptance 同款结构——被验证的形态本体）."""
    token = set_session(pg_session)
    yield PostgreSQLToolExecutionRepository()
    reset_session(token)


def _make_execution(tenant_id: uuid.UUID) -> ToolExecution:
    """最小可持久化 ToolExecution 实体（对齐 e2e 测试既有构造形态）."""
    return ToolExecution(
        execution_id=uuid.uuid4(),
        tenant_id=tenant_id,
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        tool_version="v1.0.0",
        state=ToolExecutionState.IDLE,
        started_at=datetime.now(UTC),
    )


class TestContextVarDeepChainProbe:
    """深链探针：跨 fixture/await 边界的 ContextVar 存活 + 事务隔离实证."""

    @pytest.mark.asyncio
    async def test_save_then_read_back_within_transaction(self, probe_repo: PostgreSQLToolExecutionRepository) -> None:
        """save（flush）→ get_by_id → list_by_query 三段独立 await 经 ContextVar 同 session 可见."""
        entity = _make_execution(_PROBE_TENANT_A)
        saved = await probe_repo.save(entity)
        assert saved.execution_id == entity.execution_id, "save 应回写主键（flush 语义）"

        fetched = await probe_repo.get_by_id(entity.execution_id)
        assert fetched is not None, "同事务内 get_by_id 应读回（ContextVar 深链存活——债务前提证伪）"
        assert fetched.tenant_id == _PROBE_TENANT_A

        listed = await probe_repo.list_by_query(ToolExecutionQuery(tenant_id=_PROBE_TENANT_A))
        assert any(e.execution_id == entity.execution_id for e in listed), "list_by_query 同事务可见"

    @pytest.mark.asyncio
    async def test_rollback_leaves_no_residue_from_prior_test(self, probe_repo: PostgreSQLToolExecutionRepository) -> None:
        """事务隔离实证：上一测试（tenant A）的写入经 rollback 零残留（无 DELETE 依赖的自清理）."""
        residue = await probe_repo.list_by_query(ToolExecutionQuery(tenant_id=_PROBE_TENANT_A))
        assert residue == [], f"rollback 后 tenant A 应零残留，实际 {len(residue)} 条"

        entity = _make_execution(_PROBE_TENANT_B)
        await probe_repo.save(entity)
        own = await probe_repo.list_by_query(ToolExecutionQuery(tenant_id=_PROBE_TENANT_B))
        assert len(own) == 1, "本事务内写入可见"
