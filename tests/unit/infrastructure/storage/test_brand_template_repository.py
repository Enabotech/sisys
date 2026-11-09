"""品牌模板仓储单元测试（Story 6-11 Task 2——真实 PG 形态）。

覆盖面：
- 018 migration 与 BrandTemplateModel 冻结基线（七列镜像+UNIQUE(name)+revision 链
  018→017——Task 0.3 DDL 冻结逐字比对）
- UPSERT 落库语义仓储层：按实体 template_id 有行 UPDATE（三配置字段+updated_at
  前进，template_id/name/created_at 不变）/无行 INSERT（保留字段由服务侧先行
  get_by_name 钦定后传入——仓储不承载保留判断，OD-12）
- get_by_name 命中与未命中 None
- list_templates 双序断言：updated_at 降序+name 字典序 tie-break（跨事务 save 或
  显式构造保证主排序键可区分——同事务 now() 同值退化 tie-break 致排序突变锚失效）
- 并发双 INSERT 撞 UNIQUE(name) → IntegrityError → BrandTemplateStorageError 495 包装
- 实体↔Model 映射隔离（_to_entity/_to_model 往返）

实体构造通则（R2 裁定）：所有形态实体自带显式 updated_at——UPDATE 形态 None
时 UPDATE 写 NULL 撞 NOT NULL 且被 IntegrityError→495 路径误吞（该路径另有
独立负例用例钉死）。

测试隔离：真实 PG 共享库 commit 式 + teardown 定向 DELETE（rowcount 断言防
静默 0 行假绿）；pytestmark 挂 xdist_group("blm-planning-perf") 与全部
strategic_* 提交型写入方同 worker 串行（漏挂致 6-10 S3 意外 skip）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit/infrastructure/storage/test_brand_template_repository.py -v
"""

import asyncio
import uuid as uuid_module
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from src.domain.entities.brand_template import BrandTemplate
from src.domain.exceptions import BrandTemplateStorageError, EntityValidationError
from src.infrastructure.storage.postgresql.models.brand_template import BrandTemplateModel
from src.infrastructure.storage.postgresql.repository.brand_template_repository import (
    PostgreSQLBrandTemplateRepository,
)

pytestmark = [
    pytest.mark.database,
    pytest.mark.xdist_group("blm-planning-perf"),
]

#: 仓库根（migration 文件断言）
_REPO_ROOT = Path(__file__).resolve().parents[4]

#: 018 migration 文件路径（只增红线——已合入禁改）
_MIGRATION_FILE = _REPO_ROOT / "deploy/postgresql/alembic/versions/018_brand_templates.py"

#: 七列冻结基线（Task 0.3 DDL 镜像——漂移即红）
_EXPECTED_COLUMNS: frozenset[str] = frozenset(
    {
        "template_id",
        "name",
        "color_scheme",
        "font_preset",
        "logo_object_key",
        "created_at",
        "updated_at",
    }
)

#: 模块级事件循环（真实 PG 单测——同循环驱动）
_LOOP = asyncio.new_event_loop()


def _run_async(coro: Any) -> Any:
    """在模块级循环上运行协程。"""
    return _LOOP.run_until_complete(coro)


def _require_pg() -> None:
    """PostgreSQL 可达性探测（brand_templates 表预检——018 已应用；失败动态 skip）。"""
    import asyncpg

    from tests.environments import get_test_env

    env = get_test_env()
    probe = asyncio.new_event_loop()
    try:

        async def _check() -> bool:
            try:
                conn = await asyncpg.connect(
                    host=env.postgres.host,
                    port=env.postgres.port,
                    user=env.postgres.username,
                    password=env.postgres.password,
                    database=env.postgres.database,
                )
                try:
                    await conn.execute("SELECT 1 FROM brand_templates LIMIT 1")
                finally:
                    await conn.close()
                return True
            except Exception:
                return False

        if not probe.run_until_complete(_check()):
            pytest.skip("PostgreSQL/brand_templates 不可用（018 未应用或服务未启动）")
    finally:
        probe.close()


def _make_template(**overrides: Any) -> BrandTemplate:
    """模板实体构造 helper（构造通则：默认显式 created_at/updated_at——UPDATE
    形态 None 时 UPDATE 写 NULL 撞 NOT NULL 被 IntegrityError→495 误吞）。"""
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "template_id": uuid_module.uuid4(),
        "name": f"test-{uuid_module.uuid4().hex[:8]}-模板",
        "color_scheme": "corporate-blue",
        "font_preset": "stsong",
        "logo_object_key": None,
        "created_at": now - timedelta(seconds=10),
        "updated_at": now,
    }
    defaults.update(overrides)
    return BrandTemplate(**defaults)


