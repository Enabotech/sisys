"""Circuit Breaker 单元测试

验证熔断器状态机：Closed → Open → Half-Open → Closed 循环。
使用 mock 时间控制来加速恢复超时测试。

R3-P0-1 修复新增：半开探测槽位生命周期（on_ignored 释放 + 超时再武装）——
使用 _ManualClockCircuitBreaker 手动时钟子类确定性推进时间（消除真实 sleep
的 CI 负载时序脆弱性；半开相关用例禁止依赖两次 before_call 的真实间隔）。
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from src.infrastructure.external_services.embedding.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


class _ManualClockCircuitBreaker(CircuitBreaker):
    """手动时钟熔断器（测试专用——_now() 子类重写为可推进的固定时钟）"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._mock_now = 1000.0

    def _now(self) -> float:
        return self._mock_now

    def advance(self, seconds: float) -> None:
        """推进模拟时钟"""
        self._mock_now += seconds


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
        """Half-Open 限制探测请求数（R3-P0-1 改写：手动时钟控制——真实 sleep 0.02s
        在 CI 负载下两次 before_call 间隔可能超过再武装窗口 0.01s 导致随机红）"""
        cb = _ManualClockCircuitBreaker(failure_threshold=1, recovery_timeout=10.0, half_open_max_calls=1)
        cb.on_failure()  # → Open
        cb.advance(20.0)  # 超过 recovery_timeout
        # 第一次 before_call 转为 Half-Open 并允许探测（probe_start = 当前时钟）
        cb.before_call()
        assert cb.state == CircuitState.HALF_OPEN
        # 未推进时钟（未超再武装窗口）→ 第二次 before_call 应拒绝（超过 half_open_max_calls）
        with pytest.raises(CircuitBreakerOpenError, match="半开"):
            cb.before_call()


class TestCircuitBreakerProbeLifecycle:
    """半开探测槽位生命周期（R3-P0-1 修复：on_ignored 释放 + 超时再武装防楔死）"""

    def test_on_ignored_releases_probe_slot(self) -> None:
        """on_ignored 释放半开探测槽位——释放后无需等待即可再次探测（修复前：槽位
        耗尽后永久楔死，等待任意时长无效；判别锚点：回退修复本用例必红）"""
        cb = _ManualClockCircuitBreaker(failure_threshold=1, recovery_timeout=10.0, half_open_max_calls=1)
        cb.on_failure()  # → Open
        cb.advance(20.0)
        cb.before_call()  # → Half-Open，探测槽已占用
        cb.on_ignored()  # 确定性错误（如 429）释放探测槽
        # 不推进时钟，下一次 before_call 应作为新探测放行（而非永久拒绝）
        cb.before_call()  # 不抛异常
        assert cb.state == CircuitState.HALF_OPEN

    def test_on_ignored_decrements_not_zeroes(self) -> None:
        """on_ignored 是减一而非置零——多探测在飞场景不得抹掉他人槽位（v2 评审
        必修：max(0, calls-1)，half_open_max_calls=2 时防并发探测超发）"""
        cb = _ManualClockCircuitBreaker(failure_threshold=1, recovery_timeout=10.0, half_open_max_calls=2)
        cb.on_failure()  # → Open
        cb.advance(20.0)
        cb.before_call()  # 探测 1（calls=1）
        cb.before_call()  # 探测 2（calls=2，配额满）
        cb.on_ignored()  # 探测 1 结束（calls=1，非 0）
        cb.before_call()  # 新探测放行（calls=2）
        # 配额再次满，未超时窗口内第 4 个请求应拒绝（置零实现会放行 → 本断言红）
        with pytest.raises(CircuitBreakerOpenError, match="半开"):
            cb.before_call()

    def test_on_ignored_in_closed_resets_nothing(self) -> None:
        """CLOSED 状态 on_ignored 无操作——不重置失败计数（确定性错误与可用性无关）"""
        cb = CircuitBreaker(failure_threshold=3)
        cb.on_failure()
        cb.on_failure()
        cb.on_ignored()
        assert cb._failure_count == 2  # 未被清零
        assert cb.state == CircuitState.CLOSED

    def test_probe_timeout_rearms_after_recovery_timeout(self) -> None:
        """探测回调缺失（既无 on_success/on_failure 也无 on_ignored）时，超过
        recovery_timeout 后再武装重新放行（结构性兜底——修复前永久楔死）"""
        cb = _ManualClockCircuitBreaker(failure_threshold=1, recovery_timeout=10.0, half_open_max_calls=1)
        cb.on_failure()  # → Open
        cb.advance(20.0)
        cb.before_call()  # → Half-Open 探测（probe_start 记录）
        # 探测挂起（无任何回调）→ 窗口内拒绝
        with pytest.raises(CircuitBreakerOpenError, match="半开"):
            cb.before_call()
        # 推进时钟超过 recovery_timeout → 再武装放行新探测
        cb.advance(15.0)
        cb.before_call()  # 不抛异常
        assert cb.state == CircuitState.HALF_OPEN

    def test_rearm_refreshes_probe_start(self) -> None:
        """再武装后必须刷新 probe_start——否则首个窗口过期后每次 before_call 都
        满足再武装条件，half_open_max_calls 并发上限被完全击穿（v2 评审必修 1
        判别锚点：不刷新实现下第二个请求会被错误放行 → 本用例红）"""
        cb = _ManualClockCircuitBreaker(failure_threshold=1, recovery_timeout=10.0, half_open_max_calls=1)
        cb.on_failure()  # → Open
        cb.advance(20.0)
        cb.before_call()  # → Half-Open 探测 1（probe_start=t1200）
        cb.advance(15.0)  # 超窗口（t1215）
        cb.before_call()  # 再武装放行探测 2（probe_start 应刷新为 t1215）
        # 未再超窗口（t1215 未推进）→ 第三个请求必须拒绝（probe_start 未刷新实现会放行）
        with pytest.raises(CircuitBreakerOpenError, match="半开"):
            cb.before_call()

    def test_on_success_after_ignored_release_closes(self) -> None:
        """on_ignored 释放槽位后的新探测成功 → 正常回到 Closed（端到端自愈链路）"""
        cb = _ManualClockCircuitBreaker(failure_threshold=1, recovery_timeout=10.0, half_open_max_calls=1)
        cb.on_failure()  # → Open
        cb.advance(20.0)
        cb.before_call()  # 探测（429 场景）
        cb.on_ignored()  # 429 释放槽位
        cb.before_call()  # 新探测（服务已恢复）
        cb.on_success()  # → Closed
        assert cb.state == CircuitState.CLOSED


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
