"""Circuit Breaker 单元测试

验证熔断器状态机：Closed → Open → Half-Open → Closed 循环。
使用 mock 时间控制来加速恢复超时测试。
"""

from __future__ import annotations

import time

import pytest

from src.infrastructure.external_services.embedding.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


class TestCircuitBreakerInit:
    """熔断器初始化"""

    def test_default_params(self) -> None:
        """默认参数正确初始化"""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.name == "default"

    def test_custom_params(self) -> None:
        """自定义参数正确初始化"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0, half_open_max_calls=2, name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.name == "test"

    def test_invalid_threshold_raises(self) -> None:
        """failure_threshold < 1 抛出 ValueError"""
        with pytest.raises(ValueError, match="failure_threshold"):
            CircuitBreaker(failure_threshold=0)

    def test_invalid_recovery_timeout_raises(self) -> None:
        """recovery_timeout <= 0 抛出 ValueError"""
        with pytest.raises(ValueError, match="recovery_timeout"):
            CircuitBreaker(recovery_timeout=0)

    def test_invalid_half_open_max_calls_raises(self) -> None:
        """half_open_max_calls < 1 抛出 ValueError"""
        with pytest.raises(ValueError, match="half_open_max_calls"):
            CircuitBreaker(half_open_max_calls=0)


class TestCircuitBreakerClosedState:
    """Closed 状态行为"""

    def test_before_call_returns_when_closed(self) -> None:
        """Closed 状态 before_call 正常返回"""
        cb = CircuitBreaker()
        cb.before_call()  # 不抛异常

    def test_success_resets_failure_count(self) -> None:
        """成功调用清零连续失败计数"""
        cb = CircuitBreaker(failure_threshold=3)
        cb.on_failure()
        cb.on_failure()
        cb.on_success()
        # 内部 _failure_count 应为 0
        assert cb._failure_count == 0

    def test_failure_counts_to_threshold(self) -> None:
        """连续失败达到阈值后状态变为 Open"""
        cb = CircuitBreaker(failure_threshold=3)
        cb.on_failure()
        assert cb.state == CircuitState.CLOSED
        cb.on_failure()
        assert cb.state == CircuitState.CLOSED
        cb.on_failure()
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerOpenState:
    """Open 状态行为"""

    def test_before_call_raises_when_open(self) -> None:
        """Open 状态 before_call 抛出 CircuitBreakerOpenError"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.on_failure()  # 触发 Open
        with pytest.raises(CircuitBreakerOpenError, match="已断开"):
            cb.before_call()

    def test_on_failure_in_open_stays_open(self) -> None:
        """Open 状态 on_failure 保持 Open 并更新失败时间"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.on_failure()  # Closed → Open
        old_time = cb._last_failure_time
        cb.on_failure()  # 仍 Open
        assert cb.state == CircuitState.OPEN
        assert cb._last_failure_time >= old_time

    def test_on_success_in_open_does_nothing(self) -> None:
        """Open 状态 on_success 不改变状态"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.on_failure()  # → Open
        assert cb.state == CircuitState.OPEN
        cb.on_success()
        assert cb.state == CircuitState.OPEN  # 仍为 Open


class TestCircuitBreakerHalfOpenState:
    """Half-Open 状态行为"""

    def test_opens_after_recovery_timeout(self) -> None:
        """Open 状态经过 recovery_timeout 后 before_call 进入 Half-Open"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.on_failure()  # → Open
        time.sleep(0.02)  # 等待超时
        cb.before_call()  # 应转为 Half-Open
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self) -> None:
        """Half-Open 探测成功回到 Closed"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.on_failure()  # → Open
        time.sleep(0.02)
        cb.before_call()  # → Half-Open
        cb.on_success()  # → Closed
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self) -> None:
        """Half-Open 探测失败回到 Open"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.on_failure()  # → Open
        time.sleep(0.02)
        cb.before_call()  # → Half-Open
        cb.on_failure()  # → Open
        assert cb.state == CircuitState.OPEN

    def test_half_open_max_calls_limited(self) -> None:
        """Half-Open 限制探测请求数"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01, half_open_max_calls=1)
        cb.on_failure()  # → Open
        time.sleep(0.02)
        # 第一次 before_call 转为 Half-Open 并允许探测
        cb.before_call()
        assert cb.state == CircuitState.HALF_OPEN
        # 第二次 before_call 应拒绝（超过 half_open_max_calls）
        with pytest.raises(CircuitBreakerOpenError, match="半开"):
            cb.before_call()


class TestCircuitBreakerManualReset:
    """手动重置"""

    def test_reset_returns_to_closed(self) -> None:
        """reset() 从 Open 回到 Closed"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.on_failure()  # → Open
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        cb.before_call()  # 不抛异常

    def test_reset_clears_failure_count(self) -> None:
        """reset() 清零连续失败计数"""
        cb = CircuitBreaker(failure_threshold=3)
        cb.on_failure()
        cb.on_failure()
        cb.reset()
        assert cb._failure_count == 0
        # 再次调用 on_success 不应出错
        cb.on_success()


class TestCircuitBreakerRepresentation:
    """__repr__"""

    def test_repr_contains_state(self) -> None:
        """__repr__ 包含状态信息"""
        cb = CircuitBreaker(name="test")
        rep = repr(cb)
        assert "test" in rep
        assert "closed" in rep
