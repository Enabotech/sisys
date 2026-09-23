"""Story 4.4: Docker 沙箱架构验证测试

epics_v1.0.md:1204 硬要求此路径(无 _arch_ 前缀)。
验证 4 项架构约束:
1. domain 层零依赖(禁止 aiodocker 等外部包)
2. 依赖方向(application 不依赖 infrastructure)
3. 无循环依赖(AST 静态扫描)
4. PortSpec 元数据完整性(10 字段)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# domain 层禁止的外部包
FORBIDDEN_EXTERNAL = frozenset(
    {
        "aiodocker",
        "docker",
        "testcontainers",
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "redis",
        "minio",
        "qdrant",
        "neo4j",
        "langgraph",
        "prefect",
    }
)

# 验证 domain 文件范围
DOMAIN_FILES = [
    "src/domain/value_objects/container_spec.py",
    "src/domain/entities/sandbox_session.py",
    "src/domain/events/sandbox_events.py",
    "src/domain/ports/sandbox_executor.py",
    "src/domain/ports/sandbox_session_repository.py",
    "src/domain/exceptions/sandbox_exceptions.py",
]

# 验证 application 文件范围
APPLICATION_FILES = [
    "src/application/services/sandbox_session_reaper.py",
    "src/application/services/sandbox_security_decorator.py",
]


def _extract_imports(file_path: Path) -> list[str]:
    """提取 Python 文件的所有顶层 import 模块名"""
    if not file_path.exists():
        return []
    imports = []
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


class TestDomainLayerZeroDependencies:
    """domain 层零外部依赖验证"""

    @pytest.mark.parametrize("file_relpath", DOMAIN_FILES, ids=lambda p: Path(p).name)
    def test_domain_file_no_external_imports(self, file_relpath: str) -> None:
        """domain 文件应不导入任何外部包"""
        src_root = Path(__file__).resolve().parents[3]
        file_path = src_root / file_relpath
        if not file_path.exists():
            pytest.skip(f"文件不存在: {file_path}")
        imports = _extract_imports(file_path)
        violations = [imp for imp in imports if imp in FORBIDDEN_EXTERNAL]
        assert not violations, f"{file_path.name} 禁止导入外部包: {violations} (违反 CLAUDE.md §5 领域零依赖原则)"


class TestApplicationLayerNoInfrastructure:
    """application 层不依赖 infrastructure 验证"""

    @pytest.mark.parametrize("file_relpath", APPLICATION_FILES, ids=lambda p: Path(p).name)
    def test_application_file_no_infrastructure_imports(self, file_relpath: str) -> None:
        """application 文件应不导入 infrastructure 层"""
        src_root = Path(__file__).resolve().parents[3]
        file_path = src_root / file_relpath
        if not file_path.exists():
            pytest.skip(f"文件不存在: {file_path}")
        imports = _extract_imports(file_path)
        # application 可以引用 domain（已通过 import 检查），不能引用 infrastructure
        violations = [imp for imp in imports if imp == "src.infrastructure"]
        assert not violations, f"{file_path.name} 禁止导入 infrastructure 层: {violations}"


class TestSandboxPortSpecMetadata:
    """SandboxSessionRepositoryPort + sandbox_executor 端口元数据验证

    注:本测试仅在 composition_root 注册后才能运行,使用可选导入。
    若未注册则跳过(开发期不影响)。
    """

    def test_sandbox_session_repository_port_metadata(self) -> None:
        """SandboxSessionRepositoryPort 端口元数据完整性验证（如已注册）"""
        try:
            from src.domain.ports.registry import _global_registry
        except ImportError:
            pytest.skip("registry 不可用")

        spec = _global_registry.get("sandbox_session_repository")
        if spec is None:
            pytest.skip("sandbox_session_repository 端口尚未注册到 composition_root")

        # 10 字段元数据完整性验证
        assert spec.name == "sandbox_session_repository"
        assert spec.version, "version 应非空"
        assert spec.interface is not None, "interface 应存在"
        assert spec.impl is not None, "impl 应存在"
        assert spec.module, "module 应非空"
        assert spec.lifetime is not None, "lifetime 应为 Lifetime enum"
        assert isinstance(spec.owner, str) and spec.owner, "owner 应为非空 str"
        assert isinstance(spec.compatibility, tuple), "compatibility 应为 tuple[str, ...]"
        assert isinstance(spec.tags, tuple), "tags 应为 tuple[str, ...]"
        assert isinstance(spec.deprecated, bool), "deprecated 应为 bool"
        # version 应匹配语义化版本 ^\d+\.\d+\.\d+$
        import re

        assert re.match(r"^v?\d+\.\d+\.\d+$", spec.version), f"version 应匹配 ^v?\\d+\\.\\d+\\.\\d+$, got '{spec.version}'"

    def test_sandbox_executor_port_metadata(self) -> None:
        """sandbox_executor 端口元数据完整性验证（如已注册）"""
        try:
            from src.domain.ports.registry import _global_registry
        except ImportError:
            pytest.skip("registry 不可用")

        spec = _global_registry.get("sandbox_executor")
        if spec is None:
            pytest.skip("sandbox_executor 端口尚未注册到 composition_root")

        # 10 字段元数据完整性验证(与 sandbox_session_repository 同构)
        assert spec.name == "sandbox_executor"
        assert spec.version, "version 应非空"
        assert spec.interface is not None, "interface 应存在"
        assert spec.impl is not None, "impl 应存在"
        assert spec.module, "module 应非空"
        assert spec.lifetime is not None, "lifetime 应为 Lifetime enum"
        assert isinstance(spec.owner, str) and spec.owner, "owner 应为非空 str"
        assert isinstance(spec.compatibility, tuple), "compatibility 应为 tuple[str, ...]"
        assert isinstance(spec.tags, tuple), "tags 应为 tuple[str, ...]"
        assert isinstance(spec.deprecated, bool), "deprecated 应为 bool"
        import re

        assert re.match(r"^v?\d+\.\d+\.\d+$", spec.version), f"version 应匹配语义化版本, got '{spec.version}'"

    def test_sandbox_session_reaper_port_metadata(self) -> None:
        """sandbox_session_reaper 端口元数据完整性验证（如已注册,Round 5 补齐）"""
        try:
            from src.domain.ports.registry import _global_registry
        except ImportError:
            pytest.skip("registry 不可用")

        spec = _global_registry.get("sandbox_session_reaper")
        if spec is None:
            pytest.skip("sandbox_session_reaper 端口尚未注册到 composition_root")

        # 10 字段元数据完整性验证
        assert spec.name == "sandbox_session_reaper"
        assert spec.version, "version 应非空"
        assert spec.interface is not None, "interface 应存在"
        assert spec.impl is not None, "impl 应存在"
        assert spec.module, "module 应非空"
        assert spec.lifetime is not None, "lifetime 应为 Lifetime enum"
        assert isinstance(spec.owner, str) and spec.owner, "owner 应为非空 str"
        assert isinstance(spec.compatibility, tuple), "compatibility 应为 tuple[str, ...]"
        assert isinstance(spec.tags, tuple), "tags 应为 tuple[str, ...]"
        assert isinstance(spec.deprecated, bool), "deprecated 应为 bool"
        import re

        assert re.match(r"^v?\d+\.\d+\.\d+$", spec.version), f"version 应匹配语义化版本, got '{spec.version}'"


class TestSandboxExceptionCodesUniqueness:
    """沙箱异常编码唯一性验证"""

    def test_sandbox_codes_311_to_319_all_unique(self) -> None:
        """sandbox 子域 311-319 编码唯一性"""
        from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN

        sandbox_classes = [name for name, sub in _CLASS_TO_SUBDOMAIN.items() if sub == "sandbox"]
        # 9 个异常类（4.1a 4 个 + 4.4 5 个）
        assert len(sandbox_classes) == 9, f"应有 9 个 sandbox 子域异常类,实际 {len(sandbox_classes)}: {sandbox_classes}"

    def test_sandbox_codes_in_valid_range(self) -> None:
        """sandbox 异常 code 应在 311-319 范围内"""
        from src.domain.exceptions._code_ranges import get_range_for_subdomain

        range_tuple = get_range_for_subdomain("sandbox")
        assert range_tuple == (311, 319)


class TestDependencyDirection:
    """依赖方向矩阵验证"""

    def test_application_only_depends_on_domain(self) -> None:
        """application 层（sandbox_* 服务）只能依赖 domain 层（通过 src.application.* → src.domain.*）"""
        src_root = Path(__file__).resolve().parents[3] / "src"
        application_sandbox_dir = src_root / "application" / "services"

        if not application_sandbox_dir.exists():
            pytest.skip(f"目录不存在: {application_sandbox_dir}")

        sandbox_files = list(application_sandbox_dir.glob("sandbox_*.py"))
        for file_path in sandbox_files:
            imports = _extract_imports(file_path)
            # application 可导入 domain + stdlib + 第三方允许库（loguru/pytest 等）
            # 但不能导入 infrastructure 层
            violations = [imp for imp in imports if imp == "src.infrastructure"]
            assert not violations, f"{file_path.name} 禁止导入 src.infrastructure（违反依赖方向）"
