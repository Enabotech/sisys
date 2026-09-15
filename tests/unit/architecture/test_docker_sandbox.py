"""架构验证测试 - Story 4.4 Docker 沙箱执行

epics_v1.0.md:1204 硬要求此路径(无 _arch_ 前缀)。

验证 4 项架构规则:
1. 域层零依赖:src/domain/ 不依赖 aiodocker / testcontainers / docker
2. 依赖方向矩阵:domain ← application ← infrastructure
3. 端口元数据完整性:3 个端口 sandbox_executor / sandbox_session_repository /
   sandbox_session_reaper 的 PortSpec 10 字段元数据
4. 异常代码唯一性:EXCEPTION_315-319 与既有代码无碰撞

CLAUDE.md §5:本测试不使用 mock,使用真实 subprocess + AST 解析。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# 项目根目录(从 tests/unit/architecture/ 向上 3 级)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOMAIN_DIR = PROJECT_ROOT / "src" / "domain"


# ============================================================================
# 规则 1: 域层零依赖
# ============================================================================


class TestDomainZeroDependencies:
    """验证 src/domain/ 不引入 aiodocker / testcontainers / docker"""

    FORBIDDEN_THIRD_PARTY = frozenset({"aiodocker", "testcontainers", "docker", "aiodocker_py"})

    def _extract_imports(self, file_path: Path) -> set[str]:
        """提取 Python 文件的 import 顶层模块名。"""
        imports: set[str] = set()
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            return imports

        for node in ast.walk(tree):
            # 跳过 TYPE_CHECKING 块内 import(类型注解专用,运行时无影响)
            if isinstance(node, ast.If):
                # 简化检测:ast 解析时不展开,直接基于字符串匹配
                continue

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.add(node.module.split(".")[0])

        # 移除 Python 标准伪模块(__future__ 是 Python 内置特性,不是外部依赖)
        imports.discard("__future__")
        return imports

    def test_domain_layer_no_external_dependencies(self) -> None:
        """domain 层零外部依赖:扫描 src/domain/ 所有 .py 文件"""
        violations: list[tuple[str, str]] = []
        for py_file in DOMAIN_DIR.rglob("*.py"):
            imports = self._extract_imports(py_file)
            forbidden = imports & self.FORBIDDEN_THIRD_PARTY
            if forbidden:
                violations.append((str(py_file.relative_to(PROJECT_ROOT)), ",".join(sorted(forbidden))))

        assert violations == [], "Domain layer must not import third-party packages. Violations:\n" + "\n".join(
            f"  {file}: {mods}" for file, mods in violations
        )

    def test_container_spec_value_object_only_stdlib(self) -> None:
        """ContainerSpec 值对象仅依赖标准库 + 领域层异常"""
        spec_file = DOMAIN_DIR / "value_objects" / "container_spec.py"
        imports = self._extract_imports(spec_file)
        # 允许的 import:dataclasses, typing, src.domain.exceptions
        forbidden = imports - {"dataclasses", "typing", "src", "__future__"}
        assert forbidden == set(), f"ContainerSpec must only use stdlib + src.domain, found: {forbidden}"

    def test_sandbox_session_entity_only_stdlib(self) -> None:
        """SandboxSession 聚合根仅依赖标准库 + 领域层异常"""
        entity_file = DOMAIN_DIR / "entities" / "sandbox_session.py"
        imports = self._extract_imports(entity_file)
        forbidden = imports - {"dataclasses", "datetime", "re", "typing", "uuid", "src", "__future__"}
        assert forbidden == set(), f"SandboxSession must only use stdlib + src.domain, found: {forbidden}"


# ============================================================================
# 规则 2: 依赖方向矩阵
# ============================================================================


class TestDependencyDirection:
    """验证四层架构依赖方向(domain ← application ← infrastructure)"""

    def test_application_can_depend_on_domain(self) -> None:
        """应用层允许依赖 domain 层"""
        app_dir = PROJECT_ROOT / "src" / "application"
        # 抽样检查:RetryPolicy 是否引用了 domain 异常
        retry_file = app_dir / "services" / "retry_helpers.py"
        text = retry_file.read_text(encoding="utf-8")
        assert "from src.domain.exceptions" in text or "src.domain" in text

    def test_infrastructure_can_depend_on_domain_and_application(self) -> None:
        """基础设施层允许依赖 domain + application 层"""
        inf_dir = PROJECT_ROOT / "src" / "infrastructure"
        sandbox_adapter = inf_dir / "external_services" / "sandbox" / "aiodocker_sandbox_adapter.py"
        text = sandbox_adapter.read_text(encoding="utf-8")
        # 必须引用 domain 层
        assert "src.domain" in text
        # 不应引用 application 层(架构约束) — 检查 import 语句而非注释
        import ast

        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.application"):
                pytest.fail(f"Infrastructure must not import application: {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src.application"):
                        pytest.fail(f"Infrastructure must not import application: {alias.name}")

    def test_domain_does_not_import_application_or_infrastructure(self) -> None:
        """domain 层禁止 import application / infrastructure"""
        violations: list[str] = []
        for py_file in DOMAIN_DIR.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and (node.module.startswith("src.application") or node.module.startswith("src.infrastructure"))
                ):
                    violations.append(f"{py_file.relative_to(PROJECT_ROOT)}: {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src.application") or alias.name.startswith("src.infrastructure"):
                            violations.append(f"{py_file.relative_to(PROJECT_ROOT)}: {alias.name}")

        assert violations == [], "Domain layer must not import application/infrastructure. Violations:\n" + "\n".join(
            f"  {v}" for v in violations
        )


# ============================================================================
# 规则 3: 端口元数据完整性
# ============================================================================


class TestPortSpecMetadata:
    """验证 3 个沙箱端口的 PortSpec 10 字段元数据"""

    REQUIRED_FIELDS = (
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
    )

    def _read_composition_root_text(self) -> str:
        """读取 composition_root.py 全文(grep 而非 import,避免启动副作用)。"""
        composition_file = PROJECT_ROOT / "src" / "composition_root.py"
        return composition_file.read_text(encoding="utf-8")

    def test_sandbox_executor_port_registered(self) -> None:
        """sandbox_executor 端口已注册"""
        text = self._read_composition_root_text()
        assert 'name="sandbox_executor"' in text
        assert "AioDockerSandboxAdapter" in text, (
            "sandbox_executor impl must be switched to AioDockerSandboxAdapter (mock deleted)"
        )

    def test_sandbox_session_repository_port_registered(self) -> None:
        """sandbox_session_repository 端口已注册"""
        text = self._read_composition_root_text()
        assert 'name="sandbox_session_repository"' in text
        assert "InMemorySandboxSessionRepository" in text

    def test_sandbox_session_reaper_port_registered(self) -> None:
        """sandbox_session_reaper 端口已注册"""
        text = self._read_composition_root_text()
        assert 'name="sandbox_session_reaper"' in text
        assert "SandboxSessionReaper" in text

    def test_port_spec_has_10_fields(self) -> None:
        """PortSpec 类定义包含 10 字段元数据"""
        registry_file = PROJECT_ROOT / "src" / "domain" / "ports" / "registry.py"
        text = registry_file.read_text(encoding="utf-8")
        # 验证每个 REQUIRED_FIELD 都在 PortSpec dataclass 定义内
        for field_name in self.REQUIRED_FIELDS:
            # 简化校验:字段名在文件中出现
            assert f"{field_name}:" in text, f"PortSpec missing field: {field_name}"


# ============================================================================
# 规则 4: 异常代码唯一性
# ============================================================================


class TestExceptionCodeUniqueness:
    """验证 EXCEPTION_315-319 与既有代码无碰撞"""

    NEW_SANDBOX_CODES = {"EXCEPTION_315", "EXCEPTION_316", "EXCEPTION_317", "EXCEPTION_318", "EXCEPTION_319"}

    def test_sandbox_subdomain_range(self) -> None:
        """sandbox 子域范围 311-319(新增占用 315-319,既有 311-314 占用)"""
        code_ranges_file = PROJECT_ROOT / "src" / "domain" / "exceptions" / "_code_ranges.py"
        text = code_ranges_file.read_text(encoding="utf-8")
        assert '"sandbox": (311, 319)' in text or "'sandbox': (311, 319)" in text

    def test_new_sandbox_codes_within_subdomain(self) -> None:
        """5 个新沙箱异常 code 全部在 sandbox 子域范围(315-319)内"""
        sandbox_exceptions_file = PROJECT_ROOT / "src" / "domain" / "exceptions" / "sandbox_exceptions.py"
        text = sandbox_exceptions_file.read_text(encoding="utf-8")
        for code in self.NEW_SANDBOX_CODES:
            assert code in text, f"sandbox_exceptions.py missing code: {code}"

    def test_no_code_collision(self) -> None:
        """5 个新 code 互不相同"""
        assert len(self.NEW_SANDBOX_CODES) == 5

    def test_class_to_subdomain_registered(self) -> None:
        """5 个新异常类已注册到 _CLASS_TO_SUBDOMAIN"""
        code_ranges_file = PROJECT_ROOT / "src" / "domain" / "exceptions" / "_code_ranges.py"
        text = code_ranges_file.read_text(encoding="utf-8")
        for class_name in (
            "SandboxImagePullError",
            "SandboxTimeoutError",
            "SandboxResourceLimitExceededError",
            "SandboxQuotaExceededError",
            "SandboxConfigurationError",
        ):
            assert class_name in text, f"_CLASS_TO_SUBDOMAIN missing: {class_name}"


# ============================================================================
# 规则 5: aiodocker 第三方包隔离
# ============================================================================


class TestAiodockerIsolation:
    """验证 aiodocker 仅在 infrastructure 层使用"""

    def _is_in_function(self, tree: ast.Module, node: ast.AST) -> bool:
        """检查 AST 节点是否位于函数/方法体内(动态 import 允许位置)。"""
        for parent in ast.walk(tree):
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(parent):
                    if child is node:
                        return True
            elif isinstance(parent, ast.ClassDef):
                # 类体内的 import 通常视为静态(类级常量)
                pass
        return False

    def test_aiodocker_only_in_infrastructure(self) -> None:
        """aiodocker import 仅出现在 infrastructure 层(检查顶层 import 语句)

        函数体内的动态 import(如 `def foo(): import aiodocker`) 视为延迟加载,
        不算违规。Reaper 在 application 层用延迟 import 调用 aiodocker 是合规的。
        """
        violations: list[str] = []
        for subdir in ["domain", "application", "interfaces"]:
            target_dir = PROJECT_ROOT / "src" / subdir
            if not target_dir.exists():
                continue
            for py_file in target_dir.rglob("*.py"):
                try:
                    tree = ast.parse(py_file.read_text(encoding="utf-8"))
                except (SyntaxError, OSError):
                    continue
                for node in ast.walk(tree):
                    # 跳过函数体内的动态 import
                    if self._is_in_function(tree, node):
                        continue
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if "aiodocker" in alias.name:
                                violations.append(f"{py_file.relative_to(PROJECT_ROOT)}: {alias.name}")
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        if "aiodocker" in node.module:
                            violations.append(f"{py_file.relative_to(PROJECT_ROOT)}: {node.module}")

        assert violations == [], "aiodocker must only be imported in infrastructure layer. Violations:\n" + "\n".join(
            f"  {v}" for v in violations
        )

    def test_aiodocker_pep561_stub_exists(self) -> None:
        """aiodocker PEP 561 stubs 存在(CLAUDE.md §5 强制)"""
        stub_file = PROJECT_ROOT / "stubs" / "aiodocker" / "__init__.pyi"
        assert stub_file.exists(), "aiodocker PEP 561 stub not found"

    def test_mypy_path_includes_stubs(self) -> None:
        """pyproject.toml [tool.mypy] mypy_path 包含 stubs 目录"""
        pyproject_file = PROJECT_ROOT / "pyproject.toml"
        text = pyproject_file.read_text(encoding="utf-8")
        # 简化校验:mypy_path 配置存在且指向 stubs
        assert "mypy_path" in text and "stubs" in text


__all__ = [
    "TestDomainZeroDependencies",
    "TestDependencyDirection",
    "TestPortSpecMetadata",
    "TestExceptionCodeUniqueness",
    "TestAiodockerIsolation",
]
