"""Story 2-7 TDD 单元测试 — MetadataValidationError 异常

验证 MetadataValidationError 异常的构造、属性、to_dict、cause 链、HTTP 422 映射。

Run with: poetry run pytest tests/unit/domain/exceptions/test_metadata_validation_exceptions.py -v
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.domain.exceptions import BusinessRuleViolationError
from src.domain.exceptions.storage_exceptions import MetadataValidationError
from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP, _get_http_status


class TestMetadataValidationErrorCreation:
    """验证 MetadataValidationError 构造"""

    def test_create_with_all_required_fields(self) -> None:
        """验证使用必填参数构造成功"""
        doc_id = uuid4()
        missing = ["license", "source"]
        tenant_id = "tenant-123"
        exc = MetadataValidationError(
            document_id=doc_id,
            missing_fields=missing,
            tenant_id=tenant_id,
        )
        assert exc.document_id == doc_id
        assert exc.missing_fields == missing
        assert exc.tenant_id == tenant_id

    def test_code_is_exception_217(self) -> None:
        """验证异常编码为 EXCEPTION_217"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license"])
        assert exc.code == "EXCEPTION_217"

    def test_message_format(self) -> None:
        """验证消息格式正确"""
        doc_id = uuid4()
        exc = MetadataValidationError(document_id=doc_id, missing_fields=["license", "source"])
        expected = f"文档元数据校验失败: document_id={doc_id}, missing_fields=['license', 'source']"
        assert exc.message == expected

    def test_message_without_tenant_id(self) -> None:
        """验证不传 tenant_id 时消息格式正确"""
        doc_id = uuid4()
        exc = MetadataValidationError(document_id=doc_id, missing_fields=["license"])
        assert "document_id" in exc.message
        assert "license" in exc.message

    def test_inherits_from_business_rule_violation(self) -> None:
        """验证继承自 BusinessRuleViolationError"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license"])
        assert isinstance(exc, BusinessRuleViolationError)

    def test_tenant_id_defaults_to_empty_string(self) -> None:
        """验证 tenant_id 默认为空字符串"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license"])
        assert exc.tenant_id == ""


class TestMetadataValidationErrorContext:
    """验证 MetadataValidationError 的 context 字段"""

    def test_context_contains_document_id(self) -> None:
        """验证 context 包含 document_id（str 类型）"""
        doc_id = uuid4()
        exc = MetadataValidationError(document_id=doc_id, missing_fields=["license"])
        assert "document_id" in exc.context
        assert isinstance(exc.context["document_id"], str)
        assert exc.context["document_id"] == str(doc_id)

    def test_context_contains_missing_fields(self) -> None:
        """验证 context 包含 missing_fields 列表"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license", "source"])
        assert "missing_fields" in exc.context
        assert exc.context["missing_fields"] == ["license", "source"]

    def test_context_contains_tenant_id(self) -> None:
        """验证 context 包含 tenant_id"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license"], tenant_id="tenant-456")
        assert "tenant_id" in exc.context
        assert exc.context["tenant_id"] == "tenant-456"

    def test_context_tenant_id_empty_by_default(self) -> None:
        """验证不传 tenant_id 时 context 中的 tenant_id 为空字符串"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license"])
        assert "tenant_id" in exc.context
        assert exc.context["tenant_id"] == ""


class TestMetadataValidationErrorToDict:
    """验证 to_dict() 序列化"""

    def test_to_dict_contains_code(self) -> None:
        """验证 to_dict 包含 code"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license"])
        result = exc.to_dict()
        assert result["code"] == "EXCEPTION_217"

    def test_to_dict_context_document_id_is_string(self) -> None:
        """验证 to_dict 中 document_id 为字符串类型"""
        doc_id = uuid4()
        exc = MetadataValidationError(document_id=doc_id, missing_fields=["license"])
        result = exc.to_dict()
        assert isinstance(result["context"]["document_id"], str)
        assert result["context"]["document_id"] == str(doc_id)

    def test_to_dict_context_missing_fields_matches_input(self) -> None:
        """验证 to_dict 中 missing_fields 与传入值一致"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license", "source", "business_domain"])
        result = exc.to_dict()
        assert result["context"]["missing_fields"] == ["license", "source", "business_domain"]

    def test_to_dict_context_tenant_id_correct(self) -> None:
        """验证 to_dict 中 tenant_id 值正确"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license"], tenant_id="tenant-789")
        result = exc.to_dict()
        assert result["context"]["tenant_id"] == "tenant-789"


class TestMetadataValidationErrorCauseChain:
    """验证 cause 链测试"""

    def test_cause_included_in_to_dict(self) -> None:
        """验证 cause 字段被序列化到 to_dict 中"""
        root_cause = ValueError("原始错误")
        exc = MetadataValidationError(
            document_id=uuid4(),
            missing_fields=["license"],
            cause=root_cause,
        )
        result = exc.to_dict()
        assert "cause" in result
        assert result["cause"]["type"] == "ValueError"
        assert "原始错误" in result["cause"]["message"]

    def test_cause_is_none_by_default(self) -> None:
        """验证不传 cause 时 to_dict 无 cause 字段"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license"])
        result = exc.to_dict()
        assert "cause" not in result


class TestMetadataValidationErrorHttpMapping:
    """验证 HTTP 422 映射"""

    def test_http_status_maps_to_422(self) -> None:
        """验证 _get_http_status 返回 422"""
        exc = MetadataValidationError(document_id=uuid4(), missing_fields=["license"])
        status_code = _get_http_status(exc)
        from fastapi import status
        assert status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_exception_http_map_contains_exact_type(self) -> None:
        """验证 EXCEPTION_HTTP_MAP 包含 MetadataValidationError 精确类型"""
        assert MetadataValidationError in EXCEPTION_HTTP_MAP

    def test_exception_http_map_maps_to_422(self) -> None:
        """验证 EXCEPTION_HTTP_MAP 中映射到 422"""
        from fastapi import status
        assert EXCEPTION_HTTP_MAP[MetadataValidationError] == status.HTTP_422_UNPROCESSABLE_ENTITY