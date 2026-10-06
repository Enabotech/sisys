"""数据源适配器注册表（Story 4.1f 组合根收敛重构——R-REG）

**设计意图**：组合根（composition_root）是「组合」边界——只负责「怎么注册」；
「注册哪些数据源」是数据源域自身的清单事实，应收敛为声明式注册表。
12 个适配器原以 12 块手写注册代码散落在组合根函数体内（每新源叠加注册块 +
元组表行 + shutdown 行三处），造成组合根持续膨胀且多 SSOT 漂移（4-1f 代码
审查 R1-1 发现「静态表漏改静默」问题的结构根源）。

本模块为**数据源域唯一注册表 SSOT**：契约测试表（ADAPTER_PORT_SPECS）、架构
测试三文件静态表、组合根注册调用、shutdown 清理列表全部从本表派生。
新源接入只需在本表追加一条 `AdapterRegistration` 条目（+ 受益 Skill 声明联动）。

注册形态三类（与组合根原语义逐项等价——生产行为零变化约束）：
- A 组「无条件注册」：官方免费通道可达即注册（worldbank/imf/eurostat/ipcc/
  china_nbs/sec-edgar/comtrade）——china_nbs 特殊：复用 CrawlerClientPort，
  由 factory_kind="china_nbs" 承载其 resolver.resolve 工厂差异
- B 组「条件注册——环境变量门」：key/凭据 env 非空即注册（uspto/newsapi/tavily/
  epo-ops 双凭据合取）——env_gate_keys 元组全真判定（多键合取）
- C 组「条件注册——凭据文件门」：env 非空且文件存在（google-patents GCP 双门）
  ——env_gate_keys 含 GOOGLE_APPLICATION_CREDENTIALS + GOOGLE_PATENTS_PROJECT_ID
  且凭据文件存在（file_gate=True）
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AdapterRegistration:
    """数据源适配器注册声明（注册表单条目）。

    Attributes:
        port_name: 组合根端口名（data_source_<snake_name>）
        source_name: 数据源 name（kebab-case——DataSourceRef.name / frontmatter 声明名 /
            resolver 映射键 / ADAPTER_SSOT 键 四位一体）
        impl_module: 适配器实现模块路径
        impl_cls_name: 适配器实现类名
        config_module: 配置模块路径
        config_cls_name: 配置类名
        env_gate_keys: 环境变量门元组（无条件注册源为空元组；多键为合取判定）
        file_gate: 凭据文件门（True 时 env_gate_keys 首键所引路径须实际存在——
            google-patents GCP 双门专用）
        factory_kind: 工厂形态（"default"=Config.from_env() 单参构造；
            "china_nbs"=resolver.resolve("crawler_client") 特殊工厂）
        tags: 端口 tags（含 data-source 公共标记）
    """

    port_name: str
    source_name: str
    impl_module: str
    impl_cls_name: str
    config_module: str
    config_cls_name: str
    env_gate_keys: tuple[str, ...] = ()
    file_gate: bool = False
    factory_kind: str = "default"
    tags: tuple[str, ...] = ()


_DS_MODULE_PREFIX = "src.infrastructure.external_services.datasources."
_CONFIG_MODULE_PREFIX = "src.infrastructure.config."


def _impl(port_file: str) -> str:
    return _DS_MODULE_PREFIX + port_file


def _cfg(config_file: str) -> str:
    return _CONFIG_MODULE_PREFIX + config_file


# ============================================================================
# 数据源注册表 SSOT（12 条目——4.1f 终态 + D-09）
# 新源接入：在本表追加条目 + 受益 Skill 声明联动（断言联动清单驱动）
# ============================================================================
DATA_SOURCE_REGISTRY: tuple[AdapterRegistration, ...] = (
    # ===== A 组：无条件注册（官方免费通道可达即注册——worldbank 范式） =====
    AdapterRegistration(
        port_name="data_source_worldbank",
        source_name="world-bank",
        impl_module=_impl("worldbank_adapter"),
        impl_cls_name="WorldBankAdapter",
        config_module=_cfg("worldbank"),
        config_cls_name="WorldBankConfig",
        tags=("data-source", "worldbank", "statistics"),
    ),
    AdapterRegistration(
        port_name="data_source_imf",
        source_name="imf",
        impl_module=_impl("imf_adapter"),
        impl_cls_name="IMFAdapter",
        config_module=_cfg("imf"),
        config_cls_name="IMFConfig",
        tags=("data-source", "imf", "statistics"),
    ),
    AdapterRegistration(
        port_name="data_source_eurostat",
        source_name="eurostat",
        impl_module=_impl("eurostat_adapter"),
        impl_cls_name="EurostatAdapter",
        config_module=_cfg("eurostat"),
        config_cls_name="EurostatConfig",
        tags=("data-source", "eurostat", "statistics"),
    ),
    AdapterRegistration(
        port_name="data_source_uspto",
        source_name="uspto",
        impl_module=_impl("uspto_adapter"),
        impl_cls_name="USPTOAdapter",
        config_module=_cfg("uspto"),
        config_cls_name="USPTOConfig",
        # R3-P1-3：PatentsView v1 端点强制 X-Api-Key，uspto 转条件注册（无 Key 时注册
        # 只会必然 403——条件注册使配置缺失显式化，对齐 newsapi/tavily 模式）
        env_gate_keys=("USPTO_API_KEY",),
        tags=("data-source", "uspto", "patent"),
    ),
    AdapterRegistration(
        port_name="data_source_ipcc",
        source_name="ipcc",
        impl_module=_impl("ipcc_adapter"),
        impl_cls_name="IPCCAdapter",
        config_module=_cfg("ipcc"),
        config_cls_name="IPCCConfig",
        tags=("data-source", "ipcc", "environment"),
    ),
    # ===== B 组：环境变量门条件注册（Key/凭据非空即注册——bool() 拒空串） =====
    AdapterRegistration(
        port_name="data_source_newsapi",
        source_name="newsapi",
        impl_module=_impl("newsapi_adapter"),
        impl_cls_name="NewsAPIAdapter",
        config_module=_cfg("newsapi"),
        config_cls_name="NewsAPIConfig",
        env_gate_keys=("NEWSAPI_API_KEY",),
        tags=("data-source", "newsapi", "news"),
    ),
    AdapterRegistration(
        port_name="data_source_tavily",
        source_name="tavily",
        impl_module=_impl("tavily_adapter"),
        impl_cls_name="TavilyAdapter",
        config_module=_cfg("tavily"),
        config_cls_name="TavilyConfig",
        env_gate_keys=("TAVILY_API_KEY",),
        tags=("data-source", "tavily", "web-search"),
    ),
    # ===== A 组特殊：china_nbs（复用 CrawlerClientPort——禁止直连抓取 PoC v2 验证 403） =====
    AdapterRegistration(
        port_name="data_source_china_nbs",
        source_name="china-nbs",
        impl_module=_impl("china_nbs_adapter"),
        impl_cls_name="ChinaNBSAdapter",
        config_module=_cfg("china_nbs"),
        config_cls_name="ChinaNBSConfig",
        factory_kind="china_nbs",
        tags=("data-source", "china-nbs", "crawler"),
    ),
    # ===== Story 4.1f 三新源 =====
    AdapterRegistration(
        port_name="data_source_epo_ops",
        source_name="epo-ops",
        impl_module=_impl("epo_ops_adapter"),
        impl_cls_name="EpoOpsAdapter",
        config_module=_cfg("epo_ops"),
        config_cls_name="EpoOpsConfig",
        # OAuth2 双凭据门（Consumer Key/Secret 任一缺失即不注册——双门合取）
        env_gate_keys=("EPO_OPS_CONSUMER_KEY", "EPO_OPS_CONSUMER_SECRET"),
        tags=("data-source", "epo-ops", "patent"),
    ),
    AdapterRegistration(
        port_name="data_source_sec_edgar",
        source_name="sec-edgar",
        impl_module=_impl("sec_edgar_adapter"),
        impl_cls_name="SecEdgarAdapter",
        config_module=_cfg("sec_edgar"),
        config_cls_name="SecEdgarConfig",
        tags=("data-source", "sec-edgar", "financial-report"),
    ),
    AdapterRegistration(
        port_name="data_source_comtrade",
        source_name="comtrade",
        impl_module=_impl("comtrade_adapter"),
        impl_cls_name="ComtradeAdapter",
        config_module=_cfg("comtrade"),
        config_cls_name="ComtradeConfig",
        tags=("data-source", "comtrade", "trade-statistics"),
    ),
    # ===== D-09：google-patents（GCP 双门——凭据文件存在 + 项目 ID） =====
    AdapterRegistration(
        port_name="data_source_google_patents",
        source_name="google-patents",
        impl_module=_impl("google_patents_adapter"),
        impl_cls_name="GooglePatentsAdapter",
        config_module=_cfg("google_patents"),
        config_cls_name="GooglePatentsConfig",
        env_gate_keys=("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_PATENTS_PROJECT_ID"),
        file_gate=True,
        tags=("data-source", "google-patents", "patent"),
    ),
)


def is_gate_open(registration: AdapterRegistration, *, getenv: Callable[[str], str | None] = os.getenv) -> bool:
    """判定注册门是否开启（与组合根原判定语义逐项等价——bool() 拒空串）。

    Args:
        registration: 注册条目
        getenv: 环境变量读取函数（可注入测试替身——默认 os.getenv）

    Returns:
        True = 门开（应注册）；无条件注册源恒 True（空门元组 all() 恒真）
    """
    env_open = all(bool(getenv(key)) for key in registration.env_gate_keys)
    if not env_open:
        return False
    if registration.file_gate:
        credentials_path = getenv(registration.env_gate_keys[0]) or ""
        return Path(credentials_path).is_file()
    return True


def _make_impl_factory(registration: AdapterRegistration) -> Callable[[Any], Any]:
    """构造注册工厂（lambda 延迟 import——组合根原范式同款闭包陷阱防线：
    Config 经模块级 `__import__` 延迟加载，注册期不导入适配器/配置模块）。"""

    def factory(resolver: Any) -> Any:
        config_mod = __import__(registration.config_module, fromlist=[registration.config_cls_name])
        config = getattr(config_mod, registration.config_cls_name).from_env()
        impl_mod = __import__(registration.impl_module, fromlist=[registration.impl_cls_name])
        impl_cls = getattr(impl_mod, registration.impl_cls_name)
        if registration.factory_kind == "china_nbs":
            return impl_cls(crawler_client=resolver.resolve("crawler_client"), config=config)
        return impl_cls(config=config)

    return factory


def register_all_data_sources(register_port_fn: Callable[..., Any]) -> None:
    """按注册表注册全部数据源（门开者注册，门关者跳过——条件注册语义不变）。

    Args:
        register_port_fn: 组合根的 register_port 便捷函数（依赖注入——
            避免本模块 import 组合根造成循环依赖）
    """
    from src.domain.ports.data_source import DataSourcePort
    from src.domain.ports.registry import Lifetime

    for registration in DATA_SOURCE_REGISTRY:
        if not is_gate_open(registration):
            continue
        register_port_fn(
            name=registration.port_name,
            version="v1.0.0",
            interface=DataSourcePort,
            impl=_make_impl_factory(registration),
            module=registration.impl_module,
            lifetime=Lifetime.SINGLETON,
            owner="tool-team",
            tags=registration.tags,
        )


def build_adapters_mapping(resolve_optional: Callable[[str], Any]) -> dict[str, Any]:
    """聚合已注册的数据源适配器（未注册项跳过——原 _build_data_source_adapters 等价物）。

    Args:
        resolve_optional: 组合根 resolver.resolve_optional(port_name) 委托
    """
    adapters: dict[str, Any] = {}
    for registration in DATA_SOURCE_REGISTRY:
        adapter = resolve_optional(registration.port_name)
        if adapter is not None:
            adapters[registration.source_name] = adapter
    return adapters


def httpx_owned_port_names() -> tuple[str, ...]:
    """shutdown 清理列表（自持 httpx 客户端的端口——china_nbs 复用 CrawlerClientPort
    无自持客户端，恒不在列；与原硬编码列表语义等价）。"""
    return tuple(r.port_name for r in DATA_SOURCE_REGISTRY if r.factory_kind != "china_nbs")


__all__ = [
    "AdapterRegistration",
    "DATA_SOURCE_REGISTRY",
    "build_adapters_mapping",
    "httpx_owned_port_names",
    "is_gate_open",
    "register_all_data_sources",
]
