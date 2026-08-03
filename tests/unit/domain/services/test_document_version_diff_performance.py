"""文档版本快照性能基准测试

验证 AC-1/AC-2 性能指标：
- 版本快照创建延迟 P95 < 100ms（AC-1）
- 差异计算延迟 P95 < 200ms（AC-2）
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

from src.domain.services.document_version_diff_service import compute_diff
from src.domain.value_objects.document_version import DocumentVersionSnapshot


class TestVersionSnapshotCreationPerformance:
    """验证版本快照创建性能（AC-1: P95 < 100ms）"""

    def test_create_snapshot_value_object_performance(self) -> None:
        """DocumentVersionSnapshot 构造性能测试"""
        times: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            DocumentVersionSnapshot(
                document_id=uuid4(),
                version=1,
                snapshot_id=uuid4(),
                created_at=datetime.now(UTC),
                created_by="user-1",
                change_description="测试",
                diff_summary="initial version",
                diff_json={"changed_fields": [], "is_initial": True},
            )
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 < 1.0, f"值对象构造 P95={p95:.3f}ms，预期 < 1ms"

    def test_compute_diff_metadata_performance(self) -> None:
        """compute_diff 元数据差异计算性能测试"""
        old_meta = {f"field_{i}": f"old_value_{i}" for i in range(100)}
        new_meta = {f"field_{i}": f"new_value_{i}" for i in range(100)}

        times: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            compute_diff(
                old_metadata=old_meta,
                new_metadata=new_meta,
                is_initial=False,
            )
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 < 10.0, f"元数据差异计算 P95={p95:.3f}ms，预期 < 10ms"

    def test_compute_diff_content_performance(self) -> None:
        """compute_diff 内容差异计算性能测试（含 difflib）"""
        old_content = "\n".join(f"line {i}: old content here" for i in range(1000))
        new_content = "\n".join(f"line {i}: new content here" for i in range(1000))

        times: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            compute_diff(
                old_metadata={},
                new_metadata={},
                old_content_summary=old_content,
                new_content_summary=new_content,
                is_initial=False,
            )
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 < 50.0, f"内容差异计算 P95={p95:.3f}ms，预期 < 50ms"

    def test_initial_version_instant(self) -> None:
        """首次版本标记应即时返回（无计算开销）"""
        times: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            diff = compute_diff(
                old_metadata={},
                new_metadata={},
                is_initial=True,
            )
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

            assert diff.diff_summary == "initial version"
            assert diff.changed_fields == []
            assert diff.is_initial is True

        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 < 0.5, f"首次版本标记 P95={p95:.3f}ms，预期 < 0.5ms"

    def test_no_changes_instant(self) -> None:
        """无变更检测应即时返回"""
        times: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            diff = compute_diff(
                old_metadata={"key": "value"},
                new_metadata={"key": "value"},
                old_content_summary="same content",
                new_content_summary="same content",
                is_initial=False,
            )
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

            assert diff.diff_summary == "no changes"
            assert diff.changed_fields == []

        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 < 0.5, f"无变更检测 P95={p95:.3f}ms，预期 < 0.5ms"
