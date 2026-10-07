"""工具版本管理领域服务三件套单元测试（Story 4-6 Task 1 TDD 红→绿）

覆盖：
- RolloutPolicyService：severity 分级决策（critical 拒绝 / major canary_only / minor·无破坏 any）
- TrafficRouter：规范散列公式（sha256 % 100 < weight）确定性路由 + 统计验证
  （断言锚点 = 测试内独立重算，禁以 route() 探测结果作锚点——同源循环论证）
- VersionRetentionPlanner：两级排序淘汰（无戳组 created_at 优先于带戳组
  last_stable_at）+ 保护态 + 软上限
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus
from src.domain.services.tool_version_policy import (
    RolloutDecision,
    RolloutPolicyService,
    TrafficRouter,
    VersionRetentionPlanner,
)


def _expected_hit(route_key: str, weight: int) -> bool:
    """按规范散列公式独立重算期望桶位（规范条款，实现与测试共用）。"""
    return int(hashlib.sha256(route_key.encode()).hexdigest(), 16) % 100 < weight


def _make_version(
    version: str,
    status: ToolVersionStatus,
    *,
    last_stable_at: datetime | None = None,
    traffic_weight: int = 0,
    created_at: datetime | None = None,
) -> ToolVersion:
    """构造测试用 ToolVersion。"""
    now = datetime.now(UTC)
    return ToolVersion(
        version_id=uuid.uuid4(),
        tool_id=uuid.uuid4(),
        version=version,
        input_schema={},
        output_schema={},
        status=status,
        traffic_weight=traffic_weight,
        last_stable_at=last_stable_at,
        created_at=created_at or now,
        updated_at=now,
    )


class TestRolloutPolicyService:
    """severity → 发布策略分级决策（领域纯函数）。"""

    def test_critical_rejected(self) -> None:
        """critical → allowed=False（拒绝注册，由服务层抛 397）。"""
        decision = RolloutPolicyService.decide("critical")
        assert decision.allowed is False

    def test_major_canary_only(self) -> None:
        """major → 允许注册但强制灰度（canary_only）。"""
        decision = RolloutPolicyService.decide("major")
        assert decision.allowed is True
        assert decision.mode == "canary_only"

    def test_minor_any(self) -> None:
        """minor → 允许且可直接全量（any）。"""
        decision = RolloutPolicyService.decide("minor")
        assert decision.allowed is True
        assert decision.mode == "any"

    def test_none_any(self) -> None:
        """无破坏性变更（severity=None）→ any。"""
        decision = RolloutPolicyService.decide(None)
        assert decision.allowed is True
        assert decision.mode == "any"

    def test_decision_is_frozen_value_object(self) -> None:
        """RolloutDecision 为 frozen 值对象（stdlib 原生类型字段）。"""
        decision = RolloutPolicyService.decide("major")
        assert isinstance(decision, RolloutDecision)
        assert isinstance(decision.reason, str)

    def test_decide_uses_stdlib_params_only(self) -> None:
        """决策签名为 stdlib 原生参数（不依赖应用层 SchemaCompatibilityResult）。"""
        import inspect

        sig = inspect.signature(RolloutPolicyService.decide)
        assert "max_severity" in sig.parameters


class TestTrafficRouter:
    """确定性流量路由（规范散列公式）。"""

    def test_spec_formula_hit_and_miss(self) -> None:
        """独立重算断言：固定 key 的命中/未命中与规范公式一致。"""
        hit_key = next(k for k in (f"key-{i}" for i in range(1000)) if _expected_hit(k, 30))
        miss_key = next(k for k in (f"key-{i}" for i in range(1000)) if not _expected_hit(k, 30))
        assert TrafficRouter.route(hit_key, "1.1.0", 30, "1.0.0") == "1.1.0"
        assert TrafficRouter.route(miss_key, "1.1.0", 30, "1.0.0") == "1.0.0"

    def test_statistical_distribution_1000_samples(self) -> None:
        """1000 固定样本 30%±5% 统计验证（跨次运行稳定）。"""
        hit = sum(1 for i in range(1000) if TrafficRouter.route(f"key-{i}", "canary", 30, "stable") == "canary")
        ratio = hit / 1000
        assert 0.25 <= ratio <= 0.35, f"灰度命中比例 {ratio:.1%} 超出 30%±5% 容差"

    def test_same_key_deterministic(self) -> None:
        """同一 route_key 重复解析结果完全一致（确定性）。"""
        results = {TrafficRouter.route("stable-key-42", "c", 30, "s") for _ in range(100)}
        assert len(results) == 1

    def test_weight_100_always_canary(self) -> None:
        """weight=100 边界探针：任意 key 必命中 canary（零散列依赖判定）。"""
        for i in range(50):
            assert TrafficRouter.route(f"edge-{i}", "canary", 100, "stable") == "canary"

    def test_weight_boundary_exclusive(self) -> None:
        """公式边界：%100 结果 < weight 命中——桶位恰等于 weight 不命中。"""
        # 找一个 %100 == 30 的 key（若存在），weight=30 时应未命中
        boundary_key = next(
            (k for k in (f"b-{i}" for i in range(10000)) if int(hashlib.sha256(k.encode()).hexdigest(), 16) % 100 == 30),
            None,
        )
        if boundary_key is not None:
            assert TrafficRouter.route(boundary_key, "canary", 30, "stable") == "stable"

    def test_uses_sha256_not_builtin_hash(self) -> None:
        """规范算法为 sha256（非内建 hash——PYTHONHASHSEED 跨次漂移防护）。"""
        import ast
        import inspect
        import textwrap

        source = textwrap.dedent(inspect.getsource(TrafficRouter.route))
        assert "sha256" in source
        # AST 级检查：route 方法体内无内建 hash 调用（排除 docstring 干扰）
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "hash", "禁用内建 hash()（进程盐化）"


class TestVersionRetentionPlanner:
    """版本保留策略规划器（两级排序淘汰）。"""

    def _build_pool(self) -> tuple[list[ToolVersion], dict[uuid.UUID, ToolVersion]]:
        """构造混合版本池：2 无戳 DEP + 3 带戳 DEP + 保护态各一。"""
        base = datetime.now(UTC)
        # 带戳 DEP（last_stable_at 递增：1.0 最旧 → 1.2 最新）
        stamped = [
            _make_version(
                "1.0.0",
                ToolVersionStatus.DEPRECATED,
                last_stable_at=base,
                created_at=base,
            ),
            _make_version(
                "1.1.0",
                ToolVersionStatus.DEPRECATED,
                last_stable_at=base + timedelta(hours=1),
                created_at=base + timedelta(hours=1),
            ),
            _make_version(
                "1.2.0",
                ToolVersionStatus.DEPRECATED,
                last_stable_at=base + timedelta(hours=2),
                created_at=base + timedelta(hours=2),
            ),
        ]
        # 无戳 DEP（灰度清场产物，created_at 更晚——仍优先淘汰）
        unstamped = [
            _make_version(
                "2.0.0",
                ToolVersionStatus.DEPRECATED,
                created_at=base + timedelta(hours=10),
            ),
            _make_version(
                "2.1.0",
                ToolVersionStatus.DEPRECATED,
                created_at=base + timedelta(hours=11),
            ),
        ]
        protected = [
            _make_version("3.0.0", ToolVersionStatus.STABLE, created_at=base + timedelta(hours=20)),
            _make_version("3.1.0", ToolVersionStatus.CANARY, traffic_weight=30, created_at=base + timedelta(hours=21)),
            _make_version("3.2.0", ToolVersionStatus.PENDING, created_at=base + timedelta(hours=22)),
        ]
        pool = stamped + unstamped + protected
        by_ver = {tv.version_id: tv for tv in pool}
        return pool, by_ver

    def test_under_limit_no_eviction(self) -> None:
        """总数不超上限：不淘汰。"""
        pool, _ = self._build_pool()
        assert VersionRetentionPlanner.plan(pool, max_retained=10) == []

    def test_unstamped_group_evicted_first(self) -> None:
        """第一级：无戳组（灰度清场产物）优先于带戳组（曾稳定版）。"""
        pool, by_ver = self._build_pool()
        evict = VersionRetentionPlanner.plan(pool, max_retained=7)  # 8 版本需淘汰 1
        assert [by_ver[v].version for v in evict] == ["2.0.0"], "无戳组 created_at 最旧者先淘汰"

    def test_unstamped_tiebreak_by_created_at(self) -> None:
        """无戳组内平局裁决键 = created_at 升序。"""
        pool, by_ver = self._build_pool()
        evict = VersionRetentionPlanner.plan(pool, max_retained=6)  # 需淘汰 2（无戳组清空）
        assert [by_ver[v].version for v in evict] == ["2.0.0", "2.1.0"]

    def test_stamped_group_by_last_stable_at_asc(self) -> None:
        """带戳组按 last_stable_at 升序（淘汰键与回滚价值键对齐）。"""
        pool, by_ver = self._build_pool()
        evict = VersionRetentionPlanner.plan(pool, max_retained=5)  # 需淘汰 3：无戳组 2 + 最旧带戳 1
        assert [by_ver[v].version for v in evict] == ["2.0.0", "2.1.0", "1.0.0"]

    def test_protected_states_never_evicted(self) -> None:
        """STABLE/CANARY/PENDING 受保护——淘汰从不过半保护态。"""
        pool, by_ver = self._build_pool()
        evict = VersionRetentionPlanner.plan(pool, max_retained=1)  # 极端：可淘汰仅 5 个 DEP
        evicted_versions = {by_ver[v].version for v in evict}
        assert evicted_versions == {"2.0.0", "2.1.0", "1.0.0", "1.1.0", "1.2.0"}
        assert "3.0.0" not in evicted_versions
        assert "3.1.0" not in evicted_versions
        assert "3.2.0" not in evicted_versions

    def test_soft_limit_when_deprecated_insufficient(self) -> None:
        """软上限：可淘汰 DEPRECATED 不足时不强制（保护态优先于数量上限）。"""
        base = datetime.now(UTC)
        pool = [
            _make_version("1.0.0", ToolVersionStatus.STABLE, created_at=base),
            _make_version("1.1.0", ToolVersionStatus.PENDING, created_at=base),
            _make_version("1.2.0", ToolVersionStatus.CANARY, traffic_weight=50, created_at=base),
        ]
        assert VersionRetentionPlanner.plan(pool, max_retained=2) == [], "11 全保护态不淘汰"

    def test_returns_version_ids(self) -> None:
        """返回值为待删除 version_id 列表（uuid.UUID）。"""
        pool, by_ver = self._build_pool()
        evict = VersionRetentionPlanner.plan(pool, max_retained=6)
        assert all(isinstance(v, uuid.UUID) for v in evict)
