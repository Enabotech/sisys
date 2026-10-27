"""基础设施层 Phoenix 追踪器模块（Story 5.7 — FR-EV-01 追踪面）

AgentTracingPort 实现——基于仓内既有 opentelemetry ^1.21.0（实锁 1.44.0）实现
同构追踪语义（OD-1——arize-phoenix 不引入）：project_name 经 OTel Resource
service.name 承载（Phoenix OTLP 接收端按 service.name 归项目），span 经
OTLP gRPC exporter 指向独立部署的 Phoenix server。

生命周期双模板合成：initialize/shutdown 同构照抄 otel_config（init L167/
shutdown L277 先例）；create_span 降级骨架同构 event_metrics（L227-273——
未启用 yield None 零开销降级 + ImportError/Exception 双降级）。**差异四项**：
①attributes 参数化；②tracer 双源解析（注入 provider 优先经 tracer_provider=
形参——R2-1，None 降级判据是「无 tracer 来源」非「未 initialize」）；
③handle 返回 OTel Span 原生对象（duck-type SpanHandle 协议零包装层）；
④构造器零全局副作用（R3-13——event_metrics 模板构造器在 enabled 时调 init()
设全局是照抄陷阱；本类构造器纯赋值，全局动作唯一在 initialize()）。

reset_for_testing 双复位是本模块对既有先例的必要增强（非照抄）：锁定的
OTel 1.44.0 全局 set 受 Once 闩锁（trace._TRACER_PROVIDER_SET_ONCE）约束，
otel_config.reset_for_testing 单复位形态（仅 trace._TRACER_PROVIDER = None）
不恢复 re-set 能力——同进程后续 set 仍被静默忽略；双复位 = 变量复位 +
Once 闩锁重建（主会话探针实证此形态 re-set 恢复工作）。

OTel 全局状态治理（DC-5）：生产面全局 set_tracer_provider 的唯一通道 =
本类 initialize()（默认配置下唯一激活 setter——otel_config.init 是 env 门控
休眠第二调用点）；initialize 开头已 set 检测（非 proxy 态且非本实例所 set →
logger.warning 显式提示，杜绝静默双 setter——OTel 二次 set 仅告警不抛）。
"""

from __future__ import annotations

import atexit
import logging
from contextlib import contextmanager
from typing import Any, Generator

from src.infrastructure.config.phoenix import PhoenixConfig

logger = logging.getLogger(__name__)


def _is_proxy_provider(provider: Any) -> bool:
    """全局 TracerProvider 是否处于 proxy（未 set）态。

    Args:
        provider: get_tracer_provider() 返回值

    Returns:
        True 表示全局未 set（OTel API 返回 ProxyTracerProvider——1.44 公开导出类）
    """
    try:
        from opentelemetry.trace import ProxyTracerProvider

        return isinstance(provider, ProxyTracerProvider)
    except ImportError:  # pragma: no cover —— 公开类名防御回退（版本兼容）
        return type(provider).__name__ == "ProxyTracerProvider"


