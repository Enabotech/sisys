"""financial_modeling 双端口契约测试——Story 5.12。

11 维度（use_case 主端口）+ service 依赖可达与方法清单追加维度（双端口单文件
钦定——AC-4 Then③）：resolve 可达 / 端口名 / 版本 / interface 绑定 / 生命周期
SINGLETON / owner / module / tags / impl 可调用 / impl 经 _DummyResolver 产出
实例 / execute 方法存在 + REQUIRED_METHODS_SERVICE 三方法契约断言。

_DummyResolver 分发 service 替身（use_case lambda 单依赖 financial_modeling_service
——本 Story 用例依赖是既有必注册端口，缺依赖 KeyError 自然传播零包装）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_financial_modeling.py -v
"""

from __future__ import annotations

from typing import Any

from src.domain.ports.registry import Lifetime, _global_registry

# ==== 模块常量（契约面单源） ====

USE_CASE_PORT_NAME = "financial_modeling_use_case"
SERVICE_PORT_NAME = "financial_modeling_service"
USE_CASE_CLS_NAME = "FinancialModelingUseCase"
SERVICE_CLS_NAME = "FinancialModelingService"
USE_CASE_MODULE_PATH = "src.application.use_cases.financial_modeling"
SERVICE_MODULE_PATH = "src.domain.services.financial_modeling"
USE_CASE_EXPECTED_TAGS = ("financial", "valuation", "usecase")
SERVICE_EXPECTED_TAGS = ("financial", "valuation", "domain-service")
EXPECTED_OWNER = "platform"
#: use_case 主端口方法面
REQUIRED_METHODS = ["execute"]
#: service 依赖端口方法面（三引擎契约——方法清单纳入契约验证）
REQUIRED_METHODS_SERVICE = [
    "calculate_dcf",
    "calculate_comparable_valuation",
    "calculate_precedent_valuation",
]


class _StubModelingServiceForContract:
    """零 IO 引擎替身（duck-typing 三方法——_DummyResolver 分发面）。"""

    def calculate_dcf(self, schedule: Any, assumptions: Any) -> Any:
        """DCF 桩（契约测试仅验证方法存在与调用，不真算）。"""
        return None

    def calculate_comparable_valuation(self, comparables: Any, target_ebitda: Any) -> Any:
        """可比桩。"""
        return None

    def calculate_precedent_valuation(self, transactions: Any, target_ebitda: Any) -> Any:
        """先例桩。"""
        return None


class _DummyResolver:
    """零 IO 依赖分发替身（分发 use_case lambda 消费的 financial_modeling_service 端口名）."""

    def resolve(self, name: str) -> Any:
        if name == SERVICE_PORT_NAME:
            return _StubModelingServiceForContract()
        raise KeyError(f"未注册的端口: {name}")

    def resolve_optional(self, name: str) -> Any:
        return None


