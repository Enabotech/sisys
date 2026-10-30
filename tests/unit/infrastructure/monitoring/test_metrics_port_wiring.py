"""metrics 端口接线测试——Epic 5 终局审查修复 F6 钉死.

历史缺陷：metrics 端口字符串 impl 指向不存在的 metrics_adapter 模块
（组合根重构期脚手架漂移），cost_metrics_handler 在 handler_names 激活
清单内但每次 bootstrap resolve 失败被静默吞为 warning——1-19 成本追踪
的「激活」从未真实生效。修复后本文件锁定三件事：resolve 命中真实实现、
激活链前提成立（handler 可解析 + async register 可调——bootstrap 激活环
的成功条件等价于这两点，成立则循环零 warning 并订阅 RoutingDecided）、
消费接口三方一致。
"""

import inspect

from src.domain.ports.resolver import get_resolver
from src.infrastructure.monitoring.metrics_port_impl import MetricsPortImpl


class TestMetricsPortWiring:
    """metrics 端口接线与激活链前提."""

    def test_metrics_port_resolves_to_real_impl(self) -> None:
        """resolve("metrics") 返回真实实现（修复前 RuntimeError: Failed to lazy-load）.

        conftest session autouse 已 bootstrap——get_resolver() 复用 SINGLETON
        缓存；新建 Resolver() 空实例缓存会二次构造并触发 Prometheus
        Duplicated timeseries（BusinessMetricsCollector 构造器即注册 sisys_*）。
        """
        metrics = get_resolver().resolve("metrics")

        assert isinstance(metrics, MetricsPortImpl)
        # cost_metrics_handler 消费的两个方法在实现侧可调（接口三方一致）
        assert callable(metrics.record_token_usage)
        assert callable(metrics.record_cost)

    def test_cost_metrics_handler_activation_prerequisite(self) -> None:
        """激活链前提：handler 可 resolve + register 为 async 可调.

        composition_root 激活环（handler_names 循环）的成功条件即这两点：
        resolve 成功且 register callable 则循环零 warning，经
        run_until_complete 订阅 RoutingDecided（REALTIME 通道进程内注册，
        零外部依赖——RedisSubscriber.subscribe_async 为纯内存 handler 注册）。
        修复前本用例在 resolve 处即抛 RuntimeError。
        """
        handler = get_resolver().resolve("cost_metrics_handler")

        register = getattr(handler, "register", None)
        assert callable(register)
        assert inspect.iscoroutinefunction(register)
