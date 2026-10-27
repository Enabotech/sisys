"""应用层 @trace 装饰器（Story 5.7 — FR-EV-01 追踪面）

async 方法装饰器——OTel 全局 API 手动插桩（application 侧标准形态：装饰器在
类定义时静态求值无构造注入通道，全局 get_tracer 是 OTel 官方应用侧插桩入口；
initialize 归组合根/bootstrap 职责——DC-3/DC-5 分层互证合规）。

NoOp 天然降级：全局 provider 未 set 时 OTel 返回 proxy tracer → span 操作空转
零开销零异常（比 enabled 判断更彻底——provider set 后 proxy 自动升级为真
tracer）。仅支持 async 函数（接入面全 async——YAGNI，同步支持不提供）。
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

#: 插桩名（与 PhoenixTracer.create_span 同源——sisys.agent 命名空间）
_INSTRUMENTING_NAME = "sisys.agent"


def trace(
    span_name: str,
    attributes: dict[str, Any] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """async 方法追踪装饰器（span 生命周期包裹 + 异常记录 + 零吞异常透传）。

    用法（5-7 工作链接入形态）::

        @trace(SpanNames.AGENT_EXECUTION)
        async def execute(self, agent_id: UUID, task: str) -> AgentWorkflowResult: ...

        @trace(f"{SpanNames.PHASE_PREFIX}perceive")
        async def perceive(self, state: dict[str, Any]) -> PerceptionResult: ...

    Args:
        span_name: span 名称（SpanNames 常量——agent_execution 根 /
            agent.{phase} 子，末段对齐 executed_phases 枚举）
        attributes: 进入 span 时批量写入的属性（可选——静态属性；动态业务
            属性经方法体内 get_current_span().set_attribute 写入[DC-4]）

    Returns:
        装饰器——functools.wraps 保签名（__name__/__doc__/__wrapped__ 保留，
        ParamSpec 泛型签名不窄化——存量单测兼容前提）
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            from opentelemetry.trace import StatusCode, get_tracer

            tracer = get_tracer(_INSTRUMENTING_NAME)  # 全局 API——未 set 时 proxy→NoOp 空转零开销
            with tracer.start_as_current_span(span_name) as span:
                for key, value in (attributes or {}).items():
                    span.set_attribute(key, value)
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(StatusCode.ERROR)  # OTel 原生调用（status 置位唯一发生处——R1-③）
                    raise  # 零吞异常：装饰器不改异常语义（原样上抛）

        return wrapper

    return decorator


__all__ = ["trace"]
