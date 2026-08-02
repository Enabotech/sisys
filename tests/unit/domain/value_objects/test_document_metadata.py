"""Story 2-7 TDD 单元测试 — DocumentMetadata 值对象

验证 DocumentMetadata frozen dataclass 的构造、不可变性、字段访问、相等性。

Run with: poetry run pytest tests/unit/domain/value_objects/test_document_metadata.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.domain.value_objects.document_metadata import (
    AUTO_FILLABLE_FIELDS,
    REQUIRED_METADATA_FIELDS,
    DocumentMetadata,
)


class TestRequiredMetadataFields:
    """验证 REQUIRED_METADATA_FIELDS 常量的定义"""

    def test_required_fields_contains_all_five_fields(self) -> None:
        """验证五个必需字段全部定义"""
        assert len(REQUIRED_METADATA_FIELDS) == 5
        assert "creator" in REQUIRED_METADATA_FIELDS
        assert "created_at" in REQUIRED_METADATA_FIELDS
        assert "source" in REQUIRED_METADATA_FIELDS
        assert "license" in REQUIRED_METADATA_FIELDS
        assert "business_domain" in REQUIRED_METADATA_FIELDS

    def test_required_fields_is_tuple(self) -> None:
        """验证 REQUIRED_METADATA_FIELDS 是 tuple（不可变）"""
        assert isinstance(REQUIRED_METADATA_FIELDS, tuple)

    def test_auto_fillable_fields_contains_creator_and_created_at(self) -> None:
        """验证 AUTO_FILLABLE_FIELDS 包含 creator 和 created_at"""
        assert "creator" in AUTO_FILLABLE_FIELDS
        assert "created_at" in AUTO_FILLABLE_FIELDS
        assert len(AUTO_FILLABLE_FIELDS) == 2


class TestDocumentMetadataCreation:
    """验证 DocumentMetadata 值对象构造"""

    def test_create_with_required_fields(self) -> None:
        """验证使用必填字段构造成功"""
        doc_id = uuid4()
        metadata = {"creator": "test-user", "created_at": "2024-01-15T10:30:00Z", "source": "internal", "license": "confidential", "business_domain": "finance"}
        doc_meta = DocumentMetadata(document_id=doc_id, metadata=metadata)
        assert doc_meta.document_id == doc_id
        assert doc_meta.metadata["creator"] == "test-user"
        assert doc_meta.metadata["source"] == "internal"

    def test_create_with_empty_metadata(self) -> None:
        """验证使用空 metadata 构造成功"""
        doc_id = uuid4()
        doc_meta = DocumentMetadata(document_id=doc_id)
        assert doc_meta.document_id == doc_id
        assert doc_meta.metadata == {}

    def test_create_with_none_metadata(self) -> None:
        """验证 metadata 参数为 None 时使用空字典"""
        doc_id = uuid4()
        doc_meta = DocumentMetadata(document_id=doc_id, metadata=None)
        assert doc_meta.metadata == {}

    def test_document_id_is_uuid(self) -> None:
        """验证 document_id 是 UUID 类型"""
        doc_id = uuid4()
        doc_meta = DocumentMetadata(document_id=doc_id)
        assert isinstance(doc_meta.document_id, UUID)


class TestDocumentMetadataFrozen:
    """验证 DocumentMetadata 的不可变性"""

    def test_cannot_modify_document_id(self) -> None:
        """验证 document_id 不可修改"""
        doc_meta = DocumentMetadata(document_id=uuid4())
        with pytest.raises(AttributeError):
            doc_meta.document_id = uuid4()

    def test_cannot_modify_metadata(self) -> None:
        """验证 metadata 不可修改"""
        doc_meta = DocumentMetadata(document_id=uuid4(), metadata={"creator": "test"})
        with pytest.raises(AttributeError):
            doc_meta.metadata = {}


class TestDocumentMetadataValidate:
    """验证 validate() 校验逻辑"""

    def test_validate_all_fields_present(self) -> None:
        """验证完整元数据校验通过"""
        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            },
        )
        doc_meta.validate()  # 不应抛出异常

    def test_validate_missing_single_field(self) -> None:
        """验证单个字段缺失时抛出 MetadataValidationError"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "business_domain": "finance",
            },
        )
        with pytest.raises(MetadataValidationError) as exc_info:
            doc_meta.validate()
        assert "license" in exc_info.value.context["missing_fields"]

    def test_validate_missing_multiple_fields(self) -> None:
        """验证多个字段缺失时列出所有缺失字段"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
            },
        )
        with pytest.raises(MetadataValidationError) as exc_info:
            doc_meta.validate()
        missing = exc_info.value.context["missing_fields"]
        assert "created_at" in missing
        assert "source" in missing
        assert "license" in missing
        assert "business_domain" in missing

    def test_validate_empty_string_value(self) -> None:
        """验证空字符串值视为缺失"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "",
                "license": "confidential",
                "business_domain": "finance",
            },
        )
        with pytest.raises(MetadataValidationError) as exc_info:
            doc_meta.validate()
        assert "source" in exc_info.value.context["missing_fields"]

    def test_validate_invalid_iso8601_format(self) -> None:
        """验证 created_at 非法 ISO 8601 格式时视为缺失"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
                "created_at": "2024/01/01",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            },
        )
        with pytest.raises(MetadataValidationError) as exc_info:
            doc_meta.validate()
        assert "created_at" in exc_info.value.context["missing_fields"]

    def test_validate_empty_metadata_dict(self) -> None:
        """验证空 metadata dict 时所有字段缺失"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        doc_meta = DocumentMetadata(document_id=uuid4())
        with pytest.raises(MetadataValidationError) as exc_info:
            doc_meta.validate()
        missing = exc_info.value.context["missing_fields"]
        assert len(missing) == 5

    def test_validate_raise_on_error_false_returns_missing_list(self) -> None:
        """验证 raise_on_error=False 时返回缺失字段列表而非抛出异常"""
        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
            },
        )
        missing = doc_meta.validate(raise_on_error=False)
        assert isinstance(missing, list)
        assert len(missing) == 4
        assert "created_at" in missing
        assert "source" in missing
        assert "license" in missing
        assert "business_domain" in missing

    def test_validate_raise_on_error_false_all_fields_present(self) -> None:
        """验证 raise_on_error=False 且全部字段存在时返回空列表"""
        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            },
        )
        missing = doc_meta.validate(raise_on_error=False)
        assert missing == []

    def test_validate_raise_on_error_default_is_true(self) -> None:
        """验证 raise_on_error 默认值为 True（抛出异常）"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
            },
        )
        with pytest.raises(MetadataValidationError):
            doc_meta.validate()


class TestDocumentMetadataMissingFields:
    """验证 missing_fields() 方法"""

    def test_missing_fields_all_present(self) -> None:
        """验证全部字段存在时返回空列表"""
        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            },
        )
        assert doc_meta.missing_fields() == []

    def test_missing_fields_one_missing(self) -> None:
        """验证一个字段缺失时返回该字段"""
        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "license": "confidential",
            },
        )
        missing = doc_meta.missing_fields()
        assert missing == ["business_domain"]

    def test_missing_fields_empty_string(self) -> None:
        """验证空字符串值视为缺失"""
        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "",
                "license": "confidential",
                "business_domain": "finance",
            },
        )
        missing = doc_meta.missing_fields()
        assert "source" in missing

    def test_missing_fields_invalid_iso8601(self) -> None:
        """验证非法 ISO 8601 格式的 created_at 视为缺失"""
        doc_meta = DocumentMetadata(
            document_id=uuid4(),
            metadata={
                "creator": "test-user",
                "created_at": "2024/01/01",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            },
        )
        missing = doc_meta.missing_fields()
        assert "created_at" in missing

    def test_missing_fields_empty_metadata(self) -> None:
        """验证空 metadata 时所有字段缺失"""
        doc_meta = DocumentMetadata(document_id=uuid4())
        missing = doc_meta.missing_fields()
        assert len(missing) == 5
        assert set(missing) == {"creator", "created_at", "source", "license", "business_domain"}


class TestDocumentMetadataFromUpload:
    """验证 from_upload() 工厂方法"""

    def test_from_upload_with_full_metadata(self) -> None:
        """验证完整 metadata 时 from_upload 构造正确"""
        doc_id = uuid4()
        raw = {
            "creator": "test-user",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc_meta = DocumentMetadata.from_upload(document_id=doc_id, raw_metadata=raw, uploaded_by="test-user")
        assert doc_meta.metadata["creator"] == "test-user"
        assert doc_meta.metadata["source"] == "internal"

    def test_from_upload_autofill_creator(self) -> None:
        """验证 creator 自动填充为 uploaded_by"""
        doc_id = uuid4()
        raw = {
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc_meta = DocumentMetadata.from_upload(document_id=doc_id, raw_metadata=raw, uploaded_by="auto-user")
        assert doc_meta.metadata["creator"] == "auto-user"

    def test_from_upload_autofill_created_at(self) -> None:
        """验证 created_at 自动填充为当前 UTC 时间"""
        doc_id = uuid4()
        raw = {
            "creator": "test-user",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc_meta = DocumentMetadata.from_upload(document_id=doc_id, raw_metadata=raw, uploaded_by="test-user")
        created_at = doc_meta.metadata["created_at"]
        assert created_at is not None
        assert "T" in created_at  # ISO 8601 格式
        # 验证时间接近当前时间
        parsed = datetime.fromisoformat(created_at)
        now = datetime.now(UTC)
        delta = abs((now - parsed).total_seconds())
        assert delta < 5, f"created_at 时间偏差过大: {delta} 秒"

    def test_from_upload_does_not_override_explicit_creator(self) -> None:
        """验证显式提供的 creator 不被自动填充覆盖"""
        doc_id = uuid4()
        raw = {
            "creator": "explicit-user",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc_meta = DocumentMetadata.from_upload(document_id=doc_id, raw_metadata=raw, uploaded_by="should-not-override")
        assert doc_meta.metadata["creator"] == "explicit-user"

    def test_from_upload_does_not_override_explicit_created_at(self) -> None:
        """验证显式提供的 created_at 不被自动填充覆盖"""
        doc_id = uuid4()
        raw = {
            "creator": "test-user",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc_meta = DocumentMetadata.from_upload(document_id=doc_id, raw_metadata=raw, uploaded_by="test-user")
        assert doc_meta.metadata["created_at"] == "2024-01-15T10:30:00Z"

    def test_from_upload_with_none_metadata(self) -> None:
        """验证 raw_metadata 为 None 时 still_works"""
        doc_id = uuid4()
        doc_meta = DocumentMetadata.from_upload(document_id=doc_id, raw_metadata=None, uploaded_by="test-user")
        assert doc_meta.metadata["creator"] == "test-user"
        assert "created_at" in doc_meta.metadata

    def test_from_upload_with_empty_metadata(self) -> None:
        """验证 raw_metadata 为空字典时自动填充生效"""
        doc_id = uuid4()
        doc_meta = DocumentMetadata.from_upload(document_id=doc_id, raw_metadata={}, uploaded_by="empty-user")
        assert doc_meta.metadata["creator"] == "empty-user"
        assert "created_at" in doc_meta.metadata

    def test_from_upload_without_uploaded_by(self) -> None:
        """验证 uploaded_by 为空字符串时 creator 自动填充为空字符串"""
        doc_id = uuid4()
        doc_meta = DocumentMetadata.from_upload(document_id=doc_id, raw_metadata={})
        assert doc_meta.metadata["creator"] == ""


class TestDocumentMetadataToDict:
    """验证 to_dict() 序列化方法"""

    def test_to_dict_returns_all_fields(self) -> None:
        """验证 to_dict 返回 document_id 和 metadata"""
        doc_id = uuid4()
        raw = {
            "creator": "test-user",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc_meta = DocumentMetadata.from_upload(document_id=doc_id, raw_metadata=raw, uploaded_by="test-user")
        result = doc_meta.to_dict()
        assert "document_id" in result
        assert "metadata" in result
        assert result["document_id"] == str(doc_id)
        assert result["metadata"]["creator"] == "test-user"
        assert result["metadata"]["source"] == "internal"

    def test_to_dict_document_id_is_string(self) -> None:
        """验证 document_id 序列化为字符串"""
        doc_id = uuid4()
        doc_meta = DocumentMetadata(document_id=doc_id)
        result = doc_meta.to_dict()
        assert isinstance(result["document_id"], str)
        assert result["document_id"] == str(doc_id)

    def test_to_dict_metadata_is_dict(self) -> None:
        """验证 metadata 字段保持为 dict"""
        doc_meta = DocumentMetadata(document_id=uuid4(), metadata={"creator": "test"})
        result = doc_meta.to_dict()
        assert isinstance(result["metadata"], dict)


class TestDocumentMetadataIsValidIso8601:
    """验证 _is_valid_iso8601 纯函数"""

    def test_valid_iso8601_with_z(self) -> None:
        """验证带 Z 时区的 ISO 8601 格式"""
        from src.domain.value_objects.document_metadata import _is_valid_iso8601
        assert _is_valid_iso8601("2024-01-15T10:30:00Z") is True

    def test_valid_iso8601_with_offset(self) -> None:
        """验证带时区偏移的 ISO 8601 格式"""
        from src.domain.value_objects.document_metadata import _is_valid_iso8601
        assert _is_valid_iso8601("2024-01-15T10:30:00+08:00") is True

    def test_valid_iso8601_without_seconds(self) -> None:
        """验证无秒数的 ISO 8601 格式"""
        from src.domain.value_objects.document_metadata import _is_valid_iso8601
        assert _is_valid_iso8601("2024-01-15T10:30+08:00") is True

    def test_valid_iso8601_without_timezone(self) -> None:
        """验证无时区的 ISO 8601 格式"""
        from src.domain.value_objects.document_metadata import _is_valid_iso8601
        assert _is_valid_iso8601("2024-01-15T10:30:00") is True

    def test_invalid_date_only(self) -> None:
        """验证仅日期格式无效"""
        from src.domain.value_objects.document_metadata import _is_valid_iso8601
        assert _is_valid_iso8601("2024-01-15") is False

    def test_invalid_format_slash(self) -> None:
        """验证斜杠分隔格式无效"""
        from src.domain.value_objects.document_metadata import _is_valid_iso8601
        assert _is_valid_iso8601("2024/01/15") is False

    def test_invalid_random_string(self) -> None:
        """验证随机字符串格式无效"""
        from src.domain.value_objects.document_metadata import _is_valid_iso8601
        assert _is_valid_iso8601("not-a-date") is False

    def test_invalid_empty_string(self) -> None:
        """验证空字符串格式无效"""
        from src.domain.value_objects.document_metadata import _is_valid_iso8601
        assert _is_valid_iso8601("") is False

    def test_valid_iso8601_with_t_separator(self) -> None:
        """验证含 T 分隔符的 ISO 8601 格式"""
        from src.domain.value_objects.document_metadata import _is_valid_iso8601
        assert _is_valid_iso8601("2024-01-15T10:30:00") is True

    def test_valid_iso8601_with_space_separator(self) -> None:
        """验证空格分隔符的 ISO 8601 格式"""
        from src.domain.value_objects.document_metadata import _is_valid_iso8601
        assert _is_valid_iso8601("2024-01-15 10:30:00") is True