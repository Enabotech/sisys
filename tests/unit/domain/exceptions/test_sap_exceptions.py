"""SAP 子域异常单测（sap，460-462）——Story 5.11 SAP 协议支持。

覆盖：三异常构造/属性/code 唯一/to_dict/context 键/cause 链/继承链
（SAPTimeoutError→BusinessException / SAPBusStateError→SystemException /
SAPBlackboardWriteError→SystemException）+ SAPBusStateError reason 闭集校验
（非法 reason → EntityValidationError——ArchiveStorageError._VALID_LAYERS 先例）+
HTTP 映射（460→504 / 461→409 / 462→500——语义就近映射）+ 子域段注册
（CODE_RANGES "sap": (460, 469) + _CLASS_TO_SUBDOMAIN 三行）。

Run with:
    poetry run pytest tests/unit/domain/exceptions/test_sap_exceptions.py -v
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import (
    BusinessException,
    EntityValidationError,
    SAPBlackboardWriteError,
    SAPBusStateError,
    SAPTimeoutError,
    SystemException,
)
from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN, CODE_RANGES

# ==== SAPTimeoutError（EXCEPTION_460——BusinessException，协议交互超时） ====


class TestSAPTimeoutErrorConstruction:
    """SAPTimeoutError 构造与属性（correlation_id/timeout_seconds 双键必填）。"""

    def test_default_message_and_code(self) -> None:
        """默认构造：code 460 + 非空静态文案。"""
        error = SAPTimeoutError(correlation_id="019b2c3d-0000-7000-8000-000000000001", timeout_seconds=0.1)
        assert error.code == "EXCEPTION_460"
        assert error.message, "默认消息应为非空静态文案"

    def test_context_carries_correlation_and_timeout(self) -> None:
        """context 双键：correlation_id（str 换算口径）+ timeout_seconds（数值保真）。"""
        correlation = "019b2c3d-0000-7000-8000-000000000002"
        error = SAPTimeoutError(correlation_id=correlation, timeout_seconds=0.1)
        assert error.context["correlation_id"] == correlation
        assert error.context["timeout_seconds"] == 0.1

    def test_context_accepts_int_timeout(self) -> None:
        """timeout_seconds 兼容 int 形态（SAPMessage.timeout_seconds 默认 int 300）。"""
        error = SAPTimeoutError(correlation_id="c-1", timeout_seconds=300)
        assert error.context["timeout_seconds"] == 300

    def test_context_extra_merge(self) -> None:
        """context_extra 合并（扩展键不覆盖既有双键）。"""
        error = SAPTimeoutError(
            correlation_id="c-2",
            timeout_seconds=5.0,
            context_extra={"phase": "wait_for_response"},
        )
        assert error.context["phase"] == "wait_for_response"
        assert error.context["correlation_id"] == "c-2"

    def test_cause_chain(self) -> None:
        """cause 链（显式 cause 形参传递）。"""
        original = RuntimeError("底层等待任务取消")
        error = SAPTimeoutError(correlation_id="c-3", timeout_seconds=1.0, cause=original)
        assert error.cause is original

    def test_to_dict(self) -> None:
        """to_dict 携 code/message/context 三段。"""
        error = SAPTimeoutError(correlation_id="c-4", timeout_seconds=2.0)
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_460"
        assert data["context"]["correlation_id"] == "c-4"

    def test_str_equals_static_message_with_cause(self) -> None:
        """str(异常) 恒等于 message（cause 动态文案只进 to_dict 不进 str）。"""
        original = TimeoutError("inner")
        error = SAPTimeoutError(correlation_id="c-5", timeout_seconds=3.0, cause=original)
        assert str(error) == error.message
        assert "inner" not in str(error)

    def test_inherits_business_exception(self) -> None:
        """继承链：BusinessException（协议交互超时是调用方可处理结果——ToolExecutionTimeoutError 385 三合一先例）。"""
        assert issubclass(SAPTimeoutError, BusinessException)
        assert issubclass(SAPTimeoutError, SystemException) is False


# ==== SAPTimeoutError HTTP 映射（460→504 Gateway Timeout） ====


class TestSAPTimeoutErrorHttpMapping:
    """SAPTimeoutError HTTP 映射（504——business+超时+504 三合一先例）。"""

    def test_get_http_status_504(self) -> None:
        """_get_http_status 正向 504。"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = SAPTimeoutError(correlation_id="c-6", timeout_seconds=1.0)
        assert _get_http_status(error) == 504

    def test_exception_http_map_direct(self) -> None:
        """EXCEPTION_HTTP_MAP 表直查 504。"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[SAPTimeoutError] == status.HTTP_504_GATEWAY_TIMEOUT


# ==== SAPTimeoutError 子域注册（sap 段 460-469） ====


class TestSAPTimeoutErrorSubdomainRegistration:
    """SAPTimeoutError 子域段注册（460 落 sap 段）。"""

    def test_class_to_subdomain(self) -> None:
        """_CLASS_TO_SUBDOMAIN 映射 sap。"""
        assert _CLASS_TO_SUBDOMAIN["SAPTimeoutError"] == "sap"

    def test_code_within_sap_range(self) -> None:
        """编码 460 落 sap 段 [460, 469]。"""
        assert CODE_RANGES["sap"] == (460, 469)
        low, high = CODE_RANGES["sap"]
        numeric = int(SAPTimeoutError.code.removeprefix("EXCEPTION_"))
        assert low <= numeric <= high


# ==== SAPBusStateError（EXCEPTION_461——SystemException，总线状态违规） ====


class TestSAPBusStateErrorConstruction:
    """SAPBusStateError 构造与属性（reason 闭集 + cause 形参）。"""

    @pytest.mark.parametrize(
        "reason",
        [
            "receiver_not_registered",
            "invalid_sender_id",
            "invalid_receiver_id",
            "broadcast_convention_violation",
            "bus_closed",
        ],
    )
    def test_reason_closed_set_members(self, reason: str) -> None:
        """闭集五成员全部可构造且 context 携 reason（五成员全部有触发用例）。"""
        error = SAPBusStateError(reason=reason)
        assert error.code == "EXCEPTION_461"
        assert error.message, "默认消息应为非空静态文案"
        assert error.context["reason"] == reason

    def test_invalid_reason_rejected_with_entity_validation_error(self) -> None:
        """非法 reason → EntityValidationError 携 context field=reason（ArchiveStorageError._VALID_LAYERS 先例）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            SAPBusStateError(reason="not_in_closed_set")
        error = exc_info.value
        assert error.code == "EXCEPTION_242"
        assert error.context["entity"] == "SAPBusStateError"
        assert error.context["field"] == "reason"

    def test_cause_parameter(self) -> None:
        """cause 显式形参（三异常统一——461 预留）。"""
        original = KeyError("Port not registered: sap_bus")
        error = SAPBusStateError(reason="bus_closed", cause=original)
        assert error.cause is original
        assert error.context["reason"] == "bus_closed"

    def test_context_extra_merge(self) -> None:
        """context_extra 合并。"""
        error = SAPBusStateError(reason="invalid_sender_id", context_extra={"sender_id": "not-uuid"})
        assert error.context["sender_id"] == "not-uuid"

    def test_custom_message_overrides_default(self) -> None:
        """自定义 message 覆盖静态文案。"""
        error = SAPBusStateError(reason="bus_closed", message="总线已关闭")
        assert error.message == "总线已关闭"

    def test_to_dict(self) -> None:
        """to_dict 携 code + context.reason。"""
        error = SAPBusStateError(reason="receiver_not_registered")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_461"
        assert data["context"]["reason"] == "receiver_not_registered"

    def test_inherits_system_exception(self) -> None:
        """继承链：SystemException（协议契约违规——与 InvalidStateError 同族）。"""
        assert issubclass(SAPBusStateError, SystemException)


