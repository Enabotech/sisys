"""Story 4-6 架构约束验证测试（SDD 验证——epics 硬路径，无 _arch_ 前缀）

验证维度（Story Task 8 规范）：
- 领域零依赖（AST 扫描 tool_version 相关 domain 文件——test_red_blue_debate 先例）
- 依赖方向（domain ← application ← infrastructure；应用层禁 import infrastructure）
- 端口元数据（2 新端口 PortSpec 全字段 + tool_execution_service v1.3.0 升级断言）
- 事件通道双登记（3 事件 yaml + DEFAULT_MAPPINGS 同步）
- 执行链零改动（Engine/Validator/SandboxSecurityDecorator 不 import tool_version_service）
- 禁止服务文件本地 Protocol
"""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import pytest

from src.domain.ports.registry import PortSpec, _global_registry

# 领域层禁止导入的第三方包（架构测试目录私有清单——test_red_blue_debate.py 先例）
FORBIDDEN_IMPORTS = frozenset(
    {
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
        "httpx",
        "aiohttp",
        "requests",
    }
)

# Story 4-6 领域层交付文件
DOMAIN_FILES = [
    Path("src/domain/entities/tool_version.py"),
    Path("src/domain/events/tool_version_events.py"),
    Path("src/domain/exceptions/tool_version_exceptions.py"),
    Path("src/domain/ports/tool_version_repository.py"),
    Path("src/domain/services/tool_version_policy.py"),
]

# 应用层交付文件（依赖方向校验面）
APPLICATION_FILES = [
    Path("src/application/ports/tool_version_service.py"),
    Path("src/application/services/tool_version_service.py"),
]

# 修改的执行链文件（版本路由不得渗入引擎/装饰器）
EXECUTION_CHAIN_FILES = [
    Path("src/application/services/tool_execution_engine.py"),
    Path("src/application/services/tool_output_validator.py"),
    Path("src/application/services/sandbox_security_decorator.py"),
]

SERVICE_AND_IMPL_FILES = [
    Path("src/application/services/tool_version_service.py"),
    Path("src/infrastructure/storage/inmemory/tool_version_repository.py"),
    Path("src/infrastructure/storage/postgresql/repository/tool_version_repository.py"),
]

INFRASTRUCTURE_FILES = [
    Path("src/infrastructure/storage/inmemory/tool_version_repository.py"),
    Path("src/infrastructure/storage/postgresql/repository/tool_version_repository.py"),
]


def _extract_imports(file_path: Path) -> set[str]:
    """AST 提取模块顶层 import 名（test_docker_sandbox.py:53-69 先例）。"""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def _assert_exists_with_failure(file_path: Path, message: str) -> None:
    """存在性断言（失败消息含违规文件路径与违规项——可定位到文件）。"""
    if not file_path.exists():
        pytest.fail(f"{message}: {file_path} 不存在")


# ===================================================================
# 领域零依赖（FR-AR-01）
# ===================================================================


class TestDomainLayerZeroDependency:
    """Story 4-6 领域文件零第三方依赖 + 零向上层依赖。"""

    @pytest.mark.parametrize("file_path", DOMAIN_FILES, ids=lambda p: p.name)
    def test_domain_files_no_forbidden_imports(self, file_path: Path) -> None:
        """tool_version 领域文件零第三方依赖。"""
        _assert_exists_with_failure(file_path, "领域交付文件缺失")
        violated = _extract_imports(file_path) & FORBIDDEN_IMPORTS
        assert not violated, f"{file_path} 违反领域零依赖: {violated}"

    @pytest.mark.parametrize("file_path", DOMAIN_FILES, ids=lambda p: p.name)
    def test_domain_files_no_upward_layer_imports(self, file_path: Path) -> None:
        """领域文件不导入 application/interfaces/infrastructure。"""
        upward = {"application", "interfaces", "infrastructure", "composition_root"}
        violated = _extract_imports(file_path) & upward
        assert not violated, f"{file_path} 违反依赖方向（domain 不可向上依赖）: {violated}"