class PhoenixTracer:
    """Phoenix 全链路追踪器（AgentTracingPort 实现——OTel SDK 原生承载）。

    Attributes:
        _config: PhoenixConfig 配置（构造期定格——SINGLETON 实例 env 后置变更
            不经 resolve 传导，设计事实见 5-7 DC-9）
        _provider: TracerProvider（注入优先；未注入时 initialize 自建——生产
            形态 Resource service.name + TraceIdRatioBased + BatchSpanProcessor
            + OTLP gRPC exporter）
    """

    def __init__(self, config: PhoenixConfig | None = None, tracer_provider: Any = None) -> None:
        """初始化追踪器（纯赋值——零全局副作用，全局动作唯一在 initialize）。

        Args:
            config: 配置（None 时 from_env——组合根 lambda 形态）
            tracer_provider: 注入 TracerProvider（测试/组件级注入通道——注入后
                create_span 无需 initialize 即产真 span，R2-1 双源解析）
        """
        if config is None:
            config = PhoenixConfig.from_env()
        self._config = config
        self._provider = tracer_provider
        self._initialized = False
        self._init_result: bool | None = None
        self._atexit_registered = False

    def initialize(self) -> bool:
        """配置全局 TracerProvider（幂等——实例闩 + 外来 set 检测）。

        实例闩（R2-9）：同实例再入静默返回既有结果；外来 set 检测：全局已非
        proxy 态且非本实例所 set 时 logger.warning 并返回既有状态（True——
        追踪可用，全局保持他方设置）。enabled=false 返回 False 不装配不设全局
        （NoOp 天然降级）。

        Returns:
            是否实际启用（True=已启用；False=禁用或初始化失败降级）
        """
        if self._initialized:
            return bool(self._init_result)  # 实例闩：同实例再入静默（无告警）
        if not self._config.enabled:
            self._initialized = True
            self._init_result = False
            logger.info("Phoenix 追踪未启用（PHOENIX_TRACING_ENABLED=false——NoOp 零开销降级）")
            return False

        from opentelemetry import trace as otel_trace

        current = otel_trace.get_tracer_provider()
        if not _is_proxy_provider(current) and current is not self._provider:
            logger.warning(
                "全局 TracerProvider 已被他方设置（PhoenixTracer.initialize 是默认配置下唯一激活 setter——"
                "event-bus OTel 同开时须先解决 setter 归一，见 5-7 DC-5/风险表#1）；保留既有全局状态"
            )
            self._initialized = True
            self._init_result = True
            return True

        try:
            if self._provider is None:
                self._provider = self._build_production_provider()
            otel_trace.set_tracer_provider(self._provider)
        except Exception as error:  # DC-7 追踪失败降级（初始化失败返回 False 不阻断主链）
            logger.warning("PhoenixTracer initialize 失败降级（NoOp 态）: %s", error)
            self._initialized = True
            self._init_result = False
            return False

        if not self._atexit_registered:
            atexit.register(self.shutdown)
            self._atexit_registered = True
        self._initialized = True
        self._init_result = True
        logger.info(
            "Phoenix 追踪已启用: project_name=%s endpoint=%s sampling_ratio=%.2f",
            self._config.project_name,
            self._config.endpoint,
            self._config.sampling_ratio,
        )
        return True

    def _build_production_provider(self) -> Any:
        """自建生产 TracerProvider（Resource service.name + 采样 + Batch + OTLP gRPC）。

        Returns:
            装配完成的 TracerProvider（service.name 承载 project_name——OD-1 映射）
        """
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        resource = Resource.create({"service.name": self._config.project_name})
        sampler = TraceIdRatioBased(self._config.sampling_ratio)
        provider = TracerProvider(resource=resource, sampler=sampler)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=self._config.endpoint)))
        return provider

    def shutdown(self, timeout_sec: int = 5) -> None:
        """刷盘并释放（BatchSpanProcessor 缓冲 span force_flush 后 shutdown）。

        Args:
            timeout_sec: force_flush 超时（秒）
        """
        if self._provider is None:
            return
        try:
            self._provider.force_flush(timeout_millis=timeout_sec * 1000)
            self._provider.shutdown()
            logger.info("Phoenix 追踪器已优雅关闭")
        except Exception as error:  # 关闭路径降级（退出阶段不上抛）
            logger.warning("PhoenixTracer shutdown 异常降级: %s", error)

    @contextmanager
    def create_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Any, None, None]:
        """span 生命周期上下文（双源解析 + 零开销降级——DC-7 零抛出契约）。

        Args:
            name: span 名称（SpanNames 常量——agent_execution 根 / agent.{phase} 子）
            attributes: 进入时批量写入的属性（可选）

        Yields:
            SpanHandle（OTel Span 原生对象——duck-type 协议零包装）；
            无可用 tracer 来源（未注入且未 initialize）时 yield None；
            OTel 异常降级时 yield None（logger.warning 绝不上抛）
        """
        from opentelemetry import trace as otel_trace

        if self._provider is None and _is_proxy_provider(otel_trace.get_tracer_provider()):
            yield None  # 零开销降级（R2-1——降级判据是「无 tracer 来源」非「未 initialize」）
            return
        try:
            tracer = otel_trace.get_tracer("sisys.agent", tracer_provider=self._provider)
            with tracer.start_as_current_span(name) as span:
                for key, value in (attributes or {}).items():
                    span.set_attribute(key, value)
                yield span
        except Exception as error:  # DC-7 追踪失败降级（warning + None，绝不上抛）
            logger.warning("PhoenixTracer create_span 降级（span=%s）: %s", name, error)
            yield None

    @staticmethod
    def reset_for_testing() -> None:
        """重置 OTel 全局状态（仅测试隔离用——双复位形态）。

        双复位：trace._TRACER_PROVIDER = None + _TRACER_PROVIDER_SET_ONCE = Once()
        重建——锁定的 OTel 1.44.0 Once 闩锁下单复位（仅变量复位）不恢复 re-set
        能力，同进程后续 initialize 的 set 会被静默忽略（#8639 类污染根源）。
        防御降级路径必须 logger.warning（防御不等于静默——R2-11：OTel 大版本
        升级改内部形态时以响亮信号暴露而非测试莫名串扰）。
        """
        try:
            from opentelemetry import trace as otel_trace
        except ImportError:  # pragma: no cover —— OTel 为硬依赖不可缺；防御形态对齐 otel_config 先例
            return
        otel_trace._TRACER_PROVIDER = None  # 测试隔离必需（opentelemetry 内部状态复位——otel_config L337 先例同款）
        once_attr = getattr(otel_trace, "_TRACER_PROVIDER_SET_ONCE", None)
        if once_attr is None:
            logger.warning(
                "opentelemetry 缺少 _TRACER_PROVIDER_SET_ONCE 闩锁属性（版本形态变化）——"
                "reset_for_testing 复位形态需复核（R2-11 防御信号）"
            )
            return
        try:
            from opentelemetry.util._once import Once

            otel_trace._TRACER_PROVIDER_SET_ONCE = Once()  # Once 闩锁重建（双复位第二腿——1.44.0 实证形态）
        except ImportError:  # pragma: no cover —— 防御降级必须 warning（R2-11——防御不等于静默）
            logger.warning("opentelemetry.util._once 导入失败——Once 闩锁未重建，re-set 能力未恢复（R2-11 防御信号）")


__all__ = ["PhoenixTracer"]
