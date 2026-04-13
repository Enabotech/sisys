"""Architecture constraints tests for Story 1.4.

验证领域层零 Redis 依赖，确保六边形架构的层级隔离。
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestDomainLayerZeroRedisDependency:
    """领域层不应依赖 Redis 或任何基础设施。"""

    def _get_domain_dir(self) -> Path:
        """获取领域层目录。"""
        return Path(__file__).resolve().parents[3] / "src" / "domain"

    def test_no_redis_import_in_domain(self) -> None:
        """领域层文件不应导入 redis 模块。"""
        domain_dir = self._get_domain_dir()
        violations = []

        for py_file in domain_dir.rglob("*.py"):
            content = py_file.read_text()
            # 检查 redis 导入
            if "import redis" in content or "from redis" in content:
                violations.append(str(py_file.relative_to(domain_dir.parents[1])))

        assert len(violations) == 0, f"Redis import found in domain layer: {violations}"

    def test_no_fakeredis_import_in_domain(self) -> None:
        """领域层文件不应导入 fakeredis 模块。"""
        domain_dir = self._get_domain_dir()
        violations = []

        for py_file in domain_dir.rglob("*.py"):
            content = py_file.read_text()
            if "import fakeredis" in content or "from fakeredis" in content:
                violations.append(str(py_file.relative_to(domain_dir.parents[1])))

        assert len(violations) == 0, f"fakeredis import found in domain layer: {violations}"

    def test_no_infrastructure_import_in_domain(self) -> None:
        """领域层文件不应导入基础设施层模块。"""
        domain_dir = self._get_domain_dir()
        violations = []

        for py_file in domain_dir.rglob("*.py"):
            content = py_file.read_text()
            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                violations.append(str(py_file.relative_to(domain_dir.parents[1])))

        assert len(violations) == 0, f"Infrastructure import found in domain layer: {violations}"

    def test_domain_interfaces_are_pure_python(self) -> None:
        """领域接口应只使用标准库。"""
        # 验证这些是 Protocol 类型
        from typing import Protocol

        from src.domain.repositories.session_storage import SessionStorage
        from src.domain.services.public_blackboard import PublicBlackboard
        from src.domain.services.semantic_cache import SemanticCache

        assert issubclass(SessionStorage, Protocol)  # type: ignore[arg-type]
        assert issubclass(SemanticCache, Protocol)  # type: ignore[arg-type]
        assert issubclass(PublicBlackboard, Protocol)  # type: ignore[arg-type]

    def test_domain_services_init_exports(self) -> None:
        """domain.services.__init__ 应正确导出接口。"""
        from src.domain.services import PublicBlackboard, SemanticCache

        assert PublicBlackboard is not None
        assert SemanticCache is not None

    def test_domain_repositories_init_exports(self) -> None:
        """domain.repositories.__init__ 应正确导出接口。"""
        from src.domain.repositories import SessionStorage

        assert SessionStorage is not None


class TestInfrastructureLayerPatterns:
    """基础设施层应遵循正确的模式。"""

    def test_session_storage_follow_get_pool_pattern(self) -> None:
        """RedisSessionStorage 应使用 _get_pool 模式。"""
        from src.infrastructure.storage.redis.session_storage import RedisSessionStorage

        assert hasattr(RedisSessionStorage, "_get_pool")

    def test_semantic_cache_follows_get_pool_pattern(self) -> None:
        """RedisSemanticCache 应使用 _get_pool 模式。"""
        from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache

        assert hasattr(RedisSemanticCache, "_get_pool")

    def test_public_blackboard_follows_get_pool_pattern(self) -> None:
        """RedisPublicBlackboard 应使用 _get_pool 模式。"""
        from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard

        assert hasattr(RedisPublicBlackboard, "_get_pool")

    def test_cleanup_uses_scan_not_keys(self) -> None:
        """RedisCleanup 应使用 SCAN 命令。"""
        # 读取源码验证使用 scan
        import inspect

        from src.infrastructure.storage.redis.cleanup import RedisCleanup

        source = inspect.getsource(RedisCleanup.cleanup_namespace)
        assert ".scan(" in source, "cleanup_namespace should use SCAN, not KEYS"
        assert ".keys(" not in source or ".keys" not in source.split(".scan")[0], "Should not use KEYS command"

    def test_no_global_connection_pools(self) -> None:
        """不应有全局连接池。"""
        storage_dir = Path(__file__).resolve().parents[3] / "src" / "infrastructure" / "storage" / "redis"

        for py_file in storage_dir.rglob("*.py"):
            content = py_file.read_text()
            # 检查全局 pool 定义（不在类或方法内）
            lines = content.split("\n")
            in_class = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("class "):
                    in_class = True
                elif not stripped.startswith("#") and not in_class:
                    # 全局变量不应包含 _pool =
                    if "_pool =" in stripped and not stripped.startswith("self."):
                        pytest.fail(f"Global connection pool found in {py_file.name}")
