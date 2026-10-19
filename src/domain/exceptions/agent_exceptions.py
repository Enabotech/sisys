"""领域层 Agent 子域异常模块（Story 5-1 — CEO Agent 实例化 MVP；Story 5-2 追加档案加载异常）

异常编码范围：EXCEPTION_440 ~ EXCEPTION_449（预留 10 个码，遵循
data_source(410-419)/debate(420-429)/tool_version(430-439) 独立物理段先例）。

设计理由（继承链选择）：
- AgentConfigError(440) 继承 SystemException —— 根因是系统配置资产缺陷
  （部署错误，非调用方输入错误），与 ConfigurationError(101) 同语义族；
  HTTP 映射 500（精确注册，避免回退歧义）。
- AgentRoleNotSupportedError(441) 继承 BusinessException —— MVP 阶段性
  业务能力范围规则限制（仅 CEO 开放），与 DebateLowDivergenceError(422)
  同语义族；HTTP 映射 422。
- 两者无法共享子域基类（分属 System/Business 两大抽象分层——项目规范必须
  继承三大抽象分层之一，relevance/debate 平铺无基类先例支持），故不设
  AgentError 子域基类，两类平铺。
- AgentProfileError(442) 继承 SystemException（Story 5-2）—— 根因是档案
  资产缺陷（目录缺失/文件缺失/不可读/编码非法/内容空白/超大小上限/VO 字段
  类型非法），档案资产属系统资源（部署/资产错误非调用方输入错误），与 440
  同族语义分码监控；HTTP 映射 500。
- AgentNotFoundError(443) 继承 BusinessException（Story 5-2）—— 请求方提供的
  agent_id 无法定位资源（get_by_id 返回 None，键不存在或 TTL 过期后重放旧
  agent_id），请求资源不存在语义；HTTP 映射 404。
- 442/443 延续 5-1「不设 AgentError 子域基类、平铺双分层」决策。

消息安全性：
- 默认消息为静态文案，不含 YAML 全文/绝对路径/堆栈等内部细节；
- context 仅携带结构化领域上下文（role/config_path/reason/supported_roles），
  调用方传入的 config_path 应为相对路径或文件名（调用方责任）；
- 442 的 profile_path 同样应为相对路径或文件名（档案资产缺陷定位锚点）。
"""

from __future__ import annotations

from typing import Any

from src.domain.exceptions.business_exceptions import BusinessException
from src.domain.exceptions.system_exceptions import SystemException


