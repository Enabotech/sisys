"""Story 5.6 架构约束验证测试（SDD 规范验证——验证架构约束是否被遵守）

三验证器（对齐 test_arch_agent_isolation.py 样板形态）:
- 验证器 A: domain 零外部依赖（isolation_switch_log.py 实体 +
  isolation_switch_log_repository.py 端口 AST 扫描——白名单标准库 + 同层
  events/exceptions/entities/ports import；黑名单 pydantic/sqlalchemy/redis/
  fastapi/typer/langgraph/prefect——.importlinter domain 契约的测试级双保险）
- 验证器 B: 组合根外零实例化（PostgreSQLIsolationSwitchLogRepository 实例化
  点仅 composition_root.py + tests/——src/ 全扫描，端口唯一实例化点纪律）
- 验证器 C: 端口方向（agent_cli import 白名单——src.domain./src.application.
  ports/services/use_cases 前缀合法；src.infrastructure 禁入——CLI 直消费
  domain 仓储端口，R4 接口层适配约束）

Run with:
    poetry run pytest tests/unit/architecture/test_arch_isolation_switch_log.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = REPO_ROOT / "src"

# 验证器 A 目标文件（domain 层新增两文件）
_DOMAIN_TARGET_FILES = [
    SRC_DIR / "domain" / "entities" / "isolation_switch_log.py",
    SRC_DIR / "domain" / "ports" / "isolation_switch_log_repository.py",
]

# domain 层 import 白名单（顶层模块粒度——标准库 + src 内部（黑名单拦截外部依赖）；
# 对齐 test_arch_agent_isolation 顶层拆分形态）
_DOMAIN_ALLOWED_TOP_MODULES = frozenset(
    {
        "__future__",
        "dataclasses",
        "datetime",
        "typing",
        "uuid",
        "logging",
        "src",
    }
)

# domain 层禁止 import 的外部依赖顶层模块（黑名单——.importlinter domain 契约）
_FORBIDDEN_DOMAIN_IMPORTS = frozenset(
    {
        "pydantic",
        "sqlalchemy",
        "redis",
        "fastapi",
        "typer",
        "langgraph",
        "prefect",
        "yaml",
        "celery",
        "minio",
        "qdrant",
        "neo4j",
    }
)


def _scan_file_imports(path: Path) -> set[str]:
    """AST 扫描文件全部 import（ast.walk 覆盖函数内延迟 import）——顶层模块名集合."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
            # from . import xxx 相对导入（node.module None）——level>=1 属同层
    return modules


def _iter_python_files(root: Path):
    """递归产出全部 Python 文件（rglob）。"""
    yield from root.rglob("*.py")


class TestValidatorADomainZeroExternalDeps:
    """验证器 A: domain 新增文件零外部依赖。"""

    @pytest.mark.parametrize(
        "target",
        _DOMAIN_TARGET_FILES,
        ids=[p.name for p in _DOMAIN_TARGET_FILES],
    )
    def test_domain_file_imports_within_whitelist(self, target: Path) -> None:
        """白名单内 import（标准库 + 同层 src.domain——零外部依赖）。"""
        imports = _scan_file_imports(target)
        external = imports - _DOMAIN_ALLOWED_TOP_MODULES
        assert not external, f"{target.name} 存在白名单外 import: {sorted(external)}"

    @pytest.mark.parametrize(
        "target",
        _DOMAIN_TARGET_FILES,
        ids=[p.name for p in _DOMAIN_TARGET_FILES],
    )
    def test_domain_file_no_forbidden_imports(self, target: Path) -> None:
        """黑名单零命中（pydantic/sqlalchemy/redis 等——.importlinter 契约双保险）。"""
        imports = _scan_file_imports(target)
        violated = imports & _FORBIDDEN_DOMAIN_IMPORTS
        assert not violated, f"{target.name} 违规外部依赖: {sorted(violated)}"


class TestValidatorBCompositionRootOnlyInstantiation:
    """验证器 B: PostgreSQLIsolationSwitchLogRepository 组合根外零实例化。"""

    @pytest.mark.parametrize(
        ("class_name", "allowed_paths"),
        [
            (
                "PostgreSQLIsolationSwitchLogRepository",
                {"src/composition_root.py"},
            ),
        ],
    )
    def test_infra_impl_instantiated_only_in_composition_root(self, class_name: str, allowed_paths: set[str]) -> None:
        """src/ 全扫描——实例化点仅组合根（tests/ 不在扫描范围，端口唯一实例化点纪律）。"""
        violations: list[str] = []
        for path in _iter_python_files(SRC_DIR):
            relative = str(path.relative_to(REPO_ROOT))
            if relative in allowed_paths:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name == class_name:
                    violations.append(f"{relative}:{node.lineno}")
        assert not violations, f"{class_name} 组合根外实例化点: {violations}"


class TestValidatorCPortDirection:
    """验证器 C: 端口方向（CLI 消费面——domain/application 合法、infrastructure 禁入）。"""

    def test_agent_cli_imports_no_infrastructure(self) -> None:
        """agent_cli 禁 import src.infrastructure（CLI 直消费 domain 仓储端口——
        isolation-logs 检索面经 resolve 装配，不触碰实现模块）。"""
        cli_path = SRC_DIR / "entrypoints" / "agent_cli.py"
        tree = ast.parse(cli_path.read_text(encoding="utf-8"))
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("src.infrastructure"):
                    violations.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src.infrastructure"):
                        violations.append(alias.name)
        assert not violations, f"agent_cli 违规 import infrastructure: {violations}"

    def test_agent_cli_consumes_domain_port_directly(self) -> None:
        """CLI 直消费仓储端口（isolation_switch_log_repository import 存在——
        R4 接口层适配外部请求经 domain 端口，非绕过端口直用实现）。"""
        source = (SRC_DIR / "entrypoints" / "agent_cli.py").read_text(encoding="utf-8")
        assert "IsolationSwitchLogRepository" in source or "IsolationSwitchLogQuery" in source, (
            "agent_cli 应 import domain 仓储端口类型（Query/Repository/Result）"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
