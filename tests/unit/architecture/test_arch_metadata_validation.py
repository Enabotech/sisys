"""Story 2-7: SDD 架构约束验证测试

验证文档元数据校验功能的架构合规性：
- domain 层零外部依赖（DocumentMetadata 值对象仅使用标准库）
- MetadataValidationError 继承链正确
- REQUIRED_METADATA_FIELDS 常量不可变
- _CLASS_TO_SUBDOMAIN 注册一致性
- HTTP 422 映射
"""

from __future__ import annotations

import ast
import importlib
import os
import uuid

import pytest


class TestDomainLayerPurity:
    """验证 domain 层零外部依赖"""

    def test_document_metadata_no_external_deps(self) -> None:
        """document_metadata.py 不依赖外部库"""
        mod = importlib.import_module("src.domain.value_objects.document_metadata")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if hasattr(attr, "__module__") and attr.__module__:
                assert not attr.__module__.startswith(("sqlalchemy", "pydantic", "redis", "fastapi", "minio")), (
                    f"domain 层禁止依赖 {attr.__module__}"
                )

    def test_document_metadata_imports_only_stdlib(self) -> None:
        """使用 AST 解析验证 document_metadata.py 仅导入标准库"""
        file_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "src",
            "domain",
            "value_objects",
            "document_metadata.py",
        )
        file_path = os.path.normpath(file_path)

        if not os.path.exists(file_path):
            pytest.skip("文件不存在")

        with open(file_path) as f:
            tree = ast.parse(f.read())

        stdlib_modules = {"__future__", "re", "uuid", "dataclasses", "datetime", "typing"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".")[0]
                    assert top_level in stdlib_modules, f"domain 层禁止导入非标准库: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                top_level = node.module.split(".")[0]
                if top_level == "src":
                    continue  # 允许导入本项目的其他模块
                assert top_level in stdlib_modules, f"domain 层禁止导入非标准库: {node.module}"


class TestMetadataValidationErrorInheritance:
    """验证 MetadataValidationError 继承链"""

    def test_inherits_from_business_rule_violation(self) -> None:
        """MetadataValidationError 继承 BusinessRuleViolationError"""
        from src.domain.exceptions import BusinessRuleViolationError
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        assert issubclass(MetadataValidationError, BusinessRuleViolationError)

    def test_inherits_from_business_exception(self) -> None:
        """MetadataValidationError 继承 BusinessException（间接）"""
        from src.domain.exceptions import BusinessException
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        assert issubclass(MetadataValidationError, BusinessException)

    def test_code_is_exception_217(self) -> None:
        """MetadataValidationError 编码为 EXCEPTION_217"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        assert MetadataValidationError.code == "EXCEPTION_217"


class TestHttpMapping:
    """验证 HTTP 422 映射"""

    def test_metadata_validation_error_maps_to_422(self) -> None:
        """MetadataValidationError 在 EXCEPTION_HTTP_MAP 中映射到 422"""
        from fastapi import status

        from src.domain.exceptions.storage_exceptions import MetadataValidationError
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert MetadataValidationError in EXCEPTION_HTTP_MAP
        assert EXCEPTION_HTTP_MAP[MetadataValidationError] == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_isinstance_fallback_to_business_rule_violation(self) -> None:
        """通过 isinstance 回退到 BusinessRuleViolationError 的 422 映射"""
        from fastapi import status

        from src.domain.exceptions import BusinessRuleViolationError
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert BusinessRuleViolationError in EXCEPTION_HTTP_MAP
        assert EXCEPTION_HTTP_MAP[BusinessRuleViolationError] == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestRequiredMetadataFieldsConstants:
    """验证 REQUIRED_METADATA_FIELDS 常量不可变"""

    def test_required_fields_is_tuple(self) -> None:
        """REQUIRED_METADATA_FIELDS 是 tuple 类型"""
        from src.domain.value_objects.document_metadata import REQUIRED_METADATA_FIELDS

        assert isinstance(REQUIRED_METADATA_FIELDS, tuple)

    def test_required_fields_contains_five_fields(self) -> None:
        """REQUIRED_METADATA_FIELDS 包含 5 个字段"""
        from src.domain.value_objects.document_metadata import REQUIRED_METADATA_FIELDS

        assert len(REQUIRED_METADATA_FIELDS) == 5

    def test_auto_fillable_fields_is_dict(self) -> None:
        """AUTO_FILLABLE_FIELDS 是 dict 类型"""
        from src.domain.value_objects.document_metadata import AUTO_FILLABLE_FIELDS

        assert isinstance(AUTO_FILLABLE_FIELDS, dict)

    def test_auto_fillable_fields_contains_two_fields(self) -> None:
        """AUTO_FILLABLE_FIELDS 包含 2 个字段"""
        from src.domain.value_objects.document_metadata import AUTO_FILLABLE_FIELDS

        assert len(AUTO_FILLABLE_FIELDS) == 2


class TestClassToSubdomainRegistration:
    """验证 _CLASS_TO_SUBDOMAIN 注册一致性"""

    def test_metadata_validation_error_registered_as_storage(self) -> None:
        """MetadataValidationError 注册到 storage 子域"""
        from src.domain.exceptions._code_ranges import get_subdomain_for_class

        subdomain = get_subdomain_for_class("MetadataValidationError")
        assert subdomain == "storage"

    def test_storage_range_includes_217(self) -> None:
        """storage 子域编码范围 211-219 包含 217"""
        from src.domain.exceptions._code_ranges import get_range_for_subdomain

        rng = get_range_for_subdomain("storage")
        assert rng is not None
        start, end = rng
        assert start <= 217 <= end


class TestDocumentMetadataFrozen:
    """验证 DocumentMetadata 值对象不可变"""

    def test_document_metadata_is_dataclass(self) -> None:
        """DocumentMetadata 是 dataclass"""
        from dataclasses import is_dataclass

        from src.domain.value_objects.document_metadata import DocumentMetadata

        assert is_dataclass(DocumentMetadata)

    def test_document_metadata_is_frozen(self) -> None:
        """DocumentMetadata 是 frozen dataclass（通过构造后赋值验证）"""
        from dataclasses import FrozenInstanceError

        from src.domain.value_objects.document_metadata import DocumentMetadata

        doc_meta = DocumentMetadata(document_id=uuid.uuid4())
        with pytest.raises(FrozenInstanceError):
            setattr(doc_meta, "metadata", {"test": "value"})


class TestDocumentMetadataModuleExports:
    """验证 document_metadata 模块导出"""

    def test_module_exports_required_metadata_fields(self) -> None:
        """模块导出 REQUIRED_METADATA_FIELDS"""
        import src.domain.value_objects.document_metadata as mod

        assert hasattr(mod, "REQUIRED_METADATA_FIELDS")

    def test_module_exports_document_metadata(self) -> None:
        """模块导出 DocumentMetadata 类"""
        import src.domain.value_objects.document_metadata as mod

        assert hasattr(mod, "DocumentMetadata")

    def test_module_exports_is_valid_iso8601(self) -> None:
        """模块导出 _is_valid_iso8601 函数"""
        import src.domain.value_objects.document_metadata as mod

        assert hasattr(mod, "_is_valid_iso8601")
