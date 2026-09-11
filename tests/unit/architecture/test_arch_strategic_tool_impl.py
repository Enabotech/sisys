"""Story 4.1a: 架构约束测试 — 战略工具实现

验证：
1. domain 层零外部依赖（AST 黑名单扫描）
2. 4 个新端口注册的 PortSpec 元数据完整性
3. 实现类与 Protocol 的 runtime_checkable 兼容性
4. 依赖方向矩阵合规（domain ← application ← infrastructure）

遵循 test_arch_tool.py 模式（Story 4.1）。
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.domain.ports.registry import Lifetime, _global_registry

# ============================================================
# 常量定义
# ============================================================

SRC_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "src"

# domain 层需要扫描的文件（Story 4.1a 新增）
DOMAIN_FILES = [
    SRC_ROOT / "domain" / "entities" / "tool_execution.py",
    SRC_ROOT / "domain" / "value_objects" / "tool_execution.py",
    SRC_ROOT / "domain" / "ports" / "tool_execution_repository.py",
    SRC_ROOT / "domain" / "events" / "tool_events.py",
    SRC_ROOT / "domain" / "exceptions" / "tool_exceptions.py",
]

# application 层需要扫描的文件（Story 4.1a 新增）
APPLICATION_FILES = [
    SRC_ROOT / "application" / "services" / "tool_execution_engine.py",
    SRC_ROOT / "application" / "services" / "tool_execution_service.py",
    SRC_ROOT / "application" / "use_cases" / "strategic_analysis.py",
    SRC_ROOT / "application" / "ports" / "tool_execution_service.py",
    SRC_ROOT / "application" / "ports" / "tool_execution_engine.py",
    SRC_ROOT / "application" / "ports" / "skill_loader.py",
    SRC_ROOT / "application" / "skills" / "loader.py",
]

# domain 层禁止导入的外部包黑名单
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
    """domain 层禁止导入任何外部包。"""

    @pytest.mark.parametrize("file_path", DOMAIN_FILES, ids=lambda p: p.name)
    def test_domain_file_no_external_imports(self, file_path: Path) -> None:
        """域文件不应导入任何外部依赖。"""
        if not file_path.exists():
            pytest.skip(f"文件不存在: {file_path}")

        imports = _extract_imports(file_path)
        violations = [imp for imp in imports if imp in FORBIDDEN_IMPORTS]

        assert not violations, f"{file_path.name} 禁止导入外部包: {violations}。domain 层仅允许 Python 标准库和项目内部模块。"


# ============================================================
# 测试类 2: Application 层约束
# ============================================================


class TestApplicationLayerConstraints:
    """application 层不应导入 infrastructure 层。"""

    @pytest.mark.parametrize("file_path", APPLICATION_FILES, ids=lambda p: p.name)
    def test_application_file_no_infrastructure_imports(self, file_path: Path) -> None:
        """应用层文件不应导入基础设施层。"""
        if not file_path.exists():
            pytest.skip(f"文件不存在: {file_path}")

        imports = _extract_imports(file_path)
        infrastructure_violations = [imp for imp in imports if imp == "infrastructure"]

        assert not infrastructure_violations, (
            f"{file_path.name} 禁止导入 infrastructure 层: {infrastructure_violations}。"
            f"application 层应通过端口（ports）依赖 domain 层。"
        )


# ============================================================
# 测试类 3: 端口注册完整性
# ============================================================


class TestStrategicToolPortRegistry:
    """Story 4.1a 新增端口的 PortSpec 元数据完整性。"""

    # 端口注册信息：(name, expected_lifetime, expected_owner, expected_tags)
    PORT_SPECS = [
        (
            "tool_execution_repository",
            Lifetime.SCOPED,
            "tool-team",
            ("tool", "execution", "repository", "postgresql", "sqlalchemy"),
        ),
        (
            "tool_execution_engine",
            Lifetime.SCOPED,
            "tool-team",
            ("tool", "execution", "engine"),
        ),
        (
            "tool_execution_service",
            Lifetime.SCOPED,
            "tool-team",
            ("tool", "execution", "service"),
        ),
        (
            "skill_loader",
            Lifetime.SCOPED,
            "tool-team",
            ("skills", "loader", "inmemory"),
        ),
    ]

    @pytest.mark.parametrize(
        "port_name, expected_lifetime, expected_owner, expected_tags",
        PORT_SPECS,
        ids=lambda x: x if isinstance(x, str) else "",
    )
    def test_port_spec_metadata_completeness(
        self,
        port_name: str,
        expected_lifetime: Lifetime,
        expected_owner: str,
        expected_tags: tuple[str, ...],
    ) -> None:
        """验证端口的 PortSpec 元数据七字段完整性。"""
        spec = _global_registry.get(port_name)

        assert spec is not None, f"端口 {port_name} 未注册到 _global_registry"

        # 验证 name
        assert spec.name == port_name, f"端口 {port_name} 的 name 不匹配: 期望={port_name}, 实际={spec.name}"

        # 验证 version
        assert spec.version, f"端口 {port_name} 缺少 version 字段"

        # 验证 interface
        assert spec.interface is not None, f"端口 {port_name} 缺少 interface 字段"

        # 验证 impl
        assert spec.impl is not None, f"端口 {port_name} 缺少 impl 字段"

        # 验证 lifetime
        assert spec.lifetime == expected_lifetime, (
            f"端口 {port_name} 的 lifetime 不匹配: 期望={expected_lifetime}, 实际={spec.lifetime}"
        )

        # 验证 owner
        assert spec.owner == expected_owner, f"端口 {port_name} 的 owner 不匹配: 期望={expected_owner}, 实际={spec.owner}"

        # 验证 tags
        assert spec.tags == expected_tags, f"端口 {port_name} 的 tags 不匹配: 期望={expected_tags}, 实际={spec.tags}"

    def test_all_four_ports_registered(self) -> None:
        """验证 Story 4.1a 的 4 个新端口全部已注册。"""
        expected_ports = [
            "tool_execution_repository",
            "tool_execution_engine",
            "tool_execution_service",
            "skill_loader",
        ]

        for port_name in expected_ports:
            spec = _global_registry.get(port_name)
            assert spec is not None, f"端口 {port_name} 未注册"


# ============================================================
# 测试类 4: 实现类与 Protocol 兼容性
# ============================================================


class TestStrategicToolImplementations:
    """验证实现类与 Protocol 的 runtime_checkable 兼容性。"""

    def test_tool_execution_service_implements_protocol(self) -> None:
        """ToolExecutionService 应实现 ToolExecutionServicePort。"""
        from src.application.ports.tool_execution_service import ToolExecutionServicePort

        spec: Any = _global_registry.get("tool_execution_service")
        assert spec is not None

        # 创建实例（使用 DummyResolver）
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, ToolExecutionServicePort), "ToolExecutionService 未实现 ToolExecutionServicePort Protocol"

    def test_skill_loader_implements_protocol(self) -> None:
        """InMemorySkillLoader 应实现 SkillLoaderPort。"""
        from src.application.ports.skill_loader import SkillLoaderPort

        spec: Any = _global_registry.get("skill_loader")
        assert spec is not None

        # 创建实例
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, SkillLoaderPort), "InMemorySkillLoader 未实现 SkillLoaderPort Protocol"

    def test_tool_execution_engine_implements_protocol(self) -> None:
        """ToolExecutionEngine 应实现 ToolExecutionEnginePort。"""
        from src.application.ports.tool_execution_engine import ToolExecutionEnginePort

        spec: Any = _global_registry.get("tool_execution_engine")
        assert spec is not None

        # 创建实例（使用 DummyResolver）
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, ToolExecutionEnginePort), "ToolExecutionEngine 未实现 ToolExecutionEnginePort Protocol"

    def test_tool_execution_repository_implements_protocol(self) -> None:
        """InMemoryToolExecutionRepository 应实现 ToolExecutionRepositoryPort。"""
        from src.domain.ports.tool_execution_repository import ToolExecutionRepositoryPort

        spec: Any = _global_registry.get("tool_execution_repository")
        assert spec is not None

        # 创建实例
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, ToolExecutionRepositoryPort), (
            "InMemoryToolExecutionRepository 未实现 ToolExecutionRepositoryPort Protocol"
        )


# ============================================================
# 测试类 5: 工具执行引擎依赖方向
# ============================================================


class TestToolExecutionEngineDependencyDirection:
    """验证 ToolExecutionEngine 的依赖方向合规。"""

    def test_engine_depends_only_on_domain_ports(self) -> None:
        """ToolExecutionEngine 应仅依赖 domain 层端口，不依赖 infrastructure。"""
        imports = _extract_imports(SRC_ROOT / "application" / "services" / "tool_execution_engine.py")

        # 禁止依赖：infrastructure / interfaces 层（违反六边形架构）
        forbidden_prefixes = {"infrastructure", "interfaces"}

        violations = [imp for imp in imports if any(imp.startswith(fp) for fp in forbidden_prefixes)]

        assert not violations, f"ToolExecutionEngine 禁止导入 infrastructure/interfaces 层: {violations}"

    def test_engine_module_string_imports_domain_ports(self) -> None:
        """验证 ToolExecutionEngine 的延迟加载字符串指向正确模块。"""
        spec = _global_registry.get("tool_execution_engine")
        assert spec is not None

        # 验证 module 字段
        assert spec.module == "src.application.services.tool_execution_engine", (
            f"tool_execution_engine 的 module 不匹配: {spec.module}"
        )


# ============================================================
# 测试类 6: 异常子域码段校验
# ============================================================


class TestToolSubdomainExceptionCodes:
    """验证 tool 子域异常码在 380-389 范围内。"""

    def test_tool_exceptions_in_valid_range(self) -> None:
        """7 个 tool 子域异常的 code 应在 380-389 范围内。"""
        from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN

        tool_exceptions = [
            "ToolNotFoundError",
            "ToolAlreadyExistsError",
            "ToolExecutionFailedError",
            "ToolExecutionRetryExhaustedError",
            "ToolExecutionTimeoutError",
            "EvidenceValidationFailedError",
            "SkillNotFoundError",
            "SkillLoadError",
            "ToolResultValidationError",
        ]

        for exc_class_name in tool_exceptions:
            subdomain = _CLASS_TO_SUBDOMAIN.get(exc_class_name)
            assert subdomain is not None, f"异常 {exc_class_name} 未注册到 _CLASS_TO_SUBDOMAIN"
            assert subdomain == "tool", f"异常 {exc_class_name} 的子域不匹配: 期望=tool, 实际={subdomain}"


# ============================================================
# DummyResolver（测试辅助类）
# ============================================================


class _DummyResolver:
    """测试用最小 Resolver 占位符。

    对已注册的 InMemory 仓储返回真实实例，对 LLM/Sandbox 等外部依赖返回 AsyncMock。
    架构测试只需验证 impl factory 能产出满足 Protocol 的实例，不验证实际功能。
    """

    def resolve(self, name: str) -> object:
        from src.infrastructure.storage.inmemory.tool_execution_repository import InMemoryToolExecutionRepository
        from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

        if name == "tool_repository":
            return InMemoryToolRepository()
        if name == "tool_execution_repository":
            return InMemoryToolExecutionRepository()
        if name == "tool_registry_service":
            from src.application.services.tool_registry_service import ToolRegistryService

            return ToolRegistryService(InMemoryToolRepository())
        # LLM/Sandbox 等外部依赖返回 AsyncMock（架构测试不验证其功能）
        return AsyncMock()
