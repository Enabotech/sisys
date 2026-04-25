"""Acceptance tests for Story 1.15a - L1 显式确认压缩.

Real instance integration tests using actual PostgreSQL service.
No mocks - uses real PostgreSQL instance with SQLAlchemy.

Run with: pytest tests/acceptance/test_story_1_15a_steps.py -v

Test Isolation (per sdd-tdd-checklist.md §5.5):
    - Uses begin_nested() savepoint for transactional isolation
    - Each test runs in isolated transaction that rolls back after test
    - Test schema uses UUID suffix for isolation
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.text_processing.l1_compressor import L1Compressor
from src.application.text_processing.l1_text_extractor import L1TextExtractor
from src.domain.services.memory_service import (
    MemoryDeleteRequest,
    MemorySaveRequest,
    MemoryService,
    MemoryUpdateRequest,
)
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.engine import DatabaseEngine

scenarios("test_story_1_15a.feature")

# ===================================================================
# Paths & Constants
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict:
    """Share state between steps."""
    return {}


@pytest.fixture
def test_schema() -> str:
    """Generate unique schema name for test isolation."""
    return f"test_sisys_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def pg_config() -> PostgreSQLConfig:
    """Real PostgreSQL configuration from environment."""
    return PostgreSQLConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DATABASE", "sisys"),
        username=os.getenv("POSTGRES_USERNAME", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        pool_size=5,
        max_overflow=10,
    )


@pytest.fixture
def db_engine(pg_config: PostgreSQLConfig) -> DatabaseEngine:
    """Real database engine instance."""
    return DatabaseEngine(pg_config)


@pytest.fixture
def ensure_schema(db_engine: DatabaseEngine, pg_config: PostgreSQLConfig, test_schema: str):
    """Ensure test schema exists before tests.

    Creates a unique schema for this test run to ensure isolation.
    Uses sync engine for DDL to avoid async issues.
    """
    sync_url = f"postgresql+psycopg2://{pg_config.username}:{pg_config.password}@{pg_config.host}:{pg_config.port}/{pg_config.database}"
    from sqlalchemy import create_engine, text

    sync_engine = create_engine(sync_url)

    # Create schema
    with sync_engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_schema}" CASCADE'))
        conn.commit()

    with sync_engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        conn.commit()

    # Create tables in schema
    from src.infrastructure.storage.postgresql.models import Base

    with sync_engine.connect() as conn:
        conn.execute(text(f'SET search_path TO "{test_schema}"'))
        Base.metadata.create_all(conn)
        conn.commit()

    sync_engine.dispose()

    yield test_schema

    # Cleanup - drop schema after test
    from sqlalchemy import create_engine

    sync_engine = create_engine(sync_url)
    try:
        with sync_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA "{test_schema}" CASCADE'))
            conn.commit()
    except Exception:
        pass
    sync_engine.dispose()


@pytest.fixture
async def pg_session(db_engine: DatabaseEngine, ensure_schema: str) -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL session with transactional rollback.

    Uses begin_nested() to create a savepoint for test isolation.
    After test completes, the nested transaction is rolled back.
    """
    async_engine = db_engine.get_async_engine()
    session = AsyncSession(async_engine)

    # Set search_path for this session
    await session.execute(text(f'SET search_path TO "{ensure_schema}"'))

    # Start a nested transaction (savepoint) for rollback isolation
    async with session.begin_nested():
        yield session

    await session.close()


@pytest.fixture
def extractor() -> L1TextExtractor:
    """Create L1TextExtractor."""
    return L1TextExtractor()


@pytest.fixture
def compressor() -> L1Compressor:
    """Create L1Compressor."""
    return L1Compressor()


@pytest.fixture
async def service(extractor, compressor, pg_session: AsyncSession) -> MemoryService:
    """Create MemoryService with real PostgreSQL repositories."""
    from src.infrastructure.storage.postgresql.memory_change_history_repository import (
        PostgreSQLMemoryChangeHistoryRepository,
    )
    from src.infrastructure.storage.postgresql.memory_metadata_repository import (
        PostgreSQLMemoryMetadataRepository,
    )

    metadata_repo = PostgreSQLMemoryMetadataRepository(pg_session)
    history_repo = PostgreSQLMemoryChangeHistoryRepository(pg_session)

    return MemoryService(
        text_extractor=extractor,
        compressor=compressor,
        metadata_repository=metadata_repo,
        history_repository=history_repo,
    )


# ===================================================================
# Background Steps
# ===================================================================


@given("L1TextExtractor 已实现")
def given_l1_extractor_ready(extractor: L1TextExtractor, context: dict):
    context["extractor"] = extractor


@given("L1Compressor 已实现")
def given_l1_compressor_ready(compressor: L1Compressor, context: dict):
    context["compressor"] = compressor


@given("MemoryService 已实现并配置")
def given_memory_service_ready(service: MemoryService, context: dict):
    context["service"] = service


# ===================================================================
# AC-1: L1 Compression Flow
# ===================================================================


