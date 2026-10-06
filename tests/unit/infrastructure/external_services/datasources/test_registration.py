"""数据源注册表单元测试（Story 4.1f 组合根收敛重构——R-REG）。

验证注册表 SSOT 的判定语义与组合根原手写注册区逐项等价：
- is_gate_open：A 组无条件恒真 / B 组 env 门（单键与 epo-ops 双键合取）/
  C 组凭据文件门（google-patents 双门：env 非空 + 文件存在）
- build_adapters_mapping：注册表派生聚合（未注册项跳过——等价原元组表循环）
- httpx_owned_port_names：china_nbs 恒排除（复用 CrawlerClientPort 无自持 httpx）
- 注册表完整性：12 条目 + 字段非空 + port_name/source_name 唯一 + tags 含 data-source
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

from src.infrastructure.external_services.datasources.registration import (
    DATA_SOURCE_REGISTRY,
    build_adapters_mapping,
    httpx_owned_port_names,
    is_gate_open,
)


def _env(values: dict[str, str]):
    """环境变量替身（缺省 None——与 os.getenv 缺省一致）。"""
    return lambda key: values.get(key)


class TestRegistryIntegrity:
    def test_twelve_entries_present(self) -> None:
        assert len(DATA_SOURCE_REGISTRY) == 12
        assert {r.source_name for r in DATA_SOURCE_REGISTRY} == {
            "world-bank",
            "imf",
            "eurostat",
            "uspto",
            "ipcc",
            "newsapi",
            "tavily",
            "china-nbs",
            "epo-ops",
            "sec-edgar",
            "comtrade",
            "google-patents",
        }

    def test_every_adapter_module_file_is_registered(self) -> None:
        """目录 → 注册表方向防线（Q1-F6——R-REG「漏注册静默」宣称的真闭合）。

        新适配器文件落盘但忘记在 DATA_SOURCE_REGISTRY 加条目时，既有测试全静默
        （三常量与契约表均派生自注册表——注册表里没有的源它们看不见）；本测试
        扫描 datasources 目录全部 *_adapter.py，文件 stem 集合必须是注册表
        impl_module 名集合的子集（漏登记即红）。
        """
        import src.infrastructure.external_services.datasources.registration as registration_module

        datasources_dir = Path(registration_module.__file__).resolve().parent
        adapter_stems = {Path(p).stem for p in glob.glob(str(datasources_dir / "*_adapter.py"))}
        registered_modules = {r.impl_module.rsplit(".", 1)[-1] for r in DATA_SOURCE_REGISTRY}
        assert adapter_stems <= registered_modules, (
            f"存在未登记注册表的适配器文件（新源接入须同步 DATA_SOURCE_REGISTRY）: {sorted(adapter_stems - registered_modules)}"
        )

    def test_fields_nonempty_and_unique(self) -> None:
        port_names = [r.port_name for r in DATA_SOURCE_REGISTRY]
        assert len(port_names) == len(set(port_names)), "port_name 应唯一"
        for r in DATA_SOURCE_REGISTRY:
            assert r.port_name.startswith("data_source_")
            assert r.impl_module.startswith("src.infrastructure.external_services.datasources.")
            assert r.impl_cls_name and r.config_module and r.config_cls_name
            assert "data-source" in r.tags

    def test_unconditional_group_has_no_gate(self) -> None:
        unconditional = {"world-bank", "imf", "eurostat", "ipcc", "china-nbs", "sec-edgar", "comtrade"}
        for r in DATA_SOURCE_REGISTRY:
            if r.source_name in unconditional:
                assert r.env_gate_keys == (), f"{r.source_name} 应为无条件注册（空门）"
                assert r.file_gate is False


class TestGateSemantics:
    def test_unconditional_always_open(self) -> None:
        wb = next(r for r in DATA_SOURCE_REGISTRY if r.source_name == "world-bank")
        assert is_gate_open(wb) is True  # 零 env 下恒真

    def test_single_key_gate(self) -> None:
        uspto = next(r for r in DATA_SOURCE_REGISTRY if r.source_name == "uspto")
        assert is_gate_open(uspto, getenv=_env({})) is False
        assert is_gate_open(uspto, getenv=_env({"USPTO_API_KEY": ""})) is False, "空串视为未配置"
        assert is_gate_open(uspto, getenv=_env({"USPTO_API_KEY": "fake"})) is True

    def test_dual_key_conjunction_epo(self) -> None:
        epo = next(r for r in DATA_SOURCE_REGISTRY if r.source_name == "epo-ops")
        assert is_gate_open(epo, getenv=_env({"EPO_OPS_CONSUMER_KEY": "fake"})) is False, "半凭据态不注册"
        assert is_gate_open(epo, getenv=_env({"EPO_OPS_CONSUMER_KEY": "fake", "EPO_OPS_CONSUMER_SECRET": "fake"})) is True

    def test_file_gate_google_patents(self, tmp_path: Path) -> None:
        gp = next(r for r in DATA_SOURCE_REGISTRY if r.source_name == "google-patents")
        fake_sa = tmp_path / "sa.json"
        fake_sa.write_text(json.dumps({"type": "service_account"}), encoding="utf-8")
        # 双门均满足（env 非空 + 文件存在）
        env_ok = _env({"GOOGLE_APPLICATION_CREDENTIALS": str(fake_sa), "GOOGLE_PATENTS_PROJECT_ID": "p"})
        assert is_gate_open(gp, getenv=env_ok) is True
        # env 存在但文件不存在
        env_no_file = _env({"GOOGLE_APPLICATION_CREDENTIALS": "/nonexistent/sa.json", "GOOGLE_PATENTS_PROJECT_ID": "p"})
        assert is_gate_open(gp, getenv=env_no_file) is False
        # 项目 ID 缺失
        assert is_gate_open(gp, getenv=_env({"GOOGLE_APPLICATION_CREDENTIALS": str(fake_sa)})) is False


class TestAdaptersMapping:
    def test_build_adapters_mapping_skips_unregistered(self) -> None:
        resolved = {"data_source_worldbank": object(), "data_source_tavily": object()}

        mapping = build_adapters_mapping(resolved.get)

        assert set(mapping) == {"world-bank", "tavily"}, "未注册项应跳过（优雅降级语义）"

    def test_httpx_owned_excludes_china_nbs(self) -> None:
        names = httpx_owned_port_names()
        assert "data_source_china_nbs" not in names, "china_nbs 复用 CrawlerClientPort 无自持 httpx，恒不在清理列表"
        assert len(names) == 11, f"12 注册源 - china_nbs = 11，实际 {len(names)}"


@pytest.mark.parametrize("registration", DATA_SOURCE_REGISTRY, ids=[r.source_name for r in DATA_SOURCE_REGISTRY])
def test_registry_entry_modules_importable(registration) -> None:
    """每条目的适配器与配置模块真实可导入（注册表↔实现零漂移防线——防注册表登记了不存在的模块）。"""
    impl_mod = __import__(registration.impl_module, fromlist=[registration.impl_cls_name])
    assert hasattr(impl_mod, registration.impl_cls_name)
    config_mod = __import__(registration.config_module, fromlist=[registration.config_cls_name])
    assert hasattr(config_mod, registration.config_cls_name)
