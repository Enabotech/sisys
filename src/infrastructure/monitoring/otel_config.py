"""基础设施层 OpenTelemetry 配置模块

提供 OTLP 导出器配置和 Trace SDK 生命周期管理

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Literal, cast

logger = logging.getLogger(__name__)

# 协议类型
OtlpProtocol = Literal["grpc", "http/protobuf", "http/json"]


@dataclass
class OtelConfig:
    """OpenTelemetry OTLP 导出器配置

    从环境变量读取，支持 gRPC/HTTP 协议切换
    默认关闭（EVENT_BUS_OTEL_TRACE_ENABLED=false）

    Attributes:
        trace_enabled: 是否启用 Trace（默认 false）
        endpoint: OTLP 端点（默认 "http://localhost:4317" for gRPC）
        protocol: OTLP 协议（grpc | http/protobuf | http/json）
        service_name: 服务名称（默认 "sisys-event-bus"）
        service_version: 服务版本（默认 "0.1.0"）
        deployment_environment: 部署环境（默认 "development"）
        sampler_ratio: 采样率 0.0-1.0（默认 0.1，即 10%）
        batch_max_queue_size: BatchSpanProcessor 最大队列大小（默认 2048）
        batch_max_export_batch_size: 单次导出批量大小（默认 512）
        batch_schedule_delay_millis: 导出调度延迟（毫秒，默认 5000）
        export_timeout_millis: 导出超时时间（毫秒，默认 30000）
    """

    trace_enabled: bool = False
    endpoint: str = ""
    protocol: OtlpProtocol = "grpc"
    service_name: str = "sisys-event-bus"
    service_version: str = "0.1.0"
    deployment_environment: str = "development"
    sampler_ratio: float = 0.1
    batch_max_queue_size: int = 2048
    batch_max_export_batch_size: int = 512
    batch_schedule_delay_millis: int = 5000
    export_timeout_millis: int = 30000

    @classmethod
    def from_env(cls) -> OtelConfig:
        """从环境变量创建配置

        支持的环境变量:
        - EVENT_BUS_OTEL_TRACE_ENABLED: bool (default: false)
        - OTEL_EXPORTER_OTLP_ENDPOINT: str (default: "http://localhost:4317")
        - OTEL_EXPORTER_OTLP_PROTOCOL: str (default: "grpc")
        - OTEL_SERVICE_NAME: str (default: "sisys-event-bus")
        - OTEL_TRACES_SAMPLER_ARG: float (default: 0.1)
        - OTEL_DEPLOYMENT_ENVIRONMENT: str (default: "development")

        Returns:
            OtelConfig 实例
        """
        trace_enabled = os.getenv("EVENT_BUS_OTEL_TRACE_ENABLED", "false").lower() == "true"
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc").lower()
        service_name = os.getenv("OTEL_SERVICE_NAME", "sisys-event-bus")
        deployment_env = os.getenv("OTEL_DEPLOYMENT_ENVIRONMENT", "development")

        # H-01 修复: float() 解析使用 try/except 防止非数字值抛出未捕获异常
        try:
            sampler_ratio = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1"))
        except (ValueError, TypeError):
            logger.warning("Invalid OTEL_TRACES_SAMPLER_ARG, defaulting to 0.1")
            sampler_ratio = 0.1

        # 如果 endpoint 为空，根据协议设置默认值
        if not endpoint:
            endpoint = "http://localhost:4317" if protocol == "grpc" else "http://localhost:4318/v1/traces"

        # 验证协议类型
        if protocol not in ("grpc", "http/protobuf", "http/json"):
            logger.warning("Invalid OTLP protocol '%s', defaulting to 'grpc'", protocol)
            protocol = "grpc"

        # 验证采样率
        if not 0.0 <= sampler_ratio <= 1.0:
            logger.warning("Invalid sampler ratio '%s', defaulting to 0.1", sampler_ratio)
            sampler_ratio = 0.1

        return cls(
            trace_enabled=trace_enabled,
            endpoint=endpoint,
            protocol=cast(OtlpProtocol, protocol),
            service_name=service_name,
            deployment_environment=deployment_env,
            sampler_ratio=sampler_ratio,
        )

    def get_endpoint_for_protocol(self) -> str:
        """获取协议对应的默认端点 URL

        Returns:
            端点 URL 字符串
        """
        if not self.endpoint:
            if self.protocol == "grpc":
                return "http://localhost:4317"
            return "http://localhost:4318/v1/traces"
        return self.endpoint


@dataclass
class BatchExportConfig:
    """批量导出配置

    Attributes:
        max_queue_size: 最大队列大小（默认 2048）
        max_export_batch_size: 单次导出批量大小（默认 512）
        schedule_delay_millis: 导出调度延迟（毫秒，默认 5000）
        export_timeout_millis: 导出超时时间（毫秒，默认 30000）
    """

    max_queue_size: int = 2048
    max_export_batch_size: int = 512
    schedule_delay_millis: int = 5000
    export_timeout_millis: int = 30000

    def validate(self) -> None:
        """验证配置合法性

        Raises:
            ValueError: 配置不合法时抛出
        """
        if self.max_queue_size <= 0:
            raise ValueError(f"max_queue_size must be positive, got {self.max_queue_size}")
        if self.max_export_batch_size <= 0:
            raise ValueError(f"max_export_batch_size must be positive, got {self.max_export_batch_size}")
        if self.max_export_batch_size > self.max_queue_size:
            raise ValueError(
                f"max_export_batch_size ({self.max_export_batch_size}) must be <= max_queue_size ({self.max_queue_size})"
            )
        if self.schedule_delay_millis <= 0:
            raise ValueError(f"schedule_delay_millis must be positive, got {self.schedule_delay_millis}")
        if self.export_timeout_millis <= 0:
            raise ValueError(f"export_timeout_millis must be positive, got {self.export_timeout_millis}")


# ============================================================================
# OpenTelemetry 生命周期
# ============================================================================

_init_lock = threading.Lock()
_initialized = False
_tracer_provider = None
_failed = False


def init(config: OtelConfig | None = None) -> bool:
    """初始化 OpenTelemetry SDK

    配置 OTLP 导出器、BatchSpanProcessor、采样策略和 Resource 属性
    线程安全：重复调用返回缓存状态，不会重复初始化

    Args:
        config: OtelConfig 实例，如果为 None 则从环境变量读取

    Returns:
        是否成功初始化（True=成功, False=禁用或失败）
    """
    global _initialized, _tracer_provider, _failed  # noqa: PLW0603

    with _init_lock:
        if _initialized or _failed:
            return _tracer_provider is not None

        if config is None:
            config = OtelConfig.from_env()

        if not config.trace_enabled:
            logger.info("OpenTelemetry tracing is disabled (EVENT_BUS_OTEL_TRACE_ENABLED=false)")
            _initialized = True
            return False

    # 在锁外执行实际初始化，避免长时间持有锁（导出器连接可能很慢）
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        resource = Resource.create(
            {
                "service.name": config.service_name,
                "service.version": config.service_version,
                "deployment.environment": config.deployment_environment,
            },
        )

        sampler = TraceIdRatioBased(config.sampler_ratio)
        provider = TracerProvider(resource=resource, sampler=sampler)

        exporter: Any = None
        if config.protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter as GRPCExporter,
            )

            exporter = GRPCExporter(endpoint=config.get_endpoint_for_protocol())
        elif config.protocol in ("http/protobuf", "http/json"):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter as HTTPExporter,
            )

            exporter = HTTPExporter(endpoint=config.get_endpoint_for_protocol())
        else:
            logger.warning("Unsupported OTLP protocol: %s, defaulting to gRPC", config.protocol)
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter as GRPCExporter,
            )

            exporter = GRPCExporter(endpoint=config.get_endpoint_for_protocol())

        batch_config = BatchExportConfig(
            max_queue_size=config.batch_max_queue_size,
            max_export_batch_size=config.batch_max_export_batch_size,
            schedule_delay_millis=config.batch_schedule_delay_millis,
            export_timeout_millis=config.export_timeout_millis,
        )
        batch_config.validate()

        processor = BatchSpanProcessor(
            exporter,
            max_queue_size=batch_config.max_queue_size,
            max_export_batch_size=batch_config.max_export_batch_size,
            schedule_delay_millis=batch_config.schedule_delay_millis,
            export_timeout_millis=batch_config.export_timeout_millis,
        )

        provider.add_span_processor(processor)

        with _init_lock:
            trace.set_tracer_provider(provider)
            _tracer_provider = provider
            _initialized = True

        logger.info(
            "OpenTelemetry tracing initialized: protocol=%s, endpoint=%s, sampler_ratio=%.2f, batch_size=%d",
            config.protocol,
            config.get_endpoint_for_protocol(),
            config.sampler_ratio,
            batch_config.max_export_batch_size,
        )
        return True

    except ImportError as e:
        logger.warning("OpenTelemetry OTLP exporter not installed: %s", e)
        with _init_lock:
            _failed = True
        return False
    except Exception as e:
        logger.error("Failed to initialize OpenTelemetry: %s", e)
        with _init_lock:
            _failed = True
        return False


def shutdown(timeout: int = 5) -> None:
    """优雅关闭 OpenTelemetry，刷新缓冲区中的 spans

    应在应用退出前调用（或通过 atexit 自动调用）
    调用后全局状态被重置，允许后续重新初始化

    Args:
        timeout: force_flush 的超时时间（秒）
    """
    global _initialized, _tracer_provider, _failed  # noqa: PLW0603

    if _tracer_provider is not None:
        try:
            _tracer_provider.force_flush(timeout_millis=timeout * 1000)
            _tracer_provider.shutdown()
            logger.info("OpenTelemetry tracer shut down gracefully")
        except Exception as e:
            logger.warning("Error during OpenTelemetry shutdown: %s", e)

    with _init_lock:
        _initialized = False
        _failed = False
        _tracer_provider = None


# 注册 atexit 处理器，确保进程退出时刷新缓冲区
atexit.register(shutdown)


def get_tracer_provider() -> Any | None:
    """获取全局 TracerProvider

    Returns:
        TracerProvider 实例或 None
    """
    return _tracer_provider


def reset_for_testing() -> None:
    """重置 OpenTelemetry 状态（仅用于测试隔离）

    ⚠️ 仅用于测试环境，生产环境禁止调用
    H-04 修复: 同时重置 OpenTelemetry SDK 内部的全局状态
    """
    global _initialized, _tracer_provider, _failed  # noqa: PLW0603

    if _tracer_provider is not None:
        try:
            _tracer_provider.shutdown()
        except Exception:
            pass

    _initialized = False
    _failed = False
    _tracer_provider = None

    # 重置 OpenTelemetry 内部全局状态，允许后续重新初始化
    try:
        from opentelemetry import trace

        trace._TRACER_PROVIDER = None  # noqa: SLF001 (内部 API，测试隔离必需)
    except (ImportError, AttributeError):
        pass