class TestFinancialModelingPortContract:
    """financial_modeling_use_case 主端口 11 维度 + service 追加维度。"""

    def _use_case_spec(self) -> Any:
        """use_case PortSpec 获取便捷通道。"""
        spec = _global_registry.get(USE_CASE_PORT_NAME)
        assert spec is not None, f"端口 {USE_CASE_PORT_NAME} 未注册（组合根 bootstrap 应已完成）"
        return spec

    # ==== 维度 1-8: PortSpec 元数据 ====

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：use_case 端口已注册。"""
        assert self._use_case_spec() is not None

    def test_dimension_2_port_name(self) -> None:
        """维度 2：端口名精确。"""
        assert self._use_case_spec().name == USE_CASE_PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：版本 v1.0.0。"""
        assert self._use_case_spec().version == "v1.0.0"

    def test_dimension_4_interface_binds_use_case_class(self) -> None:
        """维度 4：interface 绑用例类自身（agent_instantiation_use_case 先例）。"""
        from src.application.use_cases.financial_modeling import FinancialModelingUseCase

        assert self._use_case_spec().interface is FinancialModelingUseCase

    def test_dimension_5_lifetime_singleton(self) -> None:
        """维度 5：SINGLETON（无状态纯编排——DC-9）。"""
        assert self._use_case_spec().lifetime is Lifetime.SINGLETON

    def test_dimension_6_owner(self) -> None:
        """维度 6：owner=platform（Epic 5 族惯例）。"""
        assert self._use_case_spec().owner == EXPECTED_OWNER

    def test_dimension_7_module_path(self) -> None:
        """维度 7：module 路径。"""
        assert self._use_case_spec().module == USE_CASE_MODULE_PATH

    def test_dimension_8_tags(self) -> None:
        """维度 8：tags 三元组。"""
        assert self._use_case_spec().tags == USE_CASE_EXPECTED_TAGS

    # ==== 维度 9: impl 可调用与实例产出 ====

    def test_dimension_9a_impl_is_callable(self) -> None:
        """维度 9a：impl 是可调用 lambda。"""
        assert callable(self._use_case_spec().impl)

    def test_dimension_9b_impl_yields_use_case_instance(self) -> None:
        """维度 9b：impl 经 _DummyResolver 产出 FinancialModelingUseCase 实例。"""
        from src.application.use_cases.financial_modeling import FinancialModelingUseCase

        instance = self._use_case_spec().impl(_DummyResolver())
        assert isinstance(instance, FinancialModelingUseCase)
        assert type(instance).__name__ == USE_CASE_CLS_NAME

    # ==== 维度 10-11: 方法面与注入链 ====

    def test_dimension_10_methods_present(self) -> None:
        """维度 10：REQUIRED_METHODS 方法存在且可调用。"""
        instance = self._use_case_spec().impl(_DummyResolver())
        for method in REQUIRED_METHODS:
            assert hasattr(instance, method), f"方法缺失: {method}"
            assert callable(getattr(instance, method)), f"方法不可调用: {method}"

    def test_dimension_11_injection_chain(self) -> None:
        """维度 11：注入链（lambda 注入 service——实例 _service 非 None）。"""
        instance = self._use_case_spec().impl(_DummyResolver())
        assert getattr(instance, "_service", None) is not None, "服务依赖注入链断裂"

    # ==== service 端口追加维度（双端口单文件钦定） ====

    def test_service_port_resolvable(self) -> None:
        """service 端口 resolve 可达（字符串 impl 延迟加载——debate_evaluator 先例）。"""
        from src.domain.ports.resolver import resolve
        from src.domain.services.financial_modeling import FinancialModelingService

        instance = resolve(SERVICE_PORT_NAME)
        assert instance is not None, f"resolve('{SERVICE_PORT_NAME}') 应可达"
        assert type(instance).__name__ == SERVICE_CLS_NAME
        assert isinstance(instance, FinancialModelingService)

    def test_service_port_spec_metadata(self) -> None:
        """service PortSpec 元数据（版本/生命周期/owner/tags/module/interface——CR2-6 补 interface 绑定维度）。"""
        spec = _global_registry.get(SERVICE_PORT_NAME)
        assert spec is not None, f"端口 {SERVICE_PORT_NAME} 未注册"
        assert spec.version == "v1.0.0"
        assert spec.lifetime is Lifetime.SINGLETON, "无状态纯计算——DC-9 并发安全论证"
        assert spec.owner == EXPECTED_OWNER
        assert spec.tags == SERVICE_EXPECTED_TAGS
        assert spec.module == SERVICE_MODULE_PATH
        assert isinstance(spec.impl, str), "字符串 impl 延迟加载（debate_evaluator 先例）"
        # interface 绑定维度（CR2-6：interface 误绑时 resolve_by_interface 路径静默失效）
        from src.domain.services.financial_modeling import FinancialModelingService

        assert spec.interface is FinancialModelingService, "service 端口 interface 应绑定 FinancialModelingService"

    def test_service_methods_contract(self) -> None:
        """service 三方法契约断言（REQUIRED_METHODS_SERVICE——方法面纳入契约验证）。"""
        from src.domain.ports.resolver import resolve

        service_instance = resolve(SERVICE_PORT_NAME)
        for method in REQUIRED_METHODS_SERVICE:
            assert hasattr(service_instance, method), f"service 方法缺失: {method}"
            assert callable(getattr(service_instance, method)), f"service 方法不可调用: {method}"
