"""熔断器（Circuit Breaker）

保护外部服务不被持续调用，防止连锁故障（Cascading Failure）。
当连续失败达到阈值时"断开"（Open），后续请求快速失败；
经过恢复超时后"半开"（Half-Open），允许少量探测请求；
探测成功则"闭合"（Closed），恢复正常通行。

状态机：
  Closed ──(连续失败 ≥ threshold)──→ Open
  Open ──(等待 recovery_timeout)──→ Half-Open
  Half-Open ──(探测成功 ≥ success_threshold)──→ Closed
  Half-Open ──(探测失败)──→ Open

线程安全：使用 threading.Lock 保护所有状态变更。
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """熔断器状态"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """熔断器断开异常：请求被快速拒绝，未实际调用外部服务

    Attributes:
        message: 异常描述
        retry_after: 建议的重试等待时间（秒）
    """

    def __init__(self, message: str = "", retry_after: float = 0.0) -> None:
        self.retry_after = retry_after
        super().__init__(message or f"熔断器已断开，建议 {retry_after:.0f} 秒后重试")


class CircuitBreaker:
    """熔断器

    监控外部服务调用失败率，在服务不可用时快速失败而非继续等待超时。

    Args:
        failure_threshold: 连续失败次数阈值，达到后熔断断开
        recovery_timeout: 熔断后等待秒数，之后进入半开状态
        half_open_max_calls: 半开状态允许的最大探测请求数
        name: 熔断器名称（日志标识）
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
        name: str = "default",
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold 必须 ≥ 1")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout 必须为正数")
        if half_open_max_calls < 1:
            raise ValueError("half_open_max_calls 必须 ≥ 1")

        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        self._name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """当前熔断器状态（线程安全读取）"""
        with self._lock:
            return self._state

    @property
    def name(self) -> str:
        return self._name

    def _now(self) -> float:
        """获取当前时间（可被子类重写用于测试）"""
        return time.monotonic()

    def _should_open(self) -> bool:
        """判断是否达到熔断阈值"""
        return self._failure_count >= self._failure_threshold

    def _should_half_open(self) -> bool:
        """判断是否满足半开条件"""
        return (self._now() - self._last_failure_time) >= self._recovery_timeout

    def _transition_to_open(self) -> None:
        """Closed → Open 或 Half-Open → Open"""
        self._state = CircuitState.OPEN
        self._failure_count = 0
        self._half_open_calls = 0
        logger.warning(
            "熔断器 [%s] 已断开 (Open)，将在 %.0fs 后尝试半开探测",
            self._name,
            self._recovery_timeout,
        )

    def _transition_to_half_open(self) -> None:
        """Open → Half-Open"""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        logger.info("熔断器 [%s] 进入半开状态 (Half-Open)，允许探测请求", self._name)

    def _transition_to_closed(self) -> None:
        """Half-Open → Closed"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        logger.info("熔断器 [%s] 已恢复 (Closed)", self._name)

    def before_call(self) -> None:
        """调用外部服务前检查熔断器状态

        Raises:
            CircuitBreakerOpenError: 熔断器闭合且未满足半开条件时
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return  # 正常通行

            if self._state == CircuitState.OPEN:
                if self._should_half_open():
                    self._transition_to_half_open()
                    # 转为半开时消耗一个探测配额
                    self._half_open_calls = 1
                    return  # 允许当前请求通过作为探测
                raise CircuitBreakerOpenError(
                    f"熔断器 [{self._name}] 已断开",
                    retry_after=self._recovery_timeout - (self._now() - self._last_failure_time),
                )

            # Half-Open 状态：限制并发探测数
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self._half_open_max_calls:
                    self._half_open_calls += 1
                    return
                raise CircuitBreakerOpenError(
                    f"熔断器 [{self._name}] 半开状态，探测请求已达上限",
                    retry_after=self._recovery_timeout,
                )

    def on_success(self) -> None:
        """调用外部服务成功时记录"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0  # 连续失败计数清零

    def on_failure(self) -> None:
        """调用外部服务失败时记录"""
        with self._lock:
            self._last_failure_time = self._now()

            if self._state == CircuitState.HALF_OPEN:
                # 半开探测失败 → 立即回到断开
                self._transition_to_open()
                return

            if self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._should_open():
                    self._transition_to_open()

    def reset(self) -> None:
        """手动重置熔断器到闭合状态（用于恢复或测试）"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0
            self._half_open_calls = 0
            logger.info("熔断器 [%s] 已手动重置为 Closed", self._name)

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"CircuitBreaker(name={self._name!r}, state={self._state.value}, "
                f"failures={self._failure_count}, "
                f"last_failure_age={self._now() - self._last_failure_time:.1f}s)"
            )
