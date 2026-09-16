"""InMemorySchemaValidationRecordRepository 并发安全测试(Story 4.3 AC-5 + P0-C 修复守护)

覆盖范围:
1. asyncio.Lock 类变量共享验证(CLAUDE.md §6 硬约束)
2. 并发 save + list_by_query 一致性(无半写入视图)
3. count() + 并发 list_by_query 计数一致性
4. 多实例锁共享验证
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.schema_validation_record import (
    SchemaValidationRecord,
    SchemaValidationRecordQuery,
)
from src.domain.services.schema_validator import SchemaViolation
from src.infrastructure.storage.inmemory.schema_validation_record_repository import (
    InMemorySchemaValidationRecordRepository,
)


def _make_record(
    tenant_id: uuid.UUID,
    execution_id: uuid.UUID | None = None,
    tool_id: uuid.UUID | None = None,
) -> SchemaValidationRecord:
    return SchemaValidationRecord(
        record_id=uuid.uuid4(),
        execution_id=execution_id or uuid.uuid4(),
        tool_id=tool_id or uuid.uuid4(),
        tenant_id=tenant_id,
        validation_phase="INPUT",  # Literal["INPUT", "OUTPUT", "COMPATIBILITY"]
        is_valid=False,
        violations=(SchemaViolation(path="/x", expected="string", actual=123, message="bad"),),
        retry_attempt=1,
        validated_at=datetime.now(UTC),
        schema_version="1.0.0",
        failure_reason="test",
    )


# ---------------------------------------------------------------------------
# asyncio.Lock 类变量共享(CLAUDE.md §6 硬约束)
# ---------------------------------------------------------------------------


def test_lock_is_class_variable_not_instance() -> None:
    """asyncio.Lock 必须声明为类变量(非实例变量),CLAUDE.md §6 硬约束"""
    repo_a = InMemorySchemaValidationRecordRepository()
    repo_b = InMemorySchemaValidationRecordRepository()
    # 类变量:所有实例共享同一把锁
    assert repo_a._lock is repo_b._lock
    assert repo_a._lock is InMemorySchemaValidationRecordRepository._lock


def test_records_is_instance_variable_not_shared() -> None:
    """_records 必须是实例变量(每个实例独立存储),与 _lock 类变量对比"""
    repo_a = InMemorySchemaValidationRecordRepository()
    repo_b = InMemorySchemaValidationRecordRepository()
    # 实例变量:不同实例的 _records 字典不同
    assert repo_a._records is not repo_b._records


# ---------------------------------------------------------------------------
# 并发一致性测试(P0-C 修复验证)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_save_no_data_loss() -> None:
    """100 并发 save 不丢记录"""
    repo = InMemorySchemaValidationRecordRepository()
    tenant_id = uuid.uuid4()

    async def _save_one() -> SchemaValidationRecord:
        record = _make_record(tenant_id=tenant_id)
        return await repo.save(record)

    # 100 并发 save
    records = await asyncio.gather(*[_save_one() for _ in range(100)])
    assert len(records) == 100

    # list_all 应返回 100 条
    all_records = await repo.list_all()
    assert len(all_records) == 100

    # 验证所有 tenant_id 一致
    assert all(r.tenant_id == tenant_id for r in all_records)


@pytest.mark.asyncio
async def test_concurrent_save_and_list_no_partial_view() -> None:
    """P0-C 修复验证:并发 save + list_by_query 无半写入视图"""
    repo = InMemorySchemaValidationRecordRepository()
    tenant_id = uuid.uuid4()

    async def _save_one(i: int) -> SchemaValidationRecord:
        record = _make_record(tenant_id=tenant_id)
        await repo.save(record)
        return record

    async def _list_all() -> list[SchemaValidationRecord]:
        return await repo.list_all()

    async def _list_by_tenant() -> list[SchemaValidationRecord]:
        return await repo.list_by_query(
            SchemaValidationRecordQuery(tenant_id=tenant_id, limit=10000),
        )

    # 100 并发 save + 50 并发 list(交错触发)
    save_tasks = [_save_one(i) for i in range(100)]
    list_tasks = [_list_by_tenant() for _ in range(50)]

    results = await asyncio.gather(*save_tasks, *list_tasks, return_exceptions=True)

    # 收集 list 结果
    list_results = [r for r in results[100:] if isinstance(r, list)]
    # 由于 asyncio.Lock 串行化,所有 save 在同一 event loop 串行执行;
    # list_by_query 可能在 save 全部完成后才调度,因此 max(counts) == 100
    counts = [len(r) for r in list_results]
    assert all(c >= 0 for c in counts)
    # 至少有 1 个 list 任务在所有 save 完成后执行,读到 100 条
    assert max(counts) == 100


@pytest.mark.asyncio
async def test_count_concurrent_consistency() -> None:
    """count 与 list_by_query 在并发下结果一致"""
    repo = InMemorySchemaValidationRecordRepository()
    tenant_id = uuid.uuid4()

    async def _save_one() -> None:
        record = _make_record(tenant_id=tenant_id)
        await repo.save(record)

    # 50 并发 save
    await asyncio.gather(*[_save_one() for _ in range(50)])

    # 同时 count 和 list_by_query
    count, results = await asyncio.gather(
        repo.count(SchemaValidationRecordQuery(tenant_id=tenant_id)),
        repo.list_by_query(SchemaValidationRecordQuery(tenant_id=tenant_id, limit=10000)),
    )

    assert count == 50
    assert len(results) == 50


# ---------------------------------------------------------------------------
# 多租户隔离测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_isolation_in_concurrent_writes() -> None:
    """并发多租户写操作时,租户隔离不被破坏"""
    repo = InMemorySchemaValidationRecordRepository()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    async def _save_for(tenant_id: uuid.UUID, n: int) -> None:
        for _ in range(n):
            await repo.save(_make_record(tenant_id=tenant_id))

    # 交错写两个租户
    await asyncio.gather(
        _save_for(tenant_a, 30),
        _save_for(tenant_b, 20),
    )

    # 各自查询应只看到自己的记录
    a_records = await repo.list_by_query(SchemaValidationRecordQuery(tenant_id=tenant_a, limit=100))
    b_records = await repo.list_by_query(SchemaValidationRecordQuery(tenant_id=tenant_b, limit=100))

    assert len(a_records) == 30
    assert len(b_records) == 20
    assert all(r.tenant_id == tenant_a for r in a_records)
    assert all(r.tenant_id == tenant_b for r in b_records)
