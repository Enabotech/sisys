"""Story 6-8 - 高管简化视图 SDD 架构约束验证测试（四验证器）.

验证器 A 落位守护 / B 零 publish 守护 / C 零 domain 改动+infra 白名单+依赖方向 /
D CLI 接线——test_traceability_tree.py 四验证器直系复刻。

C 验证器白名单形态注记（R3-N1 订正）：「src/infrastructure 白名单命中集恰为
{audit_repository_impl.py}」用 rglob+集合相等结构断言持久守护（禁 git diff——
未提交窗口外恒真失效，CR1-F4 教训）。

Run with:
    poetry run pytest tests/unit/architecture/test_executive_view.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"

PORT_FILE = SRC_ROOT / "application" / "ports" / "executive_view.py"
SERVICE_FILE = SRC_ROOT / "application" / "services" / "executive_view_service.py"
USE_CASE_FILE = SRC_ROOT / "application" / "use_cases" / "get_executive_view.py"
CLI_ENTRY = SRC_ROOT / "entrypoints" / "agent_cli.py"
AUDIT_IMPL_FILE = SRC_ROOT / "infrastructure" / "security" / "audit_repository_impl.py"

# 服务 import 白名单（架构验证器 C 断言面——六边形依赖方向矩阵）
SERVICE_ALLOWED_PREFIXES: tuple[str, ...] = (
    "src.domain.ports.",
    "src.domain.entities.",
    "src.domain.value_objects.",
    "src.domain.exceptions.",
    "src.application.ports.",
    "src.application.services.",
)

# 禁第三方 import（domain 零依赖纪律的应用层延伸——本 Story 面无 pydantic/sqlalchemy 需要）
FORBIDDEN_IMPORTS: frozenset[str] = frozenset({"pydantic", "sqlalchemy", "redis", "asyncpg"})


def _imports_of(path: Path) -> set[str]:
    """AST 解析模块级 import 名集合（from X import Y 取 X；import X.Y 取 X.Y）."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
    return names


