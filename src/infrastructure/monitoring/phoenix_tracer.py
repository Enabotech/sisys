"""基础设施层 Phoenix 追踪器模块（Story 5.7 — FR-EV-01 追踪面）

AgentTracingPort 实现——基于仓内既有 opentelemetry ^1.21.0（实锁 1.44.0）实现
同构追踪语义（OD-1——arize-phoenix 不引入）：project_name 经 OTel Resource
service.name 承载（Phoenix OTLP 接收端按 service.name 归项目），span 经
OTLP gRPC exporter 指向独立部署的 Phoenix server。

生命周期双模板合成：initialize/shutdown 同构照抄 otel_config（init L167/
shutdown L277 先例）；create_span 降级骨架同构 event_metrics（L227-273——
未启用 yield None 零开销降级）。**差异五项**：
①attributes 参数化；②tracer 双源解析（注入 provider 优先经 tracer_provider=
形参——R2-1，None 降级判据是「无 tracer 来源」非「未 initialize」）；
③handle 返回 OTel Span 原生对象（duck-type SpanHandle 协议零包装层）；
④构造器零全局副作用（R3-13——event_metrics 模板构造器在 enabled 时调 init()
设全局是照抄陷阱；本类构造器纯赋值，全局动作唯一在 initialize()）；
⑤**try 收窄至装配段**（R1-F1——event_metrics 模板把 yield 罩在 except 内，
消费方在 with 体内抛出的业务异常被吞并替换为 RuntimeError；本类 try 只罩
tracer 解析段，yield 两个出口（None 降级/真 span）均在 try 外，消费方异常
原样穿透——OTel use_span __exit__ 兜底 record_exception + set ERROR）。

reset_for_testing 双复位是本模块对既有先例的必要增强（非照抄）：锁定的
OTel 1.44.0 全局 set 受 Once 闩锁（trace._TRACER_PROVIDER_SET_ONCE）约束，
otel_config.reset_for_testing 单复位形态（仅 trace._TRACER_PROVIDER = None）
不恢复 re-set 能力——同进程后续 set 仍被静默忽略；双复位 = 变量复位 +
Once 闩锁重建（主会话探针实证此形态 re-set 恢复工作）。

OTel 全局状态治理（DC-5）：生产面全局 set_tracer_provider 的唯一通道 =
本类 initialize()（默认配置下唯一激活 setter——otel_config.init 是 env 门控
休眠第二调用点；R3 注：bootstrap 内本接线是 eager 调用而 event-bus 栈
otel_config.init 是 lazy resolve 触发——双栈同开时本类恒先 set，生产串流
方向为 event-bus span 经全局 provider 流入 Phoenix 端点）。initialize 开头
已 set 检测（非 proxy 态且非本实例所 set → logger.warning 显式提示，杜绝
静默双 setter——OTel 二次 set 仅告警不抛）。ops env 前提（R3 治理注记）：
进程 env 带 OTEL_PYTHON_TRACER_PROVIDER 时 OTel API 会在 _TRACER_PROVIDER
为 None 态经 entry-point 装配非 proxy provider——initialize 走外来 set 分支
（warning + True），span 经 env 配置的 provider 导出（端点/采样由 OTEL_* env
决定——部署面须管住该变量）。
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
        追踪可用，全局保持他方设置；⚠️ R1-F10 披露：此时 span 经他方 provider
        导出，本实例 project_name/endpoint/sampling 配置不生效——返回 True 仅
        表示「span 会被记录」而非「导出到 Phoenix 端点」）。enabled=false 返回
        False 不装配不设全局（NoOp 天然降级）；装配段异常（含 OTel import
        失败）降级 False 不阻断主链（R1-F9）。R3 披露：initialize 返回 False
        （禁用/失败）**不门控 create_span**——降级态下全局被外来设置时
        create_span 照产真 span（走外来 provider，双源解析契约语义）。

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

        try:
            # 装配段整体入 try（R1-F9——OTel import/全局探测异常一律降级 False，
            # 不击穿组合根 _wire 的 except ConfigurationError 防线阻断主链启动）
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

        退出延迟语义（R3-1 修正——OTel 1.44.0 实测源码级归因）：timeout_sec
        形参传入 force_flush 但 **BatchProcessor.force_flush 静默忽略超时**
        （`_shared_internal` 源码 `# TODO: Fix force flush so the timeout is
        used #4568`——阻塞至全部缓冲批次导出完成）。实际退出上界 =
        ⌈queue 2048 / batch 512⌉ 批 ×（gRPC deadline 默认 10s
        [OTEL_EXPORTER_OTLP_TIMEOUT] + 重试退避）+ BSP worker join 30s——
        端点不可达（黑洞）时最坏**百秒级**（R1-F18 的「~35s 上限」系统性低估，
        勘误）；端点正常时毫秒级。运维封顶通道（本类零参 BSP/exporter 构造，
        经 OTel 环境变量暗消费生效）：OTEL_EXPORTER_OTLP_TIMEOUT（gRPC
        deadline）/ OTEL_BSP_EXPORT_TIMEOUT / OTEL_BSP_MAX_QUEUE_SIZE。
        关停后 create_span 仍产真 span 但 BSP.emit 静默丢弃（INFO 日志）——
        良性终态。正常解释器退出另有 TracerProvider 默认 shutdown_on_exit
        的 atexit 钩子（本方法与 atexit 双调安全——provider.shutdown 幂等 +
        本方法自带异常降级 + provider.shutdown 自带 atexit.unregister）；
        SIGTERM/SIGKILL 不经 atexit，组合根 shutdown() 的显式调用是信号退出
        路径的刷盘加固（见 composition_root.shutdown 接线——注意该调用在
        连接管理器关闭之前，挂起的 flush 会顺延后续清理，超时语义见上）。

        Args:
            timeout_sec: force_flush 超时（秒——1.44.0 下被 BSP 忽略，见上）
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
        """span 生命周期上下文（双源解析 + 零开销降级——R1-F1 修复形态）。

        异常语义边界（R1-F1——try 只罩装配段）：tracer 解析段（OTel import/
        全局探测/get_tracer）异常时 logger.warning 降级 yield None（绝不上抛
        ——DC-7 追踪失败不影响主链）；span 进入段与消费方段异常**原样穿透**
        （消费方在 with 体内抛出的业务异常不是追踪抛出面——OTel use_span
        __exit__ 自动 record_exception + set ERROR 后透传，本方法零拦截零改写）。

        Args:
            name: span 名称（SpanNames 常量——agent_execution 根 / agent.{phase} 子）
            attributes: 进入时批量写入的属性（可选）

        Yields:
            SpanHandle（OTel Span 原生对象——duck-type 协议零包装）；
            无可用 tracer 来源（未注入且未 initialize）或装配段异常时
            yield None（消费方判 None 走旁路——两个降级出口均在 try 外，
            消费方异常不因此被吞）
        """
        degraded = False
        tracer = None
        try:
            from opentelemetry import trace as otel_trace

            if self._provider is None and _is_proxy_provider(otel_trace.get_tracer_provider()):
                degraded = True  # 零开销降级（R2-1——降级判据是「无 tracer 来源」非「未 initialize」）
            else:
                tracer = otel_trace.get_tracer("sisys.agent", tracer_provider=self._provider)
        except Exception as error:  # DC-7 装配段降级（warning + None，绝不上抛）
            logger.warning("PhoenixTracer create_span 降级（span=%s）: %s", name, error)
            degraded = True
        if degraded or tracer is None:  # or 短语使 tracer 完成非 None 收窄（mypy union-attr 根因修复）
            yield None  # 降级出口在 try 外（R1-F1）——消费方异常经此点原样穿透不被吞
            return
        with tracer.start_as_current_span(name) as span:
            for key, value in (attributes or {}).items():
                span.set_attribute(key, value)
            yield span  # 消费方异常经 OTel __exit__ 记录后原样穿透（R1-F1）

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
