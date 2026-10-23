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


class AgentWorkflowError(SystemException):
    """单 Agent 工作流阶段执行失败（Story 5-3 — 单 Agent 标准工作流）

    触发场景：六阶段任一阶段的 LLM 调用失败包装（LLM 族异常 330-332 收敛）
    或图执行异常收敛。工作流执行属系统侧行为（非调用方输入错误），与 440/442
    系统资源语义同层，继承 SystemException。

    LLM 族异常传播策略（4-5 辩论纪律先例）：阶段内包装为 444 携带 phase；
    LLMConfigError（332，配置错误透传不包装）与 CancelledError（协程取消
    透传）例外。

    端到端可达前提：引擎 submit_graph 的 DomainError 透传（原引擎对 ainvoke
    任意异常包 RuntimeError from e 会改写 444 致 CLI stderr 无
    [EXCEPTION_444]——Task 5 已改造为 DomainError 原样透传、仅非 DomainError
    包 RuntimeError，端到端链路已闭合）。

    Attributes:
        code: EXCEPTION_444
        message: 默认消息（静态文案，不含动态内部细节）
        context: 领域上下文（agent_id/phase/reason——phase 为同码多因区分
            锚点，取值 perceive/plan/execute/verify/reflect/package）
    """

    code = "EXCEPTION_444"
    message = "Agent 工作流阶段执行失败"

    def __init__(
        self,
        agent_id: str = "",
        phase: str = "",
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化工作流阶段执行异常

        Args:
            agent_id: 工作流归属的 Agent 标识（字符串形态）
            phase: 失败阶段名（perceive/plan/execute/verify/reflect/package 之一）
            reason: 面向调用方可理解的失败原因摘要
            message: 覆盖默认消息（可选）
            cause: 原始异常（可选，用于异常链）
        """
        context: dict[str, str] = {
            "agent_id": agent_id,
            "phase": phase,
            "reason": reason,
        }
        super().__init__(message=message, cause=cause, context=context)


class ChainOfThoughtValidationError(SystemException):
    """思维链完整性校验失败（Story 5-3 — 单 Agent 标准工作流）

    触发场景：终局组装后的服务端完整性校验失败——五字段缺一/空值/结构
    非法。组装产物缺陷属系统侧问题（LLM 产出或组装链缺陷，非调用方输入
    错误），继承 SystemException。

    三层校验次序定稿（DC-2）：
    ① LLM 输出 Schema 校验失败已被 structured_generate 内建拦截→
       LLMResponseError(331)→服务包 444；
    ② VO __post_init__ 校验失败抛 EntityValidationError(242)——package
       阶段捕获 242 改写 445（context.missing_fields）；
    ③ 服务自检缺失直接 445。444 严格限于 LLM 调用失败与图执行异常。

    Attributes:
        code: EXCEPTION_445
        message: 默认消息（静态文案）
        context: 领域上下文（agent_id/missing_fields——缺失字段名清单为
            同码多因区分锚点）
    """

    code = "EXCEPTION_445"
    message = "Agent 思维链完整性校验失败"

    def __init__(
        self,
        agent_id: str = "",
        missing_fields: tuple[str, ...] | list[str] = (),
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化思维链完整性校验异常

        Args:
            agent_id: 工作流归属的 Agent 标识（字符串形态）
            missing_fields: 缺失/非法的字段名清单（五字段子集）
            message: 覆盖默认消息（可选）
            cause: 原始异常（可选，用于异常链——如 242 改写场景携带原异常）
        """
        context: dict[str, Any] = {
            "agent_id": agent_id,
            "missing_fields": list(missing_fields),
        }
        super().__init__(message=message, cause=cause, context=context)


class IsolationLevelNotSupportedError(BusinessException):
    """请求的 EIP 隔离等级不合法（Story 5.4 — EIP 弹性隔离协议基础）

    触发场景（双路径——同码多因区分锚在 context.level）:
    ① CLI/调用方传入非法枚举值字符串（如 "L9"——_parse_isolation_level
       第一道转换守卫拦截，禁止裸 IsolationLevel(value) 的 ValueError 逃逸）；
    ② 合法枚举但不在 MVP_ALLOWED_LEVELS（L1 融合态——SYS 监督/紧急态/强制
       审计设施均 V2，MVP 禁用；实体 initialize/switch_to 双条件守卫拦截）。
    与 441「MVP 未开放角色」同语义族（阶段性能力范围限制），HTTP 422。

    Attributes:
        code: EXCEPTION_446
        message: 默认消息
        context: 领域上下文（level 原始输入 + supported_levels 当前开放等级清单
            ——按位点区分：实体/服务侧从 MVP_ALLOWED_LEVELS 真派生
            [isolation_state._supported_level_values——V2 仅改常量一处]；CLI 侧
            SUPPORTED_ISOLATION_LEVELS 显式字面量 + 集合相等双锁形态
            [R1-F34——帮助文本稳定性；双锁红即 V2 同步提醒]）
    """

    code = "EXCEPTION_446"
    message = "隔离等级在当前阶段不支持"

    def __init__(
        self,
        level: str,
        supported_levels: tuple[str, ...] | list[str] = (),
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化隔离等级不支持异常

        Args:
            level: 请求的等级原始输入（字符串形态——非枚举实例经 str 化后传入）
            supported_levels: 当前开放等级清单（实体/服务侧从 MVP_ALLOWED_LEVELS
                真派生；CLI 侧字面量双锁——见类 docstring 位点注记）
            message: 覆盖默认消息（可选）
            cause: 原始异常（可选，用于异常链）
        """
        context: dict[str, Any] = {
            "level": level,
            "supported_levels": list(supported_levels),
        }
        super().__init__(message=message, cause=cause, context=context)


class IsolationStateNotInitializedError(BusinessException):
    """Agent 的 EIP 隔离状态缺失（Story 5.4 — EIP 弹性隔离协议基础）

    触发场景（三种成因——同码多因，context.agent_id 为区分锚）:
    ① 存量 Agent 无隔离键（5.4 部署前实例化的 agent 被查询——隔离键从未写入；
       「TTL 漂移致隔离键先过期」经写序推演不可构造，见 Story 5.4 风险 #6）；
    ② 未初始化查询（get_isolation_state 在隔离键缺失时抛出——443 守卫通过后）；
    ③ 实例化 fail-fast 后键残留（agent 键存活 → 443 守卫通过 → 隔离键缺失；
       服务级以同 id 重新 initialize 可自愈，用例/CLI 通道靠 TTL 自然回收）。
    Agent 存在与隔离状态缺失是两个聚合两个语义（443 vs 447 精确诊断），
    HTTP 404 对齐 443 NotFound 族。

    Attributes:
        code: EXCEPTION_447
        message: 默认消息
        context: 领域上下文（agent_id——raise 侧传 str(agent_id) 字符串形态）
    """

    code = "EXCEPTION_447"
    message = "Agent 隔离状态未初始化"

    def __init__(
        self,
        agent_id: str = "",
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化隔离状态未初始化异常

        Args:
            agent_id: 隔离状态缺失的 Agent 标识（字符串形态）
            message: 覆盖默认消息（可选）
            cause: 原始异常（可选，用于异常链）
        """
        context: dict[str, str] = {
            "agent_id": agent_id,
        }
        super().__init__(message=message, cause=cause, context=context)


class IsolationAccessViolationError(BusinessException):
    """跨 Agent 私有资源访问越权（Story 5.5 — Agent 三重硬隔离保证）

    触发场景: actor ≠ target 且目标资源归属 private 类（Prompt/数据面全资源——
    三重隔离判定矩阵 private+cross 格拒绝）。与 449 的分界: 448 = 跨主体越权，
    449 = 单主体操作被自身等级策略禁止——两语义轴正交。
    HTTP 403（权限不足族——Forbidden 语义，非 404 资源不存在也非 422 取值非法）。

    Attributes:
        code: EXCEPTION_448
        message: 默认消息（面向调用方可理解——禁泄露资源内容/内部键名，仅资源类别）
        context: 领域上下文五字段（actor_agent_id/target_agent_id/resource/operation/
            reason——reason 承载判定依据含等级名，并发串扰判别与三段式断言锚）
    """

    code = "EXCEPTION_448"
    message = "Agent 间私有资源访问被隔离策略拒绝"

    def __init__(
        self,
        actor_agent_id: str,
        target_agent_id: str,
        resource: str,
        operation: str,
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化跨 Agent 私有资源访问越权异常

        Args:
            actor_agent_id: 发起访问的 Agent 标识（字符串形态）
            target_agent_id: 被访问的 Agent 标识（字符串形态）
            resource: 资源归属分类值（IsolationResource.value——仅类别非内容）
            operation: 访问操作（read/write）
            reason: 判定依据（decision.reason——含等级名「硬隔离/软隔离」）
            message: 覆盖默认消息（可选）
            cause: 原始异常（可选，用于异常链）
        """
        context: dict[str, str] = {
            "actor_agent_id": actor_agent_id,
            "target_agent_id": target_agent_id,
            "resource": resource,
            "operation": operation,
            "reason": reason,
        }
        super().__init__(message=message, cause=cause, context=context)


class IsolationOperationForbiddenError(BusinessException):
    """当前隔离等级策略禁止的操作（Story 5.5 — Agent 三重硬隔离保证）

    触发场景（两类——同码多因，context.reason 编码触发细分）:
    ① L4 严格白名单外工具请求（reason=tool_not_in_allowlist:{tool_name}）；
    ② READ_ONLY/RESTRICTED_WRITE 等级下共享面写（reason=data_isolation:{mode}——
       MVP 受限写白名单未定义一律拒，Story 5.5 D-4）。
    与 448 的分界: 449 = 单主体操作被自身等级策略禁止（不涉跨主体）。
    HTTP 403（权限不足族）。

    Attributes:
        code: EXCEPTION_449
        message: 默认消息
        context: 领域上下文三字段（agent_id/operation/reason——最小化，白名单
            明细不进 context，经配置通道可查）
    """

    code = "EXCEPTION_449"
    message = "当前隔离等级策略禁止该操作"

    def __init__(
        self,
        agent_id: str,
        operation: str,
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化隔离等级策略禁止操作异常

        Args:
            agent_id: 被策略约束的 Agent 标识（字符串形态）
            operation: 被禁止的操作（execute/write 等动词形态）
            reason: 判定依据（decision.reason——tool_not_in_allowlist:{name} 或
                data_isolation:{mode} 双形态）
            message: 覆盖默认消息（可选）
            cause: 原始异常（可选，用于异常链）
        """
        context: dict[str, str] = {
            "agent_id": agent_id,
            "operation": operation,
            "reason": reason,
        }
        super().__init__(message=message, cause=cause, context=context)


__all__ = [
    "AgentConfigError",
    "AgentNotFoundError",
    "AgentProfileError",
    "AgentRoleNotSupportedError",
    "AgentWorkflowError",
    "ChainOfThoughtValidationError",
    "IsolationAccessViolationError",
    "IsolationLevelNotSupportedError",
    "IsolationOperationForbiddenError",
    "IsolationStateNotInitializedError",
]
