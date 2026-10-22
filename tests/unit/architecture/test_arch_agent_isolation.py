"""Story 5.4: EIP 隔离协议架构约束验证测试（验证器 A-D）

四验证器（SDD 六边形架构约束——5-3 形态参照 test_arch_agent_workflow.py）:
A. domain 零外部依赖——隔离五文件 AST 扫描禁 pydantic/redis/langgraph import
B. 组合根外零实例化——RedisIsolationRepository/IsolationManagementService
   全 src 面 AST 扫描（业务代码禁直接 new——组装纪律；tests 不在扫描面）
C. 端口方向——application services/use_cases import 白名单
   （domain.*/application.ports 合法；src.infrastructure 非法）
D. lifetime 决策落地——isolation_repository SINGLETON 两行式断言
   （DC-7 D7 核销的架构锚，防回退 SCOPED 无声复发）

Run with:
    poetry run pytest tests/unit/architecture/test_arch_agent_isolation.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = REPO_ROOT / "src"

# 验证器 A 扫描面（domain 隔离五文件——isolation_policy/isolation_state/
# isolation_events/agent_exceptions/isolation_repository）
DOMAIN_ISOLATION_FILES = [
    "src/domain/value_objects/isolation_policy.py",
    "src/domain/entities/isolation_state.py",
    "src/domain/events/isolation_events.py",
    "src/domain/exceptions/agent_exceptions.py",
    "src/domain/ports/isolation_repository.py",
]

# domain 层合法顶层模块白名单（标准库 + src 域内——5-3 形态）
_DOMAIN_ALLOWED_TOP_MODULES = {
    "__future__",
    "typing",
    "dataclasses",
    "uuid",
    "enum",
    "datetime",
    "collections",
    "src",
}

# 外部依赖黑名单（.importlinter domain-no-external-dependencies 契约的
# 隔离文件子集——命中即红）
_FORBIDDEN_DOMAIN_IMPORTS = frozenset({"pydantic", "sqlalchemy", "redis", "fastapi", "typer", "langgraph", "prefect", "yaml"})


def _scan_file_imports(file_path: Path) -> set[str]:
    """提取文件全部 import 的顶层模块名（ast.walk 覆盖函数内延迟 import）。"""
    if not file_path.exists():
        return set()
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


def _iter_python_files(root: Path):
    """遍历 root 下全部 .py 文件。"""
    yield from root.rglob("*.py")


class TestValidatorADomainZeroExternalDependencies:
    """验证器 A: domain 隔离文件零外部依赖（.importlinter 契约子集）。"""

    @pytest.mark.parametrize("rel_path", DOMAIN_ISOLATION_FILES)
    def test_isolation_domain_files_no_external_imports(self, rel_path: str) -> None:
        """隔离五文件顶层 import ⊆ 白名单，且与黑名单零交集。"""
        file_path = REPO_ROOT / rel_path
        assert file_path.exists(), f"文件缺失: {rel_path}"
        imports = _scan_file_imports(file_path)
        external = imports - _DOMAIN_ALLOWED_TOP_MODULES
        assert not external & _FORBIDDEN_DOMAIN_IMPORTS, f"{rel_path} 引入外部依赖: {external & _FORBIDDEN_DOMAIN_IMPORTS}"
        assert not external, f"{rel_path} 引入白名单外依赖: {external}"

    def test_isolation_state_uses_lazy_import_for_policy(self) -> None:
        """isolation_state 对 isolation_policy 的依赖经函数内延迟 import
        （打破包初始化环 entities→value_objects→events→entities——实现锚）。"""
        source = (REPO_ROOT / "src/domain/entities/isolation_state.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        module_level_imports = [
            node
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom)) and "isolation_policy" in ast.dump(node)
        ]
        assert not module_level_imports, "isolation_policy 依赖必须函数内延迟 import（包初始化环）"
        assert "isolation_policy" in source, "MVP_ALLOWED_LEVELS SSOT 依赖不得移除"


class TestValidatorBNoInstantiationOutsideCompositionRoot:
    """验证器 B: 组合根外零实例化（src 面——tests 白名单已按 5-3 R1-F12 移除）。"""

    @pytest.mark.parametrize(
        ("class_name", "allowed_paths"),
        [
            ("RedisIsolationRepository", {"src/composition_root.py"}),
            ("IsolationManagementService", {"src/composition_root.py"}),
        ],
    )
    def test_no_direct_instantiation_outside_composition_root(self, class_name: str, allowed_paths: set[str]) -> None:
        """类实例化调用仅允许组合根（业务代码禁直接 new——组装纪律）。"""
        violations: list[str] = []
        for py_file in _iter_python_files(SRC_DIR):
            rel = py_file.relative_to(REPO_ROOT).as_posix()
            if any(rel.startswith(allowed.rstrip("/")) for allowed in allowed_paths):
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
                if target == class_name:
                    violations.append(rel)
        assert not violations, f"{class_name} 在组合根外被直接实例化: {violations}"


class TestValidatorCPortDirection:
    """验证器 C: 端口方向（application→domain 合法 + application.ports 同层合法
    + 禁 import infrastructure——白名单含 src.application.ports，R1-F19）。"""

    _ALLOWED_PREFIXES = (
        "src.domain.",
        "src.application.ports.",
        "src.application.services.",
        "src.application.use_cases.",
        "src.application.event_handlers.",
    )

    @pytest.mark.parametrize(
        "rel_path",
        [
            "src/application/services/isolation_management_service.py",
            "src/application/use_cases/agent_instantiation.py",
        ],
    )
    def test_application_files_import_whitelist_only(self, rel_path: str) -> None:
        """application 层隔离相关文件 import 白名单校验（禁 infrastructure）。"""
        file_path = REPO_ROOT / rel_path
        assert file_path.exists(), f"文件缺失: {rel_path}"
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("src.infrastructure"), (
                    f"{rel_path} 禁 import infrastructure: {node.module}（六边形依赖方向）"
                )
                if node.module.startswith("src."):
                    assert node.module.startswith(self._ALLOWED_PREFIXES), f"{rel_path} import 越界: {node.module}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("src.infrastructure"), f"{rel_path} 禁 import infrastructure: {alias.name}"

    def test_isolation_service_imports_domain_ports(self) -> None:
        """IsolationManagementService 组合注入三 domain 端口（R1 基础端口锚）+
        一同层应用端口（agent_config_loader——R1-F01 TTL 真源通道）。"""
        source = (REPO_ROOT / "src/application/services/isolation_management_service.py").read_text(encoding="utf-8")
        assert "from src.domain.ports.isolation_repository import IsolationRepository" in source
        assert "from src.domain.ports.agent_repository import AgentRepository" in source
        assert "from src.domain.ports.event_publisher import EventPublisher" in source
        assert "from src.application.ports.agent_config_loader import AgentConfigLoader" in source

    def test_cli_entrypoint_imports_application_only(self) -> None:
        """CLI（entrypoints）经 resolve 应用端口——entrypoints→application 合法。

        domain 枚举/异常的纯类型 import 是既有合法形态（AgentRole/DomainError
        先例）；本断言锁定: 业务服务一律经 resolve（应用端口 import 存在）+
        禁 import infrastructure（六边形方向——entrypoints 不触技术实现）。
        """
        source = (REPO_ROOT / "src/entrypoints/agent_cli.py").read_text(encoding="utf-8")
        assert "src.application.ports.isolation_management" in source, (
            "CLI 须 import 应用端口类型（resolve 目标——R4 接口层适配）"
        )
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("src.infrastructure"), (
                    f"CLI 禁 import infrastructure: {node.module}（六边形依赖方向）"
                )


class TestValidatorDLifetimeDecision:
    """验证器 D: lifetime 决策落地（DC-7——D7 核销的架构锚，两行式收窄 R1-F29）。"""

    def test_isolation_repository_lifetime_singleton(self) -> None:
        """isolation_repository 必须 SINGLETON（防回退 SCOPED 无声复发——
        registry.get 返回 Optional，两行式断言防 mypy None 访问红）。"""
        from src.domain.ports.registry import Lifetime, _global_registry

        spec = _global_registry.get("isolation_repository")
        assert spec is not None, "isolation_repository 未注册"
        assert spec.lifetime == Lifetime.SINGLETON, (
            "isolation_repository lifetime 必须为 SINGLETON（DC-7：无状态仓储构造零 IO，"
            "被 SINGLETON 服务捕获无 captive 实害——D7 从源头避免）"
        )

    def test_isolation_management_service_lifetime_singleton(self) -> None:
        """isolation_management_service SINGLETON（无状态服务——CLI/用例捕获无实害）。"""
        from src.domain.ports.registry import Lifetime, _global_registry

        spec = _global_registry.get("isolation_management_service")
        assert spec is not None, "isolation_management_service 未注册"
        assert spec.lifetime == Lifetime.SINGLETON

    def test_use_case_wires_isolation_service_dependency(self) -> None:
        """agent_instantiation_use_case lambda 注入 isolation_management_service
        （组合根源码断言——端到端锚的静态面，运行时锚由验收 AC-2.1 背书）。"""
        source = (REPO_ROOT / "src/composition_root.py").read_text(encoding="utf-8")
        assert 'isolation_service=resolver.resolve("isolation_management_service")' in source, (
            "agent_instantiation_use_case lambda 未注入第四依赖"
        )
