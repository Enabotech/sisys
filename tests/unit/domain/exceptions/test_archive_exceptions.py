"""Archive 相关异常单元测试

验证档案异常类的构造、属性、to_dict() 序列化和继承链。
"""

from __future__ import annotations

import uuid

from src.domain.exceptions import (
    ArchiveConflictError,
    ArchiveNotFoundError,
    ArchiveStorageError,
    BusinessException,
    ConflictError,
    NotFoundError,
    ValidityPeriodConflictError,
)


class TestArchiveNotFoundError:
    """ArchiveNotFoundError 测试"""

    def test_code(self) -> None:
        """编码必须为 EXCEPTION_282"""
        exc = ArchiveNotFoundError(archive_id=uuid.uuid4())
        assert exc.code == "EXCEPTION_282"

    def test_inheritance(self) -> None:
        """必须继承 NotFoundError"""
        exc = ArchiveNotFoundError(archive_id=uuid.uuid4())
        assert isinstance(exc, NotFoundError)
        assert isinstance(exc, BusinessException)

    def test_default_message(self) -> None:
        """默认消息格式"""
        archive_id = uuid.uuid4()
        exc = ArchiveNotFoundError(archive_id=archive_id)
        assert exc.message == f"Archive not found: {archive_id}"

    def test_custom_message(self) -> None:
        """自定义消息"""
        exc = ArchiveNotFoundError(archive_id=uuid.uuid4(), message="custom")
        assert exc.message == "custom"

    def test_context_exposes_archive_id(self) -> None:
        """context 暴露 archive_id 字符串"""
        archive_id = uuid.uuid4()
        exc = ArchiveNotFoundError(archive_id=archive_id)
        assert exc.context == {"archive_id": str(archive_id)}

    def test_to_dict(self) -> None:
        """to_dict 序列化包含 code/message/context"""
        archive_id = uuid.uuid4()
        exc = ArchiveNotFoundError(archive_id=archive_id)
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_282"
        assert data["message"] == f"Archive not found: {archive_id}"
        assert data["context"] == {"archive_id": str(archive_id)}

    def test_cause(self) -> None:
        """cause 保序传递"""
        cause = ValueError("root")
        exc = ArchiveNotFoundError(archive_id=uuid.uuid4(), cause=cause)
        assert exc.cause is cause


class TestArchiveConflictError:
    """ArchiveConflictError 测试"""

    def test_code(self) -> None:
        """编码必须为 EXCEPTION_283"""
        exc = ArchiveConflictError(archive_id=uuid.uuid4())
        assert exc.code == "EXCEPTION_283"

    def test_inheritance(self) -> None:
        """必须继承 ConflictError"""
        exc = ArchiveConflictError(archive_id=uuid.uuid4())
        assert isinstance(exc, ConflictError)
        assert isinstance(exc, BusinessException)

    def test_default_message(self) -> None:
        """默认消息格式"""
        archive_id = uuid.uuid4()
        exc = ArchiveConflictError(archive_id=archive_id)
        assert exc.message == f"Archive conflict: {archive_id}"

    def test_custom_message(self) -> None:
        """自定义消息"""
        exc = ArchiveConflictError(archive_id=uuid.uuid4(), message="custom")
        assert exc.message == "custom"

    def test_context_exposes_archive_id(self) -> None:
        """context 暴露 archive_id 字符串"""
        archive_id = uuid.uuid4()
        exc = ArchiveConflictError(archive_id=archive_id)
        assert exc.context == {"archive_id": str(archive_id)}

    def test_to_dict(self) -> None:
        """to_dict 序列化"""
        archive_id = uuid.uuid4()
        exc = ArchiveConflictError(archive_id=archive_id)
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_283"
        assert data["message"] == f"Archive conflict: {archive_id}"


class TestArchiveStorageError:
    """ArchiveStorageError 测试"""

    def test_code(self) -> None:
        """编码必须为 EXCEPTION_284"""
        exc = ArchiveStorageError(layer="l2")
        assert exc.code == "EXCEPTION_284"

    def test_inheritance(self) -> None:
        """必须继承 BusinessException"""
        exc = ArchiveStorageError(layer="l3")
        assert isinstance(exc, BusinessException)

    def test_default_message(self) -> None:
        """默认消息格式"""
        exc = ArchiveStorageError(layer="l4")
        assert exc.message == "Archive storage error at layer l4"

    def test_custom_message(self) -> None:
        """自定义消息"""
        exc = ArchiveStorageError(layer="l5", message="custom")
        assert exc.message == "custom"

    def test_context_exposes_layer(self) -> None:
        """context 暴露 layer"""
        exc = ArchiveStorageError(layer="l2")
        assert exc.context == {"layer": "l2"}

    def test_to_dict(self) -> None:
        """to_dict 序列化"""
        exc = ArchiveStorageError(layer="l2")
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_284"
        assert data["context"] == {"layer": "l2"}

    def test_cause(self) -> None:
        """cause 保序传递"""
        cause = ConnectionError("down")
        exc = ArchiveStorageError(layer="l2", cause=cause)
        assert exc.cause is cause
        assert exc.to_dict()["cause"]["type"] == "ConnectionError"


class TestValidityPeriodConflictError:
    """ValidityPeriodConflictError 测试"""

    def test_code(self) -> None:
        """编码必须为 EXCEPTION_285"""
        exc = ValidityPeriodConflictError(archive_id=uuid.uuid4())
        assert exc.code == "EXCEPTION_285"

    def test_inheritance(self) -> None:
        """必须继承 ConflictError"""
        exc = ValidityPeriodConflictError(archive_id=uuid.uuid4())
        assert isinstance(exc, ConflictError)
        assert isinstance(exc, BusinessException)

    def test_default_message(self) -> None:
        """默认消息格式"""
        archive_id = uuid.uuid4()
        exc = ValidityPeriodConflictError(archive_id=archive_id)
        assert exc.message == f"Validity period conflict for archive: {archive_id}"

    def test_custom_message(self) -> None:
        """自定义消息"""
        exc = ValidityPeriodConflictError(archive_id=uuid.uuid4(), message="custom")
        assert exc.message == "custom"

    def test_context_exposes_archive_id(self) -> None:
        """context 暴露 archive_id 字符串"""
        archive_id = uuid.uuid4()
        exc = ValidityPeriodConflictError(archive_id=archive_id)
        assert exc.context == {"archive_id": str(archive_id)}

    def test_to_dict(self) -> None:
        """to_dict 序列化"""
        archive_id = uuid.uuid4()
        exc = ValidityPeriodConflictError(archive_id=archive_id)
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_285"
        assert data["message"] == f"Validity period conflict for archive: {archive_id}"
        assert data["context"] == {"archive_id": str(archive_id)}

    def test_cause(self) -> None:
        """cause 保序传递"""
        cause = ValueError("root")
        exc = ValidityPeriodConflictError(archive_id=uuid.uuid4(), cause=cause)
        assert exc.cause is cause
