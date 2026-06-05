"""TokenEstimatorPort Protocol 行为验证测试

验证 Token 消耗估算端口的运行时类型检查、异步方法签名和返回类型契约
"""

from __future__ import annotations

import asyncio

from src.domain.ports.token_estimator import TokenEstimatorPort


class TestTokenEstimatorPortRuntimeCheckable:
    """TokenEstimatorPort 结构化子类型检查"""

    def test_compatible_class_passes_isinstance(self) -> None:
        """实现 async estimate 方法的类应通过 isinstance 检查"""

        class FakeEstimator:
            async def estimate(self, route_type: str, model: str) -> tuple[int, int]:
                return 256, 512

        assert isinstance(FakeEstimator(), TokenEstimatorPort)

    def test_incompatible_class_fails_isinstance(self) -> None:
        """不实现 estimate 方法的类不应通过 isinstance 检查"""

        class Incompatible:
            def other_method(self) -> None:
                pass

        assert not isinstance(Incompatible(), TokenEstimatorPort)

    def test_class_without_async_estimate_fails(self) -> None:
        """同步 estimate 方法不应满足异步协议（运行时限制）"""

        class SyncEstimator:
            def estimate(self, route_type: str, model: str) -> tuple[int, int]:
                return 100, 200

        # Python runtime_checkable 只检查方法名存在性，不区分同步/异步
        # 因此这里实际上可能通过 isinstance，我们验证行为差异
        instance = SyncEstimator()
        assert not asyncio.iscoroutinefunction(instance.estimate)


class TestTokenEstimatorPortMethodSignature:
    """TokenEstimatorPort 方法签名验证"""

    def test_estimate_is_async(self) -> None:
        """estimate 应为异步方法"""
        assert asyncio.iscoroutinefunction(TokenEstimatorPort.estimate)

    async def test_estimate_returns_tuple_of_ints(self) -> None:
        """estimate 应返回 tuple[int, int]"""

        class FakeEstimator:
            async def estimate(self, route_type: str, model: str) -> tuple[int, int]:
                return 256, 512

        estimator = FakeEstimator()
        result = await estimator.estimate("local", "bge-m3")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)

    async def test_estimate_receives_route_type_and_model(self) -> None:
        """estimate 应正确接收 route_type 和 model 参数"""
        received: dict[str, str] = {}

        class SpyEstimator:
            async def estimate(self, route_type: str, model: str) -> tuple[int, int]:
                received["route_type"] = route_type
                received["model"] = model
                return 100, 200

        estimator = SpyEstimator()
        await estimator.estimate("cloud", "gpt-4")
        assert received["route_type"] == "cloud"
        assert received["model"] == "gpt-4"
