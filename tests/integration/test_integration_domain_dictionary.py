"""领域词典集成测试

验证真实 PG 仓储 CRUD + 快照/回滚 + 乐观锁 + RuleBasedExtractor 热更新管线。
使用真实 PostgreSQL（测试 schema 隔离 + savepoint rollback）。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from tests.environments import get_test_env

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def event_loop():
    """模块级事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_tenant_id() -> str:
    """生成唯一测试租户ID"""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def pg_config() -> PostgreSQLConfig:
    """真实 PostgreSQL 配置"""
    env = get_test_env()
    return PostgreSQLConfig(
        host=env.postgres.host,
        port=env.postgres.port,
        database=env.postgres.database,
        username=env.postgres.username,
        password=env.postgres.password,
        pool_size=5,
        max_overflow=10,
    )


@pytest.fixture
def db_engine(pg_config: PostgreSQLConfig) -> PostgreSQLManager:
    """真实数据库引擎"""
    return PostgreSQLManager(pg_config)


@pytest.fixture
def pg_available(pg_config: PostgreSQLConfig, event_loop) -> bool:
    """检查 PostgreSQL 是否可用"""
    import asyncpg

    async def _check():
        try:
            conn = await asyncpg.connect(
                host=pg_config.host,
                port=pg_config.port,
                user=pg_config.username,
                password=pg_config.password,
                database=pg_config.database,
            )
            await conn.close()
            return True
        except Exception:
            return False

    result: bool = event_loop.run_until_complete(_check())
    return result


@pytest.fixture
def repo_session(
    db_engine: PostgreSQLManager,
    pg_available: bool,
    event_loop,
) -> Generator[AsyncSession, None, None]:
    """真实 PG 会话（savepoint rollback 隔离）"""
    if not pg_available:
        pytest.skip("PostgreSQL not available")
        return

    # 确保表结构存在
    try:
        from src.infrastructure.storage.postgresql.models import Base

        Base.metadata.create_all(db_engine.get_sync_engine())
    except Exception:
        pass

    async_engine = db_engine.get_async_engine()
    session = AsyncSession(async_engine)
    event_loop.run_until_complete(session.begin())
    token = set_session(session)
    yield session
    reset_session(token)
    event_loop.run_until_complete(session.rollback())
    event_loop.run_until_complete(session.close())


def _run(coro):
    """同步运行 async 协程"""
    return asyncio.run(coro)


