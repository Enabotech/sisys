"""Story 7-1 — 统一 CLI 端口消费契约测试（12 唯一端口注册面可达）。

Subtask 0.4 载体：AC-5 表是唯一事实源（SSOT）——12 命令构成 13 个命令-端口
消费对（tool_registry_service 被 tool list/schema 双命令消费），唯一注册名
12 个。本测试逐一断言注册面可达与元数据契约，防注册名漂移（6.4-DF2 同族
守卫诉求在 CLI 消费面的落地）。

形态对齐既有零 IO 先例：test_port_contract_blm_planning.py（多端口元数据
+ resolve 可达断言）与 test_port_contract_agent_checkpoint.py（PortSpec
维度断言）。契约测试不执行业务 IO（resolve 构造仅对象组装）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_unified_cli.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.ports.registry import _global_registry

# 12 唯一端口清单（AC-5 表 SSOT）：名称 → (interface 类导入函数, 期望 lifetime)
# 消费对 13 个：tool_registry_service 被 tool list 与 tool schema 双命令消费。
_PORT_IMPORTS: dict[str, tuple[str, str, str]] = {
    "document_upload_service": ("src.application.services.document_upload_service", "DocumentUploadService", "SCOPED"),
    "document_parsing_service": ("src.application.services.document_parsing_service", "DocumentParsingService", "SCOPED"),
    "tool_registry_service": ("src.application.ports.tool_registry_service", "ToolRegistryServicePort", "SCOPED"),
    "skill_loader": ("src.application.ports.skill_loader", "SkillLoaderPort", "SCOPED"),
    "tool_execution_service": ("src.application.ports.tool_execution_service", "ToolExecutionServicePort", "SCOPED"),
    "run_tool_chain_use_case": ("src.application.use_cases.run_tool_chain", "RunToolChainUseCase", "SCOPED"),
    "agent_workflow_use_case": ("src.application.use_cases.run_agent_workflow", "RunAgentWorkflowUseCase", "SINGLETON"),
    "blm_planning_use_case": ("src.application.use_cases.run_blm_planning", "RunBlmPlanningUseCase", "SINGLETON"),
    "checkpoint_recovery_use_case": ("src.application.use_cases.create_checkpoint", "RecoverCheckpointUseCase", "SINGLETON"),
    "checkpoint_list_use_case": ("src.application.use_cases.checkpoint_approval", "ListCheckpointsUseCase", "SINGLETON"),
    "checkpoint_recovery_execute_use_case": (
        "src.application.use_cases.checkpoint_approval",
        "ExecuteCheckpointRecoveryUseCase",
        "SINGLETON",
    ),
    "blm_chain_trace_use_case": ("src.application.use_cases.get_blm_chain_trace", "GetBlmChainTraceUseCase", "SINGLETON"),
}

# 13 命令-端口消费对（12 命令 → 端口映射；tool_registry_service 双命令消费）
_COMMAND_PORT_PAIRS: tuple[tuple[str, str], ...] = (
    ("document upload", "document_upload_service"),
    ("document parse", "document_parsing_service"),
    ("tool list", "tool_registry_service"),
    ("tool schema", "tool_registry_service"),
    ("tool schema", "skill_loader"),
    ("tool run", "tool_execution_service"),
    ("tool chain run", "run_tool_chain_use_case"),
    ("agent run", "agent_workflow_use_case"),
    ("plan generate", "blm_planning_use_case"),
    ("checkpoint list", "checkpoint_list_use_case"),
    ("checkpoint show", "checkpoint_recovery_use_case"),
    ("checkpoint recover", "checkpoint_recovery_execute_use_case"),
    ("archive query", "blm_chain_trace_use_case"),
)


def _interface_cls(name: str) -> Any:
    """按端口名延迟导入 interface 类（契约测试零业务 IO）。"""
    import importlib

    module_path, cls_name, _ = _PORT_IMPORTS[name]
    return getattr(importlib.import_module(module_path), cls_name)


class TestUnifiedCliPortContracts:
    """统一 CLI 12 唯一端口契约（注册可达/元数据/interface 一致/resolve 可达）。"""

    @pytest.mark.parametrize("name", sorted(_PORT_IMPORTS))
    def test_port_registered(self, name: str) -> None:
        """维度 1：注册可达（bootstrap 后 registry 可查——防注册名漂移）。"""
        spec = _global_registry.get(name)
        assert spec is not None, f"端口 {name} 未注册"

    @pytest.mark.parametrize("name", sorted(_PORT_IMPORTS))
    def test_interface_matches(self, name: str) -> None:
        """维度 2：interface 类一致（组合根注册的 interface 与端口契约导入一致）。"""
        spec = _global_registry.get(name)
        assert spec is not None
        assert spec.interface is _interface_cls(name), f"{name} interface 与契约导入不一致"

    @pytest.mark.parametrize("name", sorted(_PORT_IMPORTS))
    def test_lifetime_matches(self, name: str) -> None:
        """维度 3：生命周期一致（SCOPED 服务/SINGLETON 用例——组合根冻结态）。"""
        from src.domain.ports.registry import Lifetime

        spec = _global_registry.get(name)
        assert spec is not None
        expected = getattr(Lifetime, _PORT_IMPORTS[name][2])
        assert spec.lifetime == expected, f"{name} lifetime 应为 {expected}"

    @pytest.mark.parametrize("name", sorted(_PORT_IMPORTS))
    def test_spec_metadata_complete(self, name: str) -> None:
        """维度 4：PortSpec 元数据齐备（version/module/owner/impl callable）。

        tags 不在断言面——document 两端口存量注册态 tags=()（非本 Story
        契约维度，改注册面超出 surgical 边界）。
        """
        spec = _global_registry.get(name)
        assert spec is not None
        assert spec.version.startswith("v"), f"{name} version 缺失"
        assert spec.module, f"{name} module 缺失"
        assert spec.owner, f"{name} owner 缺失"
        assert callable(spec.impl), f"{name} impl 应为工厂"

    @pytest.mark.parametrize("name", sorted(_PORT_IMPORTS))
    def test_resolve_yields_interface_instance(self, name: str) -> None:
        """维度 5：resolve 可达 + 实例满足 interface 契约（真实构造仅对象组装零业务 IO）。"""
        from src.domain.ports.resolver import resolve

        instance = resolve(name)
        interface_cls = _interface_cls(name)
        assert isinstance(instance, interface_cls), f"{name} resolve 产物应实现 {interface_cls.__name__}"


class TestCommandPortConsumptionMatrix:
    """13 命令-端口消费对口径守卫（12 唯一端口 / 13 消费对——R5-1 口径）。"""

    def test_consumption_pairs_count(self) -> None:
        """消费对总数 = 13（12 命令中 tool schema 双端口消费、tool_registry 双命令消费）。"""
        assert len(_COMMAND_PORT_PAIRS) == 13

    def test_unique_port_count(self) -> None:
        """唯一端口数 = 12（tool_registry_service 双命令消费不重复计数）。"""
        assert len({port for _, port in _COMMAND_PORT_PAIRS}) == 12

    @pytest.mark.parametrize("pair", _COMMAND_PORT_PAIRS)
    def test_pair_port_registered(self, pair: tuple[str, str]) -> None:
        """逐消费对端口注册可达（AC-5 表 SSOT 接线断言清单）。"""
        command, port = pair
        spec = _global_registry.get(port)
        assert spec is not None, f"命令 {command} 消费的端口 {port} 未注册"

    def test_consumed_ports_all_in_registry(self) -> None:
        """消费面端口全部在 12 唯一端口清单内（禁超 SSOT 消费未登记端口）。"""
        consumed = {port for _, port in _COMMAND_PORT_PAIRS}
        assert consumed == set(_PORT_IMPORTS), "消费面与 12 唯一端口清单不一致"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