# ===================================================================
# 依赖方向（application 禁 infrastructure；infrastructure 依赖领域端口）
# ===================================================================


class TestDependencyDirection:
    """四层依赖方向校验。"""

    @pytest.mark.parametrize("file_path", APPLICATION_FILES, ids=lambda p: p.name)
    def test_application_files_no_infrastructure(self, file_path: Path) -> None:
        """应用层文件禁 import infrastructure（分层红线——标量注入依据）。"""
        _assert_exists_with_failure(file_path, "应用层交付文件缺失")
        forbidden_layers = {"infrastructure", "interfaces", "composition_root"}
        violated = _extract_imports(file_path) & forbidden_layers
        assert not violated, f"{file_path} 应用层不可依赖基础设施/接口层: {violated}"

    @pytest.mark.parametrize("file_path", INFRASTRUCTURE_FILES, ids=lambda p: p.name)
    def test_infrastructure_depends_on_domain_port(self, file_path: Path) -> None:
        """基础设施实现依赖领域端口（依赖倒置）。"""
        source = file_path.read_text(encoding="utf-8")
        assert "src.domain.ports.tool_version_repository" in source, f"{file_path} 必须 import 领域端口（依赖倒置）"


# ===================================================================
# 端口元数据（PortSpec 完整性）
# ===================================================================


class TestPortRegistryMetadata:
    """2 新端口 + 1 升级端口的 PortSpec 断言。"""

    @pytest.mark.parametrize(
        ("port_name", "expected_version", "expected_tags"),
        [
            ("tool_version_repository", "v1.0.0", ("tool", "version", "repository", "postgresql", "sqlalchemy")),
            ("tool_version_service", "v1.0.0", ("tool", "version", "service")),
        ],
        ids=["repository", "service"],
    )
    def test_new_port_specs(
        self,
        port_name: str,
        expected_version: str,
        expected_tags: tuple[str, ...],
    ) -> None:
        """新端口 PortSpec 全字段（10 字段元数据完整）。"""
        spec = _global_registry.get(port_name)
        assert spec is not None, f"端口 {port_name} 未在组合根注册"
        assert spec.name == port_name
        assert spec.version == expected_version
        assert spec.lifetime.value == "scoped"
        assert spec.owner == "tool-team"
        assert set(expected_tags).issubset(set(spec.tags))
        assert spec.impl is not None
        assert spec.module
        assert spec.interface is not None

    def test_tool_execution_service_upgraded_v1_3_0(self) -> None:
        """tool_execution_service 升级 v1.3.0 + versioned tag（4-3 P0-A 先例）。"""
        spec = _global_registry.get("tool_execution_service")
        assert spec is not None
        assert spec.version == "v1.3.0"
        assert "versioned" in spec.tags
        assert "v1.2.0" not in spec.compatibility  # 替换语义（v1.0.0 保留）

    def test_port_spec_has_all_10_fields(self) -> None:
        """PortSpec 数据类 10 字段结构完整。"""
        expected = {
            "name",
            "version",
            "interface",
            "impl",
            "module",
            "lifetime",
            "owner",
            "compatibility",
            "tags",
            "deprecated",
        }
        assert {f.name for f in fields(PortSpec)} == expected


# ===================================================================
# 事件通道双登记（yaml + DEFAULT_MAPPINGS 同步）
# ===================================================================


