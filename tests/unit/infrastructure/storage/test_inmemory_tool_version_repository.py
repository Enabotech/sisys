"""InMemoryToolVersionRepository 单元测试（Story 4-6 Task 3 TDD 红→绿）

覆盖：CRUD / (tool_id,version) 唯一性 431 / Query 全字段过滤+分页 /
list_active（CANARY+STABLE）/ 单 STABLE·单 CANARY 不变量守护（432 并存冲突族）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus
from src.domain.exceptions.tool_version_exceptions import (
    ToolVersionAlreadyExistsError,
    ToolVersionTrafficWeightError,
)
from src.domain.ports.tool_version_repository import (
    ToolVersionQuery,
    ToolVersionRepositoryPort,
)
from src.infrastructure.storage.inmemory.tool_version_repository import (
    InMemoryToolVersionRepository,
)

TID = uuid.uuid4


def _make_tv(
    version: str,
    status: ToolVersionStatus = ToolVersionStatus.PENDING,
    *,
    tool_id: uuid.UUID | None = None,
    traffic_weight: int = 0,
    last_stable_at: datetime | None = None,
    created_at: datetime | None = None,
) -> ToolVersion:
    """构造测试版本实体。"""
    now = datetime.now(UTC)
    return ToolVersion(
        version_id=uuid.uuid4(),
        tool_id=tool_id or TID(),
        version=version,
        input_schema={},
        output_schema={},
        status=status,
        traffic_weight=traffic_weight,
        last_stable_at=last_stable_at,
        created_at=created_at or now,
        updated_at=now,
    )


async def _save_new(repo: InMemoryToolVersionRepository, tv: ToolVersion) -> ToolVersion:
    """保存新版本（预置 version_id 防随机）。"""
    return await repo.save(tv)


class TestInMemoryCrud:
    """基础 CRUD 测试。"""

    @pytest.mark.asyncio
    async def test_save_and_get_by_id(self) -> None:
        repo = InMemoryToolVersionRepository()
        tv = _make_tv("1.0.0")
        saved = await repo.save(tv)
        fetched = await repo.get_by_id(saved.version_id)
        assert fetched is not None
        assert fetched.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_by_tool_and_version(self) -> None:
        repo = InMemoryToolVersionRepository()
        tv = _make_tv("1.0.0")
        await repo.save(tv)
        fetched = await repo.get_by_tool_and_version(tv.tool_id, "1.0.0")
        assert fetched is not None
        assert fetched.version_id == tv.version_id

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self) -> None:
        repo = InMemoryToolVersionRepository()
        assert await repo.get_by_tool_and_version(TID(), "9.9.9") is None

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        repo = InMemoryToolVersionRepository()
        tv = await repo.save(_make_tv("1.0.0"))
        await repo.delete(tv.version_id)
        assert await repo.get_by_id(tv.version_id) is None

    @pytest.mark.asyncio
    async def test_save_update_in_place(self) -> None:
        """同 version_id 再 save = 原地更新（状态迁移持久化路径）。"""
        repo = InMemoryToolVersionRepository()
        tv = await repo.save(_make_tv("1.0.0"))
        tv.transition_to(ToolVersionStatus.STABLE)
        await repo.save(tv)
        fetched = await repo.get_by_id(tv.version_id)
        assert fetched is not None
        assert fetched.status is ToolVersionStatus.STABLE


class TestUniqueness:
    """(tool_id, version) 唯一性测试。"""

    @pytest.mark.asyncio
    async def test_duplicate_registration_raises_431(self) -> None:
        repo = InMemoryToolVersionRepository()
        tid = TID()
        await repo.save(_make_tv("1.0.0", tool_id=tid))
        with pytest.raises(ToolVersionAlreadyExistsError):
            await repo.save(_make_tv("1.0.0", tool_id=tid))

    @pytest.mark.asyncio
    async def test_same_version_different_tool_ok(self) -> None:
        """不同工具的同版本号不冲突。"""
        repo = InMemoryToolVersionRepository()
        await repo.save(_make_tv("1.0.0", tool_id=TID()))
        await repo.save(_make_tv("1.0.0", tool_id=TID()))


class TestSingleActiveInvariant:
    """单 STABLE / 单活跃 CANARY 不变量守护（432 并存冲突族）。"""

    @pytest.mark.asyncio
    async def test_second_stable_rejected_432(self) -> None:
        repo = InMemoryToolVersionRepository()
        tid = TID()
        await repo.save(_make_tv("1.0.0", ToolVersionStatus.STABLE, tool_id=tid))
        with pytest.raises(ToolVersionTrafficWeightError):
            await repo.save(_make_tv("2.0.0", ToolVersionStatus.STABLE, tool_id=tid))

    @pytest.mark.asyncio
    async def test_second_canary_rejected_432(self) -> None:
        repo = InMemoryToolVersionRepository()
        tid = TID()
        await repo.save(_make_tv("1.1.0", ToolVersionStatus.CANARY, tool_id=tid, traffic_weight=30))
        with pytest.raises(ToolVersionTrafficWeightError):
            await repo.save(_make_tv("1.2.0", ToolVersionStatus.CANARY, tool_id=tid, traffic_weight=50))

    @pytest.mark.asyncio
    async def test_stable_plus_canary_coexist(self) -> None:
        """STABLE 与 CANARY 并存合法（灰度态）。"""
        repo = InMemoryToolVersionRepository()
        tid = TID()
        await repo.save(_make_tv("1.0.0", ToolVersionStatus.STABLE, tool_id=tid))
        await repo.save(_make_tv("1.1.0", ToolVersionStatus.CANARY, tool_id=tid, traffic_weight=30))

    @pytest.mark.asyncio
    async def test_demote_then_promote_allows_new_stable(self) -> None:
        """先降级旧 STABLE 再提升新 STABLE（保存顺序约束的服务层路径）。"""
        repo = InMemoryToolVersionRepository()
        tid = TID()
        old = await repo.save(_make_tv("1.0.0", ToolVersionStatus.STABLE, tool_id=tid))
        old.transition_to(ToolVersionStatus.DEPRECATED)
        old.stamp_last_stable()
        await repo.save(old)
        await repo.save(_make_tv("2.0.0", ToolVersionStatus.STABLE, tool_id=tid))


class TestQuery:
    """Query Object 多字段过滤 + 分页测试。"""

    @pytest.mark.asyncio
    async def test_filter_by_status(self) -> None:
        repo = InMemoryToolVersionRepository()
        tid = TID()
        await repo.save(_make_tv("1.0.0", ToolVersionStatus.STABLE, tool_id=tid))
        await repo.save(_make_tv("1.1.0", ToolVersionStatus.CANARY, tool_id=tid))
        await repo.save(_make_tv("1.2.0", ToolVersionStatus.DEPRECATED, tool_id=tid))
        result = await repo.list_by_query(ToolVersionQuery(tool_id=tid, status=ToolVersionStatus.DEPRECATED))
        assert [tv.version for tv in result] == ["1.2.0"]

    @pytest.mark.asyncio
    async def test_filter_by_version(self) -> None:
        repo = InMemoryToolVersionRepository()
        tid = TID()
        await repo.save(_make_tv("1.0.0", tool_id=tid))
        result = await repo.list_by_query(ToolVersionQuery(tool_id=tid, version="1.0.0"))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_created_range_filter(self) -> None:
        repo = InMemoryToolVersionRepository()
        tid = TID()
        early = datetime(2026, 1, 1, tzinfo=UTC)
        late = datetime(2026, 6, 1, tzinfo=UTC)
        await repo.save(_make_tv("1.0.0", tool_id=tid, created_at=early))
        await repo.save(_make_tv("2.0.0", tool_id=tid, created_at=late))
        result = await repo.list_by_query(ToolVersionQuery(tool_id=tid, created_after=early, created_before=late))
        assert [tv.version for tv in result] == ["1.0.0"]

    @pytest.mark.asyncio
    async def test_pagination(self) -> None:
        repo = InMemoryToolVersionRepository()
        tid = TID()
        for i in range(5):
            await repo.save(_make_tv(f"1.0.{i}", tool_id=tid))
        page = await repo.list_by_query(ToolVersionQuery(tool_id=tid, offset=1, limit=2))
        assert len(page) == 2
        total = await repo.count(ToolVersionQuery(tool_id=tid))
        assert total == 5

    @pytest.mark.asyncio
    async def test_sorted_by_created_at(self) -> None:
        """按注册时间升序（list_versions 语义）。"""
        repo = InMemoryToolVersionRepository()
        tid = TID()
        base = datetime(2026, 1, 1, tzinfo=UTC)
        for i, v in enumerate(("3.0.0", "1.0.0", "2.0.0")):
            await repo.save(_make_tv(v, tool_id=tid, created_at=base.replace(hour=i)))
        result = await repo.list_by_query(ToolVersionQuery(tool_id=tid))
        assert [tv.version for tv in result] == ["3.0.0", "1.0.0", "2.0.0"]


class TestListActive:
    """活跃版本查询（CANARY+STABLE）测试。"""

    @pytest.mark.asyncio
    async def test_list_active(self) -> None:
        repo = InMemoryToolVersionRepository()
        tid = TID()
        await repo.save(_make_tv("1.0.0", ToolVersionStatus.STABLE, tool_id=tid))
        await repo.save(_make_tv("1.1.0", ToolVersionStatus.CANARY, tool_id=tid, traffic_weight=30))
        await repo.save(_make_tv("1.2.0", ToolVersionStatus.DEPRECATED, tool_id=tid))
        await repo.save(_make_tv("1.3.0", ToolVersionStatus.PENDING, tool_id=tid))
        active = await repo.list_active(tid)
        assert {tv.version for tv in active} == {"1.0.0", "1.1.0"}


class TestProtocolConformance:
    """Protocol 契约测试。"""

    def test_implements_port(self) -> None:
        assert isinstance(InMemoryToolVersionRepository(), ToolVersionRepositoryPort)

    def test_port_is_runtime_checkable(self) -> None:
        assert hasattr(ToolVersionRepositoryPort, "_is_runtime_protocol") or hasattr(
            ToolVersionRepositoryPort, "__runtime_protocol__"
        )


class TestDetachedCopyIsolation:
    """双端副本隔离测试（Round 1 审查——读路径返回副本，save 存副本）。

    判别目标：调用方在异常/失败路径上对读出实体的就地改写不得污染仓储
    持有的共享引用（publish-on-DEPRECATED 失败曾致 InMemory 双 STABLE 污染）。
    """

    @pytest.mark.asyncio
    async def test_mutating_read_result_does_not_pollute_store(self) -> None:
        """改写读出实体（未 save）不影响仓储内部状态。"""
        repo = InMemoryToolVersionRepository()
        tid = TID()
        await repo.save(_make_tv("1.0.0", ToolVersionStatus.STABLE, tool_id=tid))
        fetched = await repo.get_by_tool_and_version(tid, "1.0.0")
        assert fetched is not None
        fetched.status = ToolVersionStatus.DEPRECATED  # 就地改写（模拟失败路径泄漏）
        reread = await repo.get_by_tool_and_version(tid, "1.0.0")
        assert reread is not None
        assert reread.status is ToolVersionStatus.STABLE, "读路径必须返回隔离副本"

    @pytest.mark.asyncio
    async def test_nested_schema_mutation_does_not_pollute_store(self) -> None:
        """嵌套结构变异不影响仓储（deepcopy 真实性——copy.copy 突变必红）。"""
        repo = InMemoryToolVersionRepository()
        tid = TID()
        nested_schema = {"type": "object", "properties": {"factor": {"type": "string"}}}
        tv = ToolVersion(tool_id=tid, version="1.0.0", input_schema=nested_schema, output_schema={})
        tv.status = ToolVersionStatus.STABLE
        await repo.save(tv)
        fetched = await repo.get_by_tool_and_version(tid, "1.0.0")
        assert fetched is not None
        # 嵌套 dict 变异（浅拷贝下此写会穿透到仓储持有的同一嵌套对象）
        fetched.input_schema["properties"]["injected"] = {"type": "string"}
        fetched.input_schema["extra_list"] = ["leak"]
        reread = await repo.get_by_tool_and_version(tid, "1.0.0")
        assert reread is not None
        assert "injected" not in reread.input_schema["properties"], "嵌套 dict 必须深隔离"
        assert "extra_list" not in reread.input_schema, "嵌套新增键必须深隔离"

    @pytest.mark.asyncio
    async def test_mutating_saved_entity_after_save_does_not_pollute_store(self) -> None:
        """save 后改写调用方持有的实体不影响仓储内部状态。"""
        repo = InMemoryToolVersionRepository()
        tid = TID()
        tv = _make_tv("1.0.0", ToolVersionStatus.PENDING, tool_id=tid)
        await repo.save(tv)
        tv.status = ToolVersionStatus.STABLE  # save 后改写（模拟并发交错泄漏）
        fetched = await repo.get_by_tool_and_version(tid, "1.0.0")
        assert fetched is not None
        assert fetched.status is ToolVersionStatus.PENDING, "save 必须存副本"

    @pytest.mark.asyncio
    async def test_list_paths_return_isolated_copies(self) -> None:
        """list_active/list_by_query/list_all 同样返回隔离副本。"""
        repo = InMemoryToolVersionRepository()
        tid = TID()
        await repo.save(_make_tv("1.0.0", ToolVersionStatus.STABLE, tool_id=tid))
        for fetched in (
            *(await repo.list_active(tid)),
            *(await repo.list_by_query(ToolVersionQuery(tool_id=tid))),
            *(await repo.list_all()),
        ):
            fetched.status = ToolVersionStatus.CANARY
        reread = await repo.get_by_tool_and_version(tid, "1.0.0")
        assert reread is not None
        assert reread.status is ToolVersionStatus.STABLE