def _make_repository() -> PostgreSQLBrandTemplateRepository:
    """仓储构造（session_factory 注入——组合根 lambda 同款形态）。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.environments import get_test_env

    env = get_test_env()
    engine = create_async_engine(
        f"postgresql+asyncpg://{env.postgres.username}:{env.postgres.password}"
        f"@{env.postgres.host}:{env.postgres.port}/{env.postgres.database}"
    )
    return PostgreSQLBrandTemplateRepository(session_factory=async_sessionmaker(engine))


async def _delete_rows(template_ids: list[str]) -> None:
    """teardown 定向 DELETE（rowcount 断言防静默 0 行假绿）。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.environments import get_test_env

    env = get_test_env()
    engine = create_async_engine(
        f"postgresql+asyncpg://{env.postgres.username}:{env.postgres.password}"
        f"@{env.postgres.host}:{env.postgres.port}/{env.postgres.database}"
    )
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("DELETE FROM brand_templates WHERE template_id = ANY(:ids)"),
                {"ids": template_ids},
            )
            assert result.rowcount == len(template_ids), (
                f"DELETE 行数 {result.rowcount} != 预期 {len(template_ids)}（静默 0 行假绿防线）"
            )
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def _cleanup_written_rows() -> Any:
    """每用例清理登记（yield 前置收集器——用例内登记待删 template_id）。"""
    written: list[str] = []
    yield written
    if written:
        try:
            _run_async(_delete_rows(written))
        except AssertionError:
            raise
        except Exception as error:  # teardown 容错（表缺席等——残局防线）
            print(f"[teardown:brand-template-repo] 清理异常（容错）: {error}")


class TestMigrationBaseline:
    """018 migration 与 ORM Model 冻结基线（循环 A——DDL 逐字比对）。"""

    def test_migration_file_exists_and_revision_chain(self) -> None:
        """018 文件存在+revision 链 018→017（文本断言——alembic 标识符形态）。"""
        assert _MIGRATION_FILE.is_file(), f"migration 缺失: {_MIGRATION_FILE}"
        source = _MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'revision = "018"' in source
        assert 'down_revision = "017"' in source
        assert "brand_templates" in source

    def test_model_table_name_and_columns(self) -> None:
        """Model 表名+七列全等（Task 0.3 DDL 镜像——漂移即红）。"""
        assert BrandTemplateModel.__tablename__ == "brand_templates"
        columns = set(BrandTemplateModel.__table__.columns.keys())
        assert columns == _EXPECTED_COLUMNS, f"列集漂移: {columns ^ _EXPECTED_COLUMNS}"

    def test_model_unique_constraint_on_name(self) -> None:
        """UNIQUE(name) 约束在位（UPSERT 业务键锚——007 snapshots version unique 先例援引）。"""
        from sqlalchemy import Table, UniqueConstraint

        table = BrandTemplateModel.__table__
        assert isinstance(table, Table), "ORM 模型 __table__ 恒为 Table（类型收窄——FromClause 桩无 constraints 属性注解）"
        uniques = [tuple(uc.columns.keys()) for uc in table.constraints if isinstance(uc, UniqueConstraint)]
        assert ("name",) in uniques, f"UNIQUE(name) 缺失: {uniques}"