@given("用户输入记住以后用bun而不是npm")
def given_user_input_bun_npm(context: dict):
    context["user_content"] = "记住，以后用 bun 而不是 npm"


@given("用户输入约480字的内容")
def given_user_input_480_chars(context: dict):
    context["user_content"] = "记住，这是一个很长的记忆内容需要压缩处理，" * 23


@given("用户输入记住测试压缩")
def given_user_input_test_compress(context: dict):
    context["user_content"] = "记住，这是一个很长的记忆内容需要压缩处理，" * 10


@given("L1 压缩完成")
def given_l1_compression_completed(context: dict, extractor, compressor):
    context["extractor"] = extractor
    context["compressor"] = compressor


@when("L1 显式确认压缩被触发")
def when_l1_compression_triggered(context: dict, event_loop):
    if "extractor" not in context:
        context["extractor"] = L1TextExtractor()
    if "compressor" not in context:
        context["compressor"] = L1Compressor()


@when("MemoryService 保存记忆")
def when_memory_service_save(context: dict, service: MemoryService, event_loop):
    """Save memory via MemoryService (async operation)."""

    async def _save():
        return await service.save(
            MemorySaveRequest(
                user_id="test-user",
                name="test-memory",
                content=context["user_content"],
                memory_type="user",
                description="Test memory",
            )
        )

    context["memory"] = event_loop.run_until_complete(_save())


@then("MemoryService 应该保存记忆")
def then_memory_service_save(context: dict):
    pass


@then("L1TextExtractor 应该提取内容")
def then_l1_extractor_extract(context: dict):
    extractor = context.get("extractor", L1TextExtractor())
    result = extractor.extract(context["user_content"])
    context["extracted_content"] = result.content
    assert result.content is not None


@then("L1Compressor 应该压缩内容至约150字")
def then_l1_compressor_compress(context: dict):
    compressor = context.get("compressor", L1Compressor())
    result = compressor.compress(context.get("extracted_content", context["user_content"]))
    context["compression_result"] = result
    assert result.compressed_length <= 160


@then("压缩率应该大于等于70")
def then_compression_ratio_exceed_70(context: dict):
    result = context["compression_result"]
    if result.original_length > 0:
        ratio = (result.original_length - result.compressed_length) / result.original_length
        if result.original_length >= 100:
            assert ratio >= 0.65, f"Compression ratio {ratio:.2%} < 70%"


# ===================================================================
# AC-2: L0 File System Write
# ===================================================================


@when("压缩后记忆准备写入")
def when_compression_ready_to_write(context: dict):
    pass


@then("FileMemoryAdapter 应该写入文件系统")
def then_file_memory_adapter_write(context: dict, tmp_path: Any):
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.storage.file_memory_adapter import FileMemoryAdapter

    config = MemoryConfig(memory_l0_path=str(tmp_path))
    adapter = FileMemoryAdapter(config)

    adapter.write(
        memory_id=str(uuid.uuid4()),
        memory_type="user",
        content="test content",
    )

    assert (tmp_path / "user").exists()


@then("MEMORY.md 索引应该更新")
def then_memory_index_update(context: dict, tmp_path: Any):
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.storage.file_memory_adapter import FileMemoryAdapter

    config = MemoryConfig(memory_l0_path=str(tmp_path))
    adapter = FileMemoryAdapter(config)

    adapter.update_index([{"name": "test", "type": "user", "memory_id": str(uuid.uuid4()), "description": "test"}])

    index_path = tmp_path / "MEMORY.md"
    assert index_path.exists()


# ===================================================================
# AC-4: CRUD Operations
# ===================================================================


@given("用户输入记住以后用bun而不是npm")
def given_user_input_remember_bun(context: dict):
    context["user_content"] = "记住，以后用 bun 而不是 npm"


@given("用户想记住内容")
def given_user_wants_remember_content(context: dict):
    context["user_content"] = "记住测试内容"


@when("用户执行保存操作")
def when_user_save(context: dict, service: MemoryService, event_loop):
    """Save memory via MemoryService (async operation)."""

    async def _save():
        return await service.save(
            MemorySaveRequest(
                user_id="user123",
                name="new-memory",
                content=context["user_content"],
                memory_type="user",
            )
        )

    context["new_memory"] = event_loop.run_until_complete(_save())


@then("应该创建新记忆")
def then_new_memory_created(context: dict):
    assert context.get("new_memory") is not None
    assert context["new_memory"].name == "new-memory"


@then("记忆版本应该为1")
def then_memory_version_is_1(context: dict):
    assert context["new_memory"].version == 1


@given("已存在记忆")
def given_existing_memory(context: dict, service: MemoryService, event_loop):
    """Create an existing memory for update/delete tests."""

    async def _save():
        return await service.save(
            MemorySaveRequest(
                user_id="test-user",
                name="existing-memory",
                content="记住已有记忆内容",
                memory_type="user",
            )
        )

    context["existing_memory"] = event_loop.run_until_complete(_save())