class AgentConfigError(SystemException):
    """Agent 配置资产无效

    触发场景：配置文件缺失 / YAML 解析失败 / 必填字段无效（空列表、非列表标量、
    state_ttl 越界或非整数）/ identity.role 与请求角色不匹配。
    配置资产属系统资源（部署错误，非调用方输入错误），故入 SystemException。

    Attributes:
        code: EXCEPTION_440
        message: 默认消息（静态文案，不含动态内部细节）
        context: 领域上下文（role/config_path/reason）
    """

    code = "EXCEPTION_440"
    message = "Agent 配置资产无效"

    def __init__(
        self,
        role: str = "",
        config_path: str = "",
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化 Agent 配置异常

        Args:
            role: 请求的 Agent 角色（字符串值，如 "ceo"；无法确定时为空串）
            config_path: 配置文件路径（建议相对路径或文件名，不泄露绝对路径）
            reason: 面向调用方可理解的失败原因摘要
            message: 覆盖默认消息（可选）
            cause: 原始异常（可选，用于异常链）
        """
        context: dict[str, str] = {
            "role": role,
            "config_path": config_path,
            "reason": reason,
        }
        super().__init__(message=message, cause=cause, context=context)


class AgentRoleNotSupportedError(BusinessException):
    """请求实例化的 Agent 角色在当前阶段未开放

    触发场景：MVP 阶段仅 CEO 开放，请求 CFO/CMO/CTO/COO/CHO/AUD/SYS
    角色实例化时抛出（业务能力范围规则限制，属阶段性限制而非输入格式错误）。

    Attributes:
        code: EXCEPTION_441
        message: 默认消息
        context: 领域上下文（role + supported_roles 当前开放角色清单）
    """

    code = "EXCEPTION_441"
    message = "Agent 角色在当前阶段未开放"

    def __init__(
        self,
        role: str,
        supported_roles: tuple[str, ...] | list[str] = (),
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化角色未开放异常

        Args:
            role: 请求的角色原始输入（字符串值或原始输入字符串）
            supported_roles: 当前开放角色清单（从用例模块级常量 SUPPORTED_ROLES
                派生，勿硬编码字面量列表——V1 扩展时仅改常量一处）
            message: 覆盖默认消息（可选）
            cause: 原始异常（可选，用于异常链）
        """
        context: dict[str, Any] = {
            "role": role,
            "supported_roles": list(supported_roles),
        }
        super().__init__(message=message, cause=cause, context=context)


class AgentProfileError(SystemException):
    """Agent 身份档案资产无效（Story 5-2 — Agent 身份档案加载）

    触发场景：档案目录缺失 / 档案文件缺失 / 文件不可读（OSError 家族）/
    编码非法（非 UTF-8）/ 内容纯空白 / 单文件超 64KB 上限 / VO 字段类型非法
    （六档案非 str）。档案资产属系统资源（部署/资产错误非调用方输入错误），
    与 440「配置资产缺陷」同族语义分码监控。

    Attributes:
        code: EXCEPTION_442
        message: 默认消息（静态文案，不含动态内部细节）
        context: 领域上下文（role/profile_path/reason——profile_path 为相对
            路径形态，不泄露绝对路径；DC-5 判空主检在加载器，其 context
            携带文件名即观测锚点）
    """

    code = "EXCEPTION_442"
    message = "Agent 身份档案资产无效"

    def __init__(
        self,
        role: str = "",
        profile_path: str = "",
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化 Agent 档案异常

        Args:
            role: 请求的 Agent 角色（字符串值，如 "ceo"；无法确定时为空串）
            profile_path: 档案文件路径（相对路径或文件名形态，不泄露绝对路径）
            reason: 面向调用方可理解的失败原因摘要（同码多因区分锚点：
                目录缺失/文件缺失/不可读/编码非法/内容空白/超大小上限）
            message: 覆盖默认消息（可选）
            cause: 原始异常（可选，用于异常链）
        """
        context: dict[str, str] = {
            "role": role,
            "profile_path": profile_path,
            "reason": reason,
        }
        super().__init__(message=message, cause=cause, context=context)


class AgentNotFoundError(BusinessException):
    """请求的 Agent 实例不存在（Story 5-2 — Agent 身份档案加载）

    触发场景：get_by_id(agent_id) 返回 None（Redis 键不存在或 TTL 过期后
    重放旧 agent_id）——请求方提供的 agent_id 无法定位资源，业务查询未命中
    语义（请求资源不存在，非系统缺陷）。

    Attributes:
        code: EXCEPTION_443
        message: 默认消息
        context: 领域上下文（agent_id——raise 侧传 str(agent_id) 字符串形态，
            对齐 5-1 role=role.value 先例）
    """

    code = "EXCEPTION_443"
    message = "请求的 Agent 实例不存在"

    def __init__(
        self,
        agent_id: str,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化 Agent 不存在异常

        Args:
            agent_id: 查询未命中的 Agent 标识（字符串形态）
            message: 覆盖默认消息（可选）
            cause: 原始异常（可选，用于异常链）
        """
        context: dict[str, str] = {
            "agent_id": agent_id,
        }
        super().__init__(message=message, cause=cause, context=context)


__all__ = [
    "AgentConfigError",
    "AgentNotFoundError",
    "AgentProfileError",
    "AgentRoleNotSupportedError",
]
