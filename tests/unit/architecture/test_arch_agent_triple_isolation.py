"""Story 5.5 架构约束验证测试（Agent 三重硬隔离——验证器 A-D + 探针归位断言）

覆盖 AC-6.3（架构合规）+ AC-6.4 修订（探针套件归位集成范畴——2026-10-24
用户裁定: 专项裁撤 + marker 非必要不新增）:
- 基建验证器节: 探针套件位于 tests/integration（随既有 CI 挂载面运行）+
  专项裁撤钉子（tests/security 目录/security marker/test-security target 均不存在）
- 验证器 A: domain 零外部依赖（isolation_access.py / agent_exceptions.py AST 扫描）
- 验证器 B: 组合根外零实例化（IsolationGuardService——仅扫 src/ 面）
- 验证器 C: 端口方向（守卫服务与两接线点 import 白名单 + 接线静态锚 +
  判定真源防线[isolation_access 生产方白名单]）
- 验证器 D: lifetime 决策落地（SINGLETON 两行式收窄断言）

Run with:
    poetry run pytest tests/unit/architecture/test_arch_agent_triple_isolation.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = REPO_ROOT / "src"


# ===================================================================
# 基建验证器节: 探针套件归位集成范畴（AC-6.4 修订——2026-10-24 用户裁定）
# ===================================================================


class TestProbeSuiteIntegrationPlacement:
    """探针套件归入集成测试范畴断言（原 tests/security 独立目录 + security
    marker + 覆盖率专项规划裁撤——专项不合适，marker 非必要不新增；探针随
    tests/integration 既有 CI 挂载面与 conftest 基建运行）。
    """

    def test_probe_suite_file_in_integration_directory(self) -> None:
        """探针套件文件存在于集成目录（CI integration job pytest 路径
        `tests/integration` 天然涵盖——无需独立挂载）。"""
        assert (REPO_ROOT / "tests/integration/test_integration_isolation_security.py").exists(), (
            "探针套件应位于 tests/integration/（集成范畴归位——2026-10-24 用户裁定）"
        )

    def test_no_dedicated_security_directory_or_marker(self) -> None:
        """专项裁撤钉子: tests/security 独立目录与 security marker 均不存在
        （marker 非必要不新增——--strict-markers 下无注册即无声明）。"""
        assert not (REPO_ROOT / "tests" / "security").exists(), "tests/security 独立目录应裁撤"
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert '"security:' not in pyproject, "security marker 应不注册（非必要不新增）"
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        assert "test-security:" not in makefile, "test-security 专项 target 应裁撤"


# ===================================================================
# 验证器 A: domain 零外部依赖（三重隔离执行面 domain 文件 AST 扫描）
# ===================================================================

# domain 层合法顶层模块白名单（仅标准库 + src 同层——import-linter 契约镜像）
_DOMAIN_ALLOWED_TOP_MODULES = frozenset(
    {"__future__", "typing", "dataclasses", "uuid", "enum", "datetime", "collections", "src"}
)

# 明确禁止的外部依赖（.importlinter domain 契约对齐——禁 pydantic/redis 等）
_FORBIDDEN_DOMAIN_IMPORTS = frozenset({"pydantic", "sqlalchemy", "redis", "fastapi", "typer", "langgraph", "prefect", "yaml"})


def _scan_file_imports(file_path: Path) -> set[str]:
    """提取文件全部 import 的顶层模块名（ast.walk 覆盖函数内延迟 import）。"""
    source = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return set()
    tops: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                tops.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            tops.add(node.module.split(".")[0])
    return tops


class TestValidatorADomainZeroExternal:
    """验证器 A: 三重隔离 domain 文件零外部依赖（isolation_access / agent_exceptions）。"""

    @pytest.mark.parametrize(
        "rel_path",
        ["src/domain/value_objects/isolation_access.py", "src/domain/exceptions/agent_exceptions.py"],
    )
    def test_domain_files_no_external_dependencies(self, rel_path: str) -> None:
        """AST 扫描: 顶层模块全部在白名单内（禁 pydantic/redis——import-linter 契约镜像）。"""
        tops = _scan_file_imports(REPO_ROOT / rel_path)
        assert tops <= _DOMAIN_ALLOWED_TOP_MODULES, f"{rel_path} 引入外部依赖: {tops - _DOMAIN_ALLOWED_TOP_MODULES}"
        assert not (tops & _FORBIDDEN_DOMAIN_IMPORTS), f"{rel_path} 引入禁止依赖: {tops & _FORBIDDEN_DOMAIN_IMPORTS}"


# ===================================================================
# 验证器 B: 组合根外零实例化（仅扫 src/ 面——对齐 5-4 现形态）
# ===================================================================


class TestValidatorBInstantiationOnlyInCompositionRoot:
    """验证器 B: IsolationGuardService 仅在组合根实例化（业务代码禁直接 new）。"""

    def test_guard_service_not_instantiated_outside_root(self) -> None:
        """src/ 全扫（跳过 composition_root.py）——AST Call 形态匹配类名实例化。"""
        violations: list[str] = []
        for py_file in SRC_DIR.rglob("*.py"):
            rel = py_file.relative_to(REPO_ROOT).as_posix()
            if rel == "src/composition_root.py":
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                target = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
                if target == "IsolationGuardService":
                    violations.append(rel)
        assert not violations, f"组合根外直接实例化 IsolationGuardService: {violations}"


# ===================================================================
# 验证器 C: 端口方向 + 接线静态锚 + 判定真源防线
# ===================================================================

# isolation_access 的 src/ 生产方白名单（「矩阵唯一真源」AST 门禁——
# 白名单 = 守卫服务[唯一判定消费方] + 守卫端口[方法签名类型契约] +
# value_objects/__init__[包聚合导出惯例]；tests/ 豁免不属扫描面）
_ALLOWED_ACCESS_CONSUMERS = frozenset(
    {
        "src/application/services/isolation_guard_service.py",
        "src/application/ports/isolation_guard.py",
        "src/domain/value_objects/__init__.py",
    }
)

_WIRING_POINT_FILES = (
    "src/application/services/isolation_guard_service.py",
    "src/application/use_cases/run_agent_workflow.py",
    "src/application/services/agent_workflow_service.py",
)


class TestValidatorCPortDirectionAndWiring:
    """验证器 C: 端口方向（application 禁 infrastructure）+ 接线静态锚 + 判定真源。"""

    def test_wiring_points_no_infrastructure_import(self) -> None:
        """守卫服务与两接线点禁 import src.infrastructure（application→infrastructure 非法）。"""
        violations: list[str] = []
        for rel in _WIRING_POINT_FILES:
            tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.infrastructure"):
                    violations.append(f"{rel}: {node.module}")
        assert not violations, f"端口方向违规: {violations}"

    def test_guard_service_imports_port_and_decision_source(self) -> None:
        """守卫服务 import 应用端口（R2 组合注入锚）+ 判定真源（矩阵消费唯一面）。"""
        source = (REPO_ROOT / "src/application/services/isolation_guard_service.py").read_text(encoding="utf-8")
        assert "src.application.ports.isolation_guard" in source, "守卫实现 IsolationGuardPort import 缺失"
        assert "decide_isolation_access" in source, "守卫实现未消费判定矩阵（唯一真源锚）"
        assert "decide_tool_access" in source, "守卫实现未消费工具判定（唯一真源锚）"

    def test_both_wiring_points_reference_guard(self) -> None:
        """接线静态锚: 两接线文件均含 isolation_guard 引用（lambda 漏注入的
        架构面防线——验收 AC-6.2 行为锚的静态互补）。"""
        for rel in ("src/application/use_cases/run_agent_workflow.py", "src/application/services/agent_workflow_service.py"):
            source = (REPO_ROOT / rel).read_text(encoding="utf-8")
            assert "isolation_guard" in source, f"{rel} isolation_guard 接线引用缺失"

    def test_decision_source_single_consumer_whitelist(self) -> None:
        """判定真源防线: isolation_access 的 src/ 生产方 import 白名单三合法面
        （防第三处判定面绕过守卫自建异常翻译——矩阵唯一真源纪律的 AST 门禁）。"""
        violations: list[str] = []
        for py_file in SRC_DIR.rglob("*.py"):
            rel = py_file.relative_to(REPO_ROOT).as_posix()
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "src.domain.value_objects.isolation_access":
                    if rel not in _ALLOWED_ACCESS_CONSUMERS:
                        violations.append(rel)
        assert not violations, f"isolation_access 消费方越界: {violations}"


# ===================================================================
# 验证器 D: lifetime 决策落地（SINGLETON——两行式收窄断言）
# ===================================================================


class TestValidatorDLifetime:
    """验证器 D: isolation_guard_service lifetime 为 SINGLETON（mypy Optional 纪律两行式）。"""

    def test_guard_service_lifetime_singleton(self) -> None:
        """无状态纯判定服务 SINGLETON（SCOPED agent_repository 捕获无实害注记沿 5-4 DC-7）。"""
        from src.domain.ports.registry import Lifetime, _global_registry

        spec = _global_registry.get("isolation_guard_service")
        assert spec is not None, "isolation_guard_service 未注册"
        assert spec.lifetime == Lifetime.SINGLETON, "isolation_guard_service lifetime 必须 SINGLETON"