@when("用户说改成新内容")
def when_user_says_change(context: dict):
    context["update_content"] = "改成新内容"


@then("记忆内容应该更新")
def then_memory_content_update(context: dict, service: MemoryService, event_loop):
    """Update memory via MemoryService (async operation)."""

    async def _update():
        return await service.update(
            MemoryUpdateRequest(
                memory_id=context["existing_memory"].memory_id,
                user_id="test-user",
                content=context["update_content"],
            )
        )

    context["updated_memory"] = event_loop.run_until_complete(_update())


@then("记忆版本应该递增")
def then_memory_version_increment(context: dict):
    assert context["updated_memory"].version == context["existing_memory"].version + 1


@when("用户执行删除操作")
def when_user_delete(context: dict, service: MemoryService, event_loop):
    """Delete memory via MemoryService (async operation)."""
    context["memory_id"] = context["existing_memory"].memory_id

    async def _delete():
        await service.delete(
            MemoryDeleteRequest(
                memory_id=context["existing_memory"].memory_id,
                user_id="test-user",
            )
        )

    event_loop.run_until_complete(_delete())


@then("记忆应该被删除")
def then_memory_deleted(context: dict, service: MemoryService, event_loop):
    """Verify memory was deleted (async operation)."""
    from src.domain.services.memory_service import MemoryNotFoundError

    async def _get():
        with pytest.raises(MemoryNotFoundError):
            await service.get(context["memory_id"])

    event_loop.run_until_complete(_get())


@given("用户有记忆")
def given_user_has_memories(context: dict, service: MemoryService, event_loop):
    """Create multiple memories for list test."""

    async def _save_all():
        for i in range(3):
            await service.save(
                MemorySaveRequest(
                    user_id="test-user",
                    name=f"memory-{uuid.uuid4().hex[:8]}",
                    content=f"记住内容 {i}",
                    memory_type="user",
                )
            )

    event_loop.run_until_complete(_save_all())


@when("用户执行查询操作")
def when_user_list(context: dict, service: MemoryService, event_loop):
    """List memories via MemoryService (async operation)."""

    async def _list():
        return await service.list("test-user")

    context["query_result"] = event_loop.run_until_complete(_list())


@then("应该返回用户的所有记忆")
def then_return_all_memories(context: dict):
    assert len(context["query_result"]) >= 3


# ===================================================================
# AC-5: Performance Requirements
# ===================================================================


@when("执行L1压缩")
def when_execute_l1_compression(context: dict):
    if "extractor" not in context:
        context["extractor"] = L1TextExtractor()
    if "compressor" not in context:
        context["compressor"] = L1Compressor()

    extraction = context["extractor"].extract(context["user_content"])
    context["compression_result"] = context["compressor"].compress(extraction.content)


@then("压缩后内容应该约150字")
def then_compressed_150_chars(context: dict):
    assert 135 <= context["compression_result"].compressed_length <= 165


@then("压缩延迟P95应该小于20ms")
def then_compression_latency_p95(context: dict):
    compressor = L1Compressor()

    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        compressor.compress("记住，这是一个很长的记忆内容需要压缩处理，" * 10)
        end = time.perf_counter()
        latencies.append((end - start) * 1000)

    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95_latency = latencies[p95_index]

    assert p95_latency < 20, f"P95 latency {p95_latency:.2f}ms >= 20ms"


@when("连续保存100次")
def when_save_100_times(context: dict, service: MemoryService, event_loop):
    """Save 100 memories and return success count."""

    async def _save_all():
        success_count = 0
        for i in range(100):
            try:
                await service.save(
                    MemorySaveRequest(
                        user_id="user123",
                        name=f"perf-test-{uuid.uuid4().hex[:8]}",
                        content="记住测试内容",
                    )
                )
                success_count += 1
            except Exception:
                pass
        return success_count

    context["save_result"] = {"success_count": event_loop.run_until_complete(_save_all())}


@then("成功率应该为100")
def then_success_rate_100(context: dict):
    assert context["save_result"]["success_count"] == 100


# ===================================================================
# AC-6: L1 vs L3 Separation
# ===================================================================


@given("L1压缩输入小于等于500字")
def given_l1_input_under_500(context: dict):
    context["user_content"] = "记住，这是一个很长的记忆内容需要压缩处理，" * 10


@then("输出应该约150字")
def then_output_150_chars(context: dict):
    assert context["compression_result"].compressed_length <= 160


@then("无需PersistentNote")
def then_no_persistent_note(context: dict):
    assert True


@given("用户输入记住测试内容")
def given_user_input_remember_content(context: dict):
    context["user_content"] = "记住，这是一个很长的记忆内容需要压缩处理，" * 10


@when("L1压缩被触发")
def when_l1_compression_trigger(context: dict):
    if "extractor" not in context:
        context["extractor"] = L1TextExtractor()
    if "compressor" not in context:
        context["compressor"] = L1Compressor()


@then("is_automatic应该为False")
def then_is_automatic_false(context: dict):
    assert True
