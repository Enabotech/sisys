"""AgentConfig 值对象单元测试（Story 5-1）

覆盖 CEO Agent 基础配置值对象（frozen dataclass，零外部依赖）：
- frozen 冻结性与字段构造
- 必填非空校验（falsy 判空——空串/空列表均拦截，非仅 None）
- state_ttl 边界钉端点（60/2592000 恰好合法、59/2592001 抛——含闭区间，防 off-by-one）
- preferred_model 空串归一化为 None（与 YAML null 等价，消费方只见 None | str 两态）
- 校验失败抛 AgentConfigError(EXCEPTION_440)——「配置资产缺陷」语义与 242「实体不变量违反」分码

Run with:
    poetry run pytest tests/unit/domain/value_objects/test_agent_config.py -v
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from src.domain.entities.agent import AgentRole
from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import AgentConfigError
from src.domain.value_objects.agent_config import AgentConfig


def _make_config(**overrides) -> AgentConfig:
    """工厂：构造合法 CEO 配置（可覆盖任意字段）。"""
    defaults: dict = {
        "role": AgentRole.CEO,
        "name": "CEO Agent",
        "description": "首席执行官 Agent",
        "version": "1.0.0",
        "responsibilities": ("战略方向", "最终决策"),
        "domain_knowledge": ("宏观趋势", "竞争格局"),
        "preferred_model": None,
    }
    defaults.update(overrides)
    return AgentConfig(**defaults)


# ===================================================================
# 构造与默认值
# ===================================================================


class TestAgentConfigCreation:
    """AgentConfig 构造契约。"""

    def test_create_with_all_fields(self) -> None:
        config = _make_config()
        assert config.role == AgentRole.CEO
        assert config.name == "CEO Agent"
        assert config.version == "1.0.0"
        assert config.responsibilities == ("战略方向", "最终决策")
        assert config.domain_knowledge == ("宏观趋势", "竞争格局")

    def test_state_ttl_default_86400(self) -> None:
        """state_ttl 默认 86400（唯一默认值真源——仓储签名无默认值避免双真源）。"""
        config = _make_config()
        assert config.state_ttl == 86400

    def test_default_isolation_level_l4(self) -> None:
        config = _make_config()
        assert config.default_isolation_level is IsolationLevel.L4_HARD

    def test_frozen_immutable(self) -> None:
        config = _make_config()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(config, "name", "mutated")  # 内建 setattr 触发 frozen __setattr__（静态检查不误报）

    def test_tuple_fields(self) -> None:
        """responsibilities/domain_knowledge 为 tuple（YAML list 由加载器显式转换）。"""
        config = _make_config()
        assert isinstance(config.responsibilities, tuple)
        assert isinstance(config.domain_knowledge, tuple)


# ===================================================================
# preferred_model 归一化
# ===================================================================


class TestPreferredModelNormalization:
    """preferred_model 空串归一化为 None（与 YAML null 等价）。"""

    def test_empty_string_normalized_to_none(self) -> None:
        config = _make_config(preferred_model="")
        assert config.preferred_model is None

    def test_none_stays_none(self) -> None:
        config = _make_config(preferred_model=None)
        assert config.preferred_model is None

    def test_valid_model_kept(self) -> None:
        config = _make_config(preferred_model="qwen2.5:72b")
        assert config.preferred_model == "qwen2.5:72b"


# ===================================================================
# 必填非空校验（falsy 判空）
# ===================================================================


class TestRequiredFieldValidation:
    """必填字段 falsy 判空（空串/空 tuple 均拦截，非仅 None）。"""

    @pytest.mark.parametrize("field", ["name", "description", "version"])
    def test_empty_string_raises_440(self, field: str) -> None:
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(**{field: ""})
        assert exc_info.value.code == "EXCEPTION_440"
        assert exc_info.value.context.get("reason")

    @pytest.mark.parametrize(
        ("field", "value"),
        [("responsibilities", ()), ("domain_knowledge", ())],
    )
    def test_empty_tuple_raises_440(self, field: str, value: tuple) -> None:
        """空列表（`capabilities.responsibilities: []`）必须拦截——Agent.validate()
        不校验非空，VO falsy 判空是运行时唯一防线。"""
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(**{field: value})
        assert exc_info.value.code == "EXCEPTION_440"

    @pytest.mark.parametrize(
        ("field", "value"),
        [("responsibilities", "战略方向"), ("domain_knowledge", "宏观趋势")],
    )
    def test_string_scalar_raises_440(self, field: str, value: str) -> None:
        """字符串标量必须拦截——truthy str 越过 falsy 判空后，用例层 list() 会
        逐字符静默展开成 ('战','略',...)（静默数据损坏，与加载器标量陷阱同款）。"""
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(**{field: value})
        assert exc_info.value.code == "EXCEPTION_440"
        assert "tuple" in exc_info.value.context.get("reason", ""), "reason 须指明 tuple 契约"

    @pytest.mark.parametrize(
        ("field", "value"),
        [("responsibilities", ["战略方向"]), ("domain_knowledge", ["宏观趋势"])],
    )
    def test_list_form_raises_440(self, field: str, value: list) -> None:
        """list 形态拦截——VO 契约是 tuple（加载器显式转换后的唯一合法形态）。"""
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(**{field: value})
        assert exc_info.value.code == "EXCEPTION_440"

    def test_whitespace_only_name_raises(self) -> None:
        with pytest.raises(AgentConfigError):
            _make_config(name="   ")


# ===================================================================
# state_ttl 范围校验（钉端点，防 off-by-one）
# ===================================================================


class TestStateTtlValidation:
    """state_ttl 闭区间 60~2592000（端点值恰好合法）。"""

    def test_ttl_60_lower_bound_valid(self) -> None:
        config = _make_config(state_ttl=60)
        assert config.state_ttl == 60

    def test_ttl_2592000_upper_bound_valid(self) -> None:
        config = _make_config(state_ttl=2592000)
        assert config.state_ttl == 2592000

    def test_ttl_59_raises_440(self) -> None:
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(state_ttl=59)
        assert exc_info.value.code == "EXCEPTION_440"

    def test_ttl_2592001_raises_440(self) -> None:
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(state_ttl=2592001)
        assert exc_info.value.code == "EXCEPTION_440"

    def test_ttl_context_carries_value(self) -> None:
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(state_ttl=10)
        assert exc_info.value.context.get("role") == "ceo"


# ===================================================================
# role 校验
# ===================================================================


class TestRoleValidation:
    """role 必须为 AgentRole 枚举实例。"""

    def test_non_enum_role_raises_440(self) -> None:
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(role="ceo")  # 工厂 **overrides 未注解参数按 Any 透传（VO 校验是测试意图）
        assert exc_info.value.code == "EXCEPTION_440"


# ===================================================================
# Story 5-4 D6 残余回填：default_isolation_level 枚举化 + 标量类型守卫
# ===================================================================


class TestIsolationLevelFieldValidation:
    """default_isolation_level 枚举收紧（D6 isolation 项核销——SSOT 枚举绑定）。

    配置资产类 VO 校验失败统一 440（AgentConfigError 家族——242/440 分界原则）。
    """

    def test_enum_instance_accepted(self) -> None:
        """枚举实例合法构造（SSOT 类型——IsolationLevel 枚举绑定）。"""
        config = _make_config(default_isolation_level=IsolationLevel.L4_HARD)
        assert config.default_isolation_level is IsolationLevel.L4_HARD

    def test_other_valid_level_accepted(self) -> None:
        """其他合法枚举值构造（L3——loader 层不做 MVP 白名单，VO 只认枚举类型）。"""
        config = _make_config(default_isolation_level=IsolationLevel.L3_SOFT)
        assert config.default_isolation_level is IsolationLevel.L3_SOFT

    def test_bare_string_raises_440(self) -> None:
        """裸字符串 "L4" → 440（reason 含 isolation 语义——枚举类型才是 SSOT）。"""
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(default_isolation_level="L4")  # 工厂 **overrides 未注解参数按 Any 透传
        assert exc_info.value.code == "EXCEPTION_440"
        assert "isolation" in exc_info.value.context.get("reason", "")

    def test_non_string_non_enum_raises_440(self) -> None:
        """异构值（整数/None）→ 440。"""
        for raw in (4, None, ["L4"]):
            with pytest.raises(AgentConfigError):
                _make_config(default_isolation_level=raw)

    def test_default_value_is_enum_instance(self) -> None:
        """字段默认值本身是枚举实例（str = "L4" 裸形态核销）。"""
        config = AgentConfig(
            role=AgentRole.CEO,
            name="CEO Agent",
            description="首席执行官 Agent",
            version="1.0.0",
            responsibilities=("战略方向",),
            domain_knowledge=("宏观趋势",),
            preferred_model=None,
        )
        assert isinstance(config.default_isolation_level, IsolationLevel)


class TestScalarFieldTypeGuards:
    """标量字段类型守卫（D6 残余核销锚——原 name=123 裸 AttributeError 逃逸）。

    AgentConfig 全部标量字段（name/description/version）isinstance str 守卫，
    统一 440 分码（配置资产语义——原裸 AttributeError 逃逸是 D6 残余核销锚）。
    """

    @pytest.mark.parametrize("field_name", ["name", "description", "version"])
    def test_int_scalar_raises_440(self, field_name: str) -> None:
        """整数值 → 440（reason 中文自然语言——非 snake_case）。"""
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(**{field_name: 123})
        assert exc_info.value.code == "EXCEPTION_440"
        assert field_name in exc_info.value.context.get("reason", "")

    @pytest.mark.parametrize("field_name", ["name", "description", "version"])
    def test_list_scalar_raises_440(self, field_name: str) -> None:
        """列表值 → 440（防 falsy 判空越过后的下游静默损坏）。"""
        with pytest.raises(AgentConfigError):
            _make_config(**{field_name: ["not", "a", "string"]})

    def test_whitespace_name_still_raises_440_nail(self) -> None:
        """空白串现状钉子（D6「空白串未归一」子项核实为「拦截语义已存在」——
        钉子测试锁定即核销，存储值不做 strip 归一）。"""
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(name="   ")
        assert exc_info.value.code == "EXCEPTION_440"


# ===================================================================
# Story 5-5 追加：allowed_tools 工具白名单字段（eip_config 配置资产）
# ===================================================================


class TestAllowedToolsField:
    """allowed_tools 字段契约（Story 5.5——工具白名单配置载体）。

    默认空元组 = L4 下全部工具被拒的 fail-closed 安全默认（忘配即全拒，
    集成测试红即暴露）；去重归一由 loader 承载（VO 只守卫不归一）。
    """

    def test_default_empty_tuple(self) -> None:
        """默认空元组（fail-closed 安全默认——未配置白名单即全拒）。"""
        config = _make_config()
        assert config.allowed_tools == ()

    def test_valid_list_construction(self) -> None:
        """合法清单构造 + tuple 形态断言（frozen VO 惯例 tuple 形态）。"""
        config = _make_config(allowed_tools=("PESTEL 分析", "SWOT-TOWS"))
        assert config.allowed_tools == ("PESTEL 分析", "SWOT-TOWS")
        assert isinstance(config.allowed_tools, tuple)

    def test_non_string_element_raises_440(self) -> None:
        """元素非 str → 440（配置资产 VO 分码——Any 变量传参规避 mypy 静态
        类型拒绝，运行时守卫行为本身就是要测的；5-4 R1-F03 分界原则沿用）。"""
        bad_value: Any = ("PESTEL 分析", 123)
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(allowed_tools=bad_value)
        assert exc_info.value.code == "EXCEPTION_440"
        assert "allowed_tools" in exc_info.value.context.get("reason", "")

    def test_whitespace_string_element_raises_440(self) -> None:
        """空白串元素 → 440（白名单条目必须是有效工具名——空白即无效）。"""
        with pytest.raises(AgentConfigError) as exc_info:
            _make_config(allowed_tools=("PESTEL 分析", "   "))
        assert exc_info.value.code == "EXCEPTION_440"
        assert "allowed_tools" in exc_info.value.context.get("reason", "")

    def test_empty_tuple_is_valid(self) -> None:
        """空元组合法（显式配置空白名单 = 全拒语义——与默认值同态）。"""
        config = _make_config(allowed_tools=())
        assert config.allowed_tools == ()

    def test_backward_compatible_without_field(self) -> None:
        """既有构造点不带 allowed_tools 零破坏（向后兼容确认——默认空元组）。"""
        config = AgentConfig(
            role=AgentRole.CEO,
            name="CEO Agent",
            description="首席执行官 Agent",
            version="1.0.0",
            responsibilities=("战略方向",),
            domain_knowledge=("宏观趋势",),
            preferred_model=None,
        )
        assert config.allowed_tools == ()
