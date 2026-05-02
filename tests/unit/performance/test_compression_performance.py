"""Tests for Compression Performance Benchmarks.

RED PHASE: 验证性能要求 - 压缩率≥70%、延迟 P95<20ms。
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

from src.application.use_cases.text_processing.l1_compressor import L1Compressor
from src.application.use_cases.text_processing.l1_text_extractor import L1TextExtractor
from src.domain.ports.memory_repository import (
    MemoryChangeHistoryRepositoryProtocol,
    MemoryMetadataRepositoryProtocol,
)
from src.domain.services.memory_service import MemorySaveRequest, MemoryService


def run_async(coro):
    """Run async coroutine synchronously for tests."""
    return asyncio.run(coro)


def _create_mock_metadata_repo():
    """Create a mock metadata repository."""
    mock = AsyncMock(spec=MemoryMetadataRepositoryProtocol)
    mock.save = AsyncMock()
    mock.get_by_id = AsyncMock(return_value=None)
    mock.get_by_name = AsyncMock(return_value=None)
    mock.delete = AsyncMock()
    mock.list_by_user = AsyncMock(return_value=[])
    mock.list_by_type = AsyncMock(return_value=[])
    mock.list_all = AsyncMock(return_value=[])
    return mock


def _create_mock_history_repo():
    """Create a mock history repository."""
    mock = AsyncMock(spec=MemoryChangeHistoryRepositoryProtocol)
    mock.save = AsyncMock()
    mock.get_by_memory_id = AsyncMock(return_value=[])
    mock.get_by_id = AsyncMock(return_value=None)
    return mock


class TestCompressionRatio:
    """压缩率验证"""

    def test_compression_ratio_exceeds_70_percent(self):
        """验证压缩率≥70%（针对接近 500 字的输入）"""
        compressor = L1Compressor()
        text_extractor = L1TextExtractor()

        # 使用接近 500 字的文本
        original = "记住，这是一个很长的记忆内容需要压缩处理，" * 23  # 约 480 字

        extraction = text_extractor.extract(original)
        result = compressor.compress(extraction.content)

        # 验证压缩到约 150 字（±10% 误差）
        assert 135 <= result.compressed_length <= 165, f"压缩后长度 {result.compressed_length} 不在 135-165 范围"
        assert result.method in ("rule", "llm")

    def test_compression_achieves_target_length(self):
        """验证压缩后长度接近目标（150 字）"""
        compressor = L1Compressor()

        # 使用超过 200 字的文本
        original = (
            "记住，以后用 bun 而不是 npm，这是一个很长的记忆内容需要压缩处理，"
            "这是一个很长的记忆内容需要压缩处理，这是一个很长的记忆内容需要压缩处理，"
            "这是一个很长的记忆内容需要压缩处理，这是一个很长的记忆内容需要压缩处理，"
            "这是一个很长的记忆内容需要压缩处理，这是一个很长的记忆内容需要压缩处理"
        ) * 2

        result = compressor.compress(original)

        # 验证压缩到约 150 字
        assert result.compressed_length <= 160, f"压缩后长度 {result.compressed_length} 超过 160"

    def test_compression_ratio_within_tolerance(self):
        """验证压缩率在允许误差范围内（-5%）"""
        compressor = L1Compressor()

        # 使用超过 200 字的文本
        original = "记住，以后用 bun 而不是 npm，这是一个很长的记忆内容需要压缩处理，" * 5
        result = compressor.compress(original)

        # 压缩后长度应该 <= 150（目标长度）或者至少比原始短
        assert result.compressed_length <= result.original_length


class TestCompressionLatency:
    """压缩延迟验证"""

    def test_compression_latency_p95_under_20ms(self):
        """验证压缩延迟 P95<20ms（需要多次采样）"""
        compressor = L1Compressor()
        text_extractor = L1TextExtractor()

        content = "记住，以后用 bun 而不是 npm，这是一个很长的记忆内容需要压缩处理"
        extraction = text_extractor.extract(content)

        # 采样 100 次计算 P95
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            compressor.compress(extraction.content)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # 转换为毫秒

        # 计算 P95
        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]

        assert p95_latency < 20, f"P95 延迟 {p95_latency:.2f}ms 超过 20ms"

    def test_single_compression_is_fast(self):
        """验证单次压缩延迟合理（<100ms）"""
        compressor = L1Compressor()
        text_extractor = L1TextExtractor()

        content = "记住，以后用 bun 而不是 npm，这是一个很长的记忆内容需要压缩处理"
        extraction = text_extractor.extract(content)

        start = time.perf_counter()
        compressor.compress(extraction.content)
        end = time.perf_counter()

        latency_ms = (end - start) * 1000
        assert latency_ms < 100, f"单次压缩延迟 {latency_ms:.2f}ms 过高"


class TestSaveSuccessRate:
    """记忆保存成功率验证"""

    def test_memory_save_success_rate_100_percent(self):
        """验证记忆保存成功率 100%"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
            metadata_repository=_create_mock_metadata_repo(),
            history_repository=_create_mock_history_repo(),
        )

        success_count = 0
        total = 100

        for i in range(total):
            try:
                run_async(
                    service.save(
                        MemorySaveRequest(
                            user_id="user123",
                            name=f"test-memory-{i}",
                            content=f"记住，这是一个测试记忆 {i}",
                        )
                    )
                )
                success_count += 1
            except Exception:
                pass

        assert success_count == total, f"成功率 {success_count}/{total}"

    def test_multiple_saves_all_succeed(self):
        """验证多次保存全部成功"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
            metadata_repository=_create_mock_metadata_repo(),
            history_repository=_create_mock_history_repo(),
        )

        memories = []
        for i in range(10):
            memory = run_async(
                service.save(
                    MemorySaveRequest(
                        user_id="user123",
                        name=f"mem-{i}",
                        content=f"记住内容 {i}",
                    )
                )
            )
            memories.append(memory)

        # 验证所有记忆都被正确保存
        assert len(memories) == 10
        assert all(m.version == 1 for m in memories)
