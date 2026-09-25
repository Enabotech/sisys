"""Story 4.1b: 端口契约测试 — 8 个数据源适配器端口

验证 data_source_<name> 端口的注册、版本、接口、生命周期、owner/tags/module 元数据，
以及 8 个适配器实现类的 required_methods 与 Protocol runtime_checkable 属性。

遵循项目标准 11 维度契约测试模式（范本 tests/contracts/test_port_contract_tool.py）。

冷启动容错（Story 4.1b AC-2 决策）：Tavily/NewsAPI 适配器需 API Key，
采用条件注册（os.getenv 存在才注册）。契约测试将"注册状态"（环境依赖）
与"实现类合规"（静态可验证）解耦：
- 维度 1-8（注册元数据）：断言条件注册契约本身（Key 缺失→未注册 / Key 存在→完整元数据）；
- 维度 9-11（工厂/方法/Protocol）：monkeypatch 注入测试 Key 或直接构造，零环境依赖。
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from src.domain.ports.data_source import DataSourcePort
from src.domain.ports.registry import Lifetime, _global_registry

# 8 个适配器端口元数据表（Single Source of Truth，与 composition_root 注册保持一致）
ADAPTER_PORT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "port_name": "data_source_worldbank",
        "impl_cls_name": "WorldBankAdapter",
        "module_path": "src.infrastructure.external_services.datasources.worldbank_adapter",
        "tags": ("data-source", "worldbank", "statistics"),
        "env_key": None,
    },
    {
        "port_name": "data_source_imf",
        "impl_cls_name": "IMFAdapter",
        "module_path": "src.infrastructure.external_services.datasources.imf_adapter",
        "tags": ("data-source", "imf", "statistics"),
        "env_key": None,
    },
    {
        "port_name": "data_source_eurostat",
        "impl_cls_name": "EurostatAdapter",
        "module_path": "src.infrastructure.external_services.datasources.eurostat_adapter",
        "tags": ("data-source", "eurostat", "statistics"),
        "env_key": None,
    },
    {
        "port_name": "data_source_uspto",
        "impl_cls_name": "USPTOAdapter",
        "module_path": "src.infrastructure.external_services.datasources.uspto_adapter",
        "tags": ("data-source", "uspto", "patent"),
        "env_key": None,
    },
    {
        "port_name": "data_source_ipcc",
        "impl_cls_name": "IPCCAdapter",
        "module_path": "src.infrastructure.external_services.datasources.ipcc_adapter",
        "tags": ("data-source", "ipcc", "environment"),
        "env_key": None,
    },
    {
        "port_name": "data_source_newsapi",
        "impl_cls_name": "NewsAPIAdapter",
        "module_path": "src.infrastructure.external_services.datasources.newsapi_adapter",
        "tags": ("data-source", "newsapi", "news"),
        "env_key": "NEWSAPI_API_KEY",
        "config_module": "src.infrastructure.config.newsapi",
        "config_cls": "NewsAPIConfig",
    },
    {
        "port_name": "data_source_tavily",
        "impl_cls_name": "TavilyAdapter",
        "module_path": "src.infrastructure.external_services.datasources.tavily_adapter",
        "tags": ("data-source", "tavily", "web-search"),
        "env_key": "TAVILY_API_KEY",
        "config_module": "src.infrastructure.config.tavily",
        "config_cls": "TavilyConfig",
    },
    {
        "port_name": "data_source_china_nbs",
        "impl_cls_name": "ChinaNBSAdapter",
        "module_path": "src.infrastructure.external_services.datasources.china_nbs_adapter",
        "tags": ("data-source", "china-nbs", "crawler"),
        "env_key": None,
    },
)

EXPECTED_OWNER = "tool-team"
REQUIRED_METHODS = ["fetch", "get_metadata", "health_check"]


class _DummyResolver:
    """测试用最小 Resolver 占位符。

    china_nbs 适配器工厂需要 resolver.resolve('crawler_client')，
    本测试提供最小可工作桩（含 CrawlerClientPort 四方法）。
    """

    def resolve(self, name: str) -> Any:
        if name == "crawler_client":
            return _StubCrawlerClient()
        raise KeyError(name)

    def resolve_optional(self, name: str, **_kwargs: Any) -> Any:
        return None


class _StubCrawlerClient:
    """CrawlerClientPort 最小桩（仅满足契约测试实例化，不发起真实调用）。"""

    async def submit_task(self, *_args: Any, **_kwargs: Any) -> Any: ...

    async def get_task_status(self, *_args: Any, **_kwargs: Any) -> Any: ...

    async def cancel_task(self, *_args: Any, **_kwargs: Any) -> Any: ...

    async def list_supported_formats(self, *_args: Any, **_kwargs: Any) -> Any: ...


@pytest.mark.parametrize("spec_meta", ADAPTER_PORT_SPECS, ids=[m["port_name"] for m in ADAPTER_PORT_SPECS])
class TestDataSourceAdapterPortContract:
    """data_source_<name> 端口契约（11 维度全覆盖，参数化 8 适配器）.

    根因修复（消灭 Key 缺失 skip）：将"端口注册状态"（环境依赖，条件注册）与
    "实现类契约合规"（静态可验证）解耦——
    - 维度 1-8（注册元数据）：断言条件注册契约本身（Key 缺失→未注册 / Key 存在→完整元数据）；
    - 维度 9-11（工厂/方法/Protocol）：monkeypatch 注入测试 Key 或直接构造，零环境依赖。
    """

    def _registration_state(self, spec_meta: dict[str, Any]) -> Any:
        """断言条件注册契约并返回 PortSpec（keyed 且 Key 缺失时返回 None）。

        Returns:
            PortSpec（已注册）或 None（keyed 适配器 Key 缺失，条件注册未生效——
            该状态本身即合法契约，已断言）
        """
        env_key = spec_meta["env_key"]
        spec = _global_registry.get(spec_meta["port_name"])
        if env_key is not None and os.getenv(env_key) is None:
            assert spec is None, f"{env_key} 缺失时 {spec_meta['port_name']} 不应注册（条件注册设计）"
            return None
        assert spec is not None, f"端口 {spec_meta['port_name']} 未注册"
        return spec

    def _instantiate_adapter(self, spec_meta: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> Any:
        """实例化适配器（零环境依赖：keyed 适配器经 monkeypatch 注入测试 Key）。

        优先走注册工厂（验证真实装配路径）；未注册时（keyed 缺 Key）直接构造验证契约。
        """
        import importlib

        env_key = spec_meta["env_key"]
        if env_key is not None:
            monkeypatch.setenv(env_key, "contract-test-dummy-key")

        spec = _global_registry.get(spec_meta["port_name"])
        if spec is not None and callable(spec.impl):
            return spec.impl(_DummyResolver())

        # 未注册（keyed 缺 Key 条件注册）→ 直接构造（与工厂等价路径）
        config_mod = importlib.import_module(spec_meta["config_module"])
        config = getattr(config_mod, spec_meta["config_cls"]).from_env()
        impl_cls = getattr(importlib.import_module(spec_meta["module_path"]), spec_meta["impl_cls_name"])
        return impl_cls(config=config)

    def test_dimension_1_port_is_registered(self, spec_meta: dict[str, Any]) -> None:
        """维度 1：端口注册状态符合条件注册契约（已注册或 keyed 缺 Key 未注册）."""
        self._registration_state(spec_meta)

    def test_dimension_2_port_name(self, spec_meta: dict[str, Any]) -> None:
        """维度 2：PortSpec.name 正确."""
        spec = self._registration_state(spec_meta)
        if spec is not None:
            assert spec.name == spec_meta["port_name"]

    def test_dimension_3_port_version(self, spec_meta: dict[str, Any]) -> None:
        """维度 3：PortSpec.version 为 v1.0.0."""
        spec = self._registration_state(spec_meta)
        if spec is not None:
            assert spec.version == "v1.0.0"

    def test_dimension_4_port_interface_type(self, spec_meta: dict[str, Any]) -> None:
        """维度 4：PortSpec.interface 是 DataSourcePort Protocol."""
        spec = self._registration_state(spec_meta)
        if spec is not None:
            assert spec.interface is DataSourcePort

    def test_dimension_5_port_lifetime(self, spec_meta: dict[str, Any]) -> None:
        """维度 5：PortSpec.lifetime 为 SINGLETON（无状态 HTTP 客户端）."""
        spec = self._registration_state(spec_meta)
        if spec is not None:
            assert spec.lifetime == Lifetime.SINGLETON

    def test_dimension_6_port_owner(self, spec_meta: dict[str, Any]) -> None:
        """维度 6：PortSpec.owner 为 tool-team."""
        spec = self._registration_state(spec_meta)
        if spec is not None:
            assert spec.owner == EXPECTED_OWNER

    def test_dimension_7_port_module(self, spec_meta: dict[str, Any]) -> None:
        """维度 7：PortSpec.module 指向正确实现模块."""
        spec = self._registration_state(spec_meta)
        if spec is not None:
            assert spec.module == spec_meta["module_path"]

    def test_dimension_8_port_tags(self, spec_meta: dict[str, Any]) -> None:
        """维度 8：PortSpec.tags 元数据完整."""
        spec = self._registration_state(spec_meta)
        if spec is not None:
            assert spec.tags == spec_meta["tags"]

    def test_dimension_9_impl_is_callable(self, spec_meta: dict[str, Any]) -> None:
        """维度 9：spec.impl 可调用（lambda 工厂）；未注册时验证实现类可调用."""
        spec = self._registration_state(spec_meta)
        if spec is not None:
            assert callable(spec.impl) or isinstance(spec.impl, str)
        else:
            import importlib

            impl_cls = getattr(importlib.import_module(spec_meta["module_path"]), spec_meta["impl_cls_name"], None)
            assert impl_cls is not None and callable(impl_cls)

    def test_dimension_9_impl_factory_produces_port_instance(
        self, spec_meta: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """维度 9（续）：工厂/等价构造产出满足 DataSourcePort（runtime_checkable isinstance 校验）."""
        instance = self._instantiate_adapter(spec_meta, monkeypatch)
        assert isinstance(instance, DataSourcePort)

    def test_dimension_10_implementation_has_required_methods(self, spec_meta: dict[str, Any]) -> None:
        """维度 10：实现类包含 fetch/get_metadata/health_check 三方法（静态验证，零环境依赖）."""
        import importlib

        mod = importlib.import_module(spec_meta["module_path"])
        impl_cls = getattr(mod, spec_meta["impl_cls_name"], None)
        assert impl_cls is not None, f"模块 {spec_meta['module_path']} 缺少类 {spec_meta['impl_cls_name']}"
        for method in REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method)), f"方法不可调用: {method}"

    def test_dimension_11_protocol_is_runtime_checkable(
        self, spec_meta: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """维度 11：DataSourcePort 是 @runtime_checkable（isinstance 行为）."""
        assert getattr(DataSourcePort, "_is_runtime_protocol", False) is True
        instance = self._instantiate_adapter(spec_meta, monkeypatch)
        assert isinstance(instance, DataSourcePort)