class TestUpsertSemantics:
    """UPSERT 落库语义仓储层（真实 PG）。"""

    def test_save_insert_new_row(self, _cleanup_written_rows: list[str]) -> None:
        """首存 INSERT 新行（七字段读回直推——独立会话 commit 落库）。"""
        _require_pg()
        repository = _make_repository()
        template = _make_template()
        _cleanup_written_rows.append(str(template.template_id))

        saved = _run_async(repository.save(template))
        assert saved.template_id == template.template_id
        fetched = _run_async(repository.get_by_name(template.name))
        assert fetched is not None
        assert fetched.name == template.name
        assert fetched.color_scheme == "corporate-blue"
        assert fetched.font_preset == "stsong"
        assert fetched.logo_object_key is None
        assert fetched.created_at is not None and fetched.updated_at is not None

    def test_save_update_same_template_id(self, _cleanup_written_rows: list[str]) -> None:
        """同 template_id 再存 UPDATE（字段更新+updated_at 前进+template_id/
        name/created_at 不变——保留语义由服务侧先行传入，仓储纯落库）。"""
        _require_pg()
        repository = _make_repository()
        first = _make_template()
        _cleanup_written_rows.append(str(first.template_id))
        _run_async(repository.save(first))
        assert first.updated_at is not None, "构造通则显式 updated_at（_make_template 恒非 None——类型收窄）"

        later = _make_template(
            template_id=first.template_id,
            name=first.name,
            color_scheme="burgundy",
            font_preset="noto-sans-sc",
            logo_object_key=f"logos/{first.template_id}",
            created_at=first.created_at,
            updated_at=first.updated_at + timedelta(seconds=5),
        )
        _run_async(repository.save(later))

        fetched = _run_async(repository.get_by_name(first.name))
        assert fetched is not None
        assert fetched.template_id == first.template_id, "UPDATE 分支 template_id 漂移"
        assert fetched.created_at == first.created_at, "UPDATE 分支 created_at 漂移"
        assert fetched.color_scheme == "burgundy"
        assert fetched.font_preset == "noto-sans-sc"
        assert fetched.logo_object_key == f"logos/{first.template_id}"
        assert fetched.updated_at > first.updated_at, "updated_at 未前进（服务侧定时戳落库直推）"

    def test_save_update_without_updated_at_wraps_495(self, _cleanup_written_rows: list[str]) -> None:
        """UPDATE 形态实体 updated_at=None 撞 NOT NULL → IntegrityError → 495
        包装（构造通则的反面钉死——防御义务归仓储的运行面证据）。"""
        _require_pg()
        repository = _make_repository()
        first = _make_template()
        _cleanup_written_rows.append(str(first.template_id))
        _run_async(repository.save(first))

        bad = _make_template(
            template_id=first.template_id,
            name=first.name,
            updated_at=None,
        )
        with pytest.raises(BrandTemplateStorageError) as exc_info:
            _run_async(repository.save(bad))
        assert exc_info.value.code == "EXCEPTION_495"


class TestGetByName:
    """get_by_name 业务键查找。"""

    def test_get_by_name_miss_returns_none(self) -> None:
        """未命中返回 None（而非抛异常——服务侧 None 抛 494 的前提）。"""
        _require_pg()
        repository = _make_repository()
        fetched = _run_async(repository.get_by_name(f"ghost-{uuid_module.uuid4().hex[:8]}"))
        assert fetched is None


class TestListOrdering:
    """list_templates 双序断言（updated_at 降序+name 字典序 tie-break）。"""

    def test_list_ordering_desc_updated_at_with_name_tiebreak(self, _cleanup_written_rows: list[str]) -> None:
        """双序断言（三行显式 updated_at 降序+两行同 updated_at 时 name 字典序
        tie-break——显式构造保证主排序键可区分）。"""
        _require_pg()
        repository = _make_repository()
        base = datetime.now(UTC)
        alpha = _make_template(name=f"a-{uuid_module.uuid4().hex[:8]}", updated_at=base + timedelta(microseconds=3000))
        beta = _make_template(name=f"b-{uuid_module.uuid4().hex[:8]}", updated_at=base + timedelta(microseconds=3000))
        oldest = _make_template(name=f"z-{uuid_module.uuid4().hex[:8]}", updated_at=base + timedelta(microseconds=1000))
        for template in (oldest, alpha, beta):
            _cleanup_written_rows.append(str(template.template_id))
            _run_async(repository.save(template))

        listed = _run_async(repository.list_templates())
        mine = [t for t in listed if t.template_id in {alpha.template_id, beta.template_id, oldest.template_id}]
        assert len(mine) == 3
        # 主序 updated_at 降序（最新修订优先）；tie（alpha/beta 同 updated_at）按 name 字典序
        assert [t.name[0] for t in mine] == ["a", "b", "z"], f"双序漂移: {[t.name for t in mine]}"

    def test_list_empty_when_no_rows(self) -> None:
        """零行返回空清单（CLI 空态与品牌段零模板形态的数据面前提）。"""
        _require_pg()
        repository = _make_repository()
        listed = _run_async(repository.list_templates())
        assert isinstance(listed, list)


class TestIntegrityError:
    """并发双 INSERT 撞 UNIQUE 防御（仓储义务）。"""

    def test_double_insert_same_name_wraps_495(self, _cleanup_written_rows: list[str]) -> None:
        """两实体不同 template_id 同 name：先存 A 再存 B[新 id INSERT 撞
        UNIQUE(name)] → IntegrityError → 495 包装（CLI 单进程常态低概率，
        防御义务归仓储——AC-1）。"""
        _require_pg()
        repository = _make_repository()
        first = _make_template()
        _cleanup_written_rows.append(str(first.template_id))
        _run_async(repository.save(first))

        second = _make_template(name=first.name)
        with pytest.raises(BrandTemplateStorageError) as exc_info:
            _run_async(repository.save(second))
        assert exc_info.value.code == "EXCEPTION_495"


