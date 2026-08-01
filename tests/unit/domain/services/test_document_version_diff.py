"""文档版本差异计算领域服务单元测试

测试 compute_diff 纯函数：
- 文本 diff（使用 difflib）
- 元数据 diff（字段变更列表）
- 首次版本
- 空变更
- 边界值
"""

from __future__ import annotations

from src.domain.services.document_version_diff_service import compute_diff


class TestComputeDiffInitialVersion:
    """测试首次版本差异计算"""

    def test_initial_version_returns_initial_diff(self) -> None:
        """首次版本应返回 is_initial=True 的 diff"""
        diff = compute_diff(
            old_metadata={},
            new_metadata={},
            old_content_summary="",
            new_content_summary="",
            is_initial=True,
        )

        assert diff.is_initial is True
        assert diff.diff_summary == "initial version"
        assert diff.changed_fields == []


class TestComputeDiffNoChanges:
    """测试空变更差异计算"""

    def test_no_changes_returns_no_changes_diff(self) -> None:
        """无变更应返回 no changes 的 diff"""
        diff = compute_diff(
            old_metadata={"key1": "value1"},
            new_metadata={"key1": "value1"},
            old_content_summary="same content",
            new_content_summary="same content",
        )

        assert diff.is_initial is False
        assert diff.diff_summary == "no changes"
        assert diff.changed_fields == []


class TestComputeDiffMetadataChanges:
    """测试元数据变更差异计算"""

    def test_metadata_field_added(self) -> None:
        """新增元数据字段应检测到变更"""
        diff = compute_diff(
            old_metadata={"key1": "value1"},
            new_metadata={"key1": "value1", "key2": "value2"},
            old_content_summary="",
            new_content_summary="",
        )

        assert "key2" in diff.changed_fields
        assert "key1" not in diff.changed_fields

    def test_metadata_field_removed(self) -> None:
        """删除元数据字段应检测到变更"""
        diff = compute_diff(
            old_metadata={"key1": "value1", "key2": "value2"},
            new_metadata={"key1": "value1"},
            old_content_summary="",
            new_content_summary="",
        )

        assert "key2" in diff.changed_fields
        assert "key1" not in diff.changed_fields

    def test_metadata_field_modified(self) -> None:
        """修改元数据字段值应检测到变更"""
        diff = compute_diff(
            old_metadata={"key1": "old_value", "key2": "same"},
            new_metadata={"key1": "new_value", "key2": "same"},
            old_content_summary="",
            new_content_summary="",
        )

        assert "key1" in diff.changed_fields
        assert "key2" not in diff.changed_fields

    def test_multiple_metadata_changes(self) -> None:
        """多个元数据字段变更应全部检测"""
        diff = compute_diff(
            old_metadata={"a": "1", "b": "2", "c": "3"},
            new_metadata={"a": "changed", "b": "2", "d": "4"},
            old_content_summary="",
            new_content_summary="",
        )

        assert "a" in diff.changed_fields
        assert "c" in diff.changed_fields
        assert "d" in diff.changed_fields
        assert "b" not in diff.changed_fields


class TestComputeDiffContentChanges:
    """测试文档内容变更差异计算"""

    def test_content_changed_detected(self) -> None:
        """内容摘要变更应生成差异摘要"""
        diff = compute_diff(
            old_metadata={},
            new_metadata={},
            old_content_summary="这是旧的文档内容摘要",
            new_content_summary="这是新的文档内容摘要",
        )

        assert diff.is_initial is False
        assert diff.changed_fields == []
        # diff_summary 应包含 diff 信息
        has_diff = "diff" in diff.diff_summary.lower() or "变更" in diff.diff_summary or "change" in diff.diff_summary.lower()
        assert has_diff

    def test_content_summary_none_handling(self) -> None:
        """内容摘要为 None 时应处理为空字符串"""
        diff = compute_diff(
            old_metadata={},
            new_metadata={},
            old_content_summary=None,
            new_content_summary=None,
        )

        assert diff.is_initial is False
        assert diff.diff_summary == "no changes"


class TestComputeDiffCombinedChanges:
    """测试元数据和内容同时变更的差异计算"""

    def test_metadata_and_content_both_changed(self) -> None:
        """元数据和内容同时变更应同时反映"""
        diff = compute_diff(
            old_metadata={"parse_status": "pending"},
            new_metadata={"parse_status": "completed"},
            old_content_summary="旧内容",
            new_content_summary="新内容",
        )

        assert "parse_status" in diff.changed_fields
        assert diff.diff_summary != "no changes"
        assert diff.diff_summary != "initial version"


class TestComputeDiffEdgeCases:
    """测试边界值"""

    def test_empty_metadata(self) -> None:
        """空元数据应正确处理"""
        diff = compute_diff(
            old_metadata={},
            new_metadata={},
            old_content_summary="content",
            new_content_summary="content",
        )

        assert diff.changed_fields == []
        assert diff.diff_summary == "no changes"

    def test_nested_metadata_detected(self) -> None:
        """嵌套字段变更应检测到顶层 key"""
        diff = compute_diff(
            old_metadata={"nested": {"inner": "old"}},
            new_metadata={"nested": {"inner": "new"}},
            old_content_summary="",
            new_content_summary="",
        )

        assert "nested" in diff.changed_fields
