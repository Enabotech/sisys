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

import pytest

from src.domain.entities.agent import AgentRole
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
        assert config.default_isolation_level == "L4"

    def test_frozen_immutable(self) -> None:
        config = _make_config()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.name = "mutated"  # type: ignore[misc]

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
        不校验非空，VO falsy 判空是唯一防线。"""
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
            _make_config(role="ceo")  # type: ignore[arg-type]
        assert exc_info.value.code == "EXCEPTION_440"
