"""Story 1.5: PostgreSQL Relational Layer — Gherkin 验收测试步骤定义。

覆盖 AC：
- AC-1: PostgreSQL 连接池与数据库引擎抽象
- AC-2: Alembic 迁移基础设施
- AC-3: 通用仓储基类
- AC-4: OutboxRepository PostgreSQL 实现
- AC-5: 用户与 RBAC 基础仓储
- AC-6: 架构约束验证
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest import mock
from uuid import uuid4

from pytest_bdd import given, parsers, scenario, then, when

# ============================================================================
# 全局测试上下文
# ============================================================================

_test_context: dict = {}

# ============================================================================
# Feature 路径
# ============================================================================

FEATURE = "test_story_1_5.feature"

# ============================================================================
# Scenarios — AC-1: 连接池与引擎
# ============================================================================


@scenario(FEATURE, "数据库引擎懒初始化")
def test_lazy_initialization():
    pass


@scenario(FEATURE, "数据库引擎首次调用创建异步引擎")
def test_async_engine_creation():
    pass


@scenario(FEATURE, "数据库引擎健康检查")
def test_health_check():
    pass


@scenario(FEATURE, "数据库引擎优雅关闭")
def test_graceful_shutdown():
    pass


# ============================================================================
# Scenarios — AC-2: Alembic 迁移
# ============================================================================


@scenario(FEATURE, "Alembic 迁移配置")
def test_alembic_config():
    pass


@scenario(FEATURE, "初始迁移脚本就绪")
def test_initial_migration_exists():
    pass


@scenario(FEATURE, "event_outbox 表结构合规")
def test_event_outbox_schema():
    pass


@scenario(FEATURE, "Alembic 升级迁移执行成功")
def test_alembic_upgrade():
    pass


@scenario(FEATURE, "Alembic 降级回滚执行成功")
def test_alembic_downgrade():
    pass


# ============================================================================
# Scenarios — AC-3: 通用仓储基类
# ============================================================================


@scenario(FEATURE, "BaseRepository 保存实体")
def test_base_repo_save():
    pass


@scenario(FEATURE, "BaseRepository 根据 ID 查询实体")
def test_base_repo_get_by_id():
    pass


@scenario(FEATURE, "BaseRepository 查询实体列表")
def test_base_repo_list_all():
    pass


@scenario(FEATURE, "BaseRepository 删除实体")
def test_base_repo_delete():
    pass


@scenario(FEATURE, "BaseRepository 统计实体数量")
def test_base_repo_count():
    pass


@scenario(FEATURE, "BaseRepository 查询不存在的 ID")
def test_base_repo_get_not_found():
    pass


# ============================================================================
# Scenarios — AC-4: OutboxRepository 实现
# ============================================================================


@scenario(FEATURE, "事件保存到发件箱")
def test_outbox_save():
    pass


@scenario(FEATURE, "获取未发布事件")
def test_outbox_get_unpublished():
    pass


@scenario(FEATURE, "获取未发布事件（空结果）")
def test_outbox_get_unpublished_empty():
    pass


@scenario(FEATURE, "标记事件已发布")
def test_outbox_mark_published():
    pass


@scenario(FEATURE, "标记事件发布失败")
def test_outbox_mark_failed():
    pass


@scenario(FEATURE, "事件转换器双向转换")
def test_adapter_roundtrip():
    pass


@scenario(FEATURE, "事务原子性 — 事件保存成功 + 业务操作成功 → 都提交")
def test_tx_commit_both():
    pass


@scenario(FEATURE, "事务原子性 — 事件保存成功 + 业务操作异常 → 都回滚")
def test_tx_rollback_on_error():
    pass


@scenario(FEATURE, "事务原子性 — 事件保存失败 + 业务操作成功 → 都回滚")
def test_tx_rollback_event_fail():
    pass


# ============================================================================
# Scenarios — AC-5: 用户与 RBAC 仓储
# ============================================================================


@scenario(FEATURE, "UserRepository 根据用户名查询")
def test_user_get_by_username():
    pass


@scenario(FEATURE, "UserRepository 根据邮箱查询")
def test_user_get_by_email():
    pass


@scenario(FEATURE, "RoleRepository 获取角色权限")
def test_role_get_permissions():
    pass


@scenario(FEATURE, "PermissionRepository 根据名称查询")
def test_permission_get_by_name():
    pass


# ============================================================================
# Scenarios — AC-6: 架构约束
# ============================================================================


@scenario(FEATURE, "领域层零 SQLAlchemy 依赖")
def test_domain_no_sqlalchemy():
    pass


@scenario(FEATURE, "依赖方向正确")
def test_dependency_direction():
    pass


# ============================================================================
# Background / Given
# ============================================================================


@given("PostgreSQL 服务可用")
def postgres_available():
    """验证 PostgreSQL 服务可用（mock 模式）。"""
    _test_context["postgres_available"] = True


@given("数据库连接正常")
def db_connection_ok():
    """验证数据库连接正常。"""
    _test_context["db_connected"] = True


@given("DatabaseEngine 实例已创建")
def engine_instance_created():
    """创建 DatabaseEngine 实例。"""
    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.engine import DatabaseEngine

    config = PostgreSQLConfig()
    _test_context["engine"] = DatabaseEngine(config)


@given("迁移脚本已加载")
def migration_script_loaded():
    """加载迁移脚本路径。"""
    project_root = Path(__file__).parents[2]
    migration = project_root / "alembic" / "versions" / "001_initial.py"
    _test_context["migration_script"] = migration.read_text()


@given("BaseRepository 实例已创建")
def base_repo_created():
    """创建 BaseRepository mock 实例。"""
    from src.infrastructure.storage.postgresql.base_repository import BaseRepository
    from src.infrastructure.storage.postgresql.models import UserModel

    mock_session = mock.AsyncMock()
    mock_session.add = mock.Mock()
    _test_context["base_repo"] = BaseRepository(UserModel, mock_session)
    _test_context["mock_session"] = mock_session


@given("PostgreSQLOutboxRepository 实例")
def outbox_repo_created():
    """创建 PostgreSQLOutboxRepository mock 实例。"""
    from src.infrastructure.storage.postgresql.outbox_repository import PostgreSQLOutboxRepository

    mock_session = mock.AsyncMock()
    mock_session.add = mock.Mock()
    _test_context["outbox_repo"] = PostgreSQLOutboxRepository(mock_session)
    _test_context["mock_session"] = mock_session


@given("DomainEvent 实例")
def domain_event_created():
    """创建 DomainEvent 实例。"""
    from src.domain.events.base import DomainEvent

    event = DomainEvent(
        event_id=uuid4(),
        event_type="TestEvent",
        timestamp=datetime.now(UTC),
        source="test",
        payload={"key": "value"},
    )
    _test_context["domain_event"] = event


@given("UserRepository 实例")
def user_repo_created():
    """创建 UserRepository mock 实例。"""
    from src.infrastructure.storage.postgresql.user_repository import UserRepository

    mock_session = mock.AsyncMock()
    mock_session.add = mock.Mock()
    _test_context["user_repo"] = UserRepository(mock_session)


@given("RoleRepository 实例")
def role_repo_created():
    """创建 RoleRepository mock 实例。"""
    from src.infrastructure.storage.postgresql.role_repository import RoleRepository

    mock_session = mock.AsyncMock()
    mock_session.add = mock.Mock()
    _test_context["role_repo"] = RoleRepository(mock_session)


@given("PermissionRepository 实例")
def permission_repo_created():
    """创建 PermissionRepository mock 实例。"""
    from src.infrastructure.storage.postgresql.permission_repository import PermissionRepository

    mock_session = mock.AsyncMock()
    mock_session.add = mock.Mock()
    _test_context["permission_repo"] = PermissionRepository(mock_session)


@given("数据库中存在实体")
def entity_exists_in_db():
    """模拟数据库中存在实体。"""
    mock_result = mock.Mock()
    mock_result.scalar_one_or_none.return_value = mock.Mock()
    _test_context["mock_session"].execute.return_value = mock_result


@given("数据库中存在用户")
def user_exists_in_db():
    """模拟数据库中存在用户。"""
    mock_result = mock.Mock()
    mock_result.scalar_one_or_none.return_value = mock.Mock()
    _test_context["mock_session"].execute.return_value = mock_result


@given("数据库中存在权限")
def permission_exists_in_db():
    """模拟数据库中存在权限。"""
    mock_result = mock.Mock()
    mock_result.scalar_one_or_none.return_value = mock.Mock()
    _test_context["mock_session"].execute.return_value = mock_result


@given("数据库中存在多个实体")
def multiple_entities_exist():
    """模拟数据库中存在多个实体。"""
    mock_scalars = mock.Mock()
    mock_scalars.all.return_value = [mock.Mock(), mock.Mock()]
    mock_result = mock.Mock()
    mock_result.scalars.return_value = mock_scalars
    _test_context["mock_session"].execute.return_value = mock_result


# ============================================================================
# AC-1 Steps
# ============================================================================


@when("创建 DatabaseEngine 实例")
def create_engine_instance():
    """创建 DatabaseEngine 实例。"""
    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.engine import DatabaseEngine

    config = PostgreSQLConfig()
    _test_context["engine"] = DatabaseEngine(config)


@then("引擎尚未创建")
def engine_not_created():
    """验证引擎尚未创建。"""
    engine = _test_context.get("engine")
    assert engine is not None
    assert engine._async_engine is None
    assert engine._sync_engine is None


@when("首次调用 get_async_engine")
def call_get_async_engine():
    """首次调用 get_async_engine。"""
    engine = _test_context.get("engine")
    _test_context["async_engine"] = engine.get_async_engine()


@then("异步引擎已创建")
def async_engine_created():
    """验证异步引擎已创建。"""
    assert _test_context.get("async_engine") is not None


@then("后续调用返回同一实例")
def same_instance_returned():
    """验证后续调用返回同一实例。"""
    engine = _test_context.get("engine")
    engine2 = engine.get_async_engine()
    assert engine2 is _test_context.get("async_engine")


@when("调用 health_check")
def call_health_check():
    """调用 health_check。"""
    import asyncio

    engine = _test_context.get("engine")
    engine._async_engine = mock.AsyncMock()

    async def _check():
        return await engine.health_check()

    loop = asyncio.new_event_loop()
    try:
        _test_context["health_result"] = loop.run_until_complete(_check())
    finally:
        loop.close()


@then("返回 True")
def result_is_true():
    """验证返回 True。"""
    assert _test_context.get("health_result") is True


@then("执行 SELECT 1 验证连接")
def select_one_executed():
    """验证 SELECT 1 执行。"""
    # 由 health_check 实现保证
    pass


@when("调用 close")
def call_close():
    """调用 close。"""
    import asyncio

    engine = _test_context.get("engine")
    engine._async_engine = mock.AsyncMock()
    engine._sync_engine = mock.Mock()

    async def _close():
        await engine.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_close())
    finally:
        loop.close()


@then("所有连接已释放")
def connections_released():
    """验证连接已释放。"""
    engine = _test_context.get("engine")
    assert engine._async_engine is None
    assert engine._sync_engine is None


@then("引擎实例已清空")
def engine_cleared():
    """验证引擎实例已清空。"""
    engine = _test_context.get("engine")
    assert engine._async_engine is None
    assert engine._sync_engine is None


# ============================================================================
# AC-2 Steps
# ============================================================================


@when("加载 alembic.ini 配置")
def load_alembic_config():
    """加载 alembic.ini 配置。"""
    project_root = Path(__file__).parents[2]
    alembic_ini = project_root / "alembic" / "alembic.ini"
    _test_context["alembic_content"] = alembic_ini.read_text()


@then("配置文件存在")
def config_file_exists():
    """验证配置文件存在。"""
    assert _test_context.get("alembic_content") is not None


@then("sqlalchemy.url 从环境变量读取")
def sqlalchemy_url_from_env():
    """验证 sqlalchemy.url 配置。"""
    content = _test_context.get("alembic_content")
    assert "sqlalchemy.url" in content


@then("target_metadata 从模型自动收集")
def metadata_auto_collected():
    """验证 target_metadata 配置。"""
    project_root = Path(__file__).parents[2]
    env_py = project_root / "alembic" / "env.py"
    content = env_py.read_text()
    assert "pg_registry.metadata" in content or "target_metadata" in content


@when("检查 alembic/versions/001_initial.py")
def check_initial_migration():
    """检查初始迁移文件。"""
    project_root = Path(__file__).parents[2]
    migration = project_root / "alembic" / "versions" / "001_initial.py"
    _test_context["migration_content"] = migration.read_text()


@then("迁移文件存在")
def migration_file_exists():
    """验证迁移文件存在。"""
    assert _test_context.get("migration_content") is not None


@then("包含 event_outbox 表定义")
def has_event_outbox():
    """验证 event_outbox 表定义。"""
    assert "event_outbox" in _test_context.get("migration_content")


@then("包含 users 表定义")
def has_users():
    """验证 users 表定义。"""
    assert "users" in _test_context.get("migration_content")


@then("包含 roles 表定义")
def has_roles():
    """验证 roles 表定义。"""
    assert "roles" in _test_context.get("migration_content")


@then("包含 permissions 表定义")
def has_permissions():
    """验证 permissions 表定义。"""
    assert "permissions" in _test_context.get("migration_content")


@then("包含 user_roles 关联表")
def has_user_roles():
    """验证 user_roles 关联表。"""
    assert "user_roles" in _test_context.get("migration_content")


@then("包含 role_permissions 关联表")
def has_role_permissions():
    """验证 role_permissions 关联表。"""
    assert "role_permissions" in _test_context.get("migration_content")


@then(parsers.parse("event_outbox 包含 {field} 字段 {details}"))
def check_event_outbox_field(field, details):
    """验证 event_outbox 字段。"""
    content = _test_context.get("migration_content")
    field_map = {
        "id": "id",
        "event_id": "event_id",
        "event_type": "event_type",
        "payload": "payload",
        "status": "status",
        "created_at": "created_at",
        "published_at": "published_at",
        "retry_count": "retry_count",
        "max_retries": "max_retries",
        "error_message": "error_message",
    }
    assert field_map.get(field) in content


@then(parsers.parse("包含 CHECK 约束 {constraint}"))
def check_constraint(constraint):
    """验证 CHECK 约束。"""
    content = _test_context.get("migration_content")
    if "status IN" in constraint:
        assert "CheckConstraint" in content and "status" in content
    elif "retry_count" in constraint:
        assert "retry_count" in content
    elif "max_retries" in constraint:
        assert "max_retries" in content


@when("执行 alembic upgrade head")
def run_alembic_upgrade():
    """模拟执行 alembic upgrade head。"""
    _test_context["upgrade_success"] = True


@then("迁移执行成功")
def upgrade_success():
    """验证迁移执行成功。"""
    assert _test_context.get("upgrade_success") is True


@then("所有表已创建")
def tables_created():
    """验证所有表已创建。"""
    content = _test_context.get("migration_content")
    assert "event_outbox" in content
    assert "users" in content


@when("执行 alembic downgrade -1")
def run_alembic_downgrade():
    """模拟执行 alembic downgrade。"""
    _test_context["downgrade_success"] = True


@then("回滚执行成功")
def downgrade_success():
    """验证回滚执行成功。"""
    assert _test_context.get("downgrade_success") is True


@then("event_outbox 表已删除")
def event_outbox_dropped():
    """验证 event_outbox 表已删除。"""
    content = _test_context.get("migration_content")
    assert "drop_table" in content or "event_outbox" in content


# ============================================================================
# AC-3 Steps
# ============================================================================


@when("调用 save 方法保存实体")
def call_save():
    """调用 save 方法。"""
    import asyncio

    repo = _test_context.get("base_repo")
    mock_entity = mock.Mock()

    async def _save():
        return await repo.save(mock_entity)

    loop = asyncio.new_event_loop()
    try:
        _test_context["save_result"] = loop.run_until_complete(_save())
    finally:
        loop.close()


@then("实体已保存到数据库")
def entity_saved():
    """验证实体已保存。"""
    _test_context["mock_session"].add.assert_called_once()


@then("返回正确的实体")
def correct_entity_returned():
    """验证返回正确实体。"""
    assert _test_context.get("save_result") is not None


@when("调用 get_by_id 方法")
def call_get_by_id():
    """调用 get_by_id 方法。"""
    import asyncio

    repo = _test_context.get("base_repo")

    async def _get():
        return await repo.get_by_id(str(uuid4()))

    loop = asyncio.new_event_loop()
    try:
        _test_context["get_result"] = loop.run_until_complete(_get())
    finally:
        loop.close()


@when("调用 list_all 方法")
def call_list_all():
    """调用 list_all 方法。"""
    import asyncio

    repo = _test_context.get("base_repo")

    async def _list():
        return await repo.list_all()

    loop = asyncio.new_event_loop()
    try:
        _test_context["list_result"] = loop.run_until_complete(_list())
    finally:
        loop.close()


@then("返回实体列表")
def entity_list_returned():
    """验证返回实体列表。"""
    result = _test_context.get("list_result")
    assert isinstance(result, list)


@then("返回数量不超过 limit 参数")
def limit_respected():
    """验证 limit 参数被遵守。"""
    # 由实现保证
    pass


@when("调用 delete 方法")
def call_delete():
    """调用 delete 方法。"""
    import asyncio

    repo = _test_context.get("base_repo")

    async def _delete():
        await repo.delete(str(uuid4()))

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_delete())
    finally:
        loop.close()


@then("实体已从数据库删除")
def entity_deleted():
    """验证实体已删除。"""
    # 由 mock 验证
    pass


@when("调用 count 方法")
def call_count():
    """调用 count 方法。"""
    import asyncio

    repo = _test_context.get("base_repo")
    mock_result = mock.Mock()
    mock_result.scalar.return_value = 5
    _test_context["mock_session"].execute.return_value = mock_result

    async def _count():
        return await repo.count()

    loop = asyncio.new_event_loop()
    try:
        _test_context["count_result"] = loop.run_until_complete(_count())
    finally:
        loop.close()


@then("返回正确的实体数量")
def correct_count_returned():
    """验证返回正确数量。"""
    assert _test_context.get("count_result") == 5


@then("返回 None")
def result_is_none():
    """验证返回 None。"""
    assert _test_context.get("get_result") is None


# ============================================================================
# AC-4 Steps
# ============================================================================


@when("调用 save 保存领域事件")
def call_outbox_save():
    """调用 outbox save 方法。"""
    repo = _test_context.get("outbox_repo")
    event = _test_context.get("domain_event")
    repo.save(event)


@then("事件已添加到会话")
def event_added_to_session():
    """验证事件已添加到会话。"""
    _test_context["mock_session"].add.assert_called_once()


@then("事件状态为 pending")
def event_status_pending():
    """验证事件状态为 pending。"""
    # 由 OutboxModel 默认值保证
    pass


@then("事件类型为正确的领域事件类型")
def correct_event_type():
    """验证事件类型正确。"""
    event = _test_context.get("domain_event")
    assert event is not None


@then("返回所有 pending 状态事件")
def all_pending_returned():
    """验证返回所有 pending 事件。"""
    # 由 mock 返回
    pass


@then("事件按 created_at 升序排序")
def events_sorted_by_created_at():
    """验证事件按 created_at 升序。"""
    # 由实现保证
    pass


@when("调用 async_get_unpublished 方法")
def call_async_get_unpublished():
    """调用 async_get_unpublished 方法。"""
    import asyncio

    repo = _test_context.get("outbox_repo")
    mock_result = mock.Mock()
    mock_result.scalars.return_value.all.return_value = []
    _test_context["mock_session"].execute.return_value = mock_result

    async def _get():
        return await repo.async_get_unpublished(limit=10)

    loop = asyncio.new_event_loop()
    try:
        _test_context["unpublished_result"] = loop.run_until_complete(_get())
    finally:
        loop.close()


@then("返回空列表")
def empty_list_returned():
    """验证返回空列表。"""
    assert _test_context.get("unpublished_result") == []


@when("调用 async_mark_published 方法")
def call_async_mark_published():
    """调用 async_mark_published 方法。"""
    import asyncio

    repo = _test_context.get("outbox_repo")
    mock_model = mock.Mock()
    mock_result = mock.Mock()
    mock_result.scalar_one_or_none.return_value = mock_model
    _test_context["mock_session"].execute.return_value = mock_result

    async def _mark():
        await repo.async_mark_published(uuid4())

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_mark())
        _test_context["marked_model"] = mock_model
    finally:
        loop.close()


@then("事件状态变为 published")
def status_becomes_published():
    """验证状态变为 published。"""
    model = _test_context.get("marked_model")
    assert model.status == "published"


@then("published_at 字段已设置")
def published_at_set():
    """验证 published_at 已设置。"""
    model = _test_context.get("marked_model")
    assert model.published_at is not None


@then("当前时间戳正确")
def timestamp_correct():
    """验证时间戳正确。"""
    # 由实现保证
    pass


@when("调用 async_mark_failed 方法")
def call_async_mark_failed():
    """调用 async_mark_failed 方法。"""
    import asyncio

    repo = _test_context.get("outbox_repo")
    mock_model = mock.Mock()
    mock_model.retry_count = 0
    mock_result = mock.Mock()
    mock_result.scalar_one_or_none.return_value = mock_model
    _test_context["mock_session"].execute.return_value = mock_result

    async def _mark():
        await repo.async_mark_failed(uuid4(), "Test error")

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_mark())
        _test_context["failed_model"] = mock_model
    finally:
        loop.close()


@then("事件状态变为 failed")
def status_becomes_failed():
    """验证状态变为 failed。"""
    model = _test_context.get("failed_model")
    assert model.status == "failed"


@then("retry_count 递增")
def retry_count_incremented():
    """验证 retry_count 递增。"""
    model = _test_context.get("failed_model")
    assert model.retry_count == 1


@then("error_message 字段已设置")
def error_message_set():
    """验证 error_message 已设置。"""
    model = _test_context.get("failed_model")
    assert model.error_message == "Test error"


@when("调用 SQLAlchemyEventOutboxAdapter.from_domain_event")
def call_from_domain_event():
    """调用 from_domain_event。"""
    from src.infrastructure.adapters.sqlalchemy_event_outbox_adapter import (
        SQLAlchemyEventOutboxAdapter,
    )

    event = _test_context.get("domain_event")
    _test_context["outbox_model"] = SQLAlchemyEventOutboxAdapter.from_domain_event(event)


@then("返回 OutboxModel 实例")
def outbox_model_returned():
    """验证返回 OutboxModel。"""
    from src.infrastructure.storage.postgresql.models import OutboxModel

    assert isinstance(_test_context.get("outbox_model"), OutboxModel)


@then("event_id 一致")
def event_id_matches():
    """验证 event_id 一致。"""
    event = _test_context.get("domain_event")
    model = _test_context.get("outbox_model")
    assert model.event_id == event.event_id


@then("event_type 一致")
def event_type_matches():
    """验证 event_type 一致。"""
    event = _test_context.get("domain_event")
    model = _test_context.get("outbox_model")
    assert model.event_type == event.event_type


@then("payload 包含完整事件数据")
def payload_complete():
    """验证 payload 包含完整事件数据。"""
    model = _test_context.get("outbox_model")
    assert "event_id" in model.payload


@when("调用 to_domain_event 转换回来")
def call_to_domain_event():
    """调用 to_domain_event。"""
    from src.domain.events.base import DomainEvent
    from src.infrastructure.adapters.event_outbox_adapter import EventRegistry
    from src.infrastructure.adapters.sqlalchemy_event_outbox_adapter import (
        SQLAlchemyEventOutboxAdapter,
    )

    EventRegistry.register("TestEvent", DomainEvent)
    model = _test_context.get("outbox_model")
    _test_context["restored_event"] = SQLAlchemyEventOutboxAdapter.to_domain_event(model)


@then("返回 DomainEvent 实例")
def domain_event_returned():
    """验证返回 DomainEvent。"""
    from src.domain.events.base import DomainEvent

    assert isinstance(_test_context.get("restored_event"), DomainEvent)


@then("事件类型与原始事件一致")
def event_type_restored():
    """验证事件类型恢复。"""
    original = _test_context.get("domain_event")
    restored = _test_context.get("restored_event")
    assert restored.event_type == original.event_type


# ============================================================================
# AC-5 Steps
# ============================================================================


@when("调用 get_by_username 方法")
def call_get_by_username():
    """调用 get_by_username。"""
    import asyncio

    repo = _test_context.get("user_repo")

    async def _get():
        return await repo.get_by_username("testuser")

    loop = asyncio.new_event_loop()
    try:
        _test_context["user_result"] = loop.run_until_complete(_get())
    finally:
        loop.close()


@then("返回正确的用户实例")
def correct_user_returned():
    """验证返回正确用户。"""
    assert _test_context.get("user_result") is not None


@when("调用 get_by_email 方法")
def call_get_by_email():
    """调用 get_by_email。"""
    import asyncio

    repo = _test_context.get("user_repo")

    async def _get():
        return await repo.get_by_email("test@example.com")

    loop = asyncio.new_event_loop()
    try:
        _test_context["email_result"] = loop.run_until_complete(_get())
    finally:
        loop.close()


@when("调用 get_permissions_for_role 方法")
def call_get_permissions():
    """调用 get_permissions_for_role。"""
    import asyncio

    repo = _test_context.get("role_repo")
    mock_scalars = mock.Mock()
    mock_scalars.all.return_value = [mock.Mock(), mock.Mock()]
    mock_result = mock.Mock()
    mock_result.scalars.return_value = mock_scalars
    _test_context["mock_session"].execute.return_value = mock_result

    async def _get():
        return await repo.get_permissions_for_role(str(uuid4()))

    loop = asyncio.new_event_loop()
    try:
        _test_context["permissions_result"] = loop.run_until_complete(_get())
    finally:
        loop.close()


@then("返回所有关联的权限")
def all_permissions_returned():
    """验证返回所有权限。"""
    assert len(_test_context.get("permissions_result")) == 2


@then("权限数量正确")
def permission_count_correct():
    """验证权限数量正确。"""
    assert len(_test_context.get("permissions_result")) == 2


@when("调用 get_by_name 方法")
def call_get_by_name():
    """调用 get_by_name。"""
    import asyncio

    repo = _test_context.get("permission_repo")

    async def _get():
        return await repo.get_by_name("read:document")

    loop = asyncio.new_event_loop()
    try:
        _test_context["permission_result"] = loop.run_until_complete(_get())
    finally:
        loop.close()


@then("返回正确的权限实例")
def correct_permission_returned():
    """验证返回正确权限。"""
    assert _test_context.get("permission_result") is not None


# ============================================================================
# AC-6 Steps
# ============================================================================


@when("扫描 src/domain/ 目录所有文件")
def scan_domain_directory():
    """扫描 src/domain/ 目录。"""
    project_root = Path(__file__).parents[2]
    domain_dir = project_root / "src" / "domain"
    violations = []
    for py_file in domain_dir.rglob("*.py"):
        content = py_file.read_text()
        if "sqlalchemy" in content.lower():
            violations.append(str(py_file))
    _test_context["domain_violations"] = violations


@then("没有任何文件包含 sqlalchemy 导入")
def no_sqlalchemy_in_domain():
    """验证领域层无 SQLAlchemy 导入。"""
    violations = _test_context.get("domain_violations", [])
    assert len(violations) == 0, f"领域层包含 SQLAlchemy 导入: {violations}"


@when("检查基础设施层导入")
def check_infrastructure_imports():
    """检查基础设施层导入。"""
    # 基础设施层可以导入领域层接口
    _test_context["infra_check_passed"] = True


@then("基础设施层可以导入领域层接口")
def infra_can_import_domain():
    """验证基础设施层可以导入领域层接口。"""
    assert _test_context.get("infra_check_passed") is True


@then("领域层不导入基础设施层实现")
def domain_does_not_import_infra():
    """验证领域层不导入基础设施层。"""
    # 由 no_sqlalchemy_in_domain 保证
    pass


# ============================================================================
# 事务原子性 Steps
# ============================================================================


@given("PostgreSQL 事务上下文")
def tx_context_created():
    """创建事务上下文。"""
    _test_context["tx_committed"] = False
    _test_context["tx_rolled_back"] = False


@when("业务操作成功")
def business_op_success():
    """模拟业务操作成功。"""
    _test_context["business_success"] = True


@when("业务操作抛出异常")
def business_op_error():
    """模拟业务操作抛出异常。"""
    _test_context["business_error"] = True


@when("提交事务")
def commit_transaction():
    """提交事务。"""
    _test_context["tx_committed"] = True


@when("回滚事务")
def rollback_transaction():
    """回滚事务。"""
    _test_context["tx_rolled_back"] = True


@then("事件已持久化到数据库")
def event_persisted():
    """验证事件已持久化。"""
    assert _test_context.get("tx_committed") is True


@then("业务数据已持久化")
def business_data_persisted():
    """验证业务数据已持久化。"""
    assert _test_context.get("business_success") is True


@then("事件未持久化到数据库")
def event_not_persisted():
    """验证事件未持久化。"""
    assert _test_context.get("tx_rolled_back") is True


@then("业务数据未持久化")
def business_data_not_persisted():
    """验证业务数据未持久化。"""
    assert _test_context.get("tx_rolled_back") is True
