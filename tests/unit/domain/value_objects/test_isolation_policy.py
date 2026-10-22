"""Story 5.4: IsolationPolicy VO 与四级策略表单元测试

覆盖 AC-1（EIP 四级隔离协议模型）:
- DataIsolationMode 四值枚举完备性
- ISOLATION_POLICIES 四级 12 维度逐行（architecture.md §5.1 硬编码表）
- is_default 唯一标记（L4）+ MVP_ALLOWED_LEVELS 恰三值（L1 V2 开放）
- get_isolation_policy 工厂守卫（非枚举实例 → EntityValidationError 242）
- VO 不变量（name 空白 → 242）

Run with:
    poetry run pytest tests/unit/domain/value_objects/test_isolation_policy.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.isolation_policy import (
    ISOLATION_POLICIES,
    MVP_ALLOWED_LEVELS,
    DataIsolationMode,
    IsolationPolicy,
    get_isolation_policy,
)


class TestDataIsolationModeEnum:
    """DataIsolationMode 枚举四值完备性。"""

    def test_exactly_four_values(self) -> None:
        """恰四值（core-domain §17.3.3 四值——str,Enum 便于序列化）。"""
        assert {mode.value for mode in DataIsolationMode} == {
            "read_only",
            "restricted_write",
            "free_write",
            "full_shared",
        }

    def test_str_enum_mixin(self) -> None:
        """str 混入（序列化直传 JSON——对齐 IsolationLevel 形态）。"""
        assert DataIsolationMode.READ_ONLY == "read_only"
        assert isinstance(DataIsolationMode.READ_ONLY, str)


class TestIsolationPoliciesTable:
    """ISOLATION_POLICIES 四级策略表逐行断言（12 维度 + 每级名称）。"""

    def test_exactly_four_keys_matching_level_field(self) -> None:
        """恰四键且键 == 各策略的 level 字段（键值自洽）。"""
        assert set(ISOLATION_POLICIES) == set(IsolationLevel)
        for level, policy in ISOLATION_POLICIES.items():
            assert policy.level is level, f"键 {level} 与 level 字段 {policy.level} 不自洽"

    @pytest.mark.parametrize(
        ("level", "name", "prompt_isolation", "tool_isolation", "data_isolation"),
        [
            (IsolationLevel.L4_HARD, "硬隔离", True, True, DataIsolationMode.READ_ONLY),
            (IsolationLevel.L3_SOFT, "软隔离", True, False, DataIsolationMode.RESTRICTED_WRITE),
            (IsolationLevel.L2_COLLAB, "协作态", True, False, DataIsolationMode.FREE_WRITE),
            (IsolationLevel.L1_FUSED, "融合态", False, False, DataIsolationMode.FULL_SHARED),
        ],
        ids=["L4", "L3", "L2", "L1"],
    )
    def test_policy_dimensions_per_level(
        self,
        level: IsolationLevel,
        name: str,
        prompt_isolation: bool,
        tool_isolation: bool,
        data_isolation: DataIsolationMode,
    ) -> None:
        """三重隔离维度逐行（L4=独立/严格隔离/只读 … L1=共享/完全共享/完全共享）。"""
        policy = ISOLATION_POLICIES[level]
        assert policy.name == name
        assert policy.prompt_isolation is prompt_isolation
        assert policy.tool_isolation is tool_isolation
        assert policy.data_isolation is data_isolation

    def test_l4_is_default_only(self) -> None:
        """is_default 唯一标记在 L4（默认硬隔离——出生即 L4）。"""
        assert ISOLATION_POLICIES[IsolationLevel.L4_HARD].is_default is True
        for level in (IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB, IsolationLevel.L1_FUSED):
            assert ISOLATION_POLICIES[level].is_default is False, f"{level.value} 不得标默认"

    def test_policies_are_frozen_dataclass(self) -> None:
        """frozen VO（策略是无状态共享规则——不可变——setattr 动态调用触发）。"""
        import dataclasses

        policy = ISOLATION_POLICIES[IsolationLevel.L4_HARD]
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(policy, "name", "篡改")


class TestMvpAllowedLevels:
    """MVP 允许等级集（L1 融合态 V2 开放）。"""

    def test_exactly_three_values_without_l1(self) -> None:
        """恰三值 {L4, L3, L2}——L1_FUSED 排除（SYS 监督/紧急态/强制审计均 V2）。"""
        assert MVP_ALLOWED_LEVELS == frozenset({IsolationLevel.L4_HARD, IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB})
        assert IsolationLevel.L1_FUSED not in MVP_ALLOWED_LEVELS

    def test_is_frozenset(self) -> None:
        """frozenset 形态（模块常量不可变）。"""
        assert isinstance(MVP_ALLOWED_LEVELS, frozenset)


class TestGetIsolationPolicy:
    """get_isolation_policy 工厂（枚举键必命中 + 防御守卫）。"""

    @pytest.mark.parametrize(
        "level",
        list(IsolationLevel),
        ids=[level.value for level in IsolationLevel],
    )
    def test_returns_policy_for_all_levels(self, level: IsolationLevel) -> None:
        """四级全命中（返回与表同源实例）。"""
        assert get_isolation_policy(level) is ISOLATION_POLICIES[level]

    @pytest.mark.parametrize(
        "raw",
        ["L4", "L9", "", None, 4],
        ids=["合法值域裸str", "值域外裸str", "空串", "None", "整数"],
    )
    def test_non_enum_instance_raises_242(self, raw: Any) -> None:
        """非 IsolationLevel 实例入参抛 EntityValidationError(242)。

        裸 str 是重点防御面: str,Enum 混入语义下 hash("L4")==hash(L4_HARD)，
        "L4" 可能穿透宽松的成员判定——isinstance 先行守卫唯一可靠。
        （raw 注解 Any——参数化异构非法输入是类型防御测试面，非类型误用）
        """
        with pytest.raises(EntityValidationError) as exc_info:
            get_isolation_policy(raw)
        assert exc_info.value.code == "EXCEPTION_242"


class TestIsolationPolicyValidation:
    """VO 构造不变量。"""

    def test_valid_construction(self) -> None:
        """合法构造（非表内策略也可构造——表是协议常量，VO 是通用载体）。"""
        policy = IsolationPolicy(
            level=IsolationLevel.L4_HARD,
            name="硬隔离",
            prompt_isolation=True,
            tool_isolation=True,
            data_isolation=DataIsolationMode.READ_ONLY,
        )
        assert policy.is_default is False

    def test_blank_name_raises_242(self) -> None:
        """name 空白 → 242（实体不变量语义）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationPolicy(
                level=IsolationLevel.L4_HARD,
                name="   ",
                prompt_isolation=True,
                tool_isolation=True,
                data_isolation=DataIsolationMode.READ_ONLY,
            )
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.parametrize("name", ["", "  \t "], ids=["空串", "空白制表"])
    def test_empty_name_variants_raise(self, name: str) -> None:
        """空串与空白变体均拦截。"""
        with pytest.raises(EntityValidationError):
            IsolationPolicy(
                level=IsolationLevel.L4_HARD,
                name=name,
                prompt_isolation=True,
                tool_isolation=True,
                data_isolation=DataIsolationMode.READ_ONLY,
            )
