"""Story 5.5 架构约束验证测试（Agent 三重硬隔离——验证器 A-D + 基建四件套）

覆盖 AC-6.3（架构合规）+ AC-6.4（安全测试基建就绪）:
- 基建验证器节: tests/security 四件套（目录三文件 + pyproject security marker
  [文本断言防漏注册——--strict-markers 收集期守卫] + CI integration job 挂载
  tests/security + Makefile test-security target 两段式覆盖率命令）
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
# 基建验证器节: 安全测试基建四件套（AC-6.4——文件存在性 + 配置文本断言）
# ===================================================================


class TestSecurityInfrastructureFourPiece:
    """tests/security 四件套就绪断言（基建不存在时断言真红——TDD 先行钉死预期形态）。

    落位本文件（tests/unit/architecture/）而非 tests/security 自身——断言本文件
    存在自指恒真（Task 4 循环 A 豁免条款注记）。
    """

    def test_security_suite_files_exist(self) -> None:
        """三文件存在性（目录 __init__ + conftest + 探针套件）。"""
        expected = [
            "tests/security/__init__.py",
            "tests/security/conftest.py",
            "tests/security/test_isolation_security.py",
        ]
        missing = [rel for rel in expected if not (REPO_ROOT / rel).exists()]
        assert not missing, f"安全测试基建文件缺失: {missing}"

    def test_pyproject_registers_security_marker(self) -> None:
        """pyproject markers 注册 security（--strict-markers 下未注册即收集期炸）。"""
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert '"security:' in pyproject, "pyproject [tool.pytest.ini_options].markers 未注册 security"

    def test_ci_integration_job_mounts_security_suite(self) -> None:
        """CI integration-tests job pytest 命令含 tests/security（探针需真实 Redis——
        挂有 compose 服务栈的 job）。"""
        ci = (REPO_ROOT / ".gitea" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
        assert "tests/security" in ci, "CI integration job 未挂载 tests/security"

    def test_makefile_security_coverage_target(self) -> None:
        """Makefile test-security target（两段式覆盖率口径——D-2 偏离声明落地；
        禁 --cov=src.<module> 单段形态[仓库 coverage 配置陷阱]）。"""
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        assert "test-security:" in makefile, "Makefile 缺 test-security target"
        assert "tests/security" in makefile, "test-security 未跑 tests/security"
        assert "--fail-under=90" in makefile, "安全覆盖率专项未含 fail-under=90 门禁"


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
