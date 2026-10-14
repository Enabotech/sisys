"""领域层事件基类模块

领域事件仅使用 Python 标准库类型（dataclasses, uuid, datetime）
Pydantic 仅在应用层/基础设施层边界用于序列化和验证
"""

from __future__ import annotations

import json
import uuid
from dataclasses import MISSING, dataclass, field, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar, get_args, get_origin, get_type_hints

from src.domain.exceptions import EntityValidationError

# Core field names that are part of the DomainEvent standard schema (AC-1).
# These are serialized at the top level of to_dict(), not in payload.
_CORE_FIELD_NAMES = frozenset(
    {
        "event_id",
        "event_type",
        "timestamp",
        "source",
        "schema_version",
        "aggregate_id",
        "aggregate_type",
        "version",
        "payload",
        "correlation_id",
        "causation_id",
        "metadata",
    }
)

# Default schema version for all events
DEFAULT_SCHEMA_VERSION = "1.0.0"

# 字段名 → 已解析类型注解的类级缓存（from_dict 消费）。
# 并发性质：CPython GIL 下 dict 读写原子，最坏并发是重复解析（良性竞争、
# 结果幂等），无需锁；缓存按事件类为键，上界 = 事件类数量。
_RESOLVED_HINTS: dict[type, dict[str, Any]] = {}


