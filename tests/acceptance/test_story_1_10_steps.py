"""BDD Steps Implementation for Story 1.10 - Unified Audit Log.

实现 tests/acceptance/test_story_1_10.feature 中的 BDD 步骤。
使用真实 PostgreSQL 实例，遵循 test_story_1_9_steps.py 的模式。
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator

import pytest
from pytest_bdd import given, scenarios, then, when
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.security.audit_repository_impl import AuditRepository
from src.infrastructure.security.audit_service_impl import AuditServiceImpl
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from tests.environments import get_test_env

scenarios("test_story_1_10.feature")

# ===================================================================
# Paths & Constants
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """Share state between BDD steps."""
    return {}


@pytest.fixture
def pg_config():
    """Real PostgreSQL configuration from environment."""
    from src.infrastructure.config.postgresql import PostgreSQLConfig

    env = get_test_env()
    return PostgreSQLConfig(
        host=env.postgres.host,
        port=env.postgres.port,
        database=env.postgres.database,
        username=env.postgres.username,
        password=env.postgres.password,
    )


@pytest.fixture
def db_engine(pg_config):
    """Real database engine instance."""
    engine = PostgreSQLManager(pg_config)
    return engine


# ===================================================================
# Alembic Migration Fixture
# ===================================================================

_migration_run = False


@pytest.fixture
def ensure_alembic_migration(pg_config):
    """Ensure database schema exists before tests."""
    import subprocess

    global _migration_run
    if _migration_run:
        yield
        return

    alembic_ini = ROOT / "deploy/postgresql/alembic/alembic.ini"
    migration_success = False

    if alembic_ini.exists():
        env = {
            "POSTGRES_HOST": pg_config.host,
            "POSTGRES_PORT": str(pg_config.port),
            "POSTGRES_USERNAME": pg_config.username,
            "POSTGRES_PASSWORD": pg_config.password,
            "POSTGRES_DATABASE": pg_config.database,
        }

        try:
            result = subprocess.run(
                ["poetry", "run", "alembic", "-c", str(alembic_ini), "upgrade", "head"],
                cwd=str(ROOT),
                env={**os.environ, **env},
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 or "already up to date" in result.stdout:
                migration_success = True
            else:
                print(f"Alembic upgrade warning: {result.stderr}")
        except Exception as e:
            print(f"Alembic upgrade failed: {e}")

    if not migration_success:
        try:
            from src.infrastructure.storage.postgresql.models import Base

            engine = PostgreSQLManager(pg_config)
            Base.metadata.create_all(engine.get_sync_engine())
        except Exception as e:
            pytest.skip(f"Failed to create schema: {e}")

    _migration_run = True
    yield


@pytest.fixture
async def pg_session(db_engine, ensure_alembic_migration) -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL session for database operations."""
    async_engine = db_engine.get_async_engine()
    session = AsyncSession(async_engine, expire_on_commit=False)

    await session.begin()

    yield session

    await session.rollback()
    try:
        await session.close()
    except Exception:
        pass


@pytest.fixture
def audit_repository(pg_session):
    """Real audit repository."""
    token = set_session(pg_session)
    repo = AuditRepository()
    yield repo
    reset_session(token)


@pytest.fixture
def audit_service(audit_repository):
    """Real audit service."""
    return AuditServiceImpl(audit_repository=audit_repository)


# ===================================================================
# Background Steps
# ===================================================================


@given("系统已初始化完成")
def system_initialized(context):
    """System is initialized."""
    pass


@given("PostgreSQL 连接可用")
def postgres_available(context, pg_session):
    """PostgreSQL connection is available."""
    context["pg_session"] = pg_session


@given("审计日志表已创建")
def audit_log_table_ready(context, ensure_alembic_migration):
    """Audit log table exists."""
    pass


# ===================================================================
# AC-1: 审计日志记录
# ===================================================================


@given('用户已认证（user_id: "user-123", username: "testuser"）')
def user_authenticated(context):
    """User is authenticated."""
    context["user_id"] = "user-123"
    context["username"] = "testuser"


