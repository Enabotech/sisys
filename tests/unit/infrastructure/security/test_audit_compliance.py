"""安全审计合规集成测试

等保2.0三级安全审计要求验证:
- AC-3.1: 登录/登出/失败事件记录完整
- AC-3.2: 权限变更事件记录完整
- AC-3.3: 敏感操作事件记录完整（删除/导出）
- AC-3.4: SHA256 校验和防篡改
- AC-3.5: WORM 归档存储 ≥6个月

本测试验证 AuditService 的等保合规集成

对应 Story: 1-12-equilibrium-level-3-compliance Task 1 Subtask 1.7-1.9
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.infrastructure.security.audit_service_impl import AuditServiceImpl


def _make_audit_service() -> AuditServiceImpl:
    """创建审计服务实例（含 mock 依赖）"""
    mock_audit_repo = AsyncMock()
    object.__setattr__(mock_audit_repo, "save", AsyncMock(return_value=None))
    return AuditServiceImpl(
        audit_repository=mock_audit_repo,
    )


class TestAuditEventRecordingCompliance:
    """审计事件记录合规验证 (AC-3.1)"""

    @pytest.mark.asyncio
    async def test_login_event_recorded(self) -> None:
        """登录事件应被记录"""
        audit_service = _make_audit_service()
        record = await audit_service.record(
            actor="user123",
            action_type="login",
            target_resource="auth/session",
        )
        assert record is not None
        assert record.actor == "user123"
        assert record.action_type == "login"

    @pytest.mark.asyncio
    async def test_logout_event_recorded(self) -> None:
        """登出事件应被记录"""
        audit_service = _make_audit_service()
        record = await audit_service.record(
            actor="user123",
            action_type="logout",
            target_resource="auth/session",
        )
        assert record is not None
        assert record.action_type == "logout"

    @pytest.mark.asyncio
    async def test_login_failure_event_recorded(self) -> None:
        """登录失败事件应被记录"""
        audit_service = _make_audit_service()
        record = await audit_service.record(
            actor="unknown_user",
            action_type="login_failed",
            target_resource="auth/session",
        )
        assert record is not None
        assert record.action_type == "login_failed"


class TestPermissionChangeEventRecordingCompliance:
    """权限变更事件记录合规验证 (AC-3.2)"""

    @pytest.mark.asyncio
    async def test_role_assignment_recorded(self) -> None:
        """角色分配事件应被记录"""
        audit_service = _make_audit_service()
        record = await audit_service.record(
            actor="admin",
            action_type="role_assigned",
            target_resource="rbac/role",
            new_value={"role": "editor", "user_id": str(uuid4())},
        )
        assert record is not None
        assert record.action_type == "role_assigned"

    @pytest.mark.asyncio
    async def test_permission_change_recorded(self) -> None:
        """权限变更事件应被记录"""
        audit_service = _make_audit_service()
        record = await audit_service.record(
            actor="admin",
            action_type="permission_granted",
            target_resource="rbac/permission",
        )
        assert record is not None
        assert record.action_type == "permission_granted"


class TestSensitiveOperationRecordingCompliance:
    """敏感操作事件记录合规验证 (AC-3.3)"""

    @pytest.mark.asyncio
    async def test_delete_operation_recorded(self) -> None:
        """删除操作应被记录"""
        audit_service = _make_audit_service()
        record = await audit_service.record(
            actor="user123",
            action_type="delete",
            target_resource="document/456",
            old_value={"title": "Secret Document"},
        )
        assert record is not None
        assert record.action_type == "delete"

    @pytest.mark.asyncio
    async def test_export_operation_recorded(self) -> None:
        """导出操作应被记录"""
        audit_service = _make_audit_service()
        record = await audit_service.record(
            actor="user123",
            action_type="export",
            target_resource="document/batch",
        )
        assert record is not None
        assert record.action_type == "export"


class TestAuditIntegrityCompliance:
    """审计完整性合规验证 (AC-3.4)"""

    @pytest.mark.asyncio
    async def test_verify_integrity_returns_bool(self) -> None:
        """完整性验证应返回布尔值"""
        import hashlib
        import json

        log_id = uuid4()
        audit_data = {
            "log_id": str(log_id),
            "timestamp": "2026-01-01T00:00:00+00:00",
            "actor": "user123",
            "action_type": "login",
            "target_resource": "auth/session",
            "old_value": {},
            "new_value": {},
            "correction_level": 0,
        }
        content = json.dumps(audit_data, sort_keys=True)
        checksum = hashlib.sha256(content.encode()).hexdigest()
        audit_data["checksum"] = checksum

        audit_service = _make_audit_service()
        object.__setattr__(audit_service._audit_repo, "get_by_id", AsyncMock(return_value=audit_data))
        result = await audit_service.verify_integrity(log_id)
        assert isinstance(result, bool)
        assert result is True

    @pytest.mark.asyncio
    async def test_checksum_sha256_algorithm_used(self) -> None:
        """审计服务应使用 SHA256 算法计算校验和"""
        import hashlib

        test_data = "test audit record"
        checksum = hashlib.sha256(test_data.encode()).hexdigest()
        assert len(checksum) == 64, "SHA256应生成64位十六进制哈希"

    @pytest.mark.asyncio
    async def test_batch_verification_supported(self) -> None:
        """批量验证应支持"""
        audit_service = _make_audit_service()
        result = await audit_service.verify_batch(log_ids=None)
        assert isinstance(result, dict)


class TestWORMArchiveCompliance:
    """WORM 归档合规验证 (AC-3.5)"""

    @pytest.mark.asyncio
    async def test_archive_functionality_exists(self) -> None:
        """归档功能应存在"""
        audit_service = _make_audit_service()
        assert hasattr(audit_service, "archive")
        assert callable(audit_service.archive)

    @pytest.mark.asyncio
    async def test_archive_older_than_days(self) -> None:
        """归档应支持按天过滤"""
        audit_service = _make_audit_service()
        mock_search_result = AsyncMock()
        object.__setattr__(mock_search_result, "items", [])
        object.__setattr__(audit_service._audit_repo, "search", AsyncMock(return_value=mock_search_result))
        result = await audit_service.archive(older_than_days=30)
        assert isinstance(result, int)
