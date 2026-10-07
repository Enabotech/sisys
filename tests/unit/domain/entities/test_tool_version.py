"""ToolVersion 聚合根单元测试（Story 4-6 Task 1 TDD 红→绿）

覆盖：
- 构造校验：SemVer / traffic_weight [0,100] / required_rollout_mode 枚举 /
  状态枚举小写值 / schema 关键词规则（复用 Tool 的 _JSON_SCHEMA_KEYWORDS 语义）
- 状态机：7 个合法迁移格全过（含 CANARY→CANARY 调档同态、
  DEPRECATED→STABLE 回滚恢复）+ 非法迁移抛 EntityStateTransitionError(243)
- DEPRECATED 化三分戳记规则：被新版本替代记 last_stable_at、
  被回滚清空（置 None，含残留戳清除）、灰度清场不记
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NotRequired, TypedDict, Unpack

import pytest

from src.domain.entities.tool_version import (
    ToolVersion,
    ToolVersionStatus,
)
from src.domain.exceptions import EntityStateTransitionError, EntityValidationError


class _VersionOverrides(TypedDict):
    """_make_version 可覆盖字段（TypedDict 类型安全 kwargs——零抑制注释）。"""

    tool_id: NotRequired[str]
    input_schema: NotRequired[dict]
    output_schema: NotRequired[dict]
    traffic_weight: NotRequired[int]
    required_rollout_mode: NotRequired[str]
    last_stable_at: NotRequired[datetime | None]
    created_at: NotRequired[datetime]
    updated_at: NotRequired[datetime]


def _make_version(
    version: str = "1.0.0",
    status: ToolVersionStatus = ToolVersionStatus.PENDING,
    **kwargs: Unpack[_VersionOverrides],
) -> ToolVersion:
    """构造测试用 ToolVersion 实体。"""
    now = datetime.now(UTC)
    return ToolVersion(
        tool_id=kwargs.get("tool_id", "00000000-0000-0000-0000-000000000001"),
        version=version,
        input_schema=kwargs.get("input_schema", {}),
        output_schema=kwargs.get("output_schema", {}),
        status=status,
        traffic_weight=kwargs.get("traffic_weight", 0),
        required_rollout_mode=kwargs.get("required_rollout_mode", "any"),
        last_stable_at=kwargs.get("last_stable_at"),
        created_at=kwargs.get("created_at", now),
        updated_at=kwargs.get("updated_at", now),
    )


class TestConstructionValidation:
    """构造校验测试。"""

    def test_valid_construction_defaults(self) -> None:
        """合法构造：默认 PENDING / weight=0 / mode=any / last_stable_at=None。"""
        tv = _make_version()
        assert tv.status is ToolVersionStatus.PENDING
        assert tv.traffic_weight == 0
        assert tv.required_rollout_mode == "any"
        assert tv.last_stable_at is None

    @pytest.mark.parametrize("bad_version", ["1.0", "v1.0.0", "1.0.0.0", "abc", "1..0"])
    def test_invalid_semver_raises_242(self, bad_version: str) -> None:
        """SemVer X.Y.Z 强校验（复用 Tool _SEMVER_PATTERN 规则）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_version(version=bad_version)
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.parametrize("bad_weight", [-1, 101, 1000])
    def test_invalid_weight_raises_242(self, bad_weight: int) -> None:
        """traffic_weight 存储域 [0,100]。"""
        with pytest.raises(EntityValidationError):
            _make_version(traffic_weight=bad_weight)

    @pytest.mark.parametrize("bad_mode", ["ANY", "canary", "full", ""])
    def test_invalid_rollout_mode_raises_242(self, bad_mode: str) -> None:
        """required_rollout_mode 值域 {"any","canary_only"}（小写）。"""
        with pytest.raises(EntityValidationError):
            _make_version(required_rollout_mode=bad_mode)

    def test_status_enum_values_lowercase(self) -> None:
        """状态枚举显式小写值（与 migration CHECK 值域一一对应）。"""
        assert ToolVersionStatus.PENDING.value == "pending"
        assert ToolVersionStatus.CANARY.value == "canary"
        assert ToolVersionStatus.STABLE.value == "stable"
        assert ToolVersionStatus.DEPRECATED.value == "deprecated"

    def test_nonempty_schema_requires_keyword(self) -> None:
        """非空 schema 须含 JSON Schema 关键词（Tool 规则照搬）。"""
        now = datetime.now(UTC)
        with pytest.raises(EntityValidationError):
            ToolVersion(
                tool_id="00000000-0000-0000-0000-000000000001",
                version="1.0.0",
                input_schema={"unknown_key": 1},
                output_schema={},
                created_at=now,
                updated_at=now,
            )

    def test_empty_schema_is_valid(self) -> None:
        """空 schema 合法（catalog 工具默认形态）。"""
        tv = _make_version(input_schema={}, output_schema={})
        assert tv.input_schema == {}


