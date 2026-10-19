"""agent_profile_use_case 端口契约测试（Story 5-2 — Agent 身份档案加载）

11 维度契约断言（维度清单同 agent_profile_loader 契约测试先例）。

DummyResolver 提供四依赖名（agent_profile_loader / agent_repository /
skill_selector / event_publisher）——agent_profile_loader 与 skill_selector
零依赖直构（本地静态文件只读）；agent_repository 用 fakeredis 零 IO 替身；
event_publisher 用真实 InMemoryEventBus（无连接）。
"""

from __future__ import annotations

from typing import Any


class _DummyResolver:
    """测试用最小 Resolver 占位符（用例工厂注入四依赖）。"""

    def resolve(self, name: str) -> Any:
        if name == "agent_profile_loader":
            from src.infrastructure.agent_orch.markdown_agent_profile_loader import MarkdownAgentProfileLoader

            return MarkdownAgentProfileLoader()
        if name == "agent_repository":
            import fakeredis.aioredis

            from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
            from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository

            return RedisAgentRepository(adapter=RedisAdapter(redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True)))
        if name == "skill_selector":
            from src.application.skills.loader import InMemorySkillLoader
            from src.application.skills.registry.selector import SkillSelector

            return SkillSelector(skill_loader=InMemorySkillLoader())
        if name == "event_publisher":
            from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

            return InMemoryEventBus()
        raise KeyError(f"未注册的端口: {name}")


class TestAgentProfileUseCasePortContract:
    """agent_profile_use_case 端口契约测试 11 维度。"""

    PORT_NAME = "agent_profile_use_case"
    IMPL_CLS_NAME = "LoadAgentProfileUseCase"
    MODULE_PATH = "src.application.use_cases.agent_profile_loading"
    EXPECTED_TAGS = ("agent",)
    EXPECTED_OWNER = "platform"
    REQUIRED_METHODS = ["execute"]

    def _spec(self) -> Any:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    # 维度 1: 端口已注册
    def test_dimension_1_port_registered(self) -> None:
        assert self._spec() is not None, f"端口 {self.PORT_NAME} 未注册"

    # 维度 2: 端口名称
    def test_dimension_2_port_name(self) -> None:
        assert self._spec().name == self.PORT_NAME

    # 维度 3: 版本
    def test_dimension_3_version(self) -> None:
        assert self._spec().version == "v1.0.0"

    # 维度 4: interface 绑定用例自身类型（对齐 5-1 用例端口先例）
    def test_dimension_4_interface_is_use_case(self) -> None:
        from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase

        assert self._spec().interface is LoadAgentProfileUseCase

    # 维度 5: 生命周期
    def test_dimension_5_lifetime(self) -> None:
        from src.domain.ports.registry import Lifetime

        assert self._spec().lifetime == Lifetime.SINGLETON

    # 维度 6: owner
    def test_dimension_6_owner(self) -> None:
        assert self._spec().owner == self.EXPECTED_OWNER

    # 维度 7: 实现模块路径
    def test_dimension_7_module_path(self) -> None:
        assert self._spec().module == self.MODULE_PATH

    # 维度 8: tags
    def test_dimension_8_tags(self) -> None:
        assert self._spec().tags == self.EXPECTED_TAGS

    # 维度 9a: impl 是可调用工厂
    def test_dimension_9a_impl_callable(self) -> None:
        assert callable(self._spec().impl)

    # 维度 9b: impl 工厂产出用例实例（四依赖注入完整）
    def test_dimension_9b_impl_produces_use_case_instance(self) -> None:
        from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, LoadAgentProfileUseCase)
        assert type(instance).__name__ == self.IMPL_CLS_NAME

    # 维度 10: 实现具备必需方法
    def test_dimension_10_implementation_has_required_methods(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        for method in self.REQUIRED_METHODS:
            assert hasattr(instance, method), f"实现缺少方法: {method}"
            assert callable(getattr(instance, method)), f"方法不可调用: {method}"

    # 维度 11: isinstance 校验（用例自身类型）
    def test_dimension_11_instance_type(self) -> None:
        from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, LoadAgentProfileUseCase)


__all__ = ["TestAgentProfileUseCasePortContract"]