class TestDomainDictionaryPersistence:
    """词典存储集成测试（真实 PG）"""

    def test_crud_roundtrip(self, repo_session, event_loop):
        """词条 CRUD 端到端"""
        from src.domain.ports.domain_dictionary import (
            DictionaryEntry,
            DictionaryQuery,
        )
        from src.infrastructure.storage.postgresql.repository.domain_dictionary_repository import (
            PostgreSQLDomainDictionaryRepository,
        )

        repo = PostgreSQLDomainDictionaryRepository()

        # Add
        entry = DictionaryEntry(term="元宇宙", entity_type="CONCEPT", category="tech")
        event_loop.run_until_complete(repo.add_entry(entry))

        # Get
        fetched = event_loop.run_until_complete(repo.get_entry("元宇宙"))
        assert fetched is not None
        assert fetched.entity_type == "CONCEPT"

        # Update
        updated = DictionaryEntry(term="元宇宙", entity_type="TECH_CONCEPT", version=2)
        result = event_loop.run_until_complete(repo.update_entry("元宇宙", updated))
        assert result.entity_type == "TECH_CONCEPT"
        assert result.version == 2

        # List (all entries, no filter)
        query = DictionaryQuery()
        entries = event_loop.run_until_complete(repo.list_entries(query))
        assert len(entries) >= 1
        assert any(e.term == "元宇宙" for e in entries)

        # Delete
        event_loop.run_until_complete(repo.delete_entry("元宇宙"))
        fetched = event_loop.run_until_complete(repo.get_entry("元宇宙"))
        assert fetched is None

    def test_snapshot_and_rollback(self, repo_session, event_loop):
        """快照 + 回滚端到端"""
        from src.domain.ports.domain_dictionary import DictionaryEntry
        from src.infrastructure.storage.postgresql.repository.domain_dictionary_repository import (
            PostgreSQLDomainDictionaryRepository,
        )

        repo = PostgreSQLDomainDictionaryRepository()

        # 添加词条
        event_loop.run_until_complete(repo.add_entry(DictionaryEntry(term="BLM", entity_type="CONCEPT")))

        # 创建快照 v1
        snap = event_loop.run_until_complete(repo.create_snapshot("admin"))
        assert snap.version == 1

        # 修改词条
        event_loop.run_until_complete(
            repo.update_entry(
                "BLM",
                DictionaryEntry(term="BLM", entity_type="STRATEGY", version=2),
            )
        )

        # 回滚至 v1
        event_loop.run_until_complete(repo.rollback(1))
        restored = event_loop.run_until_complete(repo.get_entry("BLM"))
        assert restored is not None
        assert restored.entity_type == "CONCEPT"

    def test_optimistic_lock_conflict(self, repo_session, event_loop):
        """乐观锁并发冲突"""
        from src.domain.exceptions import DictionaryVersionConflictError
        from src.domain.ports.domain_dictionary import DictionaryEntry
        from src.infrastructure.storage.postgresql.repository.domain_dictionary_repository import (
            PostgreSQLDomainDictionaryRepository,
        )

        repo = PostgreSQLDomainDictionaryRepository()

        # 添加词条 version=1
        event_loop.run_until_complete(repo.add_entry(DictionaryEntry(term="SWOT", entity_type="CONCEPT")))

        # 第一次更新成功（version 1 -> 2）
        event_loop.run_until_complete(
            repo.update_entry(
                "SWOT",
                DictionaryEntry(term="SWOT", entity_type="TOOL", version=2),
            )
        )

        # 第二次基于旧版本 1 更新 -> 版本冲突
        with pytest.raises(DictionaryVersionConflictError):
            event_loop.run_until_complete(
                repo.update_entry(
                    "SWOT",
                    DictionaryEntry(term="SWOT", entity_type="TOOL", version=2),
                )
            )

    def test_get_active_dictionary(self, repo_session, event_loop):
        """获取活动词典"""
        from src.domain.ports.domain_dictionary import DictionaryEntry
        from src.infrastructure.storage.postgresql.repository.domain_dictionary_repository import (
            PostgreSQLDomainDictionaryRepository,
        )

        repo = PostgreSQLDomainDictionaryRepository()

        event_loop.run_until_complete(repo.add_entry(DictionaryEntry(term="BLM", entity_type="CONCEPT")))
        event_loop.run_until_complete(repo.add_entry(DictionaryEntry(term="SWOT", entity_type="CONCEPT", active=False)))

        active = event_loop.run_until_complete(repo.get_active_dictionary())
        terms = [t for t, _ in active]
        assert "BLM" in terms
        assert "SWOT" not in terms  # inactive 不返回