class TestVerifierAPlacement:
    """验证器 A：交付文件落位守护（application 层+ports 文件承载 VO+禁本地 Protocol）."""

    def test_delivery_files_exist_in_application_layer(self) -> None:
        """三交付文件在 application 层（零 domain 落位——OD-12）."""
        for path in (PORT_FILE, SERVICE_FILE, USE_CASE_FILE):
            assert path.is_file(), f"交付文件缺失: {path}"
            assert "application" in path.parts, f"应在 application 层: {path}"

    def test_vos_and_port_defined_in_ports_file(self) -> None:
        """六 VO+枚举+端口定义于 ports 文件（非服务本地定义）."""
        port_tree = ast.parse(PORT_FILE.read_text(encoding="utf-8"))
        class_names = {node.name for node in ast.walk(port_tree) if isinstance(node, ast.ClassDef)}
        for vo_name in (
            "ExecutiveView",
            "PlanningSection",
            "ApprovalSection",
            "AuditSection",
            "ReportSection",
            "AuditEventSummary",
            "ExecutiveHealth",
            "ExecutiveViewPort",
        ):
            assert vo_name in class_names, f"{vo_name} 应定义于 ports 文件"

    def test_no_local_protocol_in_service_or_use_case(self) -> None:
        """服务与用例禁本地 Protocol 定义（端口单源钦定）."""
        for path in (SERVICE_FILE, USE_CASE_FILE):
            module_tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(module_tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "Protocol":
                            raise AssertionError(f"禁本地 Protocol 定义: {path}::{node.name}")


class TestVerifierBZeroPublish:
    """验证器 B：视图服务零事件发布守护（查询不发布事件——OD-2/architecture.md:1293）."""

    def test_service_source_zero_publish_tokens(self) -> None:
        """服务源码 publish/event_publisher token 零出现."""
        source = SERVICE_FILE.read_text(encoding="utf-8")
        for token in ("publish", "event_publisher"):
            assert token not in source, f"视图服务应零 {token}（查询不发布事件——OD-2）"

    def test_service_source_zero_domain_event_construction(self) -> None:
        """服务 AST 零领域事件构造（pkgutil 强制导入 events 全子模块后全集比对 Call 节点）."""
        import importlib
        import pkgutil

        import src.domain.events as events_pkg
        from src.domain.events.base import DomainEvent

        for module_info in pkgutil.iter_modules(events_pkg.__path__):
            importlib.import_module(f"{events_pkg.__name__}.{module_info.name}")
        assert hasattr(events_pkg, "RAGIndexed"), "事件包导入 sanity：RAGIndexed 应在位"

        def _walk_subclasses(cls: type) -> set[str]:
            names: set[str] = set()
            for sub in cls.__subclasses__():
                names.add(sub.__name__)
                names |= _walk_subclasses(sub)
            return names

        event_names = _walk_subclasses(DomainEvent)
        assert event_names, "DomainEvent 子类集非空（强制导入 sanity）"
        module_tree = ast.parse(SERVICE_FILE.read_text(encoding="utf-8"))
        for node in ast.walk(module_tree):
            if isinstance(node, ast.Call):
                func = node.func
                called = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
                if called is not None and called in event_names:
                    raise AssertionError(f"视图服务禁事件构造位: {called}（行 {node.lineno}）")


class TestVerifierCDependencies:
    """验证器 C：零 domain 改动+infra 白名单+服务依赖方向白名单（结构断言形态——禁 git diff）."""

    def test_domain_layer_zero_executive_files(self) -> None:
        """src/domain rglob executive 词零命中（零 domain 改动——OD-12）."""
        domain_hits = [p for p in (SRC_ROOT / "domain").rglob("*executive*")]
        assert not domain_hits, f"domain 层不应新增高管视图文件: {domain_hits}"

    def test_infrastructure_executive_hits_empty_and_audit_fallback_in_place(self) -> None:
        """src/infrastructure executive 词零命中 + audit_repository_impl search fallback 在位锚.

        本 Story 唯一 infra 增量 = audit_repository_impl.py 的 search session_factory
        fallback（OD-12 R2 重开钦定）——白名单守护形态：无 executive 新 infra 文件 +
        钦定文件的 _do_search 双模式结构在位（集合断言持久守护——R3-N1）.
        """
        infra_hits = {p.name for p in (SRC_ROOT / "infrastructure").rglob("*executive*")}
        assert infra_hits == set(), f"本 Story 零 infra 新文件（唯一增量在 audit_repository_impl 内）: {infra_hits}"
        source = AUDIT_IMPL_FILE.read_text(encoding="utf-8")
        assert "_do_search" in source, "audit search fallback 结构锚缺失（_do_search 抽取形态）"
        assert "无请求 session 时经注入工厂走独立会话" in source or "经注入工厂走独立会话" in source, (
            "search 双模式 docstring 锚缺失"
        )

    def test_service_imports_within_hexagonal_whitelist(self) -> None:
        """服务 src.* import 全在白名单前缀内（禁 infrastructure/interfaces——六边形方向）."""
        imports = _imports_of(SERVICE_FILE)
        src_imports = {name for name in imports if name.startswith("src.")}
        assert src_imports, "服务应含 src 依赖（空集即锚失效）"
        for name in sorted(src_imports):
            assert name.startswith(SERVICE_ALLOWED_PREFIXES), f"依赖方向违例: {name}（白名单外）"

    def test_application_files_zero_third_party_forbidden(self) -> None:
        """三交付文件零禁第三方 import（读侧 DTO 纯标准库+domain/application 依赖）."""
        for path in (PORT_FILE, SERVICE_FILE, USE_CASE_FILE):
            root_modules = {name.split(".")[0] for name in _imports_of(path)}
            for root in root_modules:
                assert root not in FORBIDDEN_IMPORTS, f"{path.name} 禁第三方依赖: {root}"


class TestVerifierDCLIWiring:
    """验证器 D：CLI executive-view 接线（缩进敏感精确锚——add_parser 形态逐字匹配）."""

    def test_cli_has_executive_view_subcommand(self) -> None:
        """agent_cli.py 含 executive-view add_parser 注册（精确锚——8 空格缩进逐字形态）."""
        source = CLI_ENTRY.read_text(encoding="utf-8")
        assert 'add_parser(\n        "executive-view"' in source, "CLI 缺 executive-view 子命令注册（缩进敏感锚）"

    def test_cli_dispatch_branch_resolves_use_case(self) -> None:
        """分发分支+use_case resolve 调用锚（接线完整性——Epic 4 行动项 7.1-1 ②）."""
        source = CLI_ENTRY.read_text(encoding="utf-8")
        assert 'args.command == "executive-view"' in source, "CLI 缺 executive-view 分发分支"
        assert 'resolve("executive_view_use_case")' in source, "CLI 缺 use_case resolve 调用锚"
