"""agent 子域异常单元测试（Story 5-1）

覆盖 AgentConfigError(EXCEPTION_440)/AgentRoleNotSupportedError(EXCEPTION_441)：
- 构造与 context 领域上下文暴露（role/config_path/reason 与 role/supported_roles）
- to_dict 序列化契约
- HTTP 映射反向验证（440→500 配置资产属系统资源 / 441→422 业务能力范围规则，
  经 exception_handlers._get_http_status 精确注册验证——先例 test_debate_exceptions.py L188：
  441 未注册将回退基类 BusinessException→400，精确注册断言防回退）
- 子域登记（CODE_RANGES agent 440-449 + _CLASS_TO_SUBDOMAIN 双表）

Run with:
    poetry run pytest tests/unit/domain/exceptions/test_agent_exceptions.py -v
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import AgentConfigError, AgentRoleNotSupportedError
from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN, CODE_RANGES

# ===================================================================
# 构造与 context 暴露
# ===================================================================


class TestAgentConfigErrorConstruction:
    """AgentConfigError 构造契约（配置资产属系统资源，继承 SystemException）。"""

    def test_default_message_and_code(self) -> None:
        error = AgentConfigError(role="ceo", config_path="configs/agents/ceo_agent.yaml", reason="文件缺失")
        assert error.code == "EXCEPTION_440"
        assert error.message, "默认消息不能为空"

    def test_context_carries_domain_fields(self) -> None:
        error = AgentConfigError(role="ceo", config_path="configs/agents/ceo_agent.yaml", reason="YAML 解析失败")
        assert error.context["role"] == "ceo"
        assert error.context["config_path"] == "configs/agents/ceo_agent.yaml"
        assert error.context["reason"] == "YAML 解析失败"

    def test_optional_fields_default_to_empty(self) -> None:
        error = AgentConfigError(reason="state_ttl 越界")
        assert error.context["role"] == ""
        assert error.context["config_path"] == ""
        assert error.context["reason"] == "state_ttl 越界"

    def test_custom_message_overrides_default(self) -> None:
        error = AgentConfigError(role="ceo", message="自定义配置错误消息")
        assert error.message == "自定义配置错误消息"

    def test_cause_chaining(self) -> None:
        original = ValueError("yaml scanner error")
        error = AgentConfigError(role="ceo", reason="解析失败", cause=original)
        assert error.cause is original

    def test_default_message_static_no_dynamic_leak(self) -> None:
        """消息安全性：默认消息不含动态路径/全文（不泄露内部细节）。"""
        error = AgentConfigError(role="ceo", config_path="/abs/secret/path/ceo_agent.yaml", reason="x" * 500)
        assert "/abs/secret" not in error.message
        assert error.message == AgentConfigError.message


# ===================================================================
# AgentRoleNotSupportedError 构造
# ===================================================================


class TestAgentRoleNotSupportedErrorConstruction:
    """AgentRoleNotSupportedError 构造契约（MVP 阶段性业务规则，继承 BusinessException）。"""

    def test_default_message_and_code(self) -> None:
        error = AgentRoleNotSupportedError(role="cfo", supported_roles=("ceo",))
        assert error.code == "EXCEPTION_441"
        assert error.message, "默认消息不能为空"

    def test_context_carries_role_and_supported_roles(self) -> None:
        error = AgentRoleNotSupportedError(role="cfo", supported_roles=("ceo",))
        assert error.context["role"] == "cfo"
        assert error.context["supported_roles"] == ["ceo"]

    def test_supported_roles_accepts_list(self) -> None:
        error = AgentRoleNotSupportedError(role="sys", supported_roles=["ceo"])
        assert error.context["supported_roles"] == ["ceo"]

    def test_custom_message(self) -> None:
        error = AgentRoleNotSupportedError(role="cfo", supported_roles=("ceo",), message="CFO 将在 V1 开放")
        assert error.message == "CFO 将在 V1 开放"


# ===================================================================
# to_dict 序列化契约
# ===================================================================


class TestToDict:
    """to_dict 输出 code/message/context 三键（调用方可理解的脱敏结构）。"""

    def test_agent_config_error_to_dict(self) -> None:
        error = AgentConfigError(role="ceo", reason="文件缺失")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_440"
        assert data["message"] == error.message
        assert data["context"]["role"] == "ceo"

    def test_agent_role_not_supported_to_dict(self) -> None:
        error = AgentRoleNotSupportedError(role="cfo", supported_roles=("ceo",))
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_441"
        assert data["context"]["supported_roles"] == ["ceo"]


# ===================================================================
# HTTP 映射反向验证（EXCEPTION_HTTP_MAP 精确注册，避免 isinstance 回退）
# ===================================================================


class TestHttpMapping:
    """经 _get_http_status 反向验证 EXCEPTION_HTTP_MAP 精确注册。"""

    def test_config_error_maps_500(self) -> None:
        """440 → 500（配置资产属系统资源，部署错误——精确注册避免歧义）。"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = AgentConfigError(role="ceo", reason="文件缺失")
        assert _get_http_status(error) == 500

    def test_role_not_supported_maps_422(self) -> None:
        """441 → 422（业务能力范围规则违反——对齐 DebateLowDivergenceError(422) 先例）。"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = AgentRoleNotSupportedError(role="cfo", supported_roles=("ceo",))
        assert _get_http_status(error) == 422

    def test_role_not_supported_no_isinstance_fallback_to_400(self) -> None:
        """反向验证：BusinessException 基类映射 400，但 441 精确注册为 422（不回退）。"""
        from src.domain.exceptions import BusinessException
        from src.interfaces.api.exception_handlers import _get_http_status

        error = AgentRoleNotSupportedError(role="cfo", supported_roles=("ceo",))
        assert isinstance(error, BusinessException)
        assert _get_http_status(error) == 422  # 若无精确注册，isinstance 扫描会得到 400


# ===================================================================
# 子域登记（CODE_RANGES + _CLASS_TO_SUBDOMAIN 双表）
# ===================================================================


class TestSubdomainRegistration:
    """agent 子域 440-449 物理段独立登记（遵循 data_source/debate/tool_version 先例）。"""

    def test_code_ranges_contains_agent_segment(self) -> None:
        assert CODE_RANGES["agent"] == (440, 449)

    @pytest.mark.parametrize(
        ("class_name", "expected_code_num"),
        [("AgentConfigError", 440), ("AgentRoleNotSupportedError", 441)],
    )
    def test_class_registered_in_subdomain(self, class_name: str, expected_code_num: int) -> None:
        assert _CLASS_TO_SUBDOMAIN[class_name] == "agent"
        code_num = int(expected_code_num)
        low, high = CODE_RANGES["agent"]
        assert low <= code_num <= high

    def test_codes_match_contract(self) -> None:
        assert AgentConfigError.code == "EXCEPTION_440"
        assert AgentRoleNotSupportedError.code == "EXCEPTION_441"

    def test_inheritance_chain(self) -> None:
        """440 入 SystemException（系统配置资产缺陷）、441 入 BusinessException（业务规则限制）。"""
        from src.domain.exceptions import BusinessException, SystemException

        assert issubclass(AgentConfigError, SystemException)
        assert issubclass(AgentRoleNotSupportedError, BusinessException)
