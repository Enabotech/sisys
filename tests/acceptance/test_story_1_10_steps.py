"""BDD Steps Implementation for Story 1.10 - Unified Audit Log.

实现 tests/acceptance/test_story_1_10.feature 中的 BDD 步骤。
使用 event_loop.run_until_complete() 运行 async 测试。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from pytest_bdd import given, scenario, then, when

from src.domain.ports.audit_repository import (
    AuditRepositoryPort,
    AuditSearchCriteria,
    AuditSearchResult,
)
from src.domain.ports.audit_service import AuditRecord
from src.infrastructure.security.audit_service_impl import AuditServiceImpl


class FakeAuditRepository(AuditRepositoryPort):
    """Fake implementation for testing."""

    def __init__(self) -> None:
        self._logs: dict[UUID, dict[str, Any]] = {}

    async def save(self, audit_data: dict[str, Any]) -> UUID:
        log_id = UUID(audit_data["log_id"])
        self._logs[log_id] = audit_data
        return log_id

    async def get_by_id(self, log_id: UUID) -> dict[str, Any] | None:
        return self._logs.get(log_id)

    async def search(self, criteria: AuditSearchCriteria) -> AuditSearchResult:
        items = list(self._logs.values())
        filtered = []
        for item in items:
            timestamp = datetime.fromisoformat(item["timestamp"])
            if criteria.start_time and timestamp < criteria.start_time:
                continue
            if criteria.end_time and timestamp > criteria.end_time:
                continue
            if criteria.actor and item.get("actor") != criteria.actor:
                continue
            if criteria.action_type and criteria.action_type not in item.get("action_type", ""):
                continue
            filtered.append(item)
        start = criteria.offset
        end = start + criteria.limit
        return AuditSearchResult(
            items=tuple(filtered[start:end]),
            total=len(filtered),
            offset=criteria.offset,
            limit=criteria.limit,
        )

    async def update_archive_status(
        self,
        log_id: UUID,
        archived: bool,
        archived_at: datetime | None = None,
    ) -> bool:
        if log_id not in self._logs:
            return False
        self._logs[log_id]["archived"] = archived
        self._logs[log_id]["archived_at"] = archived_at.isoformat() if archived_at else None
        return True

    async def get_archive_status(self, log_id: UUID) -> dict[str, Any] | None:
        if log_id not in self._logs:
            return None
        log = self._logs[log_id]
        return {
            "log_id": str(log_id),
            "archived": log.get("archived", False),
            "archived_at": log.get("archived_at"),
            "retention_days": 2555,
        }


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def fake_repo() -> FakeAuditRepository:
    return FakeAuditRepository()


@pytest.fixture
def audit_service(fake_repo: FakeAuditRepository) -> AuditServiceImpl:
    return AuditServiceImpl(audit_repository=fake_repo)


# =============================================================================
# AC-1: 审计日志记录
# =============================================================================


@scenario("test_story_1_10.feature", "记录审计日志")
def test_record_audit_log() -> None:
    """Test recording audit log."""
    pass


@given('用户已认证（user_id: "user-123", username: "testuser"）')
def user_authenticated() -> dict[str, str]:
    return {"user_id": "user-123", "username": "testuser"}


@when('系统产生登录事件（action_type: "authentication:login"）')
def system_produces_login_event(
    audit_service: AuditServiceImpl,
    user_authenticated: dict[str, str],
) -> AuditRecord:
    return asyncio.get_event_loop().run_until_complete(
        audit_service.record(
            actor=user_authenticated["user_id"],
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
            old_value=None,
            new_value={"username": user_authenticated["username"]},
        )
    )


@then("审计日志记录到 PostgreSQL")
def audit_log_saved_to_database(
    system_produces_login_event: AuditRecord,
    fake_repo: FakeAuditRepository,
) -> None:
    assert system_produces_login_event is not None
    saved = asyncio.get_event_loop().run_until_complete(fake_repo.get_by_id(system_produces_login_event.log_id))
    assert saved is not None


@then("日志包含字段：log_id, timestamp, actor, action_type, target_resource")
def log_contains_required_fields(system_produces_login_event: AuditRecord) -> None:
    assert system_produces_login_event.log_id is not None
    assert system_produces_login_event.timestamp is not None
    assert system_produces_login_event.actor is not None
    assert system_produces_login_event.action_type is not None
    assert system_produces_login_event.target_resource is not None


@then("SHA256 校验和已计算")
def checksum_computed(
    system_produces_login_event: AuditRecord,
    fake_repo: FakeAuditRepository,
) -> None:
    saved = asyncio.get_event_loop().run_until_complete(fake_repo.get_by_id(system_produces_login_event.log_id))
    assert saved is not None
    assert len(saved["checksum"]) == 64


# =============================================================================
# AC-1: 记录认证失败事件
# =============================================================================


@scenario("test_story_1_10.feature", "记录认证失败事件")
def test_record_auth_failure() -> None:
    """Test recording authentication failure."""
    pass


@given('用户尝试登录（username: "invalid_user"）')
def user_tries_login() -> str:
    return "invalid_user"


@when('认证失败（action_type: "authentication:failed"）')
def auth_failure(
    audit_service: AuditServiceImpl,
    user_tries_login: str,
) -> AuditRecord:
    return asyncio.get_event_loop().run_until_complete(
        audit_service.record(
            actor=user_tries_login,
            action_type="authentication:failed",
            target_resource="/api/v1/auth/login",
            old_value=None,
            new_value={"username": user_tries_login, "reason": "invalid_credentials"},
        )
    )


@then("审计日志记录失败事件")
def failure_logged(auth_failure: AuditRecord) -> None:
    assert auth_failure.action_type == "authentication:failed"


# =============================================================================
# AC-2: 按时间范围检索审计日志
# =============================================================================


@scenario("test_story_1_10.feature", "按时间范围检索审计日志")
def test_search_by_time_range() -> None:
    """Test searching audit logs by time range."""
    pass


@given("审计日志已记录多条")
def audit_logs_exist(fake_repo: FakeAuditRepository) -> None:
    asyncio.get_event_loop().run_until_complete(
        fake_repo.save(
            {
                "log_id": str(uuid4()),
                "timestamp": datetime.now(UTC).isoformat(),
                "actor": "user-1",
                "action_type": "authentication:login",
                "target_resource": "/api/v1/auth/login",
                "old_value": {},
                "new_value": {},
                "checksum": "a" * 64,
            }
        )
    )
    asyncio.get_event_loop().run_until_complete(
        fake_repo.save(
            {
                "log_id": str(uuid4()),
                "timestamp": (datetime.now(UTC) - timedelta(days=365)).isoformat(),
                "actor": "user-1",
                "action_type": "authentication:login",
                "target_resource": "/api/v1/auth/login",
                "old_value": {},
                "new_value": {},
                "checksum": "b" * 64,
            }
        )
    )


@when('合规工程师查询时间范围（start: "2026-01-01", end: "2026-12-31"）')
def search_by_time(
    audit_service: AuditServiceImpl,
    fake_repo: FakeAuditRepository,
) -> AuditSearchResult:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)
    return asyncio.get_event_loop().run_until_complete(fake_repo.search(AuditSearchCriteria(start_time=start, end_time=end)))


@then("返回该时间范围内的日志")
def returns_logs_in_range(search_by_time: AuditSearchResult) -> None:
    assert search_by_time.total >= 1


@then("返回结果按时间倒序排列")
def results_ordered_desc(search_by_time: AuditSearchResult) -> None:
    items = search_by_time.items
    if len(items) > 1:
        for i in range(len(items) - 1):
            t1 = datetime.fromisoformat(items[i]["timestamp"])
            t2 = datetime.fromisoformat(items[i + 1]["timestamp"])
            assert t1 >= t2


# =============================================================================
# AC-2: 按 actor 检索审计日志
# =============================================================================


@scenario("test_story_1_10.feature", "按 actor 检索审计日志")
def test_search_by_actor() -> None:
    """Test searching audit logs by actor."""
    pass


@when('合规工程师按 actor 查询（actor: "user-123"）')
def search_by_actor(fake_repo: FakeAuditRepository) -> AuditSearchResult:
    return asyncio.get_event_loop().run_until_complete(fake_repo.search(AuditSearchCriteria(actor="user-123")))


@then("返回该用户的所有操作日志")
def returns_user_logs(search_by_actor: AuditSearchResult) -> None:
    for item in search_by_actor.items:
        assert item["actor"] == "user-123"


# =============================================================================
# AC-2: 按 action_type 检索审计日志
# =============================================================================


@scenario("test_story_1_10.feature", "按 action_type 检索审计日志")
def test_search_by_action_type() -> None:
    """Test searching audit logs by action type."""
    pass


@when('合规工程师按 action_type 查询（action_type: "authentication:login"）')
def search_by_action_type(fake_repo: FakeAuditRepository) -> AuditSearchResult:
    return asyncio.get_event_loop().run_until_complete(
        fake_repo.search(AuditSearchCriteria(action_type="authentication:login"))
    )


@then("返回所有登录操作日志")
def returns_login_logs(search_by_action_type: AuditSearchResult) -> None:
    for item in search_by_action_type.items:
        assert "authentication:login" in item["action_type"]


# =============================================================================
# AC-2: 分页检索审计日志
# =============================================================================


@scenario("test_story_1_10.feature", "分页检索审计日志")
def test_paginated_search() -> None:
    """Test paginated audit log search."""
    pass


@given("审计日志已记录超过 20 条")
def many_logs_exist(fake_repo: FakeAuditRepository) -> None:
    for i in range(25):
        asyncio.get_event_loop().run_until_complete(
            fake_repo.save(
                {
                    "log_id": str(uuid4()),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "actor": f"user-{i}",
                    "action_type": "document:upload",
                    "target_resource": f"/documents/doc-{i}",
                    "old_value": {},
                    "new_value": {},
                    "checksum": "c" * 64,
                }
            )
        )


@when("合规工程师分页查询（page: 1, page_size: 10）")
def paginated_query_page1(fake_repo: FakeAuditRepository) -> AuditSearchResult:
    return asyncio.get_event_loop().run_until_complete(fake_repo.search(AuditSearchCriteria(offset=0, limit=10)))


@then("返回前 10 条日志")
def returns_first_10(paginated_query_page1: AuditSearchResult) -> None:
    assert len(paginated_query_page1.items) <= 10


@then("返回结果包含 total 字段")
def has_total_field(paginated_query_page1: AuditSearchResult) -> None:
    assert paginated_query_page1.total >= 10


# =============================================================================
# AC-3: 验证审计日志完整性
# =============================================================================


@scenario("test_story_1_10.feature", "验证审计日志完整性")
def test_verify_integrity() -> None:
    """Test verifying audit log integrity."""
    pass


@given("审计日志已记录")
def log_recorded(audit_service: AuditServiceImpl) -> AuditRecord:
    return asyncio.get_event_loop().run_until_complete(
        audit_service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
        )
    )


@when('系统验证日志完整性（log_id: "{log_id}"）')
def verify_log_integrity(
    audit_service: AuditServiceImpl,
    log_recorded: AuditRecord,
) -> bool:
    return asyncio.get_event_loop().run_until_complete(audit_service.verify_integrity(log_recorded.log_id))


@then("SHA256 校验和验证通过")
def checksum_verified(verify_log_integrity: bool) -> None:
    assert verify_log_integrity is True


@then("返回验证结果（integrity_verified: true）")
def integrity_result_true(verify_log_integrity: bool) -> None:
    assert verify_log_integrity is True


# =============================================================================
# AC-3: 检测篡改的审计日志
# =============================================================================


@scenario("test_story_1_10.feature", "检测篡改的审计日志")
def test_detect_tampering() -> None:
    """Test detecting tampered audit log."""
    pass


@given("日志被篡改（修改 old_value）")
def log_tampered(log_recorded: AuditRecord, fake_repo: FakeAuditRepository) -> None:
    saved = asyncio.get_event_loop().run_until_complete(fake_repo.get_by_id(log_recorded.log_id))
    if saved:
        saved["actor"] = "hacker-999"
        saved["checksum"] = "invalid_checksum"


@then("校验和验证失败")
def checksum_fails(verify_log_integrity: bool) -> None:
    assert verify_log_integrity is False


@then("返回验证结果（integrity_verified: false）")
def integrity_result_false(verify_log_integrity: bool) -> None:
    assert verify_log_integrity is False


# =============================================================================
# AC-3: 批量验证审计日志完整性
# =============================================================================


@scenario("test_story_1_10.feature", "批量验证审计日志完整性")
def test_batch_verify_integrity() -> None:
    """Test batch verification of audit log integrity."""
    pass


@when("系统批量验证完整性")
def batch_verify(
    audit_service: AuditServiceImpl,
    fake_repo: FakeAuditRepository,
) -> dict[str, Any]:
    # Create a few logs
    log_ids = []
    for i in range(3):
        record = asyncio.get_event_loop().run_until_complete(
            audit_service.record(
                actor=f"user-{i}",
                action_type="authentication:login",
                target_resource="/api/v1/auth/login",
            )
        )
        log_ids.append(record.log_id)

    return asyncio.get_event_loop().run_until_complete(audit_service.verify_batch(log_ids))


@then("返回验证摘要（total: N, passed: M, failed: K）")
def verify_summary(batch_verify: dict[str, Any]) -> None:
    assert "total" in batch_verify
    assert "passed" in batch_verify
    assert "failed" in batch_verify
    assert batch_verify["total"] == 3
    assert batch_verify["passed"] == 3
    assert batch_verify["failed"] == 0


@then("包含每条日志的验证详情")
def has_details(batch_verify: dict[str, Any]) -> None:
    assert "details" in batch_verify
    assert len(batch_verify["details"]) == 3


# =============================================================================
# AC-4: 手动归档旧的审计日志
# =============================================================================


@scenario("test_story_1_10.feature", "手动归档旧的审计日志")
def test_manual_archive() -> None:
    """Test manual archival of old audit logs."""
    pass


@given("审计日志已记录超过 30 天")
def old_logs_exist(fake_repo: FakeAuditRepository) -> None:
    asyncio.get_event_loop().run_until_complete(
        fake_repo.save(
            {
                "log_id": str(uuid4()),
                "timestamp": (datetime.now(UTC) - timedelta(days=35)).isoformat(),
                "actor": "user-old",
                "action_type": "authentication:login",
                "target_resource": "/api/v1/auth/login",
                "old_value": {},
                "new_value": {},
                "checksum": "d" * 64,
            }
        )
    )


@when("管理员手动触发归档（older_than_days: 30）")
def trigger_archive(audit_service: AuditServiceImpl) -> int:
    return asyncio.get_event_loop().run_until_complete(audit_service.archive(older_than_days=30))


@then("旧日志归档到 WORM 存储")
def logs_archived_to_worm(trigger_archive: int) -> None:
    assert trigger_archive >= 1


@then("archived 标志更新为 true")
def archived_flag_updated(trigger_archive: int) -> None:
    assert trigger_archive >= 1


# =============================================================================
# AC-4: 查询归档状态
# =============================================================================


@scenario("test_story_1_10.feature", "查询归档状态")
def test_query_archive_status() -> None:
    """Test querying archive status."""
    pass


@given("审计日志已归档")
def log_archived(fake_repo: FakeAuditRepository) -> UUID:
    log_id = uuid4()
    asyncio.get_event_loop().run_until_complete(
        fake_repo.save(
            {
                "log_id": str(log_id),
                "timestamp": datetime.now(UTC).isoformat(),
                "actor": "user-1",
                "action_type": "authentication:login",
                "target_resource": "/api/v1/auth/login",
                "old_value": {},
                "new_value": {},
                "checksum": "e" * 64,
                "archived": True,
                "archived_at": datetime.now(UTC).isoformat(),
            }
        )
    )
    return log_id


@when('合规工程师查询归档状态（log_id: "{log_id}"）')
def query_archive_status(
    fake_repo: FakeAuditRepository,
    log_archived: UUID,
) -> dict[str, Any] | None:
    return asyncio.get_event_loop().run_until_complete(fake_repo.get_archive_status(log_archived))


@then('返回归档状态（archived: true, archived_at: "{timestamp}"）')
def returns_archive_status(query_archive_status: dict[str, Any] | None) -> None:
    assert query_archive_status is not None
    assert query_archive_status["archived"] is True
    assert query_archive_status["archived_at"] is not None