class TestOrmEntityMapping:
    """实体↔Model 映射隔离（往返等价——脏值不逃逸）。"""

    def test_entity_guard_rejects_empty_name_before_mapping(self) -> None:
        """实体守卫先于映射（空 name 构造即 242——映射函数零接触脏值）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_template(name="")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_save_and_fetch_roundtrip_logo_key(self, _cleanup_written_rows: list[str]) -> None:
        """logo_object_key 往返（None 与有值两形态——JSONB/NULL 映射保真）。"""
        _require_pg()
        repository = _make_repository()
        with_logo = _make_template(logo_object_key=f"logos/{uuid_module.uuid4()}")
        without_logo = _make_template()
        for template in (with_logo, without_logo):
            _cleanup_written_rows.append(str(template.template_id))
            _run_async(repository.save(template))

        fetched_with = _run_async(repository.get_by_name(with_logo.name))
        fetched_without = _run_async(repository.get_by_name(without_logo.name))
        assert fetched_with is not None and fetched_with.logo_object_key == with_logo.logo_object_key
        assert fetched_without is not None and fetched_without.logo_object_key is None


class TestFallbackWithoutFactory:
    """fallback 无 factory 防御（无请求 session 且无 factory → RuntimeError 显式失败）。"""

    def test_save_without_session_and_factory_raises_runtime_error(self) -> None:
        """save 无请求 session 且无 factory → RuntimeError（配置缺失显式失败——
        组合根恒注入使生产 CLI 不落此形态的防御路径）。"""
        repository = PostgreSQLBrandTemplateRepository()
        with pytest.raises(RuntimeError):
            _run_async(repository.save(_make_template()))

    def test_get_by_name_without_session_and_factory_raises_runtime_error(self) -> None:
        """get_by_name 同款防御路径。"""
        repository = PostgreSQLBrandTemplateRepository()
        with pytest.raises(RuntimeError):
            _run_async(repository.get_by_name("any"))

    def test_list_without_session_and_factory_raises_runtime_error(self) -> None:
        """list_templates 同款防御路径。"""
        repository = PostgreSQLBrandTemplateRepository()
        with pytest.raises(RuntimeError):
            _run_async(repository.list_templates())


class TestReadPathWraps495:
    """读路径协议外异常 → 495 包装（R1-F2——Mock 会话注入，不依赖 PG）。

    契约锚：「PG 读写失败→495」读面（use case docstring/异常 docstring/设计
    文档 §3.3.2 三处冻结）——OperationalError 族经 ``_do_get_by_name``/
    ``_do_list`` 兜底包装，fallback 分派层 RuntimeError 显式失败不入包装面
    （TestFallbackWithoutFactory 在线守护）。
    """

    @staticmethod
    def _make_failing_session() -> Any:
        """构造 execute 必败的 Mock 会话（OperationalError 注入）。"""
        from unittest.mock import AsyncMock

        from sqlalchemy.exc import OperationalError

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=OperationalError("SELECT brand_templates ...", {}, Exception("connection reset"))
        )
        return session

    def test_get_by_name_wraps_operational_error_495(self) -> None:
        """get_by_name 读失败 → 495（code/layer/cause 三锚——主格）。"""
        from sqlalchemy.exc import OperationalError

        from src.infrastructure.storage.postgresql.session_context import with_session

        repository = PostgreSQLBrandTemplateRepository()
        session = self._make_failing_session()
        captured: dict[str, Any] = {}

        async def _exercise() -> None:
            async with with_session(session):
                with pytest.raises(BrandTemplateStorageError) as exc_info:
                    await repository.get_by_name("any")
                captured["value"] = exc_info.value

        _run_async(_exercise())
        error = captured["value"]
        assert error.code == "EXCEPTION_495", "读失败应包装 495 而非裸抛 OperationalError"
        assert error.context.get("layer") == "l2", "layer=l2（L2 PG 读失败语义）"
        assert isinstance(error.cause, OperationalError), "原始异常经 cause 保留完整因果链"

    def test_list_templates_wraps_operational_error_495(self) -> None:
        """list_templates 读失败 → 495（独立格——_do_list 包装与 get_by_name 分立）。"""
        from src.infrastructure.storage.postgresql.session_context import with_session

        repository = PostgreSQLBrandTemplateRepository()
        session = self._make_failing_session()
        captured: dict[str, Any] = {}

        async def _exercise() -> None:
            async with with_session(session):
                with pytest.raises(BrandTemplateStorageError) as exc_info:
                    await repository.list_templates()
                captured["value"] = exc_info.value

        _run_async(_exercise())
        error = captured["value"]
        assert error.code == "EXCEPTION_495"
        assert error.context.get("layer") == "l2"
