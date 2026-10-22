"""Story 5.4: IsolationState 实体单元测试

覆盖 AC-2（初始化守卫）/ AC-4（实体守卫与 no-op）:
- initialize 工厂: 默认 now UTC / initial_default 原因 / initialized_at==updated_at（单 now 双用）
- initialize 等级守卫双条件: L1（合法枚举越 MVP 白名单）→ 446；裸 str "L3"（合法值域——
  str,Enum 混入语义下 in frozenset 判定 True，单 not in 守卫拦不住）与 "L9"（值域外）→ 均 446
- switch_to: 合法切换 True 且三字段更新 / 同等级 False 且零变更 / L1 → 446（context 双锚）
  / 裸 str "L3" 类型污染防线 / trigger_reason 空白 → 242
- __post_init__（绕过工厂直构造）: agent_id 非 UUID / current_level 非枚举 / 原因空 → 242
- now 参数注入确定性

Run with:
    poetry run pytest tests/unit/domain/entities/test_isolation_state.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.domain.entities.isolation_state import IsolationState
from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import EntityValidationError, IsolationLevelNotSupportedError


def _valid_state(
    level: IsolationLevel = IsolationLevel.L4_HARD,
    reason: str = "initial_default",
) -> IsolationState:
    """合法 IsolationState 直构造辅助（绕过工厂的 __post_init__ 断言面）。"""
    now = datetime.now(UTC)
    return IsolationState(
        agent_id=uuid.uuid4(),
        current_level=level,
        initialized_at=now,
        updated_at=now,
        last_trigger_reason=reason,
    )


class TestInitializeFactory:
    """initialize 类方法工厂。"""

    def test_creates_l4_with_initial_default_reason(self) -> None:
        """工厂初始化: L4 + last_trigger_reason=="initial_default"。"""
        agent_id = uuid.uuid4()
        state = IsolationState.initialize(agent_id, IsolationLevel.L4_HARD)
        assert state.agent_id == agent_id
        assert state.current_level is IsolationLevel.L4_HARD
        assert state.last_trigger_reason == "initial_default"

    def test_initialized_at_equals_updated_at(self) -> None:
        """单 now 双用——初始化两时刻严格相等（R3 时间线1）。"""
        fixed = datetime(2026, 10, 22, 8, 0, 0, tzinfo=UTC)
        state = IsolationState.initialize(uuid.uuid4(), IsolationLevel.L4_HARD, now=fixed)
        assert state.initialized_at == fixed
        assert state.updated_at == fixed
        assert state.initialized_at is state.updated_at

    def test_default_now_is_utc(self) -> None:
        """默认 now 取 UTC（tzinfo 断言）。"""
        state = IsolationState.initialize(uuid.uuid4(), IsolationLevel.L4_HARD)
        assert state.initialized_at.tzinfo is UTC
        assert state.updated_at.tzinfo is UTC

    def test_accepts_all_mvp_levels(self) -> None:
        """MVP 三级均合法初始化（L4/L3/L2）。"""
        for level in (IsolationLevel.L4_HARD, IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB):
            state = IsolationState.initialize(uuid.uuid4(), level)
            assert state.current_level is level

    def test_l1_beyond_mvp_whitelist_raises_446(self) -> None:
        """L1——合法枚举越 MVP 白名单 → 446（context 携带 level 与 supported_levels）。"""
        with pytest.raises(IsolationLevelNotSupportedError) as exc_info:
            IsolationState.initialize(uuid.uuid4(), IsolationLevel.L1_FUSED)
        assert exc_info.value.code == "EXCEPTION_446"
        assert exc_info.value.context["level"] == "L1"
        assert exc_info.value.context["supported_levels"] == ["L4", "L3", "L2"]

    def test_supported_level_values_derives_from_mvp_constant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """supported_levels 真派生行为锁：MVP_ALLOWED_LEVELS 扩容后 context 随动。

        monkeypatch 须用枚举成员（str,Enum hash 语义下裸 "L1" 无法命中 frozenset
        成员——isolation_policy L146 同款注记）；延迟 from-import 每次调用读
        sys.modules 属性，monkeypatch 即时生效（R2-OBS——同值字面量替换对
        现值断言零判别力，本用例以行为差锁定派生真源性）。
        """
        import src.domain.value_objects.isolation_policy as isolation_policy_module

        monkeypatch.setattr(
            isolation_policy_module,
            "MVP_ALLOWED_LEVELS",
            frozenset({IsolationLevel.L4_HARD, IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB, IsolationLevel.L1_FUSED}),
        )
        raw_level: Any = "L9"  # Any 注解承载故意非法类型（mypy arg-type 面——先例 bad_ttl 同款）
        with pytest.raises(IsolationLevelNotSupportedError) as exc_info:
            IsolationState.initialize(uuid.uuid4(), raw_level)  # 非枚举实例触发 446（双条件守卫第一支）
        assert exc_info.value.context["supported_levels"] == ["L4", "L3", "L2", "L1"], (
            "supported_levels 须从 MVP_ALLOWED_LEVELS 真派生（含新扩 L1）——硬编码形态在本用例红"
        )

    @pytest.mark.parametrize(
        "raw",
        ["L3", "L9"],
        ids=["合法值域裸str", "值域外裸str"],
    )
    def test_bare_string_raises_446_both_cases(self, raw: Any) -> None:
        """非枚举实例双入参 → 均 446（R3-F01 实测定谳）。

        裸 "L3"（合法值域）: str,Enum 混入语义下 hash("L3")==hash(L3_SOFT)、
        "L3" in frozenset 判定 True——单 `not in` 守卫拦不住（会放行到 242/
        类型污染），双条件 isinstance 先行才使本断言对两种入参均成立。
        （raw 注解 Any——异构非法输入是类型防御测试面）
        """
        with pytest.raises(IsolationLevelNotSupportedError) as exc_info:
            IsolationState.initialize(uuid.uuid4(), raw)
        assert exc_info.value.code == "EXCEPTION_446"

    def test_non_string_non_enum_raises_446(self) -> None:
        """整数等异构入参 → 446（isinstance 先行统一拦截）。"""
        raw: Any = 4
        with pytest.raises(IsolationLevelNotSupportedError):
            IsolationState.initialize(uuid.uuid4(), raw)


class TestSwitchTo:
    """switch_to 实例方法（领域行为内聚——等级合法性校验在实体）。"""

    def test_valid_switch_returns_true_and_updates_fields(self) -> None:
        """合法切换: 返回 True 且 current_level/updated_at/last_trigger_reason 更新。"""
        state = IsolationState.initialize(uuid.uuid4(), IsolationLevel.L4_HARD)
        before_updated = state.updated_at
        switched = state.switch_to(IsolationLevel.L3_SOFT, "任务需要软隔离")
        assert switched is True
        assert state.current_level is IsolationLevel.L3_SOFT
        assert state.updated_at >= before_updated
        assert state.last_trigger_reason == "任务需要软隔离"

    def test_switch_with_now_injection_deterministic(self) -> None:
        """now 参数注入确定性（updated_at == 注入值——不依赖墙钟）。"""
        state = IsolationState.initialize(uuid.uuid4(), IsolationLevel.L4_HARD)
        fixed = datetime(2026, 10, 22, 9, 30, 0, tzinfo=UTC)
        state.switch_to(IsolationLevel.L2_COLLAB, "协作分析", now=fixed)
        assert state.updated_at == fixed

    def test_same_level_returns_false_zero_changes(self) -> None:
        """同等级 no-op: 返回 False 且字段零变更（now 注入同值断言——updated_at 不变）。"""
        fixed_init = datetime(2026, 10, 22, 8, 0, 0, tzinfo=UTC)
        state = IsolationState.initialize(uuid.uuid4(), IsolationLevel.L4_HARD, now=fixed_init)
        later = fixed_init + timedelta(minutes=5)
        switched = state.switch_to(IsolationLevel.L4_HARD, "同等级重试", now=later)
        assert switched is False
        assert state.current_level is IsolationLevel.L4_HARD
        assert state.updated_at == fixed_init, "no-op 不得推进 updated_at"
        assert state.last_trigger_reason == "initial_default", "no-op 不得改写触发原因"

    def test_l1_switch_raises_446_with_context(self) -> None:
        """L1 切换 → 446（context 携带 level 与 supported_levels）。"""
        state = IsolationState.initialize(uuid.uuid4(), IsolationLevel.L4_HARD)
        with pytest.raises(IsolationLevelNotSupportedError) as exc_info:
            state.switch_to(IsolationLevel.L1_FUSED, "尝试融合态")
        assert exc_info.value.code == "EXCEPTION_446"
        assert exc_info.value.context["level"] == "L1"
        assert exc_info.value.context["supported_levels"] == ["L4", "L3", "L2"]

    def test_bare_string_switch_raises_446_type_pollution_guard(self) -> None:
        """裸 str "L3" 经 switch_to → 446（类型污染防线）。

        dataclass 属性赋值不触发 __post_init__——裸 str 穿透单守卫后
        self.current_level = target_level 即静默类型污染持久化；
        双条件守卫（isinstance 先行）是唯一防线。
        """
        raw_level: Any = "L3"
        state = IsolationState.initialize(uuid.uuid4(), IsolationLevel.L4_HARD)
        with pytest.raises(IsolationLevelNotSupportedError):
            state.switch_to(raw_level, "类型污染探测")
        assert isinstance(state.current_level, IsolationLevel), "裸 str 不得穿透到字段"

    @pytest.mark.parametrize("reason", ["", "   ", "\t "], ids=["空串", "空白", "制表"])
    def test_blank_reason_raises_242(self, reason: str) -> None:
        """trigger_reason 空/空白 → 242（原因缺失是实体不变量问题——与 446 语义区分）。"""
        state = IsolationState.initialize(uuid.uuid4(), IsolationLevel.L4_HARD)
        with pytest.raises(EntityValidationError) as exc_info:
            state.switch_to(IsolationLevel.L3_SOFT, reason)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_reason_stripped_on_switch(self) -> None:
        """合法原因两侧空白被 strip（存储归一）。"""
        state = IsolationState.initialize(uuid.uuid4(), IsolationLevel.L4_HARD)
        state.switch_to(IsolationLevel.L3_SOFT, "  软隔离需求  ")
        assert state.last_trigger_reason == "软隔离需求"


class TestPostInitInvariants:
    """__post_init__ 不变量（绕过工厂直构造——防御面完整性）。"""

    def test_valid_direct_construction(self) -> None:
        """合法直构造通过。"""
        state = _valid_state()
        assert isinstance(state.agent_id, uuid.UUID)
        assert state.current_level is IsolationLevel.L4_HARD

    def test_non_uuid_agent_id_raises_242(self) -> None:
        """agent_id 非 UUID → 242（bad_id 注解 Any——非法输入是类型防御测试面）。"""
        now = datetime.now(UTC)
        bad_id: Any = "not-a-uuid"
        with pytest.raises(EntityValidationError):
            IsolationState(
                agent_id=bad_id,
                current_level=IsolationLevel.L4_HARD,
                initialized_at=now,
                updated_at=now,
                last_trigger_reason="initial_default",
            )

    def test_non_enum_current_level_raises_242(self) -> None:
        """current_level 非枚举实例 → 242（直构造路径——非工厂路径的防线；
        bad_level 注解 Any——类型防御测试面）。"""
        now = datetime.now(UTC)
        bad_level: Any = "L4"
        with pytest.raises(EntityValidationError):
            IsolationState(
                agent_id=uuid.uuid4(),
                current_level=bad_level,
                initialized_at=now,
                updated_at=now,
                last_trigger_reason="initial_default",
            )

    def test_blank_reason_raises_242(self) -> None:
        """last_trigger_reason 空 → 242。"""
        now = datetime.now(UTC)
        with pytest.raises(EntityValidationError):
            IsolationState(
                agent_id=uuid.uuid4(),
                current_level=IsolationLevel.L4_HARD,
                initialized_at=now,
                updated_at=now,
                last_trigger_reason="   ",
            )

    def test_entity_is_mutable_dataclass(self) -> None:
        """非 frozen（对齐 Agent 实体可变状态机形态——有切换生命周期）。"""
        state = _valid_state()
        # 可变形态: 直接字段赋值成功即证明非 frozen（FrozenInstanceError 会炸）
        state.last_trigger_reason = "手动改写验证可变"
        assert state.last_trigger_reason == "手动改写验证可变"


class TestErrorTypeContract:
    """446 构造入参契约（裸值 str 化——非枚举实例的 context 表达）。"""

    def test_446_from_initialize_is_business_exception(self) -> None:
        """446 属 BusinessException 族（运行时用户错误——HTTP 422 语义）。"""
        from src.domain.exceptions import BusinessException

        with pytest.raises(IsolationLevelNotSupportedError) as exc_info:
            IsolationState.initialize(uuid.uuid4(), IsolationLevel.L1_FUSED)
        assert isinstance(exc_info.value, BusinessException)

    def test_242_is_entity_validation(self) -> None:
        """242 属实体校验族。"""
        state = _valid_state()
        with pytest.raises(EntityValidationError):
            state.switch_to(IsolationLevel.L3_SOFT, "")
