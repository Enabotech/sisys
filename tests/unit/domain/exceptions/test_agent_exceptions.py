"""agent 子域异常单元测试（Story 5-1 + Story 5-2 追加）

覆盖 AgentConfigError(EXCEPTION_440)/AgentRoleNotSupportedError(EXCEPTION_441)（5-1）：
- 构造与 context 领域上下文暴露（role/config_path/reason 与 role/supported_roles）
- to_dict 序列化契约
- HTTP 映射反向验证（440→500 配置资产属系统资源 / 441→422 业务能力范围规则，
  经 exception_handlers._get_http_status 精确注册验证——先例 test_debate_exceptions.py L188：
  441 未注册将回退基类 BusinessException→400，精确注册断言防回退）
- 子域登记（CODE_RANGES agent 440-449 + _CLASS_TO_SUBDOMAIN 双表）

Story 5-2 追加 AgentProfileError(EXCEPTION_442)/AgentNotFoundError(EXCEPTION_443)：
- 442 档案资产缺陷（目录缺失/文件缺失/不可读/编码非法/空白/超限/VO 字段类型非法）
- 443 请求资源不存在（get_by_id 返回 None——键不存在或 TTL 过期后重放旧 agent_id）

Run with:
    poetry run pytest tests/unit/domain/exceptions/test_agent_exceptions.py -v
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import (
    AgentConfigError,
    AgentNotFoundError,
    AgentProfileError,
    AgentRoleNotSupportedError,
    DomainError,
)
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
        "error_class", [AgentConfigError, AgentRoleNotSupportedError, AgentProfileError, AgentNotFoundError]
    )
    def test_class_registered_in_subdomain(self, error_class: type[DomainError]) -> None:
        """类实际 code 必须落在 agent 子域物理段内（锚定类 code 属性真源，防参数字面量恒真）。"""
        assert _CLASS_TO_SUBDOMAIN[error_class.__name__] == "agent"
        code_num = int(error_class.code.removeprefix("EXCEPTION_"))
        low, high = CODE_RANGES["agent"]
        assert low <= code_num <= high

    def test_codes_match_contract(self) -> None:
        assert AgentConfigError.code == "EXCEPTION_440"
        assert AgentRoleNotSupportedError.code == "EXCEPTION_441"
        assert AgentProfileError.code == "EXCEPTION_442"
        assert AgentNotFoundError.code == "EXCEPTION_443"

    def test_inheritance_chain(self) -> None:
        """440 入 SystemException（系统配置资产缺陷）、441 入 BusinessException（业务规则限制）。"""
        from src.domain.exceptions import BusinessException, SystemException

        assert issubclass(AgentConfigError, SystemException)
        assert issubclass(AgentRoleNotSupportedError, BusinessException)

    def test_inheritance_chain_story_5_2(self) -> None:
        """442 入 SystemException（档案资产缺陷与 440 同族）、443 入 BusinessException（资源不存在）。"""
        from src.domain.exceptions import BusinessException, SystemException

        assert issubclass(AgentProfileError, SystemException)
        assert issubclass(AgentNotFoundError, BusinessException)


# ===================================================================
# AgentProfileError 构造（Story 5-2 — 档案资产缺陷，442）
# ===================================================================


class TestAgentProfileErrorConstruction:
    """AgentProfileError 构造契约（档案资产属系统资源，继承 SystemException——与 440 同族分码监控）。"""

    def test_default_message_and_code(self) -> None:
        error = AgentProfileError(role="ceo", profile_path="configs/agents/profiles/ceo/IDENTITY.md", reason="档案文件缺失")
        assert error.code == "EXCEPTION_442"
        assert error.message, "默认消息不能为空"

    def test_context_carries_domain_fields(self) -> None:
        error = AgentProfileError(role="ceo", profile_path="configs/agents/profiles/ceo/SOUL.md", reason="内容纯空白")
        assert error.context["role"] == "ceo"
        assert error.context["profile_path"] == "configs/agents/profiles/ceo/SOUL.md"
        assert error.context["reason"] == "内容纯空白"

    def test_optional_fields_default_to_empty(self) -> None:
        error = AgentProfileError(reason="档案目录缺失")
        assert error.context["role"] == ""
        assert error.context["profile_path"] == ""
        assert error.context["reason"] == "档案目录缺失"

    def test_custom_message_overrides_default(self) -> None:
        error = AgentProfileError(role="ceo", message="自定义档案错误消息")
        assert error.message == "自定义档案错误消息"

    def test_cause_chaining(self) -> None:
        original = OSError("disk unreachable")
        error = AgentProfileError(role="ceo", reason="档案不可读", cause=original)
        assert error.cause is original

    def test_default_message_static_no_dynamic_leak(self) -> None:
        """消息安全性：默认消息不含动态路径/全文（不泄露内部细节与绝对路径）。"""
        error = AgentProfileError(role="ceo", profile_path="/abs/secret/path/IDENTITY.md", reason="x" * 500)
        assert "/abs/secret" not in error.message
        assert error.message == AgentProfileError.message


# ===================================================================
# AgentNotFoundError 构造（Story 5-2 — 请求资源不存在，443）
# ===================================================================


class TestAgentNotFoundErrorConstruction:
    """AgentNotFoundError 构造契约（agent_id 无法定位资源，继承 BusinessException——404 语义）。"""

    def test_default_message_and_code(self) -> None:
        error = AgentNotFoundError(agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
        assert error.code == "EXCEPTION_443"
        assert error.message, "默认消息不能为空"

    def test_context_carries_agent_id(self) -> None:
        agent_id = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
        error = AgentNotFoundError(agent_id=agent_id)
        assert error.context["agent_id"] == agent_id

    def test_custom_message(self) -> None:
        error = AgentNotFoundError(agent_id="x" * 36, message="TTL 过期后重放旧 agent_id")
        assert error.message == "TTL 过期后重放旧 agent_id"


# ===================================================================
# 442/443 to_dict 与 HTTP 映射（Story 5-2 追加）
# ===================================================================


class TestToDictStory52:
    """442/443 to_dict 输出 code/message/context 三键。"""

    def test_agent_profile_error_to_dict(self) -> None:
        error = AgentProfileError(role="ceo", reason="档案文件缺失")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_442"
        assert data["message"] == error.message
        assert data["context"]["role"] == "ceo"

    def test_agent_not_found_to_dict(self) -> None:
        error = AgentNotFoundError(agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_443"
        assert data["context"]["agent_id"] == "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"


class TestHttpMappingStory52:
    """经 _get_http_status 反向验证 442/443 精确注册。"""

    def test_profile_error_maps_500(self) -> None:
        """442 → 500（档案资产属系统资源，部署缺陷——对齐 440 同族语义）。"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = AgentProfileError(role="ceo", reason="档案文件缺失")
        assert _get_http_status(error) == 500

    def test_agent_not_found_maps_404(self) -> None:
        """443 → 404（请求资源不存在语义）。"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = AgentNotFoundError(agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
        assert _get_http_status(error) == 404

    def test_agent_not_found_no_isinstance_fallback_to_400(self) -> None:
        """反向验证：BusinessException 基类映射 400，但 443 精确注册为 404（不回退）。"""
        from src.domain.exceptions import BusinessException
        from src.interfaces.api.exception_handlers import _get_http_status

        error = AgentNotFoundError(agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
        assert isinstance(error, BusinessException)
        assert _get_http_status(error) == 404  # 若无精确注册，isinstance 扫描会得到 400