class TestStateMachine:
    """状态机迁移矩阵测试（7 合法格 + 非法迁移 243）。"""

    def test_pending_to_canary(self) -> None:
        """PENDING → CANARY（发起灰度）。"""
        tv = _make_version(status=ToolVersionStatus.PENDING)
        tv.transition_to(ToolVersionStatus.CANARY)
        assert tv.status is ToolVersionStatus.CANARY

    def test_pending_to_stable(self) -> None:
        """PENDING → STABLE（直接全量）。"""
        tv = _make_version(status=ToolVersionStatus.PENDING)
        tv.transition_to(ToolVersionStatus.STABLE)
        assert tv.status is ToolVersionStatus.STABLE

    def test_canary_to_canary_adjustment(self) -> None:
        """CANARY → CANARY（调档同态迁移——渐进放量）。"""
        tv = _make_version(status=ToolVersionStatus.CANARY, traffic_weight=30)
        tv.transition_to(ToolVersionStatus.CANARY)
        assert tv.status is ToolVersionStatus.CANARY

    def test_canary_to_stable_promote(self) -> None:
        """CANARY → STABLE（promote 转正）。"""
        tv = _make_version(status=ToolVersionStatus.CANARY)
        tv.transition_to(ToolVersionStatus.STABLE)
        assert tv.status is ToolVersionStatus.STABLE

    def test_canary_to_deprecated_abort(self) -> None:
        """CANARY → DEPRECATED（放弃灰度/回滚清场）。"""
        tv = _make_version(status=ToolVersionStatus.CANARY)
        tv.transition_to(ToolVersionStatus.DEPRECATED)
        assert tv.status is ToolVersionStatus.DEPRECATED

    def test_stable_to_deprecated_replacement(self) -> None:
        """STABLE → DEPRECATED（被新版本替代/被回滚）。"""
        tv = _make_version(status=ToolVersionStatus.STABLE)
        tv.transition_to(ToolVersionStatus.DEPRECATED)
        assert tv.status is ToolVersionStatus.DEPRECATED

    def test_deprecated_to_stable_restore(self) -> None:
        """DEPRECATED → STABLE（回滚恢复迁移——唯一合法触发方 rollback 流程）。"""
        tv = _make_version(status=ToolVersionStatus.DEPRECATED)
        tv.transition_to(ToolVersionStatus.STABLE)
        assert tv.status is ToolVersionStatus.STABLE

    @pytest.mark.parametrize(
        ("from_status", "to_status"),
        [
            (ToolVersionStatus.PENDING, ToolVersionStatus.PENDING),
            (ToolVersionStatus.PENDING, ToolVersionStatus.DEPRECATED),
            (ToolVersionStatus.CANARY, ToolVersionStatus.PENDING),
            (ToolVersionStatus.STABLE, ToolVersionStatus.PENDING),
            (ToolVersionStatus.STABLE, ToolVersionStatus.CANARY),
            (ToolVersionStatus.STABLE, ToolVersionStatus.STABLE),
            (ToolVersionStatus.DEPRECATED, ToolVersionStatus.PENDING),
            (ToolVersionStatus.DEPRECATED, ToolVersionStatus.CANARY),
            (ToolVersionStatus.DEPRECATED, ToolVersionStatus.DEPRECATED),
        ],
        ids=[
            "PENDING→PENDING",
            "PENDING→DEPRECATED",
            "CANARY→PENDING",
            "STABLE→PENDING",
            "STABLE→CANARY",
            "STABLE→STABLE",
            "DEPRECATED→PENDING",
            "DEPRECATED→CANARY",
            "DEPRECATED→DEPRECATED",
        ],
    )
    def test_illegal_transitions_raise_243(
        self,
        from_status: ToolVersionStatus,
        to_status: ToolVersionStatus,
    ) -> None:
        """非法迁移抛 EntityStateTransitionError(EXCEPTION_243)。"""
        tv = _make_version(status=from_status)
        with pytest.raises(EntityStateTransitionError) as exc_info:
            tv.transition_to(to_status)
        assert exc_info.value.code == "EXCEPTION_243"

    def test_transition_updates_updated_at(self) -> None:
        """合法迁移刷新 updated_at（构造旧时间戳——严格大于断言零时钟抖动）。"""
        tv = _make_version(status=ToolVersionStatus.PENDING, updated_at=datetime.now(UTC) - timedelta(seconds=1))
        before = tv.updated_at
        tv.transition_to(ToolVersionStatus.CANARY)
        assert tv.updated_at > before, "迁移必须刷新 updated_at"

    def test_transition_no_state_version_lock(self) -> None:
        """与 ToolExecution 先例的差异点：不携带 state_version 乐观锁自增。

        ToolVersionRepositoryPort 无乐观锁方法——原子性由 savepoint 保证。
        """
        tv = _make_version(status=ToolVersionStatus.PENDING)
        assert not hasattr(tv, "state_version")


