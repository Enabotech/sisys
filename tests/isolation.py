# =============================================================================
# SISYS 测试租户隔离管理
# =============================================================================
# 用途：提供测试租户隔离机制，支持 UUID 前缀隔离并行测试
# Story: 20-1 (sisys-testing-refactor) - Phase 3
# =============================================================================

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class TestTenant:
    """测试租户数据类

    提供 UUID 前缀，用于隔离不同测试的資源:
    - RabbitMQ 队列: test_{uuid}_queue
    - Qdrant collections: test_{uuid}_
    - Redis keys: test:{uuid}:
    - PostgreSQL schemas: test_{uuid}_
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = field(default_factory=lambda: f"tenant_{uuid.uuid4().hex[:8]}")

    @property
    def uuid_short(self) -> str:
        """返回短 UUID (12字符)"""
        return self.id

    @property
    def rabbitmq_queue_prefix(self) -> str:
        """RabbitMQ 队列前缀"""
        return f"test_{self.id}_"

    @property
    def qdrant_collection_prefix(self) -> str:
        """Qdrant collection 前缀"""
        return f"test_{self.id}_"

    @property
    def redis_key_prefix(self) -> str:
        """Redis key 前缀"""
        return f"test:{self.id}:"

    @property
    def postgres_schema(self) -> str:
        """PostgreSQL schema 名称"""
        return f"test_{self.id}"

    @property
    def minio_bucket(self) -> str:
        """MinIO bucket 名称"""
        return f"test-{self.id}"

    def __str__(self) -> str:
        return f"TestTenant(id={self.id}, name={self.name})"


class TenantContext:
    """租户上下文管理器

    使用 asyncio.current_task().ident 作为线程/协程本地存储的 key，
    确保同一进程内的不同协程拥有不同的租户隔离。
    """

    _tenants: dict[int, TestTenant] = {}
    _lock: asyncio.Lock = asyncio.Lock()  # 类变量，所有实例共享

    @classmethod
    def get_current_tenant(cls) -> TestTenant | None:
        """获取当前协程的租户"""
        task_id = cls._get_task_id()
        return cls._tenants.get(task_id)

    @classmethod
    def set_current_tenant(cls, tenant: TestTenant) -> None:
        """设置当前协程的租户"""
        task_id = cls._get_task_id()
        cls._tenants[task_id] = tenant

    @classmethod
    def clear_current_tenant(cls) -> None:
        """清除当前协程的租户"""
        task_id = cls._get_task_id()
        cls._tenants.pop(task_id, None)

    @classmethod
    def _get_task_id(cls) -> int:
        """获取当前协程/任务的唯一 ID"""
        try:
            task = asyncio.current_task()
            if task is None:
                # 不在异步上下文中，使用线程 ID
                import threading

                tid = threading.current_thread().ident
                return tid if tid is not None else 0
            # 使用 id(task) 获取任务唯一标识，兼容性好
            return id(task)
        except RuntimeError:
            #  outside of event loop, use thread identity
            import threading

            tid = threading.current_thread().ident
            return tid if tid is not None else 0

    @classmethod
    async def _async_set(cls, tenant: TestTenant) -> None:
        """异步设置租户（线程安全）"""
        async with cls._lock:
            cls.set_current_tenant(tenant)

    @classmethod
    async def _async_clear(cls) -> None:
        """异步清除租户（线程安全）"""
        async with cls._lock:
            cls.clear_current_tenant()

    @contextmanager
    def __call__(self, tenant: TestTenant | None = None) -> Generator[TestTenant, None, None]:
        """上下文管理器入口"""
        if tenant is None:
            tenant = generate_test_tenant()

        # 设置租户
        old_tenant = self.get_current_tenant()
        self.set_current_tenant(tenant)

        try:
            yield tenant
        finally:
            # 恢复之前的租户或清除
            if old_tenant is not None:
                self.set_current_tenant(old_tenant)
            else:
                self.clear_current_tenant()

    @contextmanager
    def use(self, tenant: TestTenant) -> Generator[TestTenant, None, None]:
        """同步使用租户上下文的便捷方法"""
        with self(tenant) as t:
            yield t


def generate_test_tenant() -> TestTenant:
    """生成新的测试租户

    每次调用生成唯一的租户 ID，用于隔离测试资源。
    """
    return TestTenant()


class TenantAwareMock:
    """租户感知的 Mock 基类

    自动为资源名称添加租户前缀，避免并行测试冲突。
    """

    def __init__(self, tenant: TestTenant | None = None):
        self._tenant = tenant or TenantContext.get_current_tenant()

    def _prefix_name(self, name: str) -> str:
        """为名称添加租户前缀"""
        if self._tenant is None:
            return name

        # 根据资源类型添加不同前缀
        if name.startswith("queue:"):
            # RabbitMQ 队列: queue:xxx -> test_{uuid}_queue_{xxx}
            return f"{self._tenant.rabbitmq_queue_prefix}{name[6:]}"
        elif name.startswith("collection:"):
            # Qdrant collection: collection:xxx -> test_{uuid}_{xxx}
            return f"{self._tenant.qdrant_collection_prefix}{name[11:]}"
        elif name.startswith("redis:"):
            # Redis key: redis:xxx -> test:{uuid}:{xxx}
            return f"{self._tenant.redis_key_prefix}{name[6:]}"
        elif name.startswith("schema:"):
            # PostgreSQL schema: schema:xxx -> test_{uuid}.{xxx}
            return f"{self._tenant.postgres_schema}.{name[7:]}"
        elif name.startswith("bucket:"):
            # MinIO bucket: bucket:xxx -> test-{uuid}/{xxx}
            return f"{self._tenant.minio_bucket}/{name[7:]}"
        else:
            # 默认：直接添加 uuid 前缀
            return f"{self._tenant.id}_{name}"
            return f"{self._tenant.id}_{name}"


# =============================================================================
# 便捷函数
# =============================================================================

_current_tenant_context = TenantContext()


@contextmanager
def tenant_context(tenant: TestTenant | None = None) -> Generator[TestTenant, None, None]:
    """创建租户上下文的便捷函数

    用法:
        with tenant_context() as tenant:
            print(tenant.id)
    """
    if tenant is None:
        tenant = generate_test_tenant()

    old_tenant = TenantContext.get_current_tenant()
    TenantContext.set_current_tenant(tenant)

    try:
        yield tenant
    finally:
        if old_tenant is not None:
            TenantContext.set_current_tenant(old_tenant)
        else:
            TenantContext.clear_current_tenant()
