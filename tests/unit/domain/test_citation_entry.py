"""引文条目 VO 单元测试（Story 6-5b Task 1 循环 A）。

覆盖面：
- 合法构造三态：resolved（全字段）/point_missing/document_missing（降级
  空串形态）+ resolved page=0 子形态（页码缺失非独立态——status 值域冻结）
- frozen 不可变
- __post_init__ 六查守卫：index≥1/chunk_id 非空/status 值域三元组/
  page≥0/document_id 非空时 UUID 格式——违例抛 EntityValidationError（242）

Run with:
    poetry run pytest tests/unit/domain/test_citation_entry.py -v
"""

import dataclasses

import pytest

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.citation_entry import CitationEntry


class TestCitationEntryValidConstruction:
    """合法构造（三态 + 页缺失子形态）。"""

    def test_resolved_full_fields(self) -> None:
        """resolved 正常态（全字段值级——引文解析成功产物形态）。"""
        entry = CitationEntry(
            index=1,
            document_id="0b6a6c2e-6f4e-4a3b-9c2d-1e2f3a4b5c6d",
            chunk_id="9f8e7d6c-5b4a-4c3d-2e1f-0a9b8c7d6e5f",
            filename="战略研判参考报告.pdf",
            page=12,
            status="resolved",
        )
        assert entry.index == 1
        assert entry.document_id == "0b6a6c2e-6f4e-4a3b-9c2d-1e2f3a4b5c6d"
        assert entry.chunk_id == "9f8e7d6c-5b4a-4c3d-2e1f-0a9b8c7d6e5f"
        assert entry.filename == "战略研判参考报告.pdf"
        assert entry.page == 12
        assert entry.status == "resolved"

    def test_point_missing_degraded(self) -> None:
        """point_missing 降级态（get_point 无点——document_id/filename 空串 + page 0）。"""
        entry = CitationEntry(
            index=2,
            document_id="",
            chunk_id="missing-chunk-uuid",
            filename="",
            page=0,
            status="point_missing",
        )
        assert entry.status == "point_missing"
        assert entry.document_id == ""
        assert entry.filename == ""
        assert entry.page == 0

    def test_document_missing_degraded(self) -> None:
        """document_missing 降级态（Qdrant 点在而 documents 行缺）。"""
        entry = CitationEntry(
            index=3,
            document_id="",
            chunk_id="orphan-chunk-uuid",
            filename="",
            page=0,
            status="document_missing",
        )
        assert entry.status == "document_missing"

    def test_resolved_page_zero_substate(self) -> None:
        """resolved + page=0 子形态（文档在而 chunks 元数据无该 chunk_id——页码不可得非独立态）。"""
        entry = CitationEntry(
            index=1,
            document_id="0b6a6c2e-6f4e-4a3b-9c2d-1e2f3a4b5c6d",
            chunk_id="9f8e7d6c-5b4a-4c3d-2e1f-0a9b8c7d6e5f",
            filename="无页码元数据文档.pdf",
            page=0,
            status="resolved",
        )
        assert entry.status == "resolved"
        assert entry.page == 0  # 渲染层 0→'-'

    def test_status_value_domain_frozen(self) -> None:
        """status 值域三元组冻结（类级常量单源——防散落字面）。"""
        assert CitationEntry.VALID_STATUSES == ("resolved", "point_missing", "document_missing")

    def test_frozen_immutability(self) -> None:
        """frozen dataclass 不可变（赋值抛 FrozenInstanceError）。"""
        entry = CitationEntry(
            index=1,
            document_id="",
            chunk_id="chunk-x",
            filename="",
            page=0,
            status="point_missing",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(entry, "index", 99)  # setattr 动态形态——dataclass frozen __setattr__ 运行时守卫


class TestCitationEntryValidation:
    """__post_init__ 六查守卫（违例抛 242）。"""

    def test_index_zero_raises_242(self) -> None:
        """index=0（去重保序首现次序从 1 起）抛 242。"""
        with pytest.raises(EntityValidationError) as exc_info:
            CitationEntry(index=0, document_id="", chunk_id="c", filename="", page=0, status="point_missing")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_index_negative_raises_242(self) -> None:
        """负 index 抛 242。"""
        with pytest.raises(EntityValidationError):
            CitationEntry(index=-1, document_id="", chunk_id="c", filename="", page=0, status="resolved")

    def test_empty_chunk_id_raises_242(self) -> None:
        """chunk_id 空串抛 242（引文锚定标识必填）。"""
        with pytest.raises(EntityValidationError):
            CitationEntry(index=1, document_id="", chunk_id="", filename="", page=0, status="resolved")

    def test_invalid_status_raises_242(self) -> None:
        """status 非法值（如 page_missing——页缺失是 resolved 子形态非独立态）抛 242。"""
        with pytest.raises(EntityValidationError) as exc_info:
            CitationEntry(index=1, document_id="", chunk_id="c", filename="", page=0, status="page_missing")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_page_negative_raises_242(self) -> None:
        """page=-1 抛 242（页码 ≥0——0 表不可得）。"""
        with pytest.raises(EntityValidationError):
            CitationEntry(index=1, document_id="", chunk_id="c", filename="", page=-1, status="resolved")

    def test_non_uuid_document_id_raises_242(self) -> None:
        """document_id 非空但非 UUID 格式抛 242（uuid.UUID 试解析兜底）。"""
        with pytest.raises(EntityValidationError):
            CitationEntry(
                index=1,
                document_id="not-a-uuid",
                chunk_id="c",
                filename="x.pdf",
                page=1,
                status="resolved",
            )

    def test_valid_uuid_document_id_accepted(self) -> None:
        """document_id 合法 UUID 字符串通过（Qdrant payload str→显式转换链的产物形态）。"""
        entry = CitationEntry(
            index=1,
            document_id="00000000-0000-4000-8000-000000000001",
            chunk_id="c",
            filename="x.pdf",
            page=1,
            status="resolved",
        )
        assert entry.document_id == "00000000-0000-4000-8000-000000000001"