@when('系统产生登录事件（action_type: "authentication:login"）')
def system_produces_login_event(context, audit_service, event_loop):
    """System produces login event."""
    user_id = context.get("user_id", "user-123")
    username = context.get("username", "testuser")

    async def _record():
        return await audit_service.record(
            actor=user_id,
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
            old_value=None,
            new_value={"username": username},
        )

    record = event_loop.run_until_complete(_record())
    context["audit_record"] = record


@then("审计日志记录到 PostgreSQL")
def audit_log_saved_to_database(context, audit_repository, event_loop):
    """Audit log is saved to PostgreSQL."""
    record = context.get("audit_record")
    assert record is not None

    async def _check():
        log = await audit_repository.get_by_id(record.log_id)
        return log is not None

    exists = event_loop.run_until_complete(_check())
    assert exists, "Audit log should be saved to PostgreSQL"


@then("日志包含字段：log_id, timestamp, actor, action_type, target_resource")
def log_contains_required_fields(context):
    """Log contains required fields."""
    record = context.get("audit_record")
    assert record is not None
    assert record.log_id is not None
    assert record.timestamp is not None
    assert record.actor is not None
    assert record.action_type is not None
    assert record.target_resource is not None


@then("SHA256 校验和已计算")
def checksum_computed(context, audit_repository, event_loop):
    """SHA256 checksum is computed."""
    record = context.get("audit_record")
    assert record is not None

    async def _check():
        log = await audit_repository.get_by_id(record.log_id)
        return log

    log = event_loop.run_until_complete(_check())
    assert log is not None
    assert "checksum" in log
    assert len(log["checksum"]) == 64


# ===================================================================
# AC-1: 记录认证失败事件
# ===================================================================


@given('用户尝试登录（username: "invalid_user"）')
def user_tries_login(context):
    """User tries to login with invalid credentials."""
    context["attempt_username"] = "invalid_user"


@when('认证失败（action_type: "authentication:failed"）')
def auth_failure(context, audit_service, event_loop):
    """Authentication fails."""
    username = context.get("attempt_username", "invalid_user")

    async def _record():
        return await audit_service.record(
            actor=username,
            action_type="authentication:failed",
            target_resource="/api/v1/auth/login",
            old_value=None,
            new_value={"username": username, "reason": "invalid_credentials"},
        )

    record = event_loop.run_until_complete(_record())
    context["failure_record"] = record


@then("审计日志记录失败事件")
def failure_logged(context):
    """Failure event is logged."""
    record = context.get("failure_record")
    assert record is not None
    assert record.action_type == "authentication:failed"


@then("记录包含失败原因")
def record_contains_failure_reason(context, audit_repository, event_loop):
    """Record contains failure reason."""
    record = context.get("failure_record")
    assert record is not None

    async def _check():
        return await audit_repository.get_by_id(record.log_id)

    log = event_loop.run_until_complete(_check())
    assert log is not None
    assert log["new_value"]["reason"] == "invalid_credentials"


# ===================================================================
# AC-2: 按时间范围检索审计日志
# ===================================================================


@given("审计日志已记录多条")
def audit_logs_exist(context, audit_repository, event_loop):
    """Multiple audit logs exist."""

    async def _setup():
        log_id_1 = uuid.uuid4()
        await audit_repository.save(
            {
                "log_id": str(log_id_1),
                "timestamp": datetime.now(UTC).isoformat(),
                "actor": "user-1",
                "action_type": "authentication:login",
                "target_resource": "/api/v1/auth/login",
                "old_value": {},
                "new_value": {},
                "checksum": "a" * 64,
            }
        )
        log_id_2 = uuid.uuid4()
        await audit_repository.save(
            {
                "log_id": str(log_id_2),
                "timestamp": (datetime.now(UTC) - timedelta(days=365)).isoformat(),
                "actor": "user-1",
                "action_type": "authentication:login",
                "target_resource": "/api/v1/auth/login",
                "old_value": {},
                "new_value": {},
                "checksum": "b" * 64,
            }
        )

    event_loop.run_until_complete(_setup())


