"""SAP 消息 Schema 单元测试（Story 5-3 — FR-IF-03 SAP 消息契约定义）

覆盖接口层 SAP（Structured Agent Protocol）消息 Pydantic 契约：
- SAPMessage 15 字段存在性与类型（10 必需 + 5 补充——epics 验收点名 + 设计文档）
- MessageType 五值 / MessagePriority 四值枚举集合
- 四默认值（priority=NORMAL / isolation_level=L4_HARD / blackboard_visible=False /
  timeout_seconds=300）
- conversation_id 必填（无默认）+ correlation_id 可空（UUID | None = None——
  D-7 设计缺陷修正）
- 非法枚举值构造被拒（pydantic ValidationError）+ timestamp tz-aware UTC
  （禁裸 utcnow——architecture v8.4.0 红线）
- isolation_level 复用 domain IsolationLevel 枚举（SSOT——不重复定义）
- 范围边界：不含 bus/传输/序列化性能/黑板交互（全部归 5.11——docstring 声明）

设计源：interface-design.md §7.4 L1302-1335 + sisys-core-domain-design.md
§17.3.7 L1558-1585（两份一致）。

Run with:
    poetry run pytest tests/unit/interfaces/sap/test_message.py -v
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from pydantic import ValidationError as PydanticValidationError


def _make_message_kwargs() -> dict:
    """构造合法 SAPMessage 最小必填字段集。"""
    return {
        "message_id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "sender_id": "agent-ceo",
        "receiver_id": "agent-cfo",
        "message_type": "request",
        "content": "请提供财务视角评估",
    }


def _make_message(**overrides):
    """工厂：构造合法 SAPMessage（可覆盖任意字段）。

    Story 5-3 新模块延迟 import 纪律——模块顶部 import 会使收集期整文件炸。
    """
    from src.interfaces.sap.message import SAPMessage

    kwargs = _make_message_kwargs()
    kwargs.update(overrides)
    return SAPMessage(**kwargs)


# ===================================================================
# 15 字段存在性与类型（AC-4.1）
# ===================================================================


class TestFifteenFields:
    """SAPMessage 模型 15 字段存在性与类型断言（10 必需逐一点名）。"""

    def test_model_has_exactly_fifteen_fields(self) -> None:
        """字段总数 15（多字段/少字段均红——Schema 演进绊线）。"""
        from src.interfaces.sap.message import SAPMessage

        fields = SAPMessage.model_fields
        assert len(fields) == 15, f"字段总数应为 15，实际 {len(fields)}: {sorted(fields)}"

    def test_ten_required_fields_named(self) -> None:
        """epics 验收点名的 10 必需字段逐一点名存在。"""
        from src.interfaces.sap.message import SAPMessage

        required_ten = (
            "message_id",
            "conversation_id",
            "sender_id",
            "receiver_id",
            "message_type",
            "priority",
            "content",
            "correlation_id",
            "isolation_level",
            "blackboard_visible",
        )
        for name in required_ten:
            assert name in SAPMessage.model_fields, f"必需字段缺失: {name}"

    def test_five_supplemental_fields_named(self) -> None:
        """设计文档补充的 5 字段存在（timestamp/subject/context/requires_response/timeout_seconds）。"""
        from src.interfaces.sap.message import SAPMessage

        supplemental_five = ("timestamp", "subject", "context", "requires_response", "timeout_seconds")
        for name in supplemental_five:
            assert name in SAPMessage.model_fields, f"补充字段缺失: {name}"

    def test_field_types(self) -> None:
        """关键字段类型断言（UUID/str/enum/dict/bool/int/datetime）。"""
        message = _make_message()
        assert isinstance(message.message_id, uuid.UUID)
        assert isinstance(message.conversation_id, uuid.UUID)
        assert isinstance(message.content, str)
        assert isinstance(message.context, dict)
        assert isinstance(message.blackboard_visible, bool)
        assert isinstance(message.timeout_seconds, int)
        assert isinstance(message.timestamp, datetime.datetime)


# ===================================================================
# 枚举值集合（AC-4.2）
# ===================================================================


class TestEnumValues:
    """MessageType 五值 / MessagePriority 四值枚举集合。"""

    def test_message_type_five_values(self) -> None:
        """request/response/notification/broadcast/debate 五值。"""
        from src.interfaces.sap.types import MessageType

        assert {item.value for item in MessageType} == {
            "request",
            "response",
            "notification",
            "broadcast",
            "debate",
        }

    def test_message_priority_four_values(self) -> None:
        """low/normal/high/urgent 四值。"""
        from src.interfaces.sap.types import MessagePriority

        assert {item.value for item in MessagePriority} == {"low", "normal", "high", "urgent"}

    def test_isolation_level_reuses_domain_enum(self) -> None:
        """isolation_level 复用 domain IsolationLevel 枚举（SSOT——禁止重复定义）。"""
        from src.domain.events.enums import IsolationLevel
        from src.interfaces.sap.message import SAPMessage

        field = SAPMessage.model_fields["isolation_level"]
        assert field.annotation is IsolationLevel, "isolation_level 注解必须是 domain IsolationLevel"


# ===================================================================
# 默认值（AC-4.2）
# ===================================================================


class TestDefaults:
    """四默认值契约：NORMAL / L4_HARD / False / 300。"""

    def test_default_priority_normal(self) -> None:
        from src.interfaces.sap.types import MessagePriority

        assert _make_message().priority is MessagePriority.NORMAL

    def test_default_isolation_level_l4_hard(self) -> None:
        from src.domain.events.enums import IsolationLevel

        assert _make_message().isolation_level is IsolationLevel.L4_HARD

    def test_default_blackboard_not_visible(self) -> None:
        assert _make_message().blackboard_visible is False

    def test_default_timeout_300_seconds(self) -> None:
        assert _make_message().timeout_seconds == 300

    def test_optional_defaults(self) -> None:
        """correlation_id 默认 None / subject 默认空 / context 默认空 dict / requires_response 默认 False。"""
        message = _make_message()
        assert message.correlation_id is None
        assert message.subject == ""
        assert message.context == {}
        assert message.requires_response is False


# ===================================================================
# 必填约束与非法值拒绝（AC-4.3）
# ===================================================================


class TestRequiredAndRejection:
    """conversation_id 必填 + correlation_id 可空 + 非法枚举拒绝 + UTC 感知。"""

    def test_conversation_id_required(self) -> None:
        """conversation_id 无默认——缺失构造 ValidationError。"""
        from src.interfaces.sap.message import SAPMessage

        kwargs = _make_message_kwargs()
        del kwargs["conversation_id"]
        with pytest.raises(PydanticValidationError):
            SAPMessage(**kwargs)

    @pytest.mark.parametrize(
        "field_name",
        ["message_id", "sender_id", "receiver_id", "message_type", "content"],
    )
    def test_required_fields_enforced(self, field_name: str) -> None:
        """其余必填字段缺失同样 ValidationError。"""
        from src.interfaces.sap.message import SAPMessage

        kwargs = _make_message_kwargs()
        del kwargs[field_name]
        with pytest.raises(PydanticValidationError):
            SAPMessage(**kwargs)

    def test_correlation_id_nullable_with_value(self) -> None:
        """correlation_id 可传 UUID 值（UUID | None 联合类型——D-7 修正形态）。"""
        correlation_id = uuid.uuid4()
        message = _make_message(correlation_id=correlation_id)
        assert message.correlation_id == correlation_id

    def test_invalid_message_type_rejected(self) -> None:
        """非法 message_type 字符串 → ValidationError。"""
        with pytest.raises(PydanticValidationError):
            _make_message(message_type="invalid-type")

    def test_invalid_priority_rejected(self) -> None:
        """非法 priority 字符串 → ValidationError。"""
        with pytest.raises(PydanticValidationError):
            _make_message(priority="critical")

    def test_invalid_isolation_level_rejected(self) -> None:
        """非法 isolation_level 字符串 → ValidationError（枚举复用 domain 值域）。"""
        with pytest.raises(PydanticValidationError):
            _make_message(isolation_level="L9_EXTREME")

    def test_non_uuid_message_id_rejected(self) -> None:
        """message_id 非 UUID 字符串 → ValidationError。"""
        with pytest.raises(PydanticValidationError):
            _make_message(message_id="not-a-uuid")

    def test_timestamp_is_utc_aware(self) -> None:
        """timestamp 默认值 tz-aware UTC（禁裸 utcnow——architecture v8.4.0 红线）。"""
        message = _make_message()
        assert message.timestamp.tzinfo is not None
        assert message.timestamp.utcoffset() == datetime.timedelta(0)


# ===================================================================
# 广播约定（docstring 边界声明验证）
# ===================================================================


class TestBroadcastConvention:
    """广播消息 receiver_id="broadcast" 约定值（docstring 注明——5.11 实现传输）。"""

    def test_broadcast_receiver_convention(self) -> None:
        """broadcast 类型 + receiver_id="broadcast" 约定组合合法。"""
        message = _make_message(message_type="broadcast", receiver_id="broadcast")
        assert message.receiver_id == "broadcast"
