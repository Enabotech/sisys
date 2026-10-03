"""Story 4.1b: 架构约束测试 — Skills 数据采集基础设施

验证：
1. domain 层零外部依赖（AST 黑名单扫描，显式含 httpx/tenacity——沙箱无网络不变量保护）
2. 端口注册完整性（PortSpec 10 字段 + 11 适配器 + resolver 全注册 + SINGLETON 生命周期）
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
# 与验收测试 test_acceptance_data_source 的 banned 集保持同步（18 项，R3-3 H8v2；
# sqlmodel/aioredis/instructor 属「domain 层已知诱惑库」防御性条目，非当前依赖）
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
    "sqlmodel",  # 防御性条目（ORM 诱惑库，对齐验收侧同集）
}

# 无条件注册的适配器端口清单（免 Key 统计类 + 4.1f 免 key/免费通道源）
ADAPTER_PORT_NAMES = (
    "data_source_worldbank",
    "data_source_imf",
    "data_source_eurostat",
    "data_source_ipcc",
    "data_source_china_nbs",
    "data_source_sec_edgar",  # 4.1f：免 key（官方 Fair Access，强制 UA）
    "data_source_comtrade",  # 4.1f：key 可选（preview 免 key 兜底——无条件注册）
)

# 需 API Key 的适配器（条件注册，Key 缺失时不注册——冷启动容错设计；
# uspto 自 R3-P1-3 起条件注册：PatentsView v1 端点强制 X-Api-Key 鉴权；
# epo-ops 自 4.1f 起条件注册：OAuth2 双凭据门——Consumer Key/Secret 双门合取；
# google-patents 自 4.1f D-09 起条件注册：GCP 双门（凭据文件存在 + 项目 ID））
KEYED_ADAPTER_PORT_NAMES = (
    "data_source_uspto",
    "data_source_newsapi",
    "data_source_tavily",
    "data_source_epo_ops",
    "data_source_google_patents",
)

# 端口 → (适配器模块名, 实现类名) 静态映射（条件注册端口无 Key 时不注册——
# 实现类合规校验不依赖运行时注册状态，R3-P1-3 同步；4.1f 三新源入册）
ADAPTER_IMPL_MODULES = {
    "data_source_worldbank": ("worldbank_adapter", "WorldBankAdapter"),
    "data_source_imf": ("imf_adapter", "IMFAdapter"),
    "data_source_eurostat": ("eurostat_adapter", "EurostatAdapter"),
    "data_source_uspto": ("uspto_adapter", "USPTOAdapter"),
    "data_source_ipcc": ("ipcc_adapter", "IPCCAdapter"),
    "data_source_newsapi": ("newsapi_adapter", "NewsAPIAdapter"),
    "data_source_tavily": ("tavily_adapter", "TavilyAdapter"),
    "data_source_china_nbs": ("china_nbs_adapter", "ChinaNBSAdapter"),
    "data_source_epo_ops": ("epo_ops_adapter", "EpoOpsAdapter"),
    "data_source_sec_edgar": ("sec_edgar_adapter", "SecEdgarAdapter"),
    "data_source_comtrade": ("comtrade_adapter", "ComtradeAdapter"),
    "data_source_google_patents": ("google_patents_adapter", "GooglePatentsAdapter"),
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
    """从 Python 文件中提取所有 import 语句的完整点分模块路径（ast.walk 天然覆盖函数内延迟 import）。"""
    if not file_path.exists():
        return []
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)  # 完整路径，不截断（截断会使跨层断言对 src.* 前缀失效）
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:  # 跳过相对 import（同包内，无跨层语义）
                imports.append(node.module)
    return imports


def _top_layer(module_path: str) -> str:
    """剥离可选 src. 前缀后的顶层包名（兼容 bare import 与 src. 前缀两种项目写法）。"""
    return module_path.removeprefix("src.").split(".")[0]


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
            assert _top_layer(imp) not in ("application", "interfaces", "infrastructure"), f"{file_path.name} 跨层导入: {imp}"


# ============================================================
# 测试类 2: 端口注册完整性
# ============================================================


class TestDataSourcePortRegistry:
    """11 适配器 + resolver 端口注册完整性（PortSpec 10 字段）。"""

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
        """需 Key 的适配器按条件注册（有 Key 注册 / 无 Key 不注册，两者均为合法状态）。

        uspto 自 R3-P1-3 起加入条件注册（PatentsView v1 强制 X-Api-Key）；
        epo-ops 自 4.1f 起加入（OAuth2 双凭据门——Consumer Key/Secret 多键合取：
        任一缺失即不注册，单键存在不构成注册条件——半凭据态语义防假阳性）；
        google-patents 自 4.1f D-09 起加入（GCP 双门——凭据文件存在 + 项目 ID，
        文件路径门特殊：env 存在但文件不存在同样不注册）。
        """
        import os
        from pathlib import Path

        for port_name, env_keys in (
            ("data_source_uspto", ("USPTO_API_KEY",)),
            ("data_source_newsapi", ("NEWSAPI_API_KEY",)),
            ("data_source_tavily", ("TAVILY_API_KEY",)),
            ("data_source_epo_ops", ("EPO_OPS_CONSUMER_KEY", "EPO_OPS_CONSUMER_SECRET")),
        ):
            spec = _global_registry.get(port_name)
            all_keys_present = all(bool(os.getenv(key)) for key in env_keys)
            if not all_keys_present:
                assert spec is None, f"{env_keys} 任一缺失时 {port_name} 不应注册（多键合取）"
            else:
                assert spec is not None, f"{env_keys} 全部存在时 {port_name} 应注册"

        # google-patents 特殊门：env 双键非空 + 凭据文件实际存在（D-09 双门）
        gp_spec = _global_registry.get("data_source_google_patents")
        gp_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        gp_enabled = bool(gp_credentials) and bool(os.getenv("GOOGLE_PATENTS_PROJECT_ID")) and Path(gp_credentials).is_file()
        if gp_enabled:
            assert gp_spec is not None, "GCP 双门齐备时 data_source_google_patents 应注册"
        else:
            assert gp_spec is None, "GCP 凭据文件缺失/项目 ID 缺失时 data_source_google_patents 不应注册"


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

    @pytest.mark.parametrize("port_name,impl_pair", list(ADAPTER_IMPL_MODULES.items()))
    def test_adapter_class_has_port_methods(self, port_name: str, impl_pair: tuple[str, str]) -> None:
        """实现类合规校验经静态模块映射加载（R3-P1-3 同步：条件注册端口在无 Key
        环境未注册——`_global_registry.get` 返回 None 会使校验误红，改不依赖注册状态）"""
        import importlib

        module_name, cls_name = impl_pair
        mod = importlib.import_module(f"src.infrastructure.external_services.datasources.{module_name}")
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
            assert _top_layer(imp) != "infrastructure", f"{file_path.name} 导入 infrastructure: {imp}"

    def test_data_source_resolver_has_no_infrastructure_dependency(self) -> None:
        """data_source_resolver 全文件禁止 import infrastructure（依赖方向强制）。

        应用层缓存键构造内联实现（与 key_builder 输出格式一致），
        不允许任何形式的跨层 import（含函数内延迟导入）。
        """
        file_path = SRC_ROOT / "application" / "services" / "data_source_resolver.py"
        imports = _extract_imports(file_path)
        for imp in imports:
            assert _top_layer(imp) != "infrastructure", f"data_source_resolver 导入 infrastructure: {imp}"

    def test_cross_layer_assertion_mutation_guard(self, tmp_path: Path) -> None:
        """变异验证（R2-2-C3 空断言防护）：跨层违规 import 必须被判定逻辑捕获。

        历史上 _extract_imports 截断模块路径（split(".")[0] 恒为 "src"），
        跨层断言对 src.* 前缀 import 永不命中（空断言）。本用例用含违规 import
        的临时文件做阳性对照，钉死断言判别力。
        """
        violating = tmp_path / "violating_service.py"
        violating.write_text(
            "from src.infrastructure.storage.redis import key_builder\n"
            "from src.domain.ports.data_source import DataSourcePort\n",
            encoding="utf-8",
        )
        imports = _extract_imports(violating)
        assert any(_top_layer(imp) == "infrastructure" for imp in imports), (
            "变异验证失败：含 src.infrastructure 导入未被跨层判定捕获（断言空转回归）"
        )
        clean = tmp_path / "clean_service.py"
        clean.write_text("from src.domain.ports.data_source import DataSourcePort\n", encoding="utf-8")
        assert all(_top_layer(imp) != "infrastructure" for imp in _extract_imports(clean))

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
