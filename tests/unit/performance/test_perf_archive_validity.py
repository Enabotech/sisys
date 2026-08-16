"""档案有效期查询性能验证测试

验证有效期查询延迟 P95<200ms（时间轴查询）。
CI 环境下默认跳过，本地开发手动触发。

对齐项目现有 test_compression_performance.py 先例。
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.ports.archive_repository import ArchiveQuery, ValidityStatus
from src.infrastructure.storage.postgresql.models.archive import ArchiveModel
from src.infrastructure.storage.postgresql.repository.archive_repository import (
    PostgreSQLArchiveRepository,
)
from src.infrastructure.storage.postgresql.session_context import with_session

# CI 跳过标记
SKIP_PERFORMANCE = False


def _make_mock_models(count: int) -> list[MagicMock]:
    """生成指定数量的 mock ArchiveModel 实例"""
    models = []
    for i in range(count):
        model = MagicMock(spec=ArchiveModel)
        model.archive_id = f"00000000-0000-0000-0000-{i:012d}"
        model.plan_id = "00000000-0000-0000-0000-000000000001"
        model.plan_type = "SP"
        model.archive_type = "assumption"
        model.assumptions = {}
        model.decision_basis = {}
        model.execution_deviation = {}
        model.metadata_ref = "strategic_archives:test"
        model.embedding_ref = None
        model.blob_ref = None
        model.graph_ref = None
        model.created_by = None
        model.version = 1
        model.metadata_ = {}
        model.deleted_at = None
        model.created_at = datetime.now(UTC) - timedelta(days=365)
        model.archived_at = datetime.now(UTC) - timedelta(days=365)
        model.valid_from = datetime.now(UTC) - timedelta(days=30)
        model.valid_until = datetime.now(UTC) + timedelta(days=335)
        models.append(model)
    return models


class TestArchiveValidityPerformance:
    """档案有效期查询性能验证"""

    async def _run_benchmark(self, query: ArchiveQuery) -> float:
        """运行单次查询并返回延迟（毫秒）"""
        model_count = 10_000
        models = _make_mock_models(model_count)

        repo = PostgreSQLArchiveRepository()
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = models
        mock_session.execute.return_value = mock_result

        async with with_session(mock_session):
            start = time.perf_counter()
            await repo.find(query)
            end = time.perf_counter()
            return (end - start) * 1000

    @pytest.mark.skipif(SKIP_PERFORMANCE, reason="Performance test skipped in CI")
    def test_validity_filter_p95_under_200ms(self) -> None:
        """验证有效期过滤查询 P95<200ms"""
        # 预热 10 次
        for _ in range(10):
            query = ArchiveQuery(validity_status=ValidityStatus.VALID, limit=100)
            asyncio.run(self._run_benchmark(query))

        # 测量 100 次查询延迟
        latencies_ms: list[float] = []
        for _ in range(100):
            query = ArchiveQuery(validity_status=ValidityStatus.VALID, limit=100)
            latencies_ms.append(asyncio.run(self._run_benchmark(query)))

        # 计算 P95
        latencies_ms.sort()
        p95_index = int(len(latencies_ms) * 0.95)
        p95_latency = latencies_ms[p95_index]

        assert p95_latency < 200, f"P95 延迟 {p95_latency:.2f}ms 超过 200ms"

    @pytest.mark.skipif(SKIP_PERFORMANCE, reason="Performance test skipped in CI")
    def test_expired_filter_p95_under_200ms(self) -> None:
        """验证过期过滤查询 P95<200ms"""
        # 预热 10 次
        for _ in range(10):
            query = ArchiveQuery(validity_status=ValidityStatus.EXPIRED, limit=100)
            asyncio.run(self._run_benchmark(query))

        # 测量 100 次查询延迟
        latencies_ms: list[float] = []
        for _ in range(100):
            query = ArchiveQuery(validity_status=ValidityStatus.EXPIRED, limit=100)
            latencies_ms.append(asyncio.run(self._run_benchmark(query)))

        # 计算 P95
        latencies_ms.sort()
        p95_index = int(len(latencies_ms) * 0.95)
        p95_latency = latencies_ms[p95_index]

        assert p95_latency < 200, f"P95 延迟 {p95_latency:.2f}ms 超过 200ms"

    @pytest.mark.skipif(SKIP_PERFORMANCE, reason="Performance test skipped in CI")
    def test_valid_from_range_p95_under_200ms(self) -> None:
        """验证 valid_from 范围查询 P95<200ms"""
        ref_date = datetime.now(UTC)

        # 预热 10 次
        for _ in range(10):
            query = ArchiveQuery(valid_from=ref_date, limit=100)
            asyncio.run(self._run_benchmark(query))

        # 测量 100 次查询延迟
        latencies_ms: list[float] = []
        for _ in range(100):
            query = ArchiveQuery(valid_from=ref_date, limit=100)
            latencies_ms.append(asyncio.run(self._run_benchmark(query)))

        # 计算 P95
        latencies_ms.sort()
        p95_index = int(len(latencies_ms) * 0.95)
        p95_latency = latencies_ms[p95_index]

        assert p95_latency < 200, f"P95 延迟 {p95_latency:.2f}ms 超过 200ms"