class TestLastStableAtStamps:
    """DEPRECATED 化三分戳记规则测试。"""

    def test_stamp_on_replacement(self) -> None:
        """被新版本替代降级：记录 last_stable_at（曾全量服务标记）。"""
        tv = _make_version(status=ToolVersionStatus.STABLE)
        now = datetime.now(UTC)
        tv.transition_to(ToolVersionStatus.DEPRECATED)
        tv.stamp_last_stable(now)
        assert tv.last_stable_at == now

    def test_clear_on_rollback_demotion(self) -> None:
        """被回滚降级：显式清空（置 None）——含 promote 期残留戳清除。"""
        now = datetime.now(UTC)
        tv = _make_version(status=ToolVersionStatus.STABLE, last_stable_at=now)
        tv.transition_to(ToolVersionStatus.DEPRECATED)
        tv.clear_last_stable()
        assert tv.last_stable_at is None

    def test_no_stamp_on_canary_cleanup(self) -> None:
        """灰度清场降级：不记 last_stable_at（从未稳定）。"""
        tv = _make_version(status=ToolVersionStatus.CANARY, traffic_weight=30)
        tv.transition_to(ToolVersionStatus.DEPRECATED)
        assert tv.last_stable_at is None

    def test_clear_semantics_for_rollback_candidate(self) -> None:
        """清空后的版本退出回滚候选（带戳 → clear → None = 非候选）。"""
        now = datetime.now(UTC)
        tv = _make_version(status=ToolVersionStatus.DEPRECATED, last_stable_at=now)
        tv.clear_last_stable()
        assert tv.last_stable_at is None


class TestWeightSemantics:
    """traffic_weight 存储语义测试。"""

    def test_weight_zero_valid_for_pending(self) -> None:
        """PENDING 初始态 weight=0 合法（实体存储域含 0）。"""
        tv = _make_version(status=ToolVersionStatus.PENDING, traffic_weight=0)
        assert tv.traffic_weight == 0

    def test_weight_bounds_inclusive(self) -> None:
        """存储域闭区间 [0,100]。"""
        assert _make_version(traffic_weight=0).traffic_weight == 0
        assert _make_version(traffic_weight=100).traffic_weight == 100
