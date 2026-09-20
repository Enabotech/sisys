"""SchemaValidationRecord 聚合根 + 仓储端口契约测试（Story 4.3 AC-5）

测试覆盖：
- 11 字段聚合根
- 不变量校验(4 项)
- Query Object frozen dataclass(7 字段)
- InMemory Repository CRUD + list_by_query + count + asyncio.Lock 类变量并发安全
- 跨实例锁共享反例验证(防止未来误改)
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime
from typing import cast

import pytest

from src.domain.entities.schema_validation_record import (
    SchemaValidationRecord,
    SchemaValidationRecordQuery,
    ValidationPhase,
)
from src.domain.exceptions import EntityValidationError
from src.domain.ports.l2_rdb import L2RdbPort
from src.domain.ports.schema_validation_record_repository import (
    SchemaValidationRecordRepositoryPort,
)
from src.domain.services.schema_validator import SchemaViolation
from src.infrastructure.storage.inmemory.schema_validation_record_repository import (
    InMemorySchemaValidationRecordRepository,
)


def _make_record(
    is_valid: bool = True,
    violations: tuple[SchemaViolation, ...] | None = None,
    tenant_id: uuid.UUID | None = None,
    tool_id: uuid.UUID | None = None,
    execution_id: uuid.UUID | None = None,
    validation_phase: ValidationPhase | str = "INPUT",
    retry_attempt: int = 1,
) -> SchemaValidationRecord:
    """构造测试用 SchemaValidationRecord

    Args:
        violations: None = 自动按 is_valid 决定;tuple = 显式使用
    """
    if violations is None:
        if not is_valid:
            violation = SchemaViolation(path="/x", expected="string", actual=1, message="m")
            violations = (violation,)
        else:
            violations = ()
    return SchemaValidationRecord(
        record_id=uuid.uuid4(),
        execution_id=execution_id or uuid.uuid4(),
        tool_id=tool_id or uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        validation_phase=cast("ValidationPhase", validation_phase),
        is_valid=is_valid,
        violations=violations,
        retry_attempt=retry_attempt,
        validated_at=datetime.now(UTC),
        schema_version="1.0.0",
        failure_reason=None if is_valid else "validation failed",
    )


# ============================================================================
# 1. 11 字段聚合根
# ============================================================================


def test_aggregate_has_eleven_init_fields() -> None:
    """SchemaValidationRecord 必须 11 init 字段"""
    init_fields = {f.name for f in fields(SchemaValidationRecord) if f.init}
    expected = {
        "record_id",
        "execution_id",
        "tool_id",
        "tenant_id",
        "validation_phase",
        "is_valid",
        "violations",
        "retry_attempt",
        "validated_at",
        "schema_version",
        "failure_reason",
    }
    assert init_fields == expected


def test_aggregate_default_values() -> None:
    """violations 默认空 tuple,retry_attempt 默认 1,schema_version 默认 '1.0.0'"""
    record = _make_record(is_valid=True)
    assert record.retry_attempt == 1
    assert record.schema_version == "1.0.0"


# ============================================================================
# 2. 不变量校验
# ============================================================================


def test_invalid_validation_phase_raises() -> None:
    """validation_phase 不在枚举内 → EntityValidationError"""
    with pytest.raises(EntityValidationError):
        _make_record(validation_phase="UNKNOWN")


def test_invalid_retry_attempt_raises() -> None:
    """retry_attempt < 1 → EntityValidationError"""
    with pytest.raises(EntityValidationError):
        _make_record(retry_attempt=0)


def test_invalid_without_violations_raises() -> None:
    """is_valid=False 时 violations 为空 → EntityValidationError"""
    with pytest.raises(EntityValidationError):
        _make_record(is_valid=False, violations=())


def test_naive_datetime_raises() -> None:
    """validated_at 无 tzinfo → EntityValidationError"""
    with pytest.raises(EntityValidationError):
        SchemaValidationRecord(
            record_id=uuid.uuid4(),
            execution_id=uuid.uuid4(),
            tool_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            validation_phase="INPUT",
            is_valid=True,
            validated_at=datetime(2026, 9, 10),  # 无 tzinfo
        )


# ============================================================================
# 3. to_dict 序列化
# ============================================================================


def test_to_dict_includes_all_fields() -> None:
    """to_dict 含全部 11 字段,UUID 转 str,datetime ISO"""
    record = _make_record()
    serialized = record.to_dict()
    assert len(serialized) == 11
    assert isinstance(serialized["record_id"], str)
    assert isinstance(serialized["validated_at"], str)


# ============================================================================
# 4. Query Object frozen dataclass(7 字段)
# ============================================================================


def test_query_object_has_seven_init_fields() -> None:
    """SchemaValidationRecordQuery 必须 7 init 字段"""
    init_fields = {f.name for f in fields(SchemaValidationRecordQuery) if f.init}
    expected = {
        "tenant_id",
        "tool_id",
        "execution_id",
        "validation_phase",
        "is_valid",
        "offset",
        "limit",
    }
    assert init_fields == expected


def test_query_object_is_frozen() -> None:
    """SchemaValidationRecordQuery 是 frozen dataclass"""
    query = SchemaValidationRecordQuery()
    with pytest.raises(FrozenInstanceError):
        setattr(query, "limit", 200)


def test_query_default_offset_limit() -> None:
    """默认 offset=0, limit=100"""
    query = SchemaValidationRecordQuery()
    assert query.offset == 0
    assert query.limit == 100


# ============================================================================
# 5. 端口继承 L2RdbPort + runtime_checkable
# ============================================================================


def test_port_inherits_l2_rdb_port() -> None:
    """SchemaValidationRecordRepositoryPort 必须继承 L2RdbPort[T]"""
    assert issubclass(SchemaValidationRecordRepositoryPort, L2RdbPort)


def test_inmemory_impl_runtime_checkable() -> None:
    """InMemorySchemaValidationRecordRepository 必须实现 Protocol"""
    repo = InMemorySchemaValidationRecordRepository()
    assert isinstance(repo, SchemaValidationRecordRepositoryPort)


# ============================================================================
# 6. CRUD 操作
# ============================================================================


@pytest.mark.asyncio
async def test_save_and_get_by_id() -> None:
    """save + get_by_id 往返"""
    repo = InMemorySchemaValidationRecordRepository()
    record = _make_record()
    saved = await repo.save(record)
    assert saved.record_id == record.record_id
    fetched = await repo.get_by_id(record.record_id)
    assert fetched == record


@pytest.mark.asyncio
async def test_get_by_id_missing_returns_none() -> None:
    """get_by_id 不存在时返回 None"""
    repo = InMemorySchemaValidationRecordRepository()
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_delete_removes_record() -> None:
    """delete 后 get_by_id 返回 None"""
    repo = InMemorySchemaValidationRecordRepository()
    record = _make_record()
    await repo.save(record)
    await repo.delete(record.record_id)
    assert await repo.get_by_id(record.record_id) is None


# ============================================================================
# 7. list_by_query 多字段过滤
# ============================================================================


@pytest.mark.asyncio
async def test_list_by_query_tenant_filter() -> None:
    """list_by_query 按 tenant_id 过滤(多租户隔离)"""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    repo = InMemorySchemaValidationRecordRepository()
    await repo.save(_make_record(tenant_id=tenant_a))
    await repo.save(_make_record(tenant_id=tenant_b))
    result = await repo.list_by_query(SchemaValidationRecordQuery(tenant_id=tenant_a))
    assert len(result) == 1
    assert result[0].tenant_id == tenant_a


@pytest.mark.asyncio
async def test_list_by_query_phase_filter() -> None:
    """list_by_query 按 validation_phase 过滤"""
    repo = InMemorySchemaValidationRecordRepository()
    await repo.save(_make_record(validation_phase="INPUT"))
    await repo.save(_make_record(validation_phase="OUTPUT"))
    input_results = await repo.list_by_query(SchemaValidationRecordQuery(validation_phase="INPUT"))
    assert len(input_results) == 1


@pytest.mark.asyncio
async def test_list_by_query_pagination() -> None:
    """list_by_query offset/limit 分页"""
    repo = InMemorySchemaValidationRecordRepository()
    for _ in range(5):
        await repo.save(_make_record())
    page1 = await repo.list_by_query(SchemaValidationRecordQuery(offset=0, limit=2))
    page2 = await repo.list_by_query(SchemaValidationRecordQuery(offset=2, limit=2))
    assert len(page1) == 2
    assert len(page2) == 2


# ============================================================================
# 8. count
# ============================================================================


@pytest.mark.asyncio
async def test_count() -> None:
    """count 统计符合条件记录数"""
    repo = InMemorySchemaValidationRecordRepository()
    for _ in range(3):
        await repo.save(_make_record())
    total = await repo.count(SchemaValidationRecordQuery())
    assert total == 3


# ============================================================================
# 9. asyncio.Lock 类变量(CLAUDE.md §6 硬约束)
# ============================================================================


def test_asyncio_lock_is_class_variable() -> None:
    """_lock 必须是类变量(非实例变量)"""
    assert "_lock" in InMemorySchemaValidationRecordRepository.__dict__


def test_lock_shared_across_instances() -> None:
    """两个实例共享同一锁对象"""
    repo1 = InMemorySchemaValidationRecordRepository()
    repo2 = InMemorySchemaValidationRecordRepository()
    assert repo1._lock is repo2._lock


def test_records_is_instance_variable() -> None:
    """_records 是实例变量(每个实例独立,与 _lock 类变量对比)"""
    repo1 = InMemorySchemaValidationRecordRepository()
    repo2 = InMemorySchemaValidationRecordRepository()
    assert repo1._records is not repo2._records


@pytest.mark.asyncio
async def test_concurrent_save_safety() -> None:
    """100 并发 save 不丢失记录"""
    repo = InMemorySchemaValidationRecordRepository()

    async def save_record() -> None:
        await repo.save(_make_record())

    await asyncio.gather(*[save_record() for _ in range(100)])
    all_records = await repo.list_all()
    assert len(all_records) == 100