class TestDictionaryHotReloadPipeline:
    """词典热更新管线（真实 RuleBasedExtractor）"""

    def test_hot_reload_new_term_recognized(self, repo_session, event_loop):
        """添加词条 -> 热更新 -> 抽取识别新词"""
        from src.domain.ports.domain_dictionary import DictionaryEntry
        from src.infrastructure.external_services.entity_extraction.rule_extractor import (
            RuleBasedExtractor,
        )
        from src.infrastructure.storage.postgresql.repository.domain_dictionary_repository import (
            PostgreSQLDomainDictionaryRepository,
        )

        repo = PostgreSQLDomainDictionaryRepository()
        extractor = RuleBasedExtractor()

        # 初始词典不含"元宇宙"
        result = event_loop.run_until_complete(extractor.extract_entities("元宇宙技术趋势"))
        assert all(e.name != "元宇宙" for e in result.entities)

        # 添加词条 + 热更新
        event_loop.run_until_complete(repo.add_entry(DictionaryEntry(term="元宇宙", entity_type="CONCEPT")))
        active = event_loop.run_until_complete(repo.get_active_dictionary())
        extractor.reload_dictionary(active)

        # 热更新后识别
        result = event_loop.run_until_complete(extractor.extract_entities("元宇宙技术趋势"))
        assert any(e.name == "元宇宙" and e.entity_type == "CONCEPT" for e in result.entities)

    def test_hot_reload_deleted_term_no_longer_recognized(self, repo_session, event_loop):
        """删除词条 -> 热更新 -> 抽取不再匹配"""
        from src.domain.ports.domain_dictionary import DictionaryEntry
        from src.infrastructure.external_services.entity_extraction.rule_extractor import (
            RuleBasedExtractor,
        )
        from src.infrastructure.storage.postgresql.repository.domain_dictionary_repository import (
            PostgreSQLDomainDictionaryRepository,
        )

        repo = PostgreSQLDomainDictionaryRepository()
        extractor = RuleBasedExtractor()

        # 添加两个词条并热更新（reload 后自动机已构建）
        event_loop.run_until_complete(repo.add_entry(DictionaryEntry(term="元宇宙", entity_type="CONCEPT")))
        event_loop.run_until_complete(repo.add_entry(DictionaryEntry(term="SWOT", entity_type="CONCEPT")))
        active = event_loop.run_until_complete(repo.get_active_dictionary())
        extractor.reload_dictionary(active)

        # 此时词典包含"元宇宙"和"SWOT"，自动机有效
        result = event_loop.run_until_complete(extractor.extract_entities("元宇宙技术趋势"))
        assert any(e.name == "元宇宙" for e in result.entities)

        # 删除"元宇宙"再热更新（SWOT 仍存在，自动机非空）
        event_loop.run_until_complete(repo.delete_entry("元宇宙"))
        active = event_loop.run_until_complete(repo.get_active_dictionary())
        extractor.reload_dictionary(active)

        result = event_loop.run_until_complete(extractor.extract_entities("元宇宙技术趋势"))
        assert all(e.name != "元宇宙" for e in result.entities)

    def test_hot_reload_latency_below_threshold(self, repo_session, event_loop):
        """热更新延迟 P95 < 100ms"""
        import time

        from src.infrastructure.external_services.entity_extraction.rule_extractor import (
            RuleBasedExtractor,
        )

        extractor = RuleBasedExtractor()
        dictionary = [("词条A", "CONCEPT"), ("词条B", "CONCEPT"), ("词条C", "CONCEPT")]

        # 多次热更新计时
        latencies = []
        for _ in range(5):
            start = time.monotonic()
            extractor.reload_dictionary(dictionary)
            latencies.append((time.monotonic() - start) * 1000)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0
        assert p95 < 100, f"热更新延迟 P95={p95:.2f}ms 超过 100ms"

    def test_core_strategy_concepts_coverage(self, repo_session, event_loop):
        """核心战略概念覆盖率 >= 95%"""
        from src.infrastructure.external_services.entity_extraction.rule_extractor import (
            RuleBasedExtractor,
        )

        extractor = RuleBasedExtractor()

        # 预置核心战略概念
        core_concepts = [
            "BLM",
            "BEM",
            "SWOT",
            "PESTEL",
            "NPV",
            "IRR",
        ]
        content = " ".join(core_concepts)

        result = event_loop.run_until_complete(extractor.extract_entities(content))
        recognized = {e.name for e in result.entities}

        matched = sum(1 for c in core_concepts if c in recognized)
        coverage = matched / len(core_concepts)
        assert coverage >= 0.95, f"核心战略概念覆盖率 {coverage:.0%} 低于 95%"
