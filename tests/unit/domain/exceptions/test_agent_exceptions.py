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


# ===================================================================
# Story 5-3 追加：AgentWorkflowError(444) / ChainOfThoughtValidationError(445)
# ===================================================================


class TestAgentWorkflowErrorConstruction:
    """AgentWorkflowError 构造契约（工作流阶段执行失败，继承 SystemException）。"""

    def test_default_message_and_code(self) -> None:
        from src.domain.exceptions import AgentWorkflowError

        error = AgentWorkflowError(
            agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
            phase="verify",
            reason="LLM 阶段调用失败",
        )
        assert error.code == "EXCEPTION_444"
        assert error.message, "默认消息不能为空"

    def test_context_carries_phase_anchor(self) -> None:
        """同码多因区分锚点：phase ∈ {perceive,plan,execute,verify,reflect,package}。"""
        from src.domain.exceptions import AgentWorkflowError

        for phase in ("perceive", "plan", "execute", "verify", "reflect", "package"):
            error = AgentWorkflowError(agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0", phase=phase, reason="失败")
            assert error.context["phase"] == phase
            assert error.context["agent_id"] == "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
            assert error.context["reason"] == "失败"

    def test_inherits_system_exception(self) -> None:
        """444 属系统执行失败语义（LLM 调用失败/图执行异常收敛）。"""
        from src.domain.exceptions import AgentWorkflowError, SystemException

        error = AgentWorkflowError(agent_id="a", phase="plan", reason="r")
        assert isinstance(error, SystemException)
        assert isinstance(error, DomainError)

    def test_to_dict_serialization(self) -> None:
        from src.domain.exceptions import AgentWorkflowError

        error = AgentWorkflowError(agent_id="0f1e2d3c", phase="reflect", reason="反思阶段 LLM 超时")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_444"
        assert data["context"]["phase"] == "reflect"


class TestChainOfThoughtValidationErrorConstruction:
    """ChainOfThoughtValidationError 构造契约（思维链完整性校验失败，继承 SystemException）。"""

    def test_default_message_and_code(self) -> None:
        from src.domain.exceptions import ChainOfThoughtValidationError

        error = ChainOfThoughtValidationError(
            agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
            missing_fields=("reflection", "final_answer"),
        )
        assert error.code == "EXCEPTION_445"
        assert error.message, "默认消息不能为空"

    def test_context_carries_missing_fields(self) -> None:
        """同码多因区分锚点：missing_fields 列表（五字段缺一/空值/结构非法）。"""
        from src.domain.exceptions import ChainOfThoughtValidationError

        error = ChainOfThoughtValidationError(agent_id="0f1e2d3c", missing_fields=("tools_used",))
        assert error.context["missing_fields"] == ["tools_used"]
        assert error.context["agent_id"] == "0f1e2d3c"

    def test_inherits_system_exception(self) -> None:
        from src.domain.exceptions import ChainOfThoughtValidationError, SystemException

        error = ChainOfThoughtValidationError(agent_id="a", missing_fields=())
        assert isinstance(error, SystemException)

    def test_to_dict_serialization(self) -> None:
        from src.domain.exceptions import ChainOfThoughtValidationError

        error = ChainOfThoughtValidationError(agent_id="0f1e2d3c", missing_fields=("input_summary",))
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_445"
        assert data["context"]["missing_fields"] == ["input_summary"]


class TestHttpMappingStory53:
    """经 _get_http_status 反向验证 444/445 精确注册。"""

    def test_workflow_error_maps_500(self) -> None:
        """444 → 500（系统执行失败语义）。"""
        from src.domain.exceptions import AgentWorkflowError
        from src.interfaces.api.exception_handlers import _get_http_status

        error = AgentWorkflowError(agent_id="a", phase="plan", reason="r")
        assert _get_http_status(error) == 500

    def test_chain_validation_error_maps_500(self) -> None:
        """445 → 500（组装后完整性校验失败属系统侧缺陷）。"""
        from src.domain.exceptions import ChainOfThoughtValidationError
        from src.interfaces.api.exception_handlers import _get_http_status

        error = ChainOfThoughtValidationError(agent_id="a", missing_fields=("reflection",))
        assert _get_http_status(error) == 500

    def test_workflow_error_no_isinstance_fallback_to_500_ambiguity(self) -> None:
        """反向验证：444 精确注册（SystemException 基类同为 500，精确注册防回退歧义）。"""
        from src.domain.exceptions import AgentWorkflowError
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert AgentWorkflowError in EXCEPTION_HTTP_MAP
        assert EXCEPTION_HTTP_MAP[AgentWorkflowError] == 500


class TestSubdomainRegistrationStory53:
    """444/445 子域登记（agent 段 440-449 预留段核销）。"""

    def test_classes_registered_in_agent_subdomain(self) -> None:
        assert _CLASS_TO_SUBDOMAIN["AgentWorkflowError"] == "agent"
        assert _CLASS_TO_SUBDOMAIN["ChainOfThoughtValidationError"] == "agent"

    def test_codes_within_agent_range(self) -> None:
        """码值落在 agent 段 (440, 449) 内。"""
        from src.domain.exceptions import AgentWorkflowError, ChainOfThoughtValidationError

        low, high = CODE_RANGES["agent"]
        assert low <= int(AgentWorkflowError.code.removeprefix("EXCEPTION_")) <= high
        assert low <= int(ChainOfThoughtValidationError.code.removeprefix("EXCEPTION_")) <= high

    def test_codes_unique_across_agent_subdomain(self) -> None:
        """444/445 与既有 440-443 码值互异（同码即冲突）。"""
        from src.domain.exceptions import (
            AgentConfigError,
            AgentNotFoundError,
            AgentProfileError,
            AgentRoleNotSupportedError,
            AgentWorkflowError,
            ChainOfThoughtValidationError,
        )

        codes = {
            AgentConfigError.code,
            AgentRoleNotSupportedError.code,
            AgentProfileError.code,
            AgentNotFoundError.code,
            AgentWorkflowError.code,
            ChainOfThoughtValidationError.code,
        }
        assert len(codes) == 6, f"agent 子域六码应互异: {codes}"


# ===================================================================
# Story 5-4 追加：IsolationLevelNotSupportedError(446) / IsolationStateNotInitializedError(447)
# ===================================================================


class TestIsolationLevelNotSupportedErrorConstruction:
    """446 构造契约（隔离等级不合法，继承 BusinessException——「不支持的取值」族）。

    构造器对齐 441 实际形态: level 首参必填、supported_levels 接受 tuple 或 list。
    """

    def test_default_message_and_code(self) -> None:
        from src.domain.exceptions import IsolationLevelNotSupportedError

        error = IsolationLevelNotSupportedError(level="L1", supported_levels=("L4", "L3", "L2"))
        assert error.code == "EXCEPTION_446"
        assert error.message, "默认消息不能为空"

    def test_level_is_required_first_param(self) -> None:
        """level 必填（441 role 同款无默认值——省略即 TypeError；Any 变量调用
        规避 mypy 签名检查——必填缺失本身就是要测的运行时行为）。"""
        from typing import Any

        from src.domain.exceptions import IsolationLevelNotSupportedError

        error_cls: Any = IsolationLevelNotSupportedError
        with pytest.raises(TypeError):
            error_cls()

    def test_context_carries_level_and_supported(self) -> None:
        from src.domain.exceptions import IsolationLevelNotSupportedError

        error = IsolationLevelNotSupportedError(level="L9", supported_levels=("L4", "L3", "L2"))
        assert error.context["level"] == "L9"
        assert error.context["supported_levels"] == ["L4", "L3", "L2"], "context 内 list 化（441 同款）"

    def test_supported_levels_accepts_list_form(self) -> None:
        """supported_levels 接受 tuple 或 list 两形态。"""
        from src.domain.exceptions import IsolationLevelNotSupportedError

        error = IsolationLevelNotSupportedError(level="L1", supported_levels=["L4", "L3", "L2"])
        assert error.context["supported_levels"] == ["L4", "L3", "L2"]

    def test_inherits_business_exception(self) -> None:
        """446 入 BusinessException（运行时用户错误族——422 语义）。"""
        from src.domain.exceptions import BusinessException, IsolationLevelNotSupportedError

        error = IsolationLevelNotSupportedError(level="L1")
        assert isinstance(error, BusinessException)

    @pytest.mark.parametrize(
        ("level", "supported"),
        [("L9", ("L4", "L3", "L2")), ("L1", ("L4", "L3", "L2"))],
        ids=["非法枚举值字符串", "合法枚举但MVP禁用"],
    )
    def test_dual_trigger_paths(self, level: str, supported: tuple[str, ...]) -> None:
        """446 双触发路径参数化: 非法枚举值字符串 + 合法枚举但 MVP 禁用（L1 融合态）。"""
        from src.domain.exceptions import IsolationLevelNotSupportedError

        error = IsolationLevelNotSupportedError(level=level, supported_levels=supported)
        assert error.code == "EXCEPTION_446"
        assert error.context["level"] == level


class TestIsolationStateNotInitializedErrorConstruction:
    """447 构造契约（隔离状态缺失，继承 BusinessException——404 NotFound 族语义）。"""

    def test_default_message_and_code(self) -> None:
        from src.domain.exceptions import IsolationStateNotInitializedError

        error = IsolationStateNotInitializedError(agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
        assert error.code == "EXCEPTION_447"
        assert error.message, "默认消息不能为空"

    def test_context_carries_agent_id(self) -> None:
        from src.domain.exceptions import IsolationStateNotInitializedError

        agent_id = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
        error = IsolationStateNotInitializedError(agent_id=agent_id)
        assert error.context["agent_id"] == agent_id

    def test_agent_id_optional_default_empty(self) -> None:
        """agent_id 可默认空串（兜底形态——上下文仍含键）。"""
        from src.domain.exceptions import IsolationStateNotInitializedError

        error = IsolationStateNotInitializedError()
        assert error.context["agent_id"] == ""

    def test_inherits_business_exception(self) -> None:
        """447 入 BusinessException（资源不存在——对齐 443 族语义）。"""
        from src.domain.exceptions import BusinessException, IsolationStateNotInitializedError

        error = IsolationStateNotInitializedError(agent_id="x")
        assert isinstance(error, BusinessException)

    def test_to_dict_contains_code(self) -> None:
        """to_dict 含编码（CLI stderr 断言锚）。"""
        from src.domain.exceptions import IsolationStateNotInitializedError

        error = IsolationStateNotInitializedError(agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_447"
        assert data["context"]["agent_id"] == "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"


class TestHttpMappingStory54:
    """经 _get_http_status 反向验证 446/447 精确注册。"""

    def test_level_not_supported_maps_422(self) -> None:
        """446 → 422（「不支持的取值」族——对齐 441 精确注册先例）。"""
        from src.domain.exceptions import IsolationLevelNotSupportedError
        from src.interfaces.api.exception_handlers import _get_http_status

        error = IsolationLevelNotSupportedError(level="L1", supported_levels=("L4", "L3", "L2"))
        assert _get_http_status(error) == 422

    def test_state_not_initialized_maps_404(self) -> None:
        """447 → 404（状态缺失 NotFound 族——对齐 443 语义）。"""
        from src.domain.exceptions import IsolationStateNotInitializedError
        from src.interfaces.api.exception_handlers import _get_http_status

        error = IsolationStateNotInitializedError(agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
        assert _get_http_status(error) == 404

    def test_precise_registration_no_fallback(self) -> None:
        """反向验证: BusinessException 基类 400，446/447 精确注册防回退歧义。"""
        from src.domain.exceptions import IsolationLevelNotSupportedError, IsolationStateNotInitializedError
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[IsolationLevelNotSupportedError] == 422
        assert EXCEPTION_HTTP_MAP[IsolationStateNotInitializedError] == 404


class TestSubdomainRegistrationStory54:
    """446/447 子域登记（agent 段预留位核销——448-449 留给 5.5）。"""

    def test_classes_registered_in_agent_subdomain(self) -> None:
        assert _CLASS_TO_SUBDOMAIN["IsolationLevelNotSupportedError"] == "agent"
        assert _CLASS_TO_SUBDOMAIN["IsolationStateNotInitializedError"] == "agent"

    def test_codes_within_agent_range(self) -> None:
        from src.domain.exceptions import IsolationLevelNotSupportedError, IsolationStateNotInitializedError

        low, high = CODE_RANGES["agent"]
        assert low <= int(IsolationLevelNotSupportedError.code.removeprefix("EXCEPTION_")) <= high
        assert low <= int(IsolationStateNotInitializedError.code.removeprefix("EXCEPTION_")) <= high

    def test_codes_unique_across_agent_subdomain(self) -> None:
        """446/447 与既有 440-445 码值互异（八码全查重）。"""
        from src.domain.exceptions import (
            AgentConfigError,
            AgentNotFoundError,
            AgentProfileError,
            AgentRoleNotSupportedError,
            AgentWorkflowError,
            ChainOfThoughtValidationError,
            IsolationLevelNotSupportedError,
            IsolationStateNotInitializedError,
        )

        codes = {
            AgentConfigError.code,
            AgentRoleNotSupportedError.code,
            AgentProfileError.code,
            AgentNotFoundError.code,
            AgentWorkflowError.code,
            ChainOfThoughtValidationError.code,
            IsolationLevelNotSupportedError.code,
            IsolationStateNotInitializedError.code,
        }
        assert len(codes) == 8, f"agent 子域八码应互异: {codes}"


# ===================================================================
# Story 5-5 追加：IsolationAccessViolationError(448) / IsolationOperationForbiddenError(449)
# ===================================================================


class TestIsolationAccessViolationErrorConstruction:
    """448 构造契约（跨 Agent 私有资源访问越权，继承 BusinessException——403 Forbidden 族）。

    构造器对齐 446/441 首参必填形态: actor_agent_id 必填; context 携带五字段
    （actor/target/resource/operation/reason——reason 承载判定依据含等级名，
    并发串扰判别与三段式断言的结构化通道）。
    """

    def test_default_message_and_code(self) -> None:
        from src.domain.exceptions import IsolationAccessViolationError

        error = IsolationAccessViolationError(
            actor_agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
            target_agent_id="1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
            resource="profile",
            operation="read",
            reason="跨 Agent 私有资源访问被拒（硬隔离）",
        )
        assert error.code == "EXCEPTION_448"
        assert error.message, "默认消息不能为空"
        assert "隔离" in error.message, "消息面向调用方可理解（禁泄露资源内容/内部键名）"

    def test_actor_agent_id_is_required_first_param(self) -> None:
        """actor_agent_id 必填（446/441 同款无默认值——省略即 TypeError；Any
        变量调用规避 mypy 签名检查——必填缺失本身就是要测的运行时行为）。"""
        from typing import Any

        from src.domain.exceptions import IsolationAccessViolationError

        error_cls: Any = IsolationAccessViolationError
        with pytest.raises(TypeError):
            error_cls()

    def test_context_carries_five_fields(self) -> None:
        """context 五字段逐项（actor/target/resource/operation/reason——
        reason 含等级名是并发串扰判别锚）。"""
        from src.domain.exceptions import IsolationAccessViolationError

        actor = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
        target = "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d"
        reason = "跨 Agent 私有资源访问被拒（软隔离）"
        error = IsolationAccessViolationError(
            actor_agent_id=actor, target_agent_id=target, resource="session", operation="write", reason=reason
        )
        assert set(error.context) == {"actor_agent_id", "target_agent_id", "resource", "operation", "reason"}
        assert error.context["actor_agent_id"] == actor
        assert error.context["target_agent_id"] == target
        assert error.context["resource"] == "session"
        assert error.context["operation"] == "write"
        assert error.context["reason"] == reason
        assert "软隔离" in error.context["reason"], "reason 须含等级名（串扰判别锚）"

    def test_inherits_business_exception(self) -> None:
        """448 入 BusinessException（跨主体越权——403 权限不足族语义）。"""
        from src.domain.exceptions import BusinessException, IsolationAccessViolationError

        error = IsolationAccessViolationError(
            actor_agent_id="a", target_agent_id="b", resource="memory", operation="read", reason="判定依据"
        )
        assert isinstance(error, BusinessException)

    def test_to_dict_contains_code_and_context(self) -> None:
        """to_dict 含编码与五字段 context（CLI stderr 断言锚）。"""
        from src.domain.exceptions import IsolationAccessViolationError

        error = IsolationAccessViolationError(
            actor_agent_id="a", target_agent_id="b", resource="profile", operation="read", reason="判定依据"
        )
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_448"
        assert data["context"]["actor_agent_id"] == "a"
        assert data["context"]["resource"] == "profile"


class TestIsolationOperationForbiddenErrorConstruction:
    """449 构造契约（当前隔离等级策略禁止的操作，继承 BusinessException——403 族）。

    与 448 分界: 448 = 跨主体越权（actor≠target 私有资源）; 449 = 单主体操作被
    自身等级策略禁止（白名单外工具 / READ_ONLY·RESTRICTED_WRITE 共享面写）——
    两语义轴正交。reason 双形态: tool_not_in_allowlist:{name} / data_isolation:{mode}。
    """

    def test_default_message_and_code(self) -> None:
        from src.domain.exceptions import IsolationOperationForbiddenError

        error = IsolationOperationForbiddenError(agent_id="0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0", operation="execute")
        assert error.code == "EXCEPTION_449"
        assert error.message, "默认消息不能为空"

    def test_agent_id_is_required_first_param(self) -> None:
        """agent_id 必填（448/446/441 同款无默认值——省略即 TypeError）。"""
        from typing import Any

        from src.domain.exceptions import IsolationOperationForbiddenError

        error_cls: Any = IsolationOperationForbiddenError
        with pytest.raises(TypeError):
            error_cls()

    def test_context_carries_three_fields(self) -> None:
        """context 三字段（agent_id/operation/reason——最小化，白名单明细不进）。"""
        from src.domain.exceptions import IsolationOperationForbiddenError

        error = IsolationOperationForbiddenError(
            agent_id="agent-1", operation="execute", reason="tool_not_in_allowlist:幻觉工具"
        )
        assert set(error.context) == {"agent_id", "operation", "reason"}
        assert error.context["agent_id"] == "agent-1"
        assert error.context["operation"] == "execute"
        assert error.context["reason"] == "tool_not_in_allowlist:幻觉工具"

    @pytest.mark.parametrize(
        ("operation", "reason"),
        [
            ("execute", "tool_not_in_allowlist:GE-麦肯锡矩阵"),
            ("write", "data_isolation:read_only"),
        ],
        ids=["工具白名单外", "共享面只读写"],
    )
    def test_dual_trigger_paths(self, operation: str, reason: str) -> None:
        """449 双触发路径参数化: L4 白名单外工具 + READ_ONLY 等级共享面写
        （同码多因经 context reason 区分——446 双路径先例）。"""
        from src.domain.exceptions import IsolationOperationForbiddenError

        error = IsolationOperationForbiddenError(agent_id="agent-1", operation=operation, reason=reason)
        assert error.code == "EXCEPTION_449"
        assert error.context["reason"] == reason

    def test_inherits_business_exception(self) -> None:
        """449 入 BusinessException（操作被策略禁止——403 族语义）。"""
        from src.domain.exceptions import BusinessException, IsolationOperationForbiddenError

        error = IsolationOperationForbiddenError(agent_id="a", operation="write", reason="data_isolation:read_only")
        assert isinstance(error, BusinessException)

    def test_to_dict_contains_code(self) -> None:
        """to_dict 含编码（CLI stderr 断言锚）。"""
        from src.domain.exceptions import IsolationOperationForbiddenError

        error = IsolationOperationForbiddenError(agent_id="a", operation="execute", reason="r")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_449"
        assert data["context"]["agent_id"] == "a"


class TestHttpMappingStory55:
    """经 _get_http_status 反向验证 448/449 精确注册（403 权限不足族）。"""

    def test_access_violation_maps_403(self) -> None:
        """448 → 403（Forbidden——跨主体越权标准码）。"""
        from src.domain.exceptions import IsolationAccessViolationError
        from src.interfaces.api.exception_handlers import _get_http_status

        error = IsolationAccessViolationError(
            actor_agent_id="a", target_agent_id="b", resource="profile", operation="read", reason="r"
        )
        assert _get_http_status(error) == 403

    def test_operation_forbidden_maps_403(self) -> None:
        """449 → 403（Forbidden——操作被策略禁止）。"""
        from src.domain.exceptions import IsolationOperationForbiddenError
        from src.interfaces.api.exception_handlers import _get_http_status

        error = IsolationOperationForbiddenError(agent_id="a", operation="execute", reason="r")
        assert _get_http_status(error) == 403

    def test_precise_registration_no_fallback(self) -> None:
        """反向验证: EXCEPTION_HTTP_MAP 精确注册 448/449 → 403。"""
        from src.domain.exceptions import IsolationAccessViolationError, IsolationOperationForbiddenError
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[IsolationAccessViolationError] == 403
        assert EXCEPTION_HTTP_MAP[IsolationOperationForbiddenError] == 403


class TestSubdomainRegistrationStory55:
    """448/449 子域登记（agent 段预留位核销——440-449 至此全分配）。"""

    def test_classes_registered_in_agent_subdomain(self) -> None:
        assert _CLASS_TO_SUBDOMAIN["IsolationAccessViolationError"] == "agent"
        assert _CLASS_TO_SUBDOMAIN["IsolationOperationForbiddenError"] == "agent"

    def test_codes_within_agent_range(self) -> None:
        from src.domain.exceptions import IsolationAccessViolationError, IsolationOperationForbiddenError

        low, high = CODE_RANGES["agent"]
        assert low <= int(IsolationAccessViolationError.code.removeprefix("EXCEPTION_")) <= high
        assert low <= int(IsolationOperationForbiddenError.code.removeprefix("EXCEPTION_")) <= high

    def test_codes_unique_across_agent_subdomain_ten(self) -> None:
        """448/449 与既有 440-447 码值互异（十码全查重——agent 段全分配终态）。"""
        from src.domain.exceptions import (
            AgentConfigError,
            AgentNotFoundError,
            AgentProfileError,
            AgentRoleNotSupportedError,
            AgentWorkflowError,
            ChainOfThoughtValidationError,
            IsolationAccessViolationError,
            IsolationLevelNotSupportedError,
            IsolationOperationForbiddenError,
            IsolationStateNotInitializedError,
        )

        codes = {
            AgentConfigError.code,
            AgentRoleNotSupportedError.code,
            AgentProfileError.code,
            AgentNotFoundError.code,
            AgentWorkflowError.code,
            ChainOfThoughtValidationError.code,
            IsolationLevelNotSupportedError.code,
            IsolationStateNotInitializedError.code,
            IsolationAccessViolationError.code,
            IsolationOperationForbiddenError.code,
        }
        assert len(codes) == 10, f"agent 子域十码应互异: {codes}"