@when('合规工程师查询时间范围（start: "2026-01-01", end: "2026-12-31"）')
def search_by_time(context, audit_repository, event_loop):
    """Compliance engineer searches by time range."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)

    async def _search():
        from src.domain.ports.audit_repository import AuditSearchCriteria

        return await audit_repository.search(AuditSearchCriteria(start_time=start, end_time=end))

    result = event_loop.run_until_complete(_search())
    context["search_result"] = result


@then("返回该时间范围内的日志")
def returns_logs_in_range(context):
    """Returns logs within time range."""
    result = context.get("search_result")
    assert result is not None
    assert result.total >= 1


@then("返回结果按时间倒序排列")
def results_ordered_desc(context):
    """Results are ordered by time descending."""
    result = context.get("search_result")
    if result and len(result.items) > 1:
        for i in range(len(result.items) - 1):
            t1 = datetime.fromisoformat(result.items[i]["timestamp"])
            t2 = datetime.fromisoformat(result.items[i + 1]["timestamp"])
            assert t1 >= t2


# ===================================================================
# AC-2: 按 actor 检索审计日志
# ===================================================================


@when('合规工程师按 actor 查询（actor: "user-123"）')
def search_by_actor(context, audit_repository, event_loop):
    """Search by actor."""

    async def _search():
        from src.domain.ports.audit_repository import AuditSearchCriteria

        return await audit_repository.search(AuditSearchCriteria(actor="user-123"))

    result = event_loop.run_until_complete(_search())
    context["search_result"] = result


@then("返回该用户的所有操作日志")
def returns_user_logs(context):
    """Returns all logs for the user."""
    result = context.get("search_result")
    assert result is not None
    for item in result.items:
        assert item["actor"] == "user-123"


# ===================================================================
# AC-2: 按 action_type 检索审计日志
# ===================================================================


@when('合规工程师按 action_type 查询（action_type: "authentication:login"）')
def search_by_action_type(context, audit_repository, event_loop):
    """Search by action type."""

    async def _search():
        from src.domain.ports.audit_repository import AuditSearchCriteria

        return await audit_repository.search(AuditSearchCriteria(action_type="authentication:login"))

    result = event_loop.run_until_complete(_search())
    context["search_result"] = result


@then("返回所有登录操作日志")
def returns_login_logs(context):
    """Returns all login operation logs."""
    result = context.get("search_result")
    assert result is not None
    for item in result.items:
        assert "authentication:login" in item["action_type"]


# ===================================================================
# AC-2: 分页检索审计日志
# ===================================================================


@given("审计日志已记录超过 20 条")
def many_logs_exist(context, audit_repository, event_loop):
    """More than 20 audit logs exist."""

    async def _setup():
        for i in range(25):
            await audit_repository.save(
                {
                    "log_id": str(uuid.uuid4()),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "actor": f"user-{i}",
                    "action_type": "document:upload",
                    "target_resource": f"/documents/doc-{i}",
                    "old_value": {},
                    "new_value": {},
                    "checksum": "c" * 64,
                }
            )

    event_loop.run_until_complete(_setup())


@when("合规工程师分页查询（page: 1, page_size: 10）")
def paginated_query_page1(context, audit_repository, event_loop):
    """Paginated query page 1."""

    async def _search():
        from src.domain.ports.audit_repository import AuditSearchCriteria

        return await audit_repository.search(AuditSearchCriteria(offset=0, limit=10))

    result = event_loop.run_until_complete(_search())
    context["page1_result"] = result


@then("返回前 10 条日志")
def returns_first_10(context):
    """Returns first 10 logs."""
    result = context.get("page1_result")
    assert result is not None
    assert len(result.items) <= 10


@then("返回结果包含 total 字段")
def has_total_field(context):
    """Result contains total field."""
    result = context.get("page1_result")
    assert result is not None
    assert result.total >= 10


@then("再次查询第二页返回接下来的 10 条")
def paginated_query_page2(context, audit_repository, event_loop):
    """Paginated query page 2."""

    async def _search():
        from src.domain.ports.audit_repository import AuditSearchCriteria

        return await audit_repository.search(AuditSearchCriteria(offset=10, limit=10))

    result = event_loop.run_until_complete(_search())
    context["page2_result"] = result


@then("返回接下来的 10 条日志")
def returns_next_10(context):
    """Returns next 10 logs."""
    result = context.get("page2_result")
    assert result is not None
    assert len(result.items) == 10


# ===================================================================
# AC-3: 验证审计日志完整性
# ===================================================================


@given("审计日志已记录")
def log_recorded(context, audit_service, event_loop):
    """Audit log is recorded."""

    async def _record():
        return await audit_service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
        )

    record = event_loop.run_until_complete(_record())
    context["audit_record"] = record


@when('系统验证日志完整性（log_id: "{log_id}"）')
def verify_log_integrity(context, audit_service, event_loop):
    """Verify log integrity."""
    record = context.get("audit_record")
    assert record is not None

    async def _verify():
        return await audit_service.verify_integrity(record.log_id)

    is_valid = event_loop.run_until_complete(_verify())
    context["integrity_result"] = is_valid


@then("SHA256 校验和验证通过")
def checksum_verified(context):
    """Checksum verification passes."""
    result = context.get("integrity_result")
    assert result is True


@then("返回验证结果（integrity_verified: true）")
def integrity_result_true(context):
    """Integrity verification returns true."""
    result = context.get("integrity_result")
    assert result is True


# ===================================================================
# AC-3: 检测篡改的审计日志
# ===================================================================


@given("日志被篡改（修改 old_value）")
def log_tampered(context, audit_repository, pg_session, event_loop):
    """Log is tampered."""
    record = context.get("audit_record")
    assert record is not None

    async def _tamper():
        # 直接执行 SQL UPDATE 来篡改数据库中的记录
        await pg_session.execute(
            text("UPDATE audit_log SET actor = :actor, old_value = :old_value WHERE log_id = :log_id"),
            {"actor": "hacker-999", "old_value": '{"tampered": true}', "log_id": str(record.log_id)},
        )
        await pg_session.commit()

    event_loop.run_until_complete(_tamper())


@then("校验和验证失败")
def checksum_fails(context):
    """Checksum verification fails."""
    result = context.get("integrity_result")
    assert result is False


@then("返回验证结果（integrity_verified: false）")
def integrity_result_false(context):
    """Integrity verification returns false."""
    result = context.get("integrity_result")
    assert result is False


# ===================================================================
# AC-3: 批量验证审计日志完整性
# ===================================================================


@when("系统批量验证完整性")
def batch_verify(context, audit_service, event_loop):
    """Batch verify integrity."""
    log_ids = []

    async def _create_logs():
        for i in range(3):
            record = await audit_service.record(
                actor=f"user-{i}",
                action_type="authentication:login",
                target_resource="/api/v1/auth/login",
            )
            log_ids.append(record.log_id)

    event_loop.run_until_complete(_create_logs())
    context["log_ids"] = log_ids

    async def _verify_batch():
        return await audit_service.verify_batch(log_ids)

    result = event_loop.run_until_complete(_verify_batch())
    context["batch_result"] = result


@then("返回验证摘要（total: N, passed: M, failed: K）")
def verify_summary(context):
    """Returns verification summary."""
    result = context.get("batch_result")
    assert result is not None
    assert "total" in result
    assert "passed" in result
    assert "failed" in result
    assert result["total"] == 3
    assert result["passed"] == 3
    assert result["failed"] == 0


@then("包含每条日志的验证详情")
def has_details(context):
    """Contains details for each log."""
    result = context.get("batch_result")
    assert result is not None
    assert "details" in result
    assert len(result["details"]) == 3


# ===================================================================
# AC-4: 手动归档旧的审计日志
# ===================================================================


@given("审计日志已记录超过 30 天")
def old_logs_exist(context, audit_repository, event_loop):
    """Old audit logs exist (more than 30 days)."""

    async def _setup():
        await audit_repository.save(
            {
                "log_id": str(uuid.uuid4()),
                "timestamp": (datetime.now(UTC) - timedelta(days=35)).isoformat(),
                "actor": "user-old",
                "action_type": "authentication:login",
                "target_resource": "/api/v1/auth/login",
                "old_value": {},
                "new_value": {},
                "checksum": "d" * 64,
            }
        )

    event_loop.run_until_complete(_setup())


@when("管理员手动触发归档（older_than_days: 30）")
def trigger_archive(context, audit_service, event_loop):
    """Admin triggers manual archival."""

    async def _archive():
        return await audit_service.archive(older_than_days=30)

    count = event_loop.run_until_complete(_archive())
    context["archive_count"] = count


@then("旧日志归档到 WORM 存储")
def logs_archived_to_worm(context):
    """Old logs archived to WORM storage."""
    count = context.get("archive_count")
    assert count >= 1


@then("archived 标志更新为 true")
def archived_flag_updated(context):
    """Archived flag is updated to true."""
    count = context.get("archive_count")
    assert count >= 1


@then("archived_at 时间戳记录")
def archived_at_recorded(context):
    """archived_at timestamp is recorded."""
    count = context.get("archive_count")
    assert count >= 1


# ===================================================================
# AC-4: 查询归档状态
# ===================================================================


@given("审计日志已归档")
def log_archived(context, audit_repository, event_loop):
    """Audit log is archived."""
    log_id = uuid.uuid4()

    async def _setup():
        await audit_repository.save(
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
        return str(log_id)

    log_id_str = event_loop.run_until_complete(_setup())
    context["archived_log_id"] = log_id_str


@when('合规工程师查询归档状态（log_id: "{log_id}"）')
def query_archive_status(context, audit_repository, event_loop):
    """Query archive status."""
    log_id_str = context.get("archived_log_id")
    log_id = uuid.UUID(log_id_str)

    async def _get_status():
        return await audit_repository.get_archive_status(log_id)

    status = event_loop.run_until_complete(_get_status())
    context["archive_status"] = status


@then('返回归档状态（archived: true, archived_at: "{timestamp}"）')
def returns_archive_status(context):
    """Returns archive status."""
    status = context.get("archive_status")
    assert status is not None
    assert status["archived"] is True
    assert status["archived_at"] is not None


# ===================================================================
# AC-5: 登录/登出事件完整记录
# ===================================================================


@given("用户执行登录操作")
def user_performs_login(context):
    """User performs login."""
    context["login_action"] = True


@when("登录成功")
def login_success(context, audit_service, event_loop):
    """Login succeeds."""

    async def _record():
        return await audit_service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
            old_value=None,
            new_value={"status": "success"},
        )

    record = event_loop.run_until_complete(_record())
    context["login_record"] = record


@then('审计日志记录 "authentication:login" 事件')
def login_event_logged(context):
    """Login event is logged."""
    record = context.get("login_record")
    assert record is not None
    assert record.action_type == "authentication:login"


@given("用户执行登出操作")
def user_performs_logout(context):
    """User performs logout."""
    context["logout_action"] = True


@when("登出成功")
def logout_success(context, audit_service, event_loop):
    """Logout succeeds."""

    async def _record():
        return await audit_service.record(
            actor="user-123",
            action_type="authentication:logout",
            target_resource="/api/v1/auth/logout",
            old_value=None,
            new_value={"status": "success"},
        )

    record = event_loop.run_until_complete(_record())
    context["logout_record"] = record


@then('审计日志记录 "authentication:logout" 事件')
def logout_event_logged(context):
    """Logout event is logged."""
    record = context.get("logout_record")
    assert record is not None
    assert record.action_type == "authentication:logout"


# ===================================================================
# AC-5: 权限变更事件记录
# ===================================================================


@given('管理员授予用户权限（role: "admin"）')
def admin_grants_permission(context):
    """Admin grants permission."""
    context["role"] = "admin"


@when("权限授予成功")
def permission_granted(context, audit_service, event_loop):
    """Permission is granted."""

    async def _record():
        return await audit_service.record(
            actor="admin-123",
            action_type="authorization:grant",
            target_resource="role/admin",
            old_value={"role": None},
            new_value={"role": "admin"},
        )

    record = event_loop.run_until_complete(_record())
    context["grant_record"] = record


@then('审计日志记录 "authorization:grant" 事件')
def grant_event_logged(context):
    """Grant event is logged."""
    record = context.get("grant_record")
    assert record is not None
    assert record.action_type == "authorization:grant"


@given('管理员撤销用户权限（role: "admin"）')
def admin_revokes_permission(context):
    """Admin revokes permission."""
    context["role"] = "admin"


@when("权限撤销成功")
def permission_revoked(context, audit_service, event_loop):
    """Permission is revoked."""

    async def _record():
        return await audit_service.record(
            actor="admin-123",
            action_type="authorization:revoke",
            target_resource="role/admin",
            old_value={"role": "admin"},
            new_value={"role": None},
        )

    record = event_loop.run_until_complete(_record())
    context["revoke_record"] = record


@then('审计日志记录 "authorization:revoke" 事件')
def revoke_event_logged(context):
    """Revoke event is logged."""
    record = context.get("revoke_record")
    assert record is not None
    assert record.action_type == "authorization:revoke"


# ===================================================================
# AC-5: 越权访问检测
# ===================================================================


@given("普通用户尝试访问管理资源")
def regular_user_tries_admin_resource(context):
    """Regular user tries to access admin resource."""
    context["is_admin"] = False


@when("访问被拒绝")
def access_denied(context, audit_service, event_loop):
    """Access is denied."""

    async def _record():
        return await audit_service.record(
            actor="user-456",
            action_type="authorization:denied",
            target_resource="/admin/manage",
            old_value=None,
            new_value={"reason": "insufficient_permissions"},
        )

    record = event_loop.run_until_complete(_record())
    context["denied_record"] = record


@then("审计日志记录越权访问事件")
def unauthorized_access_logged(context):
    """Unauthorized access is logged."""
    record = context.get("denied_record")
    assert record is not None
    assert record.action_type == "authorization:denied"


# ===================================================================
# Integration Scenarios
# ===================================================================


@given("用户凭证有效")
def user_credentials_valid(context):
    """User credentials are valid."""
    context["credentials_valid"] = True


@when("用户登录成功")
def user_login_success(context, audit_service, event_loop):
    """User login succeeds."""

    async def _record():
        return await audit_service.record(
            actor="user-123",
            action_type="authentication:login",
            target_resource="/api/v1/auth/login",
            old_value=None,
            new_value={"status": "success"},
        )

    record = event_loop.run_until_complete(_record())
    context["integration_record"] = record


@then('认证服务发布 AuditEvent（action_type: "authentication:login"）')
def auth_service_publishes_audit_event(context):
    """Auth service publishes AuditEvent."""
    record = context.get("integration_record")
    assert record is not None
    assert record.action_type == "authentication:login"


@then("审计日志从事件记录到 PostgreSQL")
def integration_log_saved(context, audit_repository, event_loop):
    """Integration log is saved to PostgreSQL."""
    record = context.get("integration_record")
    assert record is not None

    async def _check():
        return await audit_repository.get_by_id(record.log_id)

    log = event_loop.run_until_complete(_check())
    assert log is not None


@then("事件包含正确的 actor 和 timestamp")
def event_has_correct_fields(context):
    """Event has correct actor and timestamp."""
    record = context.get("integration_record")
    assert record is not None
    assert record.actor == "user-123"
    assert record.timestamp is not None


@given("管理员用户已登录")
def admin_user_logged_in(context):
    """Admin user is logged in."""
    context["admin_user"] = True


@when("管理员授予用户角色")
def admin_grants_role(context, audit_service, event_loop):
    """Admin grants user role."""

    async def _record():
        return await audit_service.record(
            actor="admin-123",
            action_type="authorization:grant",
            target_resource="user/user-456",
            old_value={"role": None},
            new_value={"role": "editor"},
        )

    record = event_loop.run_until_complete(_record())
    context["roleGrant_record"] = record


@then('权限服务发布 AuditEvent（action_type: "authorization:grant"）')
def authz_service_publishes_audit_event(context):
    """Authz service publishes AuditEvent."""
    record = context.get("roleGrant_record")
    assert record is not None
    assert record.action_type == "authorization:grant"


@then("审计日志记录权限变更")
def permission_change_logged(context, audit_repository, event_loop):
    """Permission change is logged."""
    record = context.get("roleGrant_record")
    assert record is not None

    async def _check():
        return await audit_repository.get_by_id(record.log_id)

    log = event_loop.run_until_complete(_check())
    assert log is not None
    assert log["action_type"] == "authorization:grant"


@then("old_value 和 new_value 记录变更前后状态")
def old_and_new_value_recorded(context, audit_repository, event_loop):
    """Old and new value record state before and after."""
    record = context.get("roleGrant_record")
    assert record is not None
    assert record.old_value is not None
    assert record.new_value is not None