@dataclass(frozen=True)
class DomainEvent:
    """所有领域事件的基类

    AC-1 标准字段:
        event_id: 本次事件实例的唯一标识符
        event_type: 类型判别字符串（如 "DocumentProcessed"）
        timestamp: 事件发生时间（UTC）
        source: 产生此事件的系统或模块来源
        schema_version: 此事件模式的版本（如 "1.0.0"）
        aggregate_id: 产生此事件的聚合 ID
        aggregate_type: 聚合类型名称（如 "Document"）
        version: 此事件的单调递增版本号
        payload: 事件特定数据字典
    """

    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    schema_version: str = DEFAULT_SCHEMA_VERSION
    aggregate_id: uuid.UUID | None = None
    aggregate_type: str = ""
    version: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    # AC-4: Enhanced traceability fields
    correlation_id: uuid.UUID | None = None
    causation_id: uuid.UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Event type registry for polymorphic deserialization
    _registry: ClassVar[dict[str, type[DomainEvent]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """自动按 event_type 注册子类

        从 cls.__dict__ 读取 event_type 字段描述符，绕过 @dataclass
        装饰器时序问题（__init_subclass__ 在 @dataclass 之前调用，
        此时 is_dataclass(cls) 为 False）
        """
        super().__init_subclass__(**kwargs)
        et_field = cls.__dict__.get("event_type")
        if et_field is not None and hasattr(et_field, "init") and not et_field.init:
            if et_field.default is not MISSING:
                DomainEvent._registry[et_field.default] = cls

    @classmethod
    def register(cls, event_type: str, event_class: type[DomainEvent]) -> None:
        """手动注册事件类用于多态反序列化

        Args:
            event_type: 映射到此类的 event_type 字符串
            event_class: 要注册的事件类
        """
        cls._registry[event_type] = event_class

    @classmethod
    def reset_registry(cls) -> None:
        """重置事件注册表（仅用于测试隔离）.

        注意（破坏性语义警示）：清空后**不自动恢复** import 期注册的事件类——
        跨用例需要注册表稳定时优先使用快照/恢复形态（见
        tests/unit/domain/events/conftest.py 的 autouse fixture），本方法
        仅适合「用例内重建注册表」的自包含场景。
        """
        cls._registry.clear()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """序列化事件为字典，包含子类特定字段。子类特定字段（超出核心 DomainEvent 字典）合并到 payload 字典

        Returns:
            事件的字典表示

        Raises:
            EntityValidationError: event_type 为空或 payload 不可 JSON 序列化
        """
        if not self.event_type:
            raise EntityValidationError(
                message="event_type must not be empty", context={"entity": "DomainEvent", "field": "event_type"}
            )

        # Collect subclass-specific fields into extra payload
        extra_payload: dict[str, Any] = {}
        for f in fields(self):
            if f.name not in _CORE_FIELD_NAMES and f.init:
                value = getattr(self, f.name)
                extra_payload[f.name] = self._serialize_value(value)

        # Merge with existing payload
        merged_payload = {**self.payload, **extra_payload}

        result: dict[str, Any] = {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "schema_version": self.schema_version,
            "occurred_on": self.timestamp.isoformat(),  # backward compat alias
            "payload": merged_payload,
        }
        if self.aggregate_id is not None:
            result["aggregate_id"] = str(self.aggregate_id)
        if self.aggregate_type:
            result["aggregate_type"] = self.aggregate_type
        result["version"] = self.version
        # AC-4: Traceability fields (only include when set)
        if self.correlation_id is not None:
            result["correlation_id"] = str(self.correlation_id)
        if self.causation_id is not None:
            result["causation_id"] = str(self.causation_id)
        if self.metadata:
            # metadata 走 _serialize_value 序列化（R2-D3 清偿）——UUID/datetime 等
            # 非原生 JSON 类型在源头转 str，防直透 outbox JSONB/redis/rabbitmq 的
            # json.dumps 时才炸（曾被 RabbitMQEventBus except 吞为静默发布失败）
            result["metadata"] = {k: self._serialize_value(v) for k, v in self.metadata.items()}

        try:
            json.dumps(merged_payload)
            json.dumps(result.get("metadata", {}))
        except (TypeError, ValueError) as e:
            raise EntityValidationError(
                message=f"payload or metadata is not JSON serializable: {e}",
                context={"entity": "DomainEvent", "field": "payload"},
            )
        return result

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """序列化单个字段值用于 JSON 传输"""
        if value is None:
            return None
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list | tuple):
            return [DomainEvent._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {k: DomainEvent._serialize_value(v) for k, v in value.items()}
        return value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        """使用事件类型注册表从字典反序列化事件。如果 event_type 映射到已注册子类，则实例化该子类；否则返回基础 DomainEvent

        Args:
            data: 包含事件数据的字典

        Returns:
            重建的 DomainEvent 实例（可能是子类）

        Raises:
            EntityValidationError: 必需字段缺失或格式错误
        """
        if "event_id" not in data:
            raise EntityValidationError(
                message="Missing required field: event_id", context={"entity": "DomainEvent", "field": "event_id"}
            )
        if "event_type" not in data:
            raise EntityValidationError(
                message="Missing required field: event_type", context={"entity": "DomainEvent", "field": "event_type"}
            )
        # Support both "timestamp" and backward-compat "occurred_on"
        ts_raw = data.get("timestamp") or data.get("occurred_on")
        if ts_raw is None:
            raise EntityValidationError(
                message="Missing required field: timestamp", context={"entity": "DomainEvent", "field": "timestamp"}
            )

        try:
            eid = uuid.UUID(data["event_id"])
        except (ValueError, AttributeError):
            raise EntityValidationError(
                message=f"Invalid event_id: {data.get('event_id', 'missing')}",
                context={"entity": "DomainEvent", "field": "event_id"},
            )

        try:
            ts = datetime.fromisoformat(ts_raw)
        except (ValueError, AttributeError, TypeError):
            raise EntityValidationError(
                message=f"Invalid timestamp: {ts_raw!r}", context={"entity": "DomainEvent", "field": "timestamp"}
            )

        agg_id: uuid.UUID | None = None
        if data.get("aggregate_id") is not None:
            try:
                agg_id = uuid.UUID(data["aggregate_id"])
            except (ValueError, AttributeError):
                raise EntityValidationError(
                    message=f"Invalid aggregate_id: {data.get('aggregate_id', 'missing')}",
                    context={"entity": "DomainEvent", "field": "aggregate_id"},
                )

        event_type = data["event_type"]
        payload = data.get("payload", {}).copy()

        # Look up the correct class from the registry
        target_class: type[DomainEvent] = cls
        if event_type in cls._registry:
            target_class = cls._registry[event_type]

        # Extract subclass-specific fields from payload
        extra_kwargs: dict[str, Any] = {}
        event_type_field: Any = None
        if target_class is not DomainEvent and is_dataclass(target_class):
            hints = cls._field_type_hints(target_class)
            for f in fields(target_class):
                if f.name == "event_type":
                    event_type_field = f
                    continue
                if f.name in _CORE_FIELD_NAMES or not f.init:
                    continue
                if f.name in payload:
                    try:
                        value = cls._deserialize_value(payload[f.name], hints.get(f.name, f.type))
                    except (ValueError, TypeError) as exc:
                        # 畸形 payload（非法 UUID/datetime/Enum 值）统一包装 242，
                        # 禁裸内置异常逃逸（与 event_id/aggregate_id 核心字段同构）
                        raise EntityValidationError(
                            message=f"Invalid payload field '{f.name}': {payload[f.name]!r}",
                            context={"entity": target_class.__name__, "field": f.name},
                        ) from exc
                    extra_kwargs[f.name] = value

        # 仅当 event_type 字段的 init=True 时才传入构造函数
        if event_type_field is None or event_type_field.init:
            extra_kwargs["event_type"] = event_type

        # 核心字段按 target_class 的 init=False 声明过滤（saga_events 的
        # source/aggregate_type 等声明 init=False——无条件传递会使
        # from_dict(to_dict()) roundtrip 抛 TypeError；过滤后 init=False 成员
        # 保持类默认值，与「event_type 仅 init=True 时传」同构）
        non_init_core = {f.name for f in fields(target_class) if not f.init} if is_dataclass(target_class) else set()
        core_kwargs: dict[str, Any] = {
            "event_id": eid,
            "timestamp": ts,
            "source": data.get("source", ""),
            "schema_version": data.get("schema_version", DEFAULT_SCHEMA_VERSION),
            "aggregate_id": agg_id,
            "aggregate_type": data.get("aggregate_type", ""),
            "version": data.get("version", 0),
            "payload": payload,
            # AC-4: Traceability fields（可选——None 合法；畸形值与核心字段同构包装 242）
            "correlation_id": cls._parse_optional_uuid(data.get("correlation_id"), "correlation_id"),
            "causation_id": cls._parse_optional_uuid(data.get("causation_id"), "causation_id"),
            "metadata": data.get("metadata", {}),
        }
        return target_class(
            **{k: v for k, v in core_kwargs.items() if k not in non_init_core},
            **extra_kwargs,
        )

    @staticmethod
    def _parse_optional_uuid(value: Any, field_name: str) -> uuid.UUID | None:
        """解析可选 UUID 追踪字段（None 合法；畸形值包装 242）。

        异常元组取 timestamp 式三元组（ValueError/AttributeError/TypeError）而非
        event_id 式二元组——`uuid.UUID(非 str)` 走 AttributeError/TypeError 面。

        Args:
            value: 原始值（None 或 UUID 可解析形态）
            field_name: 字段名（异常 context 用）

        Returns:
            UUID 对象或 None

        Raises:
            EntityValidationError: 值非 None 且不可解析为 UUID（EXCEPTION_242）
        """
        if value is None:
            return None
        try:
            return uuid.UUID(value)
        except (ValueError, AttributeError, TypeError):
            raise EntityValidationError(
                message=f"Invalid {field_name}: {value!r}",
                context={"entity": "DomainEvent", "field": field_name},
            )

    @classmethod
    def _field_type_hints(cls, target_class: type[DomainEvent]) -> dict[str, Any]:
        """解析目标事件类的字段类型注解（PEP 563 字符串注解 → 类型对象，按类缓存）。

        事件模块均启用 ``from __future__ import annotations``，dataclasses.fields()
        返回的 f.type 是字符串注解（如 "uuid.UUID"），直接与类型对象做 is 比较
        恒为 False——必须经 get_type_hints 解析为真实类型后才能驱动
        _deserialize_value 的 UUID/datetime/Enum/容器还原分支。

        Args:
            target_class: 目标事件类（含继承链全字段）

        Returns:
            字段名 → 已解析类型对象的映射
        """
        hints = _RESOLVED_HINTS.get(target_class)
        if hints is None:
            try:
                hints = get_type_hints(target_class)
            except NameError as exc:
                # 不可解析注解（引用模块命名空间外的名字，如函数内局部类型）包装 242，
                # 禁裸 NameError 逃逸统一异常体系；解析失败时缓存未写入（赋值在解析后），无毒化
                raise EntityValidationError(
                    message=f"Unresolvable type annotations on {target_class.__name__}: {exc}",
                    context={"entity": target_class.__name__, "field": "<type_hints>"},
                ) from exc
            _RESOLVED_HINTS[target_class] = hints
        return hints

    @classmethod
    def _deserialize_value(cls, value: Any, target_type: Any) -> Any:
        """反序列化 payload 值为原始 Python 类型

        处理 UUID、datetime、Enum 及容器类型（list、dict），
        正确处理 uuid.UUID | None 等联合类型。

        放行策略（有意宽容）：具体类型分支均有 isinstance(value, str) 守卫——
        合法往返的序列化值恒为 str（to_dict 保证）；非 str 标量（畸形生产方
        写入的 int 等）不匹配任何分支时原样透传而非报错，由构造方类型注解
        与下游消费方兜底。
        """
        if value is None:
            return None

        origin = get_origin(target_type)
        args = get_args(target_type)

        # Handle Optional / Union types: try each arg in order
        if origin is not None:
            for arg in args:
                if arg is type(None):
                    continue
                try:
                    return cls._deserialize_value(value, arg)
                except (ValueError, TypeError):
                    continue
            # If no arg matched, return as-is
            return value

        # Concrete types
        if target_type is uuid.UUID and isinstance(value, str):
            return uuid.UUID(value)
        if target_type is datetime and isinstance(value, str):
            return datetime.fromisoformat(value)
        if isinstance(target_type, type) and issubclass(target_type, Enum) and isinstance(value, str):
            return target_type(value)
        if origin is list and isinstance(value, list):
            item_type = args[0] if args else Any
            return [cls._deserialize_value(item, item_type) for item in value]
        if origin is dict and isinstance(value, dict):
            key_type = args[0] if args else Any
            val_type = args[1] if args else Any
            return {cls._deserialize_value(k, key_type): cls._deserialize_value(v, val_type) for k, v in value.items()}
        return value
