"""档案有效期查询性能基准测试

使用真实 PostgreSQL 验证有效期查询延迟 P95<200ms（时间轴查询）。
基准数据量级：≥10,000 条记录，连续执行 100 次查询取 P95 百分位，
执行 10 次预热后开始测量。

前置条件：
- PostgreSQL 服务运行在 localhost:5432（或通过 get_test_env() 配置）

运行方式：
    poetry run pytest tests/benchmark/test_benchmark_archive_validity.py -v
    poetry run pytest tests/benchmark/test_benchmark_archive_validity.py -v -k "validity_filter"
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.ports.archive_repository import ArchiveQuery, ValidityStatus
from src.infrastructure.storage.postgresql.models import Base
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.repository.archive_repository import (
    PostgreSQLArchiveRepository,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from tests.environments import get_test_env

logger = logging.getLogger(__name__)

# 性能目标阈值
P95_TARGET_MS = 200.0

# 基准测试参数
BENCHMARK_RECORD_COUNT = 10_000  # 数据量级：≥10,000 条记录
WARMUP_ITERATIONS = 10  # 预热次数
MEASURE_ITERATIONS = 100  # 测量次数


def _pg_available() -> bool:
    """检查 PostgreSQL 是否可用"""
    import asyncio

    import asyncpg

    env = get_test_env()

    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(
                host=env.postgres.host,
                port=env.postgres.port,
                user=env.postgres.username,
                password=env.postgres.password,
                database=env.postgres.database,
            )
            await conn.close()
            return True
        except Exception:
            return False

    return asyncio.run(_check())


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture(scope="module")
def event_loop():
    """模块级事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def pg_config():
    """真实 PostgreSQL 配置"""
    env = get_test_env()
    return {
        "host": env.postgres.host,
        "port": env.postgres.port,
        "database": env.postgres.database,
        "username": env.postgres.username,
        "password": env.postgres.password,
    }


@pytest.fixture(scope="module")
def pg_available(pg_config, event_loop) -> bool:
    """检查 PostgreSQL 是否可用"""
    import asyncpg

    async def _check():
        try:
            conn = await asyncpg.connect(
                host=pg_config["host"],
                port=pg_config["port"],
                user=pg_config["username"],
                password=pg_config["password"],
                database=pg_config["database"],
            )
            await conn.close()
            return True
        except Exception:
            return False

    result: bool = event_loop.run_until_complete(_check())
    return result


@pytest.fixture(scope="module")
def db_engine(pg_config) -> PostgreSQLManager:
    """真实数据库引擎"""
    from src.infrastructure.config.postgresql import PostgreSQLConfig

    config = PostgreSQLConfig(
        host=pg_config["host"],
        port=pg_config["port"],
        database=pg_config["database"],
        username=pg_config["username"],
        password=pg_config["password"],
        pool_size=2,
        max_overflow=5,
    )
    return PostgreSQLManager(config)


@pytest.fixture(scope="module")
def benchmark_data(db_engine, pg_available, event_loop) -> list[StrategicArchive] | None:
    """生成基准测试数据（模块级一次性准备，所有测试复用）

    在独立 session 中插入 ≥10,000 条档案记录并提交，
    确保索引在真实查询中生效。
    """
    if not pg_available:
        pytest.skip("PostgreSQL not available")
        return None

    async_engine = db_engine.get_async_engine()

    # 确保表结构存在
    try:
        Base.metadata.create_all(db_engine.get_sync_engine())
    except Exception:
        pass

    from sqlalchemy.ext.asyncio import AsyncSession

    session = AsyncSession(async_engine)
    repo = PostgreSQLArchiveRepository()
    token = set_session(session)

    plan_id = uuid4()
    base_time = datetime.now(UTC)
    created: list[StrategicArchive] = []

    try:
        # 分批插入数据，避免单次事务过大
        batch_size = 500
        total_batches = BENCHMARK_RECORD_COUNT // batch_size

        for batch_idx in range(total_batches):
            batch = []
            for i in range(batch_size):
                offset = batch_idx * batch_size + i
                # 前半部分有效，后半部分过期，混合 valid_from/valid_until 分布
                if offset < BENCHMARK_RECORD_COUNT // 2:
                    vf = base_time - timedelta(days=30)
                    vu = base_time + timedelta(days=335)
                else:
                    vf = base_time - timedelta(days=400)
                    vu = base_time - timedelta(days=30)

                archive = StrategicArchive(
                    archive_id=uuid4(),
                    plan_id=plan_id,
                    plan_type="SP",
                    archive_type=ArchiveType.ASSUMPTION,
                    archived_at=base_time - timedelta(days=365 - offset % 365),
                    valid_from=vf,
                    valid_until=vu,
                    metadata_ref=f"strategic_archives:benchmark:{offset}",
                )
                batch.append(archive)

            for a in batch:
                event_loop.run_until_complete(repo.save(a))
            created.extend(batch)

            if (batch_idx + 1) % 5 == 0:
                logger.info("已插入 %d/%d 条基准数据", len(created), BENCHMARK_RECORD_COUNT)

        # 提交事务，确保数据固化且索引生效
        event_loop.run_until_complete(session.commit())
        logger.info("基准数据准备完成: %d 条记录", len(created))
    except Exception as e:
        logger.error("基准数据准备失败: %s", e)
        event_loop.run_until_complete(session.rollback())
        raise
    finally:
        reset_session(token)
        event_loop.run_until_complete(session.close())

    return created


# ===================================================================
# 基准测试
# ===================================================================