class TestEventChannelSync:
    """3 事件双通道配置同步（防配置漂移门禁）。"""

    def test_three_events_in_default_mappings(self) -> None:
        """DEFAULT_MAPPINGS 已注册 3 事件（realtime）。"""
        from src.infrastructure.messaging.channel_router import (
            ChannelRouter,
            DeliveryMode,
        )

        for event_type in ("ToolVersionRegistered", "ToolVersionPublished", "ToolRolledBack"):
            mapping = ChannelRouter.DEFAULT_MAPPINGS.get(event_type)
            assert mapping is not None, f"DEFAULT_MAPPINGS 未注册 {event_type}"
            assert mapping.delivery_mode is DeliveryMode.REALTIME

    def test_three_events_in_yaml(self) -> None:
        """event_channels.yaml 已配置 3 事件。"""
        import yaml

        config = yaml.safe_load(Path("configs/event_channels.yaml").read_text(encoding="utf-8"))
        channels = config["event_channels"]
        for event_type in ("ToolVersionRegistered", "ToolVersionPublished", "ToolRolledBack"):
            assert event_type in channels, f"event_channels.yaml 未配置 {event_type}"
            assert channels[event_type]["delivery_mode"] == "realtime"


# ===================================================================
# 执行链零改动（版本路由不渗入引擎/装饰器）
# ===================================================================


class TestExecutionChainUntouched:
    """Engine/OutputValidator/SandboxSecurityDecorator 无版本路由代码。"""

    @pytest.mark.parametrize("file_path", EXECUTION_CHAIN_FILES, ids=lambda p: p.name)
    def test_no_version_routing_in_chain(self, file_path: Path) -> None:
        """执行链文件不 import tool_version 相关模块（路由在服务层）。"""
        source = file_path.read_text(encoding="utf-8")
        assert "tool_version_service" not in source, f"{file_path} 出现版本路由引用——路由应仅在 ToolExecutionService 服务层"
        assert "resolve_version" not in source

    def test_routing_lives_in_service_layer(self) -> None:
        """版本路由的实现位置在 ToolExecutionService（正向锚点）。"""
        source = Path("src/application/services/tool_execution_service.py").read_text(encoding="utf-8")
        assert "_resolve_execution_tool" in source
        assert "tool_version_service" in source


# ===================================================================
# 禁止服务文件本地 Protocol
# ===================================================================


class TestNoLocalProtocolInServiceFiles:
    """端口抽象统一在 ports/ 目录定义。"""

    @pytest.mark.parametrize("file_path", SERVICE_AND_IMPL_FILES, ids=lambda p: p.name)
    def test_no_local_protocol_definition(self, file_path: Path) -> None:
        """服务/实现文件禁止本地定义 Protocol。"""
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "Protocol":
                        pytest.fail(
                            f"{file_path} 本地定义了 Protocol（{node.name}）——"
                            "端口抽象必须定义在 src/domain/ports/ 或 src/application/ports/"
                        )


# ===================================================================
# 状态机守护（7 合法迁移格 / 8 触发语义常量锚点）
# ===================================================================


class TestStateMachineContract:
    """状态机迁移矩阵结构断言（静态契约锚点）。"""

    def test_valid_transitions_seven_cells(self) -> None:
        """VALID_TRANSITIONS 恰好 7 个合法 (from,to) 格。"""
        from src.domain.entities.tool_version import (
            VALID_TRANSITIONS,
            ToolVersionStatus,
        )

        cells = {(frm, to) for frm, targets in VALID_TRANSITIONS.items() for to in targets}
        assert len(cells) == 7, f"合法迁移格应为 7，实际 {len(cells)}: {cells}"
        # 关键迁移存在性（P0 修复的三格 + 回滚恢复）
        assert (ToolVersionStatus.PENDING, ToolVersionStatus.CANARY) in cells
        assert (ToolVersionStatus.CANARY, ToolVersionStatus.CANARY) in cells, "调档同态迁移"
        assert (ToolVersionStatus.CANARY, ToolVersionStatus.STABLE) in cells, "promote 毕业通道"
        assert (ToolVersionStatus.DEPRECATED, ToolVersionStatus.STABLE) in cells, "回滚恢复"

    def test_status_enum_values(self) -> None:
        """状态枚举小写值与 migration CHECK 值域一致。"""
        from src.domain.entities.tool_version import ToolVersionStatus

        assert {s.value for s in ToolVersionStatus} == {"pending", "canary", "stable", "deprecated"}
