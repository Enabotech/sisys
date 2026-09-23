"""Story 4.4 — Docker 沙箱性能基准测试(AC-9)

热启动 P95 < 2s + 冷启动 < 30s + 并发 ≥ 10 + 配额边界。

**执行约束**: 冷启动用例会 rmi 钉版镜像,与并行 worker 的容器引用冲突——
xdist 并行环境(-n auto)下该用例自动 skip。完整基准请独立执行:

    pytest tests/benchmark/test_performance_docker_sandbox.py -n 0 -m benchmark

Docker daemon 不可用时动态 pytest.skip。
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time
import uuid
from collections.abc import AsyncGenerator

import pytest

from src.domain.exceptions import SandboxQuotaExceededError
from src.infrastructure.external_services.sandbox.aiodocker_sandbox_adapter import (
    AioDockerSandboxAdapter,
)
from src.infrastructure.storage.inmemory.sandbox_session_repository import (
    InMemorySandboxSessionRepository,
)

_PINNED_IMAGE = "python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534"
_PINNED_NAME_TAG = "python:3.11-slim"

pytestmark = [pytest.mark.integration, pytest.mark.docker, pytest.mark.benchmark, pytest.mark.slow]


@pytest.fixture
async def docker_daemon_or_skip() -> None:
    """动态检查 Docker daemon 可用性"""
    import aiodocker

    client = aiodocker.Docker()
    try:
        await client.version()
    except Exception as exc:
        await client.close()
        pytest.skip(f"Docker daemon 不可用: {exc}")
    await client.close()


@pytest.fixture
async def adapter(docker_daemon_or_skip: None) -> AsyncGenerator[AioDockerSandboxAdapter, None]:
    instance = AioDockerSandboxAdapter(session_repo=InMemorySandboxSessionRepository())
    yield instance
    await instance.aclose()


def _session_id() -> str:
    return f"perf-{uuid.uuid4().hex[:12]}"


class TestWarmStartLatency:
    """热启动 P95 < 2s(AC-9,修正验收层 P100 当 P95 的口径)"""

    async def test_warm_start_p95_under_2s(self, adapter: AioDockerSandboxAdapter) -> None:
        # warmup: 1 次 start/stop 不计入样本(消除首样本镜像/pull 污染)
        warmup_id = _session_id()
        await adapter.start_container(warmup_id)
        await adapter.stop_container(warmup_id)

        latencies: list[float] = []
        for _ in range(20):
            sid = _session_id()
            started = time.perf_counter()
            await adapter.start_container(sid)
            latencies.append(time.perf_counter() - started)
            await adapter.stop_container(sid)

        # N=20 样本 P95: statistics.quantiles(n=20)[18] 恰为第 19/20 分位
        p95 = statistics.quantiles(latencies, n=20)[18]
        assert p95 < 2.0, f"热启动 P95={p95:.3f}s 超阈值 2s(样本: {[f'{x:.2f}' for x in sorted(latencies)]})"


class TestColdStart:
    """冷启动 < 30s(含镜像拉取,AC-9;验收层空断言伪覆盖的真实化)"""

    @pytest.mark.skipif(
        os.environ.get("PYTEST_XDIST_WORKER") is not None,
        reason=(
            "rmi 与并行 worker 容器引用冲突;"
            "独立执行: pytest tests/benchmark/test_performance_docker_sandbox.py -n 0 -m benchmark"
        ),
    )
    async def test_cold_start_under_30s(self, adapter: AioDockerSandboxAdapter) -> None:
        import aiodocker

        client = aiodocker.Docker()
        try:
            # 删除本地镜像确保真实冷启动(rmi 前删除本用例关联容器——本用例尚未创建)
            try:
                await client.images.delete(_PINNED_NAME_TAG, force=False)
            except Exception:
                pass  # 镜像不存在或被引用(独立执行时无引用)均不阻断

            started = time.perf_counter()
            sid = _session_id()
            await adapter.start_container(sid)
            cold_elapsed = time.perf_counter() - started
            await adapter.stop_container(sid)

            assert cold_elapsed < 30.0, f"冷启动 {cold_elapsed:.1f}s 超阈值 30s"
        finally:
            # 恢复镜像缓存供后续用例
            try:
                await client.images.pull(_PINNED_NAME_TAG)
            except Exception:
                pass
            await client.close()


class TestConcurrencyThroughput:
    """并发 ≥ 10(AC-9 性能基准)"""

    async def test_concurrent_10_throughput(self, adapter: AioDockerSandboxAdapter) -> None:
        session_ids = [_session_id() for _ in range(10)]

        async def _lifecycle(sid: str) -> None:
            await adapter.start_container(sid)
            await adapter.execute_code(sid, "print('x')")
            await adapter.stop_container(sid)

        started = time.perf_counter()
        results = await asyncio.gather(*(_lifecycle(sid) for sid in session_ids), return_exceptions=True)
        wall = time.perf_counter() - started

        # 结果导向断言: 10 个会话全部成功(wall-time 仅观测日志,满负载并行下硬阈值 flaky)
        failures = [r for r in results if isinstance(r, BaseException)]
        assert not failures, f"并发会话失败 {len(failures)}/10: {failures[0]}"
        assert wall < 120.0, f"10 并发耗时 {wall:.1f}s 异常(疑似串行退化或 daemon 卡死)"


class TestQuotaBoundary:
    """配额上限边界(AC-9 加压验证;小参数化避免真开 50 容器)"""

    async def test_quota_boundary_rejects_overflow(self, docker_daemon_or_skip: None) -> None:
        # 类变量计数基线快照(同 worker 前序用例泄漏防护):动态容量 = 基线 + 2
        baseline = AioDockerSandboxAdapter._running_count
        adapter = AioDockerSandboxAdapter(max_concurrent=baseline + 2, session_repo=InMemorySandboxSessionRepository())
        started: list[str] = []
        try:
            for _ in range(2):
                sid = _session_id()
                await adapter.start_container(sid)
                started.append(sid)
            # 第 3 个必抛 318(与基线无关,断言永远稳定)
            with pytest.raises(SandboxQuotaExceededError) as exc_info:
                await adapter.start_container(_session_id())
            assert exc_info.value.code == "EXCEPTION_318"
        finally:
            for sid in started:
                await adapter.stop_container(sid)
            await adapter.aclose()
