"""ToolVersionService 单元测试（Story 4-6 Task 4 TDD 红→绿）

Mock 工厂模式（AsyncMock/MagicMock spec=端口）+ 真实领域组件混合：
- register：431 重复 / 380 工具不存在 / 397 critical 拦截（断言存在性+max
  severity 不断言条数）/ canary_only 标记 / 首版本跳过校验
- publish 状态感知：PENDING 发起灰度 / 无 STABLE 432 / canary_only 直接全量
  432 / CANARY 调档 / promote 放行 / 权重越界（含 0）/ 并存 432 / 243 非法迁移
- abort_canary：成功清场不记戳 / 无活跃 CANARY 243
- rollback：缺省目标排除 from_version（防 ping-pong）/ 清空戳 / 430 / 433 /
  无 STABLE 433 / 清场 CANARY
- resolve：精确 430 / 规范散列路由 / 惰性三分支
- retention：注册触发两级排序淘汰
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.application.services.tool_version_service import ToolVersionService
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus
from src.domain.exceptions import (
    EntityStateTransitionError,
    ToolNotFoundError,
)
from src.domain.exceptions.tool_schema_exceptions import ToolSchemaCompatibilityError
from src.domain.exceptions.tool_version_exceptions import (
    ToolVersionAlreadyExistsError,
    ToolVersionNotFoundError,
    ToolVersionRollbackError,
    ToolVersionTrafficWeightError,
)
from src.domain.ports.tool_version_repository import ToolVersionQuery
from src.infrastructure.validation.jsonschema_validator import JsonSchemaValidatorImpl

BASE = {"type": "object", "properties": {"factor": {"type": "string"}}, "required": ["factor"]}
MAJOR = {
    "type": "object",
    "properties": {"factor": {"type": "string"}, "extra": {"type": "string"}},
    "required": ["factor", "extra"],
}


def _schema_variant(kind: str) -> dict:
    """Schema 判别性构造（major=新增 required；其余 base）。"""
    return MAJOR if kind == "major" else BASE


def _make_tv(
    tool_id: uuid.UUID,
    version: str,
    status: ToolVersionStatus = ToolVersionStatus.PENDING,
    *,
    traffic_weight: int = 0,
    last_stable_at: datetime | None = None,
    created_at: datetime | None = None,
    required_rollout_mode: str = "any",
) -> ToolVersion:
    """构造版本实体。"""
    now = datetime.now(UTC)
    return ToolVersion(
        version_id=uuid.uuid4(),
        tool_id=tool_id,
        version=version,
        input_schema=dict(BASE),
        output_schema=dict(BASE),
        status=status,
        traffic_weight=traffic_weight,
        required_rollout_mode=required_rollout_mode,
        last_stable_at=last_stable_at,
        created_at=created_at or now,
        updated_at=now,
    )


class _FakeRepo:
    """轻量内存仓储替身（spec 语义由 Protocol isinstance 保障，真实校验路径）。"""

    def __init__(self) -> None:
        self._by_key: dict[tuple[uuid.UUID, str], ToolVersion] = {}

    async def save(self, entity: ToolVersion) -> ToolVersion:
        self._by_key[(entity.tool_id, entity.version)] = entity
        return entity

    async def get_by_id(self, id: uuid.UUID) -> ToolVersion | None:
        return next((tv for tv in self._by_key.values() if tv.version_id == id), None)

    async def get_by_tool_and_version(self, tool_id: uuid.UUID, version: str) -> ToolVersion | None:
        return self._by_key.get((tool_id, version))

    async def list_by_query(self, query: ToolVersionQuery) -> list[ToolVersion]:
        results = [tv for tv in self._by_key.values() if query.tool_id is None or tv.tool_id == query.tool_id]
        if query.status is not None:
            results = [tv for tv in results if tv.status == query.status]
        results.sort(key=lambda tv: tv.created_at)
        return results[query.offset : query.offset + query.limit]

    async def count(self, query: ToolVersionQuery) -> int:
        return len(await self.list_by_query(query))

    async def list_active(self, tool_id: uuid.UUID) -> list[ToolVersion]:
        return [
            tv
            for tv in self._by_key.values()
            if tv.tool_id == tool_id and tv.status in (ToolVersionStatus.CANARY, ToolVersionStatus.STABLE)
        ]

    async def delete(self, id: uuid.UUID) -> None:
        for key, tv in list(self._by_key.items()):
            if tv.version_id == id:
                del self._by_key[key]

    async def list_all(self) -> list[ToolVersion]:
        return list(self._by_key.values())


def _make_registry(tool: Tool) -> MagicMock:
    """registry mock（get_tool 返回真实 Tool）。"""
    registry = MagicMock()
    registry.get_tool = MagicMock(return_value=tool)
    return registry


def _make_service(
    max_retained: int = 10,
    tool: Tool | None = None,
) -> tuple[ToolVersionService, _FakeRepo, uuid.UUID, MagicMock]:
    """构造被测服务（真实校验器 + 轻量仓储 + registry mock）。"""
    tool = tool or _make_tool()
    repo = _FakeRepo()
    registry = _make_registry(tool)
    service = ToolVersionService(
        repository=repo,
        schema_validator=JsonSchemaValidatorImpl(),
        tool_registry=registry,
        max_retained_versions=max_retained,
    )
    return service, repo, tool.tool_id, registry


def _make_tool(version: str = "1.0.0") -> Tool:
    """构造真实 Tool。"""
    now = datetime.now(UTC)
    return Tool(
        tool_id=uuid.uuid4(),
        name=f"svc-tool-{uuid.uuid4().hex[:6]}",
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema=dict(BASE),
        output_schema=dict(BASE),
        status=ToolStatus.ACTIVE,
        version=version,
        created_at=now,
        updated_at=now,
    )


def _expected_hit(route_key: str, weight: int) -> bool:
    """规范散列公式独立重算。"""
    return int(hashlib.sha256(route_key.encode()).hexdigest(), 16) % 100 < weight


# ============================================================================
# register_version
# ============================================================================


class TestRegister:
    """注册流程（兼容性分级拦截）。"""

    async def test_register_first_version_skips_compatibility(self) -> None:
        service, repo, tid, _ = _make_service()
        tv = await service.register_version(tid, "2.0.0", dict(BASE), dict(BASE))
        assert tv.required_rollout_mode == "any"
        assert tv.status is ToolVersionStatus.PENDING

    async def test_register_tool_not_found_380(self) -> None:
        tool = _make_tool()
        repo = _FakeRepo()
        registry = MagicMock()
        registry.get_tool = MagicMock(side_effect=ToolNotFoundError(tool_id=str(tool.tool_id)))
        service = ToolVersionService(
            repository=repo,
            schema_validator=JsonSchemaValidatorImpl(),
            tool_registry=registry,
        )
        with pytest.raises(ToolNotFoundError):
            await service.register_version(tool.tool_id, "1.0.0", {}, {})

    async def test_register_duplicate_431(self) -> None:
        service, _, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        with pytest.raises(ToolVersionAlreadyExistsError) as exc_info:
            await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        assert exc_info.value.code == "EXCEPTION_431"

    async def test_register_critical_rejected_397(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        critical = {"type": "object", "properties": {"factor": {"type": "integer"}}, "required": ["factor"]}
        with pytest.raises(ToolSchemaCompatibilityError) as exc_info:
            await service.register_version(tid, "2.0.0", critical, dict(BASE))
        # 断言存在性 + 关键 context 字段（不断言条数——双重上报实态）
        assert exc_info.value.code == "EXCEPTION_397"
        assert "breaking_changes" in exc_info.value.context
        assert exc_info.value.context["breaking_changes"]

    async def test_register_major_marks_canary_only(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        tv = await service.register_version(tid, "2.0.0", dict(MAJOR), dict(BASE))
        assert tv.required_rollout_mode == "canary_only"

    async def test_register_minor_mode_any(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        tv = await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        assert tv.required_rollout_mode == "any"


# ============================================================================
# publish_version（状态感知）
# ============================================================================


class TestPublish:
    """发布流程（灰度发起/调档/直接全量/promote）。"""

    async def test_publish_canary_from_pending(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        tv = await service.publish_version(tid, "1.1.0", 30)
        assert tv.status is ToolVersionStatus.CANARY
        assert tv.traffic_weight == 30

    async def test_publish_canary_without_stable_432(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        with pytest.raises(ToolVersionTrafficWeightError):
            await service.publish_version(tid, "1.1.0", 30)

    async def test_publish_canary_only_direct_full_432(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "2.0.0", dict(MAJOR), dict(BASE))
        with pytest.raises(ToolVersionTrafficWeightError):
            await service.publish_version(tid, "2.0.0", 100)

    async def test_publish_any_direct_full(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        tv = await service.publish_version(tid, "1.1.0", 100)
        assert tv.status is ToolVersionStatus.STABLE

    async def test_publish_adjustment_keeps_canary(self) -> None:
        """CANARY 调档：状态不变、weight 更新。"""
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.1.0", 30)
        tv = await service.publish_version(tid, "1.1.0", 50)
        assert tv.status is ToolVersionStatus.CANARY
        assert tv.traffic_weight == 50

    async def test_publish_promote_canary_only_allowed(self) -> None:
        """canary_only 毕业转正放行（灰度毕业通道）。"""
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "2.0.0", dict(MAJOR), dict(BASE))
        await service.publish_version(tid, "2.0.0", 30)
        tv = await service.publish_version(tid, "2.0.0", 100)
        assert tv.status is ToolVersionStatus.STABLE

    async def test_publish_weight_zero_432(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        with pytest.raises(ToolVersionTrafficWeightError):
            await service.publish_version(tid, "1.1.0", 0)

    async def test_publish_weight_over_100_432(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        with pytest.raises(ToolVersionTrafficWeightError):
            await service.publish_version(tid, "1.1.0", 101)

    async def test_publish_other_canary_conflict_432(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.1.0", 30)
        await service.register_version(tid, "1.2.0", dict(BASE), dict(BASE))
        with pytest.raises(ToolVersionTrafficWeightError):
            await service.publish_version(tid, "1.2.0", 50)

    async def test_publish_on_stable_243(self) -> None:
        """STABLE 上再 publish（非调档语义）→ 非法迁移 243。"""
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        with pytest.raises(EntityStateTransitionError):
            await service.publish_version(tid, "1.0.0", 30)

    async def test_promote_demotes_old_stable_with_stamp(self) -> None:
        """promote：旧 STABLE 降级 + 记戳（曾全量服务标记）。"""
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.1.0", 100)
        old = await repo.get_by_tool_and_version(tid, "1.0.0")
        assert old is not None
        assert old.status is ToolVersionStatus.DEPRECATED
        assert old.last_stable_at is not None

    async def test_publish_version_not_found_430(self) -> None:
        service, _, tid, _ = _make_service()
        with pytest.raises(ToolVersionNotFoundError):
            await service.publish_version(tid, "9.9.9", 30)


# ============================================================================
# abort_canary
# ============================================================================


class TestAbortCanary:
    """放弃灰度（STABLE 不动）。"""

    async def test_abort_success_unstamped(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.1.0", 30)
        tv = await service.abort_canary(tid)
        assert tv.status is ToolVersionStatus.DEPRECATED
        assert tv.last_stable_at is None
        stable = await repo.get_by_tool_and_version(tid, "1.0.0")
        assert stable is not None
        assert stable.status is ToolVersionStatus.STABLE

    async def test_abort_without_canary_243(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        with pytest.raises(EntityStateTransitionError):
            await service.abort_canary(tid)


# ============================================================================
# rollback
# ============================================================================


class TestRollback:
    """一键回滚（防 ping-pong + 430/433 分立 + 清空戳）。"""

    async def _setup_three_generations(self, service: ToolVersionService, tid: uuid.UUID) -> None:
        for v in ("1.0.0", "1.1.0", "2.0.0"):
            await service.register_version(tid, v, dict(BASE), dict(BASE))
            await service.publish_version(tid, v, 100)

    async def test_rollback_default_target_latest_stamped(self) -> None:
        service, repo, tid, _ = _make_service()
        await self._setup_three_generations(service, tid)
        tv = await service.rollback(tid)
        assert tv.version == "1.1.0"
        assert tv.status is ToolVersionStatus.STABLE
        demoted = await repo.get_by_tool_and_version(tid, "2.0.0")
        assert demoted is not None
        assert demoted.status is ToolVersionStatus.DEPRECATED
        assert demoted.last_stable_at is None, "回滚降级必须清空戳（指针原则）"

    async def test_rollback_twice_no_ping_pong(self) -> None:
        """连续两次缺省回滚：第二次到 1.0.0（不回 2.0.0）。"""
        service, repo, tid, _ = _make_service()
        await self._setup_three_generations(service, tid)
        first = await service.rollback(tid)
        assert first.version == "1.1.0"
        second = await service.rollback(tid)
        assert second.version == "1.0.0"

    async def test_rollback_explicit_missing_430(self) -> None:
        service, _, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        with pytest.raises(ToolVersionNotFoundError):
            await service.rollback(tid, target_version="9.9.9")

    async def test_rollback_explicit_non_stable_433(self) -> None:
        service, _, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        with pytest.raises(ToolVersionRollbackError):
            await service.rollback(tid, target_version="1.1.0")  # PENDING 非曾稳定

    async def test_rollback_no_stable_history_433(self) -> None:
        service, _, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        with pytest.raises(ToolVersionRollbackError):
            await service.rollback(tid)

    async def test_rollback_clears_active_canary(self) -> None:
        """回滚清场活跃 CANARY（不记戳）。"""
        service, repo, tid, _ = _make_service()
        await self._setup_three_generations(service, tid)
        await service.register_version(tid, "2.1.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "2.1.0", 30)
        await service.rollback(tid)
        canary = await repo.get_by_tool_and_version(tid, "2.1.0")
        assert canary is not None
        assert canary.status is ToolVersionStatus.DEPRECATED
        assert canary.last_stable_at is None


# ============================================================================
# resolve_version
# ============================================================================


class TestResolve:
    """版本路由（规范散列）+ 惰性三分支。"""

    async def test_resolve_explicit_version(self) -> None:
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        tv = await service.resolve_version(tid, requested_version="1.0.0")
        assert tv.version == "1.0.0"

    async def test_resolve_explicit_missing_430(self) -> None:
        service, _, tid, _ = _make_service()
        with pytest.raises(ToolVersionNotFoundError):
            await service.resolve_version(tid, requested_version="9.9.9")

    async def test_resolve_canary_routing_spec_formula(self) -> None:
        """命中/未命中按规范公式独立重算断言。"""
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.1.0", 30)
        hit_key = next(k for k in (f"key-{i}" for i in range(1000)) if _expected_hit(k, 30))
        miss_key = next(k for k in (f"key-{i}" for i in range(1000)) if not _expected_hit(k, 30))
        assert (await service.resolve_version(tid, route_key=hit_key)).version == "1.1.0"
        assert (await service.resolve_version(tid, route_key=miss_key)).version == "1.0.0"

    async def test_resolve_lazy_initial_registration(self) -> None:
        """惰性：无记录 → 以 tool.version 注册 STABLE。"""
        service, repo, tid, _ = _make_service()
        tv = await service.resolve_version(tid, route_key="first-call")
        assert tv.version == "1.0.0"
        assert tv.status is ToolVersionStatus.STABLE

    async def test_resolve_records_without_active_430(self) -> None:
        """三分支 ③：有记录但无活跃版本 → 430。"""
        service, repo, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        # 仅 PENDING（无活跃）
        with pytest.raises(ToolVersionNotFoundError):
            await service.resolve_version(tid, route_key="any")


# ============================================================================
# retention（注册触发）
# ============================================================================


class TestRetention:
    """保留策略（两级排序淘汰，注册触发）。"""

    async def test_register_evicts_unstamped_first(self) -> None:
        service, repo, tid, _ = _make_service(max_retained=3)
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.1.0", 100)  # 1.0 带戳 DEP
        await service.register_version(tid, "1.2.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.2.0", 30)
        await service.abort_canary(tid)  # 1.2 无戳 DEP；总数 3
        await service.register_version(tid, "1.3.0", dict(BASE), dict(BASE))
        remaining = {tv.version for tv in await repo.list_all()}
        assert "1.2.0" not in remaining, "无戳弃用版本最先淘汰"
        assert "1.0.0" in remaining

    async def test_register_evicts_oldest_stamped_next(self) -> None:
        service, repo, tid, _ = _make_service(max_retained=3)
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.1.0", 100)  # 1.0.0 带戳 DEP；总数 2
        await service.register_version(tid, "1.3.0", dict(BASE), dict(BASE))  # 总数 3（上限内）
        await service.register_version(tid, "1.4.0", dict(BASE), dict(BASE))  # 总数 4 → 淘汰 1
        remaining = {tv.version for tv in await repo.list_all()}
        assert len(remaining) == 3
        assert "1.0.0" not in remaining, "无戳组空后应淘汰最旧带戳版本"


# ============================================================================
# list_versions / get_version_traffic / 构造签名
# ============================================================================


class TestQueries:
    """查询方法。"""

    async def test_list_versions_sorted(self) -> None:
        service, _, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.register_version(tid, "2.0.0", dict(BASE), dict(BASE))
        versions = await service.list_versions(tid)
        assert [tv.version for tv in versions] == ["1.0.0", "2.0.0"]

    async def test_get_version_traffic_canary_view(self) -> None:
        service, _, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.0.0", 100)
        await service.register_version(tid, "1.1.0", dict(BASE), dict(BASE))
        await service.publish_version(tid, "1.1.0", 30)
        view = await service.get_version_traffic(tid)
        assert view["stable_version"] == "1.0.0"
        assert view["canary_version"] == "1.1.0"
        assert view["canary_weight"] == 30

    async def test_get_version_traffic_null_when_no_active(self) -> None:
        service, _, tid, _ = _make_service()
        await service.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
        view = await service.get_version_traffic(tid)
        assert view == {"stable_version": None, "canary_version": None, "canary_weight": None}


def asyncio_run(coro: Any) -> Any:
    """同步包装（Given 构造辅助——独立短生命周期循环）。"""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
