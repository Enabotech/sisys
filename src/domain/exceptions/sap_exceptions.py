"""SAP 子域异常（sap，460-469）——Story 5.11 SAP 协议支持（内部 Agent 通信）。

sap 子域三异常：SAPTimeoutError（460——请求-响应关联等待超时，BusinessException）/
SAPBusStateError（461——总线状态违规，SystemException）/ SAPBlackboardWriteError
（462——公共黑板写入失败，SystemException）。

开段先例（第六段）：agent 段 440-449 已满 + evaluation 段 450-459 语义独立于 SAP
协议域——「前段满/语义独立 → 开独立段」（data_source 410/debate 420/tool_version
430/agent 440/evaluation 450 同款）；463-469 预留 sap 域后续异常。

语义归属：460 business（协议交互超时是调用方可处理结果——等待方决定降级/裁决升级，
ToolExecutionTimeoutError 385「business+超时+504」三合一先例）；461/462 system（协议
契约违规 / 基础设施写失败）。462 与 StorageError 103 系统资源族同族但不复用（子域
分立——MessageBusError 与 SAP 协议分立的同款先例：debate 420 段独立于 event 段）。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException
from src.domain.exceptions.system_exceptions import SystemException

__all__ = ["SAPBlackboardWriteError", "SAPBusStateError", "SAPTimeoutError"]


class SAPTimeoutError(BusinessException):
    """SAP 请求-响应关联等待超时（Story 5.11 — AC-2 协议交互超时）

    触发场景：
    - wait_for_response(correlation_id, timeout_seconds) 等满超时仍无 RESPONSE resolve
    - 未挂起 correlation 条目的等待按超时路径处理（等满 timeout——不 special-case）

    计时锚点：timeout 从 wait_for_response 调用时刻起算（asyncio.wait_for duration
    语义——非 send 时刻 deadline 语义）；超时抛出前取消底层等待任务。

    Attributes:
        code: EXCEPTION_460
        message: 默认消息（静态文案，不含动态内部细节）
        context: 领域上下文（correlation_id——str 换算口径；timeout_seconds——数值保真）
    """

    code = "EXCEPTION_460"
    message = "SAP 请求-响应关联等待超时"

    def __init__(
        self,
        correlation_id: str,
        timeout_seconds: float | int,
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """初始化协议交互超时异常

        Args:
            correlation_id: 关联锚（OD-9 锚约定——所等待 REQUEST 的 message_id，str 换算）
            timeout_seconds: 等满的超时秒数（wait_for_response 调用时刻起算）
            message: 自定义消息（缺省回落类属性静态文案）
            cause: 底层异常（超时清理取消等待任务等场景）
            context_extra: 扩展上下文键（合并不覆盖既有双键）
        """
        context: dict[str, str | float | int] = {
            "correlation_id": correlation_id,
            "timeout_seconds": timeout_seconds,
        }
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)


class SAPBusStateError(SystemException):
    """SAP 总线状态违规（Story 5.11 — AC-1 校验面/关闭态协议契约错误）

    触发场景（reason 闭集五成员——全部有触发用例）：
    - receiver_not_registered: 单播目标接收方未注册（fail-loud——比静默入队后无人消费更诚实）
    - invalid_sender_id: sender_id 非 UUID 可解析形态（OD-5 标识口径）
    - invalid_receiver_id: receiver_id 非 UUID 且非 "broadcast" 约定值（send/subscribe 双侧）
    - broadcast_convention_violation: BROADCAST ⇔ receiver_id="broadcast" 组合双向违规（OD-8）
    - bus_closed: 关闭后调用 send/subscribe/wait_for_response（校验次序：开闭态首位）

    Attributes:
        code: EXCEPTION_461
        message: 默认消息（静态文案）
        context: 领域上下文（reason 闭集成员）
    """

    code = "EXCEPTION_461"
    message = "SAP 总线状态违规"

    _VALID_REASONS = (
        "receiver_not_registered",
        "invalid_sender_id",
        "invalid_receiver_id",
        "broadcast_convention_violation",
        "bus_closed",
    )

    def __init__(
        self,
        reason: str,
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """初始化总线状态违规异常

        Args:
            reason: 违规细分（闭集 _VALID_REASONS 五成员）
            message: 自定义消息（缺省回落类属性静态文案）
            cause: 底层异常（预留形参——三异常统一显式 cause）
            context_extra: 扩展上下文键（合并不覆盖 reason）

        Raises:
            EntityValidationError: reason 不在闭集内（ArchiveStorageError._VALID_LAYERS 先例）
        """
        if reason not in self._VALID_REASONS:
            from src.domain.exceptions import EntityValidationError

            raise EntityValidationError(
                message=f"reason must be one of {self._VALID_REASONS}, got {reason!r}",
                context={"entity": "SAPBusStateError", "field": "reason"},
            )
        context: dict[str, str] = {"reason": reason}
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)


class SAPBlackboardWriteError(SystemException):
    """SAP 公共黑板写入失败（Story 5.11 — AC-3 黑板桥 fail-loud，OD-7）

    触发场景：blackboard_visible=True 消息经守卫放行后 PublicBlackboard.post 返回
    version == 0（RedisPublicBlackboard 既有吞 ConnectionError/TimeoutError 返 0 语义
    的写失败检测点）——fail-loud 非降级：显式置位的黑板可见性是消息主语义面，写失败
    静默降级 = 静默丢协作数据；调用方拿到明确失败可决定重试/降级/裁决升级。

    发送原子性：黑板承诺面失败则整条 send 失败（先黑板后入队次序——消息不投递）。

    Attributes:
        code: EXCEPTION_462
        message: 默认消息（静态文案）
        context: 领域上下文（conversation_id——str 换算口径）
    """

    code = "EXCEPTION_462"
    message = "SAP 公共黑板写入失败"

    def __init__(
        self,
        conversation_id: str,
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """初始化黑板写入失败异常

        Args:
            conversation_id: 会话标识（str 形态——黑板键口径）
            message: 自定义消息（缺省回落类属性静态文案）
            cause: 底层异常（post 失败根因透传）
            context_extra: 扩展上下文键（合并不覆盖 conversation_id）
        """
        context: dict[str, str] = {"conversation_id": conversation_id}
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)
