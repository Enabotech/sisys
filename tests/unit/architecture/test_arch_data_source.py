"""Story 4.1b: 架构约束测试 — Skills 数据采集基础设施

验证：
1. domain 层零外部依赖（AST 黑名单扫描，显式含 httpx/tenacity——沙箱无网络不变量保护）
2. 端口注册完整性（PortSpec 10 字段 + 8 适配器 + resolver 全注册 + SINGLETON 生命周期）
3. 实现类 isinstance Protocol 校验
4. 依赖方向校验（application 新文件不 import infrastructure，适配器仅经 composition_root 注册）
5. 异常码段校验（EXCEPTION_410-413 ∈ data_source 子域）

遵循 test_arch_strategic_tool_impl.py 模式（Story 4.1a）。
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.domain.ports.registry import Lifetime, _global_registry

# ============================================================
# 常量定义
# ============================================================

SRC_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "src"

# domain 层需要扫描的文件（Story 4.1b 新增）
DOMAIN_FILES = [
    SRC_ROOT / "domain" / "ports" / "data_source.py",
    SRC_ROOT / "domain" / "value_objects" / "data_source.py",
    SRC_ROOT / "domain" / "exceptions" / "data_source_exceptions.py",
    SRC_ROOT / "domain" / "events" / "data_source_events.py",
]

# application 层需要扫描的文件（Story 4.1b 新增/修改）
APPLICATION_FILES = [
    SRC_ROOT / "application" / "ports" / "data_source_resolver.py",
    SRC_ROOT / "application" / "services" / "data_source_resolver.py",
    SRC_ROOT / "application" / "services" / "data_source_marker.py",
]

# domain 层禁止导入的外部包黑名单（独立定义，显式含 httpx/tenacity——
# 对齐 Story 4.1b 硬约束 line 60-62；现有 4.1a 黑名单 15 项缺这两项，
# 新建文件独立定义避免污染通用黑名单）
FORBIDDEN_IMPORTS = {
    "pydantic",
    "sqlalchemy",
    "redis",
    "fastapi",
    "typer",
    "langgraph",
    "prefect",
    "qdrant",
    "minio",
    "neo4j",
    "aio_pika",
    "litellm",
    "instructor",
    "asyncpg",
    "aioredis",
    "httpx",  # 数据源 HTTP 仅允许在 infrastructure 适配器层
    "tenacity",  # 重试库仅允许在 infrastructure 适配器层
}

# 8 个适配器端口 + resolver 端口注册清单
ADAPTER_PORT_NAMES = (
    "data_source_worldbank",
    "data_source_imf",
    "data_source_eurostat",
    "data_source_uspto",
    "data_source_ipcc",
    "data_source_china_nbs",
)

# 需 API Key 的适配器（条件注册，Key 缺失时不注册——冷启动容错设计）
KEYED_ADAPTER_PORT_NAMES = ("data_source_newsapi", "data_source_tavily")

ADAPTER_IMPL_CLASSES = {
    "data_source_worldbank": "WorldBankAdapter",
    "data_source_imf": "IMFAdapter",
    "data_source_eurostat": "EurostatAdapter",
    "data_source_uspto": "USPTOAdapter",
    "data_source_ipcc": "IPCCAdapter",
    "data_source_china_nbs": "ChinaNBSAdapter",
}

# 数据源异常码段（data_source 子域 410-419）
EXPECTED_EXCEPTION_CODES = {
    "DataSourceError": "EXCEPTION_410",
    "DataSourceUnavailableError": "EXCEPTION_411",
    "DataSourceRateLimitError": "EXCEPTION_412",
    "DataSourceResponseError": "EXCEPTION_413",
}


# ============================================================
# 辅助函数
# ============================================================


def _extract_imports(file_path: Path) -> list[str]:
    """从 Python 文件中提取所有 import 语句的模块名。"""
    if not file_path.exists():
        return []
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


# ============================================================
# 测试类 1: Domain 层零外部依赖
# ============================================================


class TestDomainLayerConstraints:
    """domain 层禁止导入任何外部包（含 httpx/tenacity——沙箱无网络不变量保护）。"""

    @pytest.mark.parametrize("file_path", DOMAIN_FILES, ids=lambda p: p.name)
    def test_no_forbidden_imports(self, file_path: Path) -> None:
        assert file_path.exists(), f"domain 文件不存在: {file_path}"
        imports = _extract_imports(file_path)
        violations = set(imports) & FORBIDDEN_IMPORTS
        assert not violations, f"{file_path.name} 导入禁止的外部包: {violations}"

    @pytest.mark.parametrize("file_path", DOMAIN_FILES, ids=lambda p: p.name)
    def test_no_cross_layer_imports(self, file_path: Path) -> None:
        """domain 禁止导入 application/interfaces/infrastructure 层。"""
        imports = _extract_imports(file_path)
        for imp in imports:
            assert not imp.startswith(("application", "interfaces", "infrastructure")), f"{file_path.name} 跨层导入: {imp}"


# ============================================================
# 测试类 2: 端口注册完整性
# ============================================================


class TestDataSourcePortRegistry:
    """8 适配器 + resolver 端口注册完整性（PortSpec 10 字段）。"""

    @pytest.mark.parametrize("port_name", ADAPTER_PORT_NAMES)
    def test_adapter_ports_registered(self, port_name: str) -> None:
        spec = _global_registry.get(port_name)
        assert spec is not None, f"端口 {port_name} 未注册"
        assert spec.name == port_name
        assert spec.version == "v1.0.0"
        assert spec.interface is not None
        assert spec.impl is not None
        assert spec.module.startswith("src.infrastructure.external_services.datasources.")
        assert spec.lifetime == Lifetime.SINGLETON
        assert spec.owner == "tool-team"
        assert "data-source" in spec.tags
        assert spec.deprecated is False

    def test_resolver_port_registered(self) -> None:
        spec = _global_registry.get("data_source_resolver")
        assert spec is not None, "端口 data_source_resolver 未注册"
        assert spec.module == "src.application.services.data_source_resolver"
        assert spec.lifetime == Lifetime.SINGLETON
        assert spec.owner == "tool-team"

    def test_keyed_adapters_conditional_registration(self) -> None:
        """需 Key 的适配器按条件注册（有 Key 注册 / 无 Key 不注册，两者均为合法状态）。"""
        import os

        for port_name, env_key in (
            ("data_source_newsapi", "NEWSAPI_API_KEY"),
            ("data_source_tavily", "TAVILY_API_KEY"),
        ):
            spec = _global_registry.get(port_name)
            if os.getenv(env_key) is None:
                assert spec is None, f"{env_key} 缺失时 {port_name} 不应注册"
            else:
                assert spec is not None, f"{env_key} 存在时 {port_name} 应注册"


# ============================================================
# 测试类 3: 实现类 isinstance Protocol 校验
# ============================================================


class TestImplementationCompliance:
    """适配器实现类满足 DataSourcePort（runtime_checkable isinstance）。"""

    def test_resolver_service_implements_port(self) -> None:
        from src.application.ports.data_source_resolver import DataSourceResolverPort
        from src.application.services.data_source_resolver import DataSourceResolverService
        from src.domain.ports.l1_cache import L1CachePort

        cache_stub = AsyncMock(spec=L1CachePort)
        service = DataSourceResolverService(adapters={}, cache=cache_stub)
        assert isinstance(service, DataSourceResolverPort)

    @pytest.mark.parametrize("port_name,cls_name", list(ADAPTER_IMPL_CLASSES.items()))
    def test_adapter_class_has_port_methods(self, port_name: str, cls_name: str) -> None:
        import importlib

        spec = _global_registry.get(port_name)
        assert spec is not None
        mod = importlib.import_module(spec.module)
        impl_cls = getattr(mod, cls_name)
        for method in ("fetch", "get_metadata", "health_check"):
            assert callable(getattr(impl_cls, method, None)), f"{cls_name} 缺少方法 {method}"


# ============================================================
# 测试类 4: 依赖方向校验
# ============================================================


class TestDependencyDirection:
    """application 新文件禁止 import infrastructure；适配器仅经 composition_root 注册。"""

    @pytest.mark.parametrize("file_path", APPLICATION_FILES, ids=lambda p: p.name)
    def test_application_no_infrastructure_import(self, file_path: Path) -> None:
        assert file_path.exists()
        imports = _extract_imports(file_path)
        for imp in imports:
            assert not imp.startswith("infrastructure"), f"{file_path.name} 导入 infrastructure: {imp}"

    def test_data_source_resolver_has_no_infrastructure_dependency(self) -> None:
        """data_source_resolver 全文件禁止 import infrastructure（依赖方向强制）。

        应用层缓存键构造内联实现（与 key_builder 输出格式一致），
        不允许任何形式的跨层 import（含函数内延迟导入）。
        """
        file_path = SRC_ROOT / "application" / "services" / "data_source_resolver.py"
        imports = _extract_imports(file_path)
        for imp in imports:
            assert not imp.startswith("infrastructure"), f"data_source_resolver 导入 infrastructure: {imp}"

    def test_engine_resolve_delegates_to_marker_and_resolver(self) -> None:
        """Engine 复杂度控制：Execute 前置逻辑委托标记解析器 + Resolver（引擎本体仅编排）。"""
        source = (SRC_ROOT / "application" / "services" / "tool_execution_engine.py").read_text(encoding="utf-8")
        assert "parse_data_source_markers" in source
        assert "inject_data_sources" in source
        assert "set_data_source_resolver" in source
        # __init__ 参数数量不变（Story 4.4 AC-7.4 保护：llm_client/sandbox/retry_policy/repository 4 参数）
        import inspect

        from src.application.services.tool_execution_engine import ToolExecutionEngine

        params = list(inspect.signature(ToolExecutionEngine.__init__).parameters)
        assert params == ["self", "llm_client", "sandbox", "retry_policy", "tool_execution_repository"]


# ============================================================
# 测试类 5: 异常码段校验
# ============================================================


class TestDataSourceExceptionCodes:
    """EXCEPTION_410-413 ∈ data_source 子域（410-419）。"""

    def test_codes_in_subdomain_range(self) -> None:
        from src.domain.exceptions import (
            DataSourceError,
            DataSourceRateLimitError,
            DataSourceResponseError,
            DataSourceUnavailableError,
        )

        for cls in (DataSourceError, DataSourceUnavailableError, DataSourceRateLimitError, DataSourceResponseError):
            code_num = int(cls.code.split("_")[1])
            assert 410 <= code_num <= 419, f"{cls.__name__} 编码 {cls.code} 超出 data_source 子域范围"

    def test_code_range_registered(self) -> None:
        from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN, CODE_RANGES

        assert CODE_RANGES["data_source"] == (410, 419)
        for cls_name in EXPECTED_EXCEPTION_CODES:
            assert _CLASS_TO_SUBDOMAIN[cls_name] == "data_source"

    def test_exception_codes_match_contract(self) -> None:
        from src.domain import exceptions as exc_mod

        for cls_name, expected_code in EXPECTED_EXCEPTION_CODES.items():
            cls = getattr(exc_mod, cls_name)
            assert cls.code == expected_code
