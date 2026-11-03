"""Story 6-4 — 思维链归档端口契约测试（注册/spec 元数据/resolve/注入链）。

契约面（Task 3 循环 A 红→绿钦定——组合根三注册块守护）：
- chain_of_thought_archive_service：SINGLETON + 双注入（strategic_archive_service
  + resolve_optional("l4_object")——R1-F6）
- blm_chain_trace_use_case：SINGLETON 薄用例
- blm_planning_service lambda 增量注入第九依赖 chain_of_thought_archive_service
  （version v1.0.0→v1.1.0——恰 1 行版本变更 R1-F11）
- 版本 v 前缀 + 端口协议 interface + tags

形态对齐 test_port_contract_blm_planning.py（直接 import _global_registry——
6-1 先例形态；getsource 包含性断言——增量注入不破坏既有断言的验证基础）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/contracts/test_port_contract_chain_of_thought.py -v
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from src.application.ports.chain_of_thought_archive import ChainOfThoughtArchiveServicePort
from src.domain.ports.registry import Lifetime, _global_registry

PORT_NAMES: tuple[str, ...] = (
    "chain_of_thought_archive_service",
    "blm_chain_trace_use_case",
)


class TestChainOfThoughtArchiveContracts:
    """思维链归档服务端口契约（注册/元数据/resolve/注入链）。"""

    @pytest.mark.parametrize("port_name", PORT_NAMES)
    def test_port_registered(self, port_name: str) -> None:
        """注册可达（_global_registry 含两端口）。"""
        spec = _global_registry.get(port_name)
        assert spec is not None, f"端口 {port_name} 未注册（组合根三注册块缺失）"

    def test_archive_service_spec_metadata(self) -> None:
        """spec 元数据（interface/lifetime/tags）。"""
        spec = _global_registry.get("chain_of_thought_archive_service")
        assert spec is not None
        assert spec.interface is ChainOfThoughtArchiveServicePort
        assert spec.lifetime == Lifetime.SINGLETON
        assert "chain-of-thought" in spec.tags or "blm" in spec.tags

    def test_trace_use_case_spec_metadata(self) -> None:
        """用例端口元数据（SINGLETON 薄用例）。"""
        spec = _global_registry.get("blm_chain_trace_use_case")
        assert spec is not None
        assert spec.lifetime == Lifetime.SINGLETON

    @pytest.mark.parametrize("port_name", PORT_NAMES)
    def test_port_spec_version_present(self, port_name: str) -> None:
        """版本 v 前缀在位。"""
        spec = _global_registry.get(port_name)
        assert spec is not None
        assert spec.version.startswith("v"), f"端口 {port_name} 版本缺 v 前缀: {spec.version!r}"

    def test_archive_service_lambda_dual_injection(self) -> None:
        """双注入 lambda 源码（R1-F6——archive_service + resolve_optional l4_object）。"""
        spec = _global_registry.get("chain_of_thought_archive_service")
        assert spec is not None and callable(spec.impl)
        source = inspect.getsource(spec.impl)
        assert "strategic_archive_service" in source, "lambda 未注入 strategic_archive_service（归档编排断裂）"
        assert "l4_object" in source, "lambda 未注入 l4_object（include_blob 解引用通道断裂——R1-F6）"

    def test_archive_service_resolves_to_implementation(self) -> None:
        """resolve 可达 + 实现类协议形态（注入链活体验证）。"""
        from src.domain.ports.resolver import get_resolver

        instance: Any = get_resolver().resolve("chain_of_thought_archive_service")
        assert isinstance(instance, ChainOfThoughtArchiveServicePort)

    def test_blm_planning_service_lambda_injects_chain_archive(self) -> None:
        """blm_planning_service lambda 增量注入第九依赖（既有 getsource 断言不破坏——
        包含性断言追加面）。"""
        spec = _global_registry.get("blm_planning_service")
        assert spec is not None and callable(spec.impl)
        source = inspect.getsource(spec.impl)
        assert "chain_of_thought_archive_service" in source, (
            "blm_planning_service lambda 未注入 chain_archive_service（6-4 挂接装配面断裂）"
        )
        assert spec.version == "v1.1.0", f"version 应升级 v1.1.0（恰 1 行版本变更——R1-F11）: {spec.version!r}"
