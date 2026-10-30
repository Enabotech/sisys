"""metrics 端口接线测试——Epic 5 终局审查修复 F6 钉死（R2 修订版）.

历史缺陷：metrics 端口字符串 impl 指向不存在的 metrics_adapter 模块
（组合根重构期脚手架漂移），cost_metrics_handler 在 handler_names 激活
清单内但每次 bootstrap resolve 失败被静默吞为 warning——1-19 成本追踪
的「激活」从未真实生效。修复后本文件锁定四件事：resolve 命中真实实现、
激活链真实执行（register() 实调零异常——订阅落位 RedisEventSubscriber
纯内存 dict）、消费接口三方一致、以及 clear_singleton 驱逐后的重建幂等
（R2 修复语义：工厂进程级单例复用，杜绝全局 REGISTRY 重复注册）。
"""

import asyncio

from src.domain.ports.resolver import get_resolver
from src.infrastructure.monitoring.metrics_port_impl import MetricsPortImpl


class TestMetricsPortWiring:
    """metrics 端口接线与激活链前提."""

    def test_metrics_port_resolves_to_real_impl(self) -> None:
        """resolve("metrics") 返回真实实现（修复前 RuntimeError: Failed to lazy-load）.

        conftest session autouse 已 bootstrap——get_resolver() 复用 SINGLETON
        缓存；缓存被 clear_singleton 驱逐的形态由 test_singleton_rebuild_is_idempotent
        单独锁定（重建幂等，不再触发 Duplicated timeseries）。
        """
        metrics = get_resolver().resolve("metrics")

        assert isinstance(metrics, MetricsPortImpl)
        # cost_metrics_handler 消费的两个方法在实现侧可调（接口三方一致）
        assert callable(metrics.record_token_usage)
        assert callable(metrics.record_cost)

    def test_cost_metrics_handler_activation_executes(self) -> None:
        """激活链真实执行：handler 可 resolve + register() 实调零异常.

        composition_root 激活环（handler_names 循环）的 async 分支以独立事件
        循环执行 register()——本用例同款实调验证订阅注册真实完成（比 callable
        断言强一级：subscribe_async 全链执行，落位 DualChannelEventBus→
        RedisEventSubscriber 纯内存 dict，零外部依赖）；循环用毕即关对齐
        激活环修复形态。修复前本用例在 resolve 处即抛 RuntimeError。
        """
        handler = get_resolver().resolve("cost_metrics_handler")

        register = getattr(handler, "register", None)
        assert callable(register)
        assert asyncio.iscoroutinefunction(register)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(register())
        finally:
            loop.close()

    def test_singleton_rebuild_is_idempotent(self) -> None:
        """clear_singleton 驱逐后重建幂等（R2 修复语义——工厂进程级单例复用）.

        5.x 验收场景级重建纪律（clear_singleton）会驱逐 resolver 的 SINGLETON
        实例缓存；Prometheus 默认 REGISTRY 是进程级资源不随缓存丢弃——工厂以
        模块级实例缓存对齐两生命周期：驱逐后裸 resolve 重建返回同一实例，
        不再触发 BusinessMetricsCollector 二构的 Duplicated timeseries
        （修复前该组合在四目录全量实测确定性红）。
        """
        resolver = get_resolver()
        resolver.clear_singleton()

        rebuilt = resolver.resolve("metrics")

        assert isinstance(rebuilt, MetricsPortImpl)
        # 进程级单例复用：重建与再重建是同一实例（registry 已注册指标的持有者）
        rebuilt_again = resolver.resolve("metrics")
        assert rebuilt is rebuilt_again
