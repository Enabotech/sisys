"""Story 4.7: 端口契约测试 — Validation Feedback 应用服务

验证 validation_feedback_service 端口的注册、版本、接口、生命周期、owner/tags/module
元数据、工厂双句柄注入形态（engine + inner_chain——R9-14 定稿）与
Protocol runtime_checkable 属性。

遵循项目标准 11 维度契约测试模式（与 test_port_contract_tool.py 样板对齐）。
"""

from __future__ import annotations

from typing import Any

from src.application.ports.validation_feedback_service import ValidationFeedbackServicePort
from src.domain.ports.registry import Lifetime, _global_registry


class _DummyResolver:
    """测试用最小 Resolver——提供 ValidationFeedbackService 工厂的全部依赖替身。

    双句柄注入清单（SSOT 表行为准）：
    - llm_client / error_case_repository / evolution_log_repository / event_publisher
    - engine 引用（防放大封顶用——裸引擎，_retry 属性所在）
    - inner_chain 引用（重执行用＝SSD>TOV>Engine 完整内层链）
    不注入 RetryPolicy（fix-gen 重试封顶由服务内自建——防「按值恢复」陷阱）。
    """

    def resolve(self, name: str) -> Any:
        from unittest.mock import AsyncMock, MagicMock

        from src.application.services.tool_execution_engine import ToolExecutionEngine
        from src.infrastructure.storage.inmemory.error_case_repository import (
            InMemoryErrorCaseRepository,
        )
        from src.infrastructure.storage.inmemory.evolution_log_repository import (
            InMemoryEvolutionLogRepository,
        )

        if name == "error_case_repository":
            return InMemoryErrorCaseRepository()
        if name == "evolution_log_repository":
            return InMemoryEvolutionLogRepository()
        if name == "llm_client":
            mock = AsyncMock()
            mock.generate = AsyncMock()
            return mock
        if name == "event_publisher":
            return MagicMock()
        if name == "schema_validator":
            return MagicMock(spec=["validate_arguments", "validate_output", "validate_schema_compatibility"])
        if name == "sandbox_executor":
            return MagicMock()
        if name == "sandbox_session_repository":
            return MagicMock()
        if name in ("tool_execution_engine", "tool_execution_inner_chain"):
            return ToolExecutionEngine(llm_client=AsyncMock(), sandbox=AsyncMock())
        raise KeyError(name)


class TestValidationFeedbackServicePortContract:
    """validation_feedback_service 端口契约（11 维度全覆盖）."""

    PORT_NAME = "validation_feedback_service"
    IMPL_CLS_NAME = "ValidationFeedbackService"
    MODULE_PATH = "src.application.services.validation_feedback_service"
    EXPECTED_TAGS = ("tool", "feedback", "service")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = [
        "recover",
        "should_enter_feedback_loop",
    ]

    def _spec(self) -> Any:
        return _global_registry.get(self.PORT_NAME)

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已注册."""
        spec = self._spec()
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_dimension_2_port_name(self) -> None:
        """维度 2：PortSpec.name 正确."""
        spec = self._spec()
        assert spec is not None
        assert spec.name == self.PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：PortSpec.version 为 v1.0.0."""
        spec = self._spec()
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4：PortSpec.interface 是 ValidationFeedbackServicePort Protocol."""
        spec = self._spec()
        assert spec is not None
        assert spec.interface is ValidationFeedbackServicePort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：PortSpec.lifetime 为 SCOPED."""
        spec = self._spec()
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_dimension_6_port_owner(self) -> None:
        """维度 6：PortSpec.owner 为 tool-team."""
        spec = self._spec()
        assert spec is not None
        assert spec.owner == self.EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7：PortSpec.module 指向正确实现模块."""
        spec = self._spec()
        assert spec is not None
        assert spec.module == self.MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8：PortSpec.tags 元数据完整."""
        spec = self._spec()
        assert spec is not None
        assert spec.tags == self.EXPECTED_TAGS

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9：spec.impl 是可调用工厂."""
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl), "impl 应为 lambda 工厂函数"

    def test_dimension_9_impl_factory_produces_port_instance(self) -> None:
        """维度 9（续）：工厂产出满足 Protocol（runtime_checkable isinstance 校验）."""
        spec = self._spec()
        assert spec is not None
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, ValidationFeedbackServicePort)

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10：实现类包含所有必需方法."""
        import importlib

        spec = self._spec()
        assert spec is not None
        assert spec.module
        mod = importlib.import_module(spec.module)
        impl_cls = getattr(mod, self.IMPL_CLS_NAME, None)
        assert impl_cls is not None
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method)), f"方法不可调用: {method}"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：Protocol 是 @runtime_checkable（isinstance 行为）."""
        from src.application.services.validation_feedback_service import (
            ValidationFeedbackService,
        )

        service = ValidationFeedbackService(
            llm_client=_DummyResolver().resolve("llm_client"),
            error_case_repository=_DummyResolver().resolve("error_case_repository"),
            evolution_log_repository=_DummyResolver().resolve("evolution_log_repository"),
            event_publisher=None,
            engine=_DummyResolver().resolve("tool_execution_engine"),
            inner_chain=_DummyResolver().resolve("tool_execution_inner_chain"),
        )
        assert isinstance(service, ValidationFeedbackServicePort)

    def test_extra_recover_signature_contract(self) -> None:
        """附加维度：recover 签名契约（execution_id 幂等键取自 trigger_error.context）."""
        import inspect

        sig = inspect.signature(ValidationFeedbackServicePort.recover)
        params = sig.parameters
        for expected in ("tool_id", "tool", "tool_call", "context", "trigger_error"):
            assert expected in params, f"recover 缺少参数 {expected}"


class TestDualHandleAssemblyContract:
    """双句柄装配契约（R9-14/R10-3：engine 句柄与 inner_chain 最内层引擎同一对象）."""

    def test_engine_handle_identity_with_inner_chain(self) -> None:
        """同一性：service._engine is inner_chain 内引擎（否则封顶封的是另一台引擎，
        防放大失效；生产 SCOPED 缓存可保，契约测试须显式断言——R10-3②）."""

        from src.application.services.validation_feedback_service import (
            build_validation_feedback_service,
        )

        resolver = _DummyResolver()
        service = build_validation_feedback_service(resolver, max_concurrent_containers=5)
        # inner_chain = SSD > TOV > engine——逐层解包取最内层
        ssd = service._inner_chain
        tov = ssd._wrapped
        engine_in_chain = tov._wrapped
        assert service._engine is engine_in_chain, "双句柄同一性破坏（防放大失效）"

    def test_tov_no_explicit_retry_policy_precondition(self) -> None:
        """前置条件：TOV 构造未显式注入 retry_policy（or 短路才走动态读
        engine._retry——AC-2 防放大测试须同时断言该构造形态）."""
        from src.application.services.tool_output_validator import ToolOutputValidator
        from src.application.services.validation_feedback_service import (
            build_validation_feedback_service,
        )

        resolver = _DummyResolver()
        service = build_validation_feedback_service(resolver, max_concurrent_containers=5)
        tov = service._inner_chain._wrapped
        assert isinstance(tov, ToolOutputValidator)
        assert tov._retry_policy is None, "TOV 显式注入 retry_policy 会使动态封顶失效"
