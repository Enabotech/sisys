"""溯源树架构约束验证（Story 6-7 Task 6——SDD 架构验证测试，OD-9 命名）。

四验证器（test_pdf_report.py 形态模板——AST/源码扫描）：
A 落位守护（树服务/用例/VO 全在 application 层 + VO 在 ports 文件非服务文件
  本地定义——禁本地 Protocol 守护）
B 零 publish 守护（树服务源码零 publish 调用 + 零 DomainEvent 子类构造——
  查询不发布事件 OD-2 的源码断言面）
C 零 domain 改动守护（本 Story 新增文件全部在 application/entrypoints 层——
  src/domain/ 零新文件）+ 依赖方向（树服务 import 面=domain ports+application
  白名单——六边形依赖矩阵）
D CLI 接线（agent_cli.py 含 trace-tree 分发分支 + resolve traceability_tree_
  use_case 调用锚）

Run with:
    poetry run pytest tests/unit/architecture/test_traceability_tree.py -v
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"

#: 本 Story 应用层交付文件（落位校验面）
TREE_SERVICE = SRC_ROOT / "application" / "services" / "traceability_tree_service.py"
TREE_PORT = SRC_ROOT / "application" / "ports" / "traceability_tree.py"
TREE_USE_CASE = SRC_ROOT / "application" / "use_cases" / "get_traceability_tree.py"
CLI_ENTRY = SRC_ROOT / "entrypoints" / "agent_cli.py"

#: 领域层零依赖禁 import 清单（importlinter 同源）
FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
    {
        "pydantic",
        "sqlalchemy",
        "redis",
        "fastapi",
        "typer",
        "qdrant_client",
        "minio",
        "neo4j",
        "aio_pika",
        "litellm",
        "instructor",
        "reportlab",
    }
)

#: 树服务合法 import 白名单（domain ports/entities/value_objects + application 同层——六边形依赖矩阵；
#: infrastructure 仅经组合根装配，服务文件零 import）
SERVICE_ALLOWED_PREFIXES: tuple[str, ...] = (
    "src.domain.ports",
    "src.domain.entities",
    "src.domain.value_objects",
    "src.application.ports",
    "src.application.services",
)


def _imports_of(path: Path) -> set[str]:
    """解析文件顶层 import（ast 扫描——src.* 前缀全集）."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


# ===================================================================
# 验证器 A：落位守护
# ===================================================================