class TestArchiveValidityBenchmark:
    """档案有效期查询性能基准测试"""

    @pytest.mark.skipif(not _pg_available(), reason="PostgreSQL not available")
    def test_validity_filter_p95_under_200ms(
        self,
        benchmark_data,
        db_engine,
        event_loop,
    ) -> None:
        """验证有效期过滤（valid）查询 P95<200ms"""
        if benchmark_data is None:
            pytest.skip("No benchmark data")

        async_engine = db_engine.get_async_engine()
        from sqlalchemy.ext.asyncio import AsyncSession

        session = AsyncSession(async_engine)
        repo = PostgreSQLArchiveRepository()
        token = set_session(session)

        try:
            # 预热 10 次
            for _ in range(WARMUP_ITERATIONS):
                query = ArchiveQuery(validity_status=ValidityStatus.VALID, limit=100)
                event_loop.run_until_complete(repo.find(query))

            # 测量 100 次查询延迟
            latencies_ms: list[float] = []
            for _ in range(MEASURE_ITERATIONS):
                query = ArchiveQuery(validity_status=ValidityStatus.VALID, limit=100)
                t0 = time.perf_counter()
                event_loop.run_until_complete(repo.find(query))
                t1 = time.perf_counter()
                latencies_ms.append((t1 - t0) * 1000)

            # 计算 P95
            latencies_ms.sort()
            p95_index = int(len(latencies_ms) * 0.95)
            p95_latency = latencies_ms[p95_index]
            p50_latency = statistics.median(latencies_ms)

            logger.info(
                "validity_filter: P50=%.2fms, P95=%.2fms, 采样=%d次",
                p50_latency,
                p95_latency,
                len(latencies_ms),
            )

            assert p95_latency < P95_TARGET_MS, f"P95 延迟 {p95_latency:.2f}ms 超过 {P95_TARGET_MS:.0f}ms 目标"
        finally:
            reset_session(token)
            event_loop.run_until_complete(session.close())

    @pytest.mark.skipif(not _pg_available(), reason="PostgreSQL not available")
    def test_expired_filter_p95_under_200ms(
        self,
        benchmark_data,
        db_engine,
        event_loop,
    ) -> None:
        """验证过期过滤查询 P95<200ms"""
        if benchmark_data is None:
            pytest.skip("No benchmark data")

        async_engine = db_engine.get_async_engine()
        from sqlalchemy.ext.asyncio import AsyncSession

        session = AsyncSession(async_engine)
        repo = PostgreSQLArchiveRepository()
        token = set_session(session)

        try:
            # 预热 10 次
            for _ in range(WARMUP_ITERATIONS):
                query = ArchiveQuery(validity_status=ValidityStatus.EXPIRED, limit=100)
                event_loop.run_until_complete(repo.find(query))

            # 测量 100 次查询延迟
            latencies_ms: list[float] = []
            for _ in range(MEASURE_ITERATIONS):
                query = ArchiveQuery(validity_status=ValidityStatus.EXPIRED, limit=100)
                t0 = time.perf_counter()
                event_loop.run_until_complete(repo.find(query))
                t1 = time.perf_counter()
                latencies_ms.append((t1 - t0) * 1000)

            # 计算 P95
            latencies_ms.sort()
            p95_index = int(len(latencies_ms) * 0.95)
            p95_latency = latencies_ms[p95_index]
            p50_latency = statistics.median(latencies_ms)

            logger.info(
                "expired_filter: P50=%.2fms, P95=%.2fms, 采样=%d次",
                p50_latency,
                p95_latency,
                len(latencies_ms),
            )

            assert p95_latency < P95_TARGET_MS, f"P95 延迟 {p95_latency:.2f}ms 超过 {P95_TARGET_MS:.0f}ms 目标"
        finally:
            reset_session(token)
            event_loop.run_until_complete(session.close())

    @pytest.mark.skipif(not _pg_available(), reason="PostgreSQL not available")
    def test_valid_from_range_p95_under_200ms(
        self,
        benchmark_data,
        db_engine,
        event_loop,
    ) -> None:
        """验证 valid_from 范围查询 P95<200ms"""
        if benchmark_data is None:
            pytest.skip("No benchmark data")

        ref_date = datetime.now(UTC) - timedelta(days=200)

        async_engine = db_engine.get_async_engine()
        from sqlalchemy.ext.asyncio import AsyncSession

        session = AsyncSession(async_engine)
        repo = PostgreSQLArchiveRepository()
        token = set_session(session)

        try:
            # 预热 10 次
            for _ in range(WARMUP_ITERATIONS):
                query = ArchiveQuery(valid_from=ref_date, limit=100)
                event_loop.run_until_complete(repo.find(query))

            # 测量 100 次查询延迟
            latencies_ms: list[float] = []
            for _ in range(MEASURE_ITERATIONS):
                query = ArchiveQuery(valid_from=ref_date, limit=100)
                t0 = time.perf_counter()
                event_loop.run_until_complete(repo.find(query))
                t1 = time.perf_counter()
                latencies_ms.append((t1 - t0) * 1000)

            # 计算 P95
            latencies_ms.sort()
            p95_index = int(len(latencies_ms) * 0.95)
            p95_latency = latencies_ms[p95_index]
            p50_latency = statistics.median(latencies_ms)

            logger.info(
                "valid_from_range: P50=%.2fms, P95=%.2fms, 采样=%d次",
                p50_latency,
                p95_latency,
                len(latencies_ms),
            )

            assert p95_latency < P95_TARGET_MS, f"P95 延迟 {p95_latency:.2f}ms 超过 {P95_TARGET_MS:.0f}ms 目标"
        finally:
            reset_session(token)
            event_loop.run_until_complete(session.close())