# ==== SAPBusStateError HTTP 映射（461→409 Conflict） ====


class TestSAPBusStateErrorHttpMapping:
    """SAPBusStateError HTTP 映射（409——协议状态冲突语义就近映射）。"""

    def test_get_http_status_409(self) -> None:
        """_get_http_status 正向 409。"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = SAPBusStateError(reason="bus_closed")
        assert _get_http_status(error) == 409

    def test_exception_http_map_direct(self) -> None:
        """EXCEPTION_HTTP_MAP 表直查 409。"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[SAPBusStateError] == status.HTTP_409_CONFLICT


class TestSAPBusStateErrorSubdomainRegistration:
    """SAPBusStateError 子域段注册（461 落 sap 段）。"""

    def test_class_to_subdomain(self) -> None:
        """_CLASS_TO_SUBDOMAIN 映射 sap。"""
        assert _CLASS_TO_SUBDOMAIN["SAPBusStateError"] == "sap"

    def test_code_within_sap_range(self) -> None:
        """编码 461 落 sap 段。"""
        low, high = CODE_RANGES["sap"]
        numeric = int(SAPBusStateError.code.removeprefix("EXCEPTION_"))
        assert low <= numeric <= high


# ==== SAPBlackboardWriteError（EXCEPTION_462——SystemException，黑板写失败） ====