class TestValidatorAPlacement:
    """A——树交付件落位（application 层 + VO 在 ports 文件 + 禁本地 Protocol）."""

    def test_delivery_files_exist_in_application_layer(self) -> None:
        """三交付文件存在且均在 application 层（树 VO 是应用层读侧 DTO——OD-4）."""
        for path in (TREE_SERVICE, TREE_PORT, TREE_USE_CASE):
            assert path.is_file(), f"交付文件缺失: {path}"
            assert "application" in path.parts, f"落位违例（应在 application 层）: {path}"

    def test_five_vos_defined_in_ports_file(self) -> None:
        """五 VO 定义于 ports 文件（非服务文件本地定义——禁本地 VO/Protocol 纪律）."""
        port_source = TREE_PORT.read_text(encoding="utf-8")
        port_tree = ast.parse(port_source)
        class_names = {node.name for node in ast.walk(port_tree) if isinstance(node, ast.ClassDef)}
        for vo_name in ("TraceabilityTree", "ConclusionNode", "StageNode", "ChunkNode", "DocumentNode"):
            assert vo_name in class_names, f"{vo_name} 应定义于 ports 文件（非服务文件本地定义）"
        assert "TraceabilityTreePort" in class_names, "端口 Protocol 应在 ports 文件"

    def test_no_local_protocol_in_service_or_use_case(self) -> None:
        """服务/用例文件禁本地 Protocol 定义（6-1~6-6 纪律沿袭）."""
        for path in (TREE_SERVICE, TREE_USE_CASE):
            module_tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(module_tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "Protocol":
                            raise AssertionError(f"禁本地 Protocol 定义: {path}::{node.name}")


# ===================================================================
# 验证器 B：零 publish 守护（OD-2——查询不发布事件）
# ===================================================================


class TestValidatorBZeroPublish:
    """B——树服务零事件发布/零事件构造源码断言."""

    def test_service_source_zero_publish_calls(self) -> None:
        """树服务源码零 publish 调用（6-6「发布点守护」的零发布变体）."""
        source = TREE_SERVICE.read_text(encoding="utf-8")
        for token in ("publish", "event_publisher"):
            assert token not in source, f"树服务应零 {token}（查询不发布事件——OD-2）"

    def test_service_source_zero_domain_event_construction(self) -> None:
        """树服务零 DomainEvent 子类构造（AST 扫描——零事件构造位）.

        事件名全集比对（R1-F5 升级）：运行时递归收集 DomainEvent 全部子类名
        （包级 import 确保模块全注册）——后缀启发式仅覆盖 ~15% 事件类
        （RAGIndexed 等不以 Event/Created 等结尾），全集比对零漏检零误报。
        """
        import src.domain.events as events_pkg
        from src.domain.events.base import DomainEvent

        # 包级导入使全部事件模块注册进 __subclasses__（使用性断言兼 sanity——RAGIndexed 在位）
        assert hasattr(events_pkg, "RAGIndexed"), "事件包导入 sanity：RAGIndexed 应在位"

        def _walk_subclasses(cls: type) -> set[str]:
            names: set[str] = set()
            for sub in cls.__subclasses__():
                names.add(sub.__name__)
                names |= _walk_subclasses(sub)
            return names

        event_names = _walk_subclasses(DomainEvent)
        assert event_names, "DomainEvent 子类集非空（包级导入 sanity）"
        module_tree = ast.parse(TREE_SERVICE.read_text(encoding="utf-8"))
        for node in ast.walk(module_tree):
            if isinstance(node, ast.Call):
                func = node.func
                called = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
                if called is not None and called in event_names:
                    raise AssertionError(f"树服务禁事件构造位: {called}（行 {node.lineno}）")


# ===================================================================
# 验证器 C：零 domain 改动 + 依赖方向
# ===================================================================


class TestValidatorCZeroDomainAndDependencies:
    """C——本 Story 零 domain 改动守护 + 树服务 import 白名单."""

    def test_story_files_outside_domain(self) -> None:
        """本 Story 新增文件全部在 application/entrypoints 层（src/domain/ 零新文件——OD-12）."""
        new_files = [
            "application/ports/traceability_tree.py",
            "application/services/traceability_tree_service.py",
            "application/use_cases/get_traceability_tree.py",
        ]
        for relative in new_files:
            path = SRC_ROOT / relative
            assert path.is_file(), f"新增文件缺失: {relative}"
            assert not relative.startswith("domain/"), f"零 domain 改动违例: {relative}"
        # payload 扩键仅触 application/event_handlers（handler 是应用层——非 infrastructure）
        handler = SRC_ROOT / "application" / "event_handlers" / "chunk_indexing_handler.py"
        assert handler.is_file(), "chunk_indexing_handler 应在 application/event_handlers（应用层事件处理器）"

    def test_domain_layer_zero_new_files_for_story(self) -> None:
        """domain 层本 Story 零新文件（树 VO/端口全在 application——静态清单对照）."""
        domain_new_candidates = [p for p in (SRC_ROOT / "domain").rglob("*tree*.py")]
        assert not domain_new_candidates, f"domain 层不应新增树相关文件: {domain_new_candidates}"

    def test_service_imports_within_hexagonal_whitelist(self) -> None:
        """树服务 import 面=domain ports/entities/value_objects + application 同层（依赖矩阵）."""
        imports = _imports_of(TREE_SERVICE)
        src_imports = {name for name in imports if name.startswith("src.")}
        for name in sorted(src_imports):
            assert name.startswith(SERVICE_ALLOWED_PREFIXES), f"依赖方向违例: {name}（白名单外）"

    def test_application_files_zero_third_party_forbidden(self) -> None:
        """三应用层交付文件零禁 import（六边形 application 层零技术依赖）."""
        for path in (TREE_SERVICE, TREE_PORT, TREE_USE_CASE):
            imports = _imports_of(path)
            for name in imports:
                root_module = name.split(".")[0]
                assert root_module not in FORBIDDEN_IMPORTS, f"{path.name} 禁 import {name}"


# ===================================================================
# 验证器 D：CLI 接线
# ===================================================================


class TestValidatorDCliWiring:
    """D——CLI trace-tree 入口接线（分发分支 + resolve 调用锚）."""

    def test_cli_has_trace_tree_subcommand(self) -> None:
        """agent_cli.py 含 trace-tree add_parser 注册（精确锚——R1-F6 删 or 右支恒真吞噬）."""
        source = CLI_ENTRY.read_text(encoding="utf-8")
        assert 'add_parser(\n        "trace-tree"' in source, "CLI 缺 trace-tree 子命令注册"

    def test_cli_dispatch_branch_resolves_use_case(self) -> None:
        """分发分支 + resolve traceability_tree_use_case 调用锚（接线闭环）."""
        source = CLI_ENTRY.read_text(encoding="utf-8")
        assert 'args.command == "trace-tree"' in source, "CLI 缺 trace-tree 分发分支"
        assert 'resolve("traceability_tree_use_case")' in source, "CLI 缺 use_case resolve 调用锚"