class TestSAPBlackboardWriteErrorConstruction:
    """SAPBlackboardWriteError 构造与属性（conversation_id 必填 + cause 链）。"""

    def test_default_message_and_code(self) -> None:
        """默认构造：code 462 + 非空静态文案。"""
        error = SAPBlackboardWriteError(conversation_id="019b2c3d-0000-7000-8000-000000000003")
        assert error.code == "EXCEPTION_462"
        assert error.message, "默认消息应为非空静态文案"

    def test_context_carries_conversation_id(self) -> None:
        """context 携 conversation_id（str 形态——黑板键口径）。"""
        conversation_id = "019b2c3d-0000-7000-8000-000000000004"
        error = SAPBlackboardWriteError(conversation_id=conversation_id)
        assert error.context["conversation_id"] == conversation_id

    def test_cause_chain(self) -> None:
        """cause 链（post 返 0 检测点的底层异常透传）。"""
        original = ConnectionError("redis down")
        error = SAPBlackboardWriteError(conversation_id="c-7", cause=original)
        assert error.cause is original

    def test_to_dict(self) -> None:
        """to_dict 携 code + context.conversation_id + cause 链解析。"""
        error = SAPBlackboardWriteError(conversation_id="c-8")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_462"
        assert data["context"]["conversation_id"] == "c-8"

    def test_context_extra_merge(self) -> None:
        """context_extra 合并。"""
        error = SAPBlackboardWriteError(conversation_id="c-9", context_extra={"version": "0"})
        assert error.context["version"] == "0"

    def test_inherits_system_exception(self) -> None:
        """继承链：SystemException（基础设施写失败——StorageError 103 系统资源族同族）。"""
        assert issubclass(SAPBlackboardWriteError, SystemException)


# ==== SAPBlackboardWriteError HTTP 映射（462→500） ====


class TestSAPBlackboardWriteErrorHttpMapping:
    """SAPBlackboardWriteError HTTP 映射（500——基础设施写失败语义）。"""

    def test_get_http_status_500(self) -> None:
        """_get_http_status 正向 500。"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = SAPBlackboardWriteError(conversation_id="c-10")
        assert _get_http_status(error) == 500

    def test_exception_http_map_direct(self) -> None:
        """EXCEPTION_HTTP_MAP 表直查 500。"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[SAPBlackboardWriteError] == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestSAPBlackboardWriteErrorSubdomainRegistration:
    """SAPBlackboardWriteError 子域段注册（462 落 sap 段）。"""

    def test_class_to_subdomain(self) -> None:
        """_CLASS_TO_SUBDOMAIN 映射 sap。"""
        assert _CLASS_TO_SUBDOMAIN["SAPBlackboardWriteError"] == "sap"

    def test_code_within_sap_range(self) -> None:
        """编码 462 落 sap 段。"""
        low, high = CODE_RANGES["sap"]
        numeric = int(SAPBlackboardWriteError.code.removeprefix("EXCEPTION_"))
        assert low <= numeric <= high


# ==== 三码互异与段位校验 ====


class TestSAPCodeUniqueness:
    """三码互异（460/461/462 各自独立 + 与 evaluation 段 450-452 零冲突）。"""

    def test_three_codes_distinct(self) -> None:
        """460/461/462 三码互异。"""
        codes = {SAPTimeoutError.code, SAPBusStateError.code, SAPBlackboardWriteError.code}
        assert codes == {"EXCEPTION_460", "EXCEPTION_461", "EXCEPTION_462"}

    def test_codes_distinct_from_evaluation_segment(self) -> None:
        """与 evaluation 段既有三码零冲突（子域分立——物理段独立）。"""
        evaluation_codes = {"EXCEPTION_450", "EXCEPTION_451", "EXCEPTION_452"}
        sap_codes = {SAPTimeoutError.code, SAPBusStateError.code, SAPBlackboardWriteError.code}
        assert sap_codes & evaluation_codes == set()
