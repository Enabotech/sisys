"""Story 6-1 — BLM 规划架构约束验证测试（SDD Task 6）。

三验证器（形态对齐 test_arch_agent_profile_loading.py + 5-11 现代形态
test_arch_sap_protocol.py）：
- 验证器 A：domain 新增文件零第三方 import（AST 扫描——函数内延迟 import
  全覆盖 walk）
- 验证器 B：依赖方向矩阵（blm_planning_service 在 application 编排语义/
  sp_blm_graph 在 infrastructure 实现应用层端口/CLI 在 entrypoints）
- 验证器 C：落位断言（sp_blm_graph.py 钦定落位 + 组合根唯一装配 + 零抑制
  注释）

Run with:
    poetry run pytest tests/unit/architecture/test_blm_planning_arch.py -v
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
REPO_ROOT = SRC_ROOT.parent

#: Story 6-1 domain 新增/修改文件清单（零第三方依赖红线覆盖面）
BLM_DOMAIN_FILES: tuple[Path, ...] = (
    SRC_ROOT / "domain" / "value_objects" / "blm_phases.py",
    SRC_ROOT / "domain" / "events" / "planning_events.py",
    SRC_ROOT / "domain" / "exceptions" / "planning_exceptions.py",
)

#: 第三方黑名单（test_arch_agent_profile_loading.py 先例集合）
FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
    {
        "pydantic",
        "sqlalchemy",
        "redis",
        "fastapi",
        "typer",
        "langgraph",
        "prefect",
        "qdrant_client",
        "minio",
        "neo4j",
        "aio_pika",
        "litellm",
        "instructor",
        "asyncpg",
        "httpx",
        "yaml",
        "dotenv",
    }
)

#: domain 零依赖合法顶层（标准库 + src.domain 同层）
_DOMAIN_ALLOWED_TOP_LEVELS: frozenset[str] = frozenset({"src", "__future__"} | set(sys.stdlib_module_names))


def _extract_imports(file_path: Path) -> list[str]:
    """提取全部 import 目标（ast.walk——覆盖函数内延迟 import）。"""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets.append(node.module)
    return targets


def _top_layer(module_path: str) -> str:
    """模块路径顶层段（依赖方向判别用）。"""
    return module_path.removeprefix("src.").split(".")[0]


# ===================================================================
# 验证器 A：domain 新增文件零第三方依赖
# ===================================================================


class TestDomainZeroDependencies:
    """domain 层零第三方依赖（六边形红线——AST 扫描）。"""

    def test_blm_domain_files_exist(self) -> None:
        """三文件存在（blm_phases/planning_events/planning_exceptions）。"""
        for file_path in BLM_DOMAIN_FILES:
            assert file_path.is_file(), f"缺少 domain 交付件: {file_path}"

    def test_no_third_party_imports(self) -> None:
        """黑名单零命中（pydantic/sqlalchemy/redis/langgraph 等全禁）。"""
        for file_path in BLM_DOMAIN_FILES:
            for module in _extract_imports(file_path):
                top = module.split(".")[0]
                assert top not in FORBIDDEN_IMPORTS, f"{file_path.name} 引入第三方依赖: {module}（domain 零外部依赖红线）"

    def test_only_stdlib_and_domain_layer(self) -> None:
        """仅标准库 + src.domain 同层引用（不 import application/infrastructure）。"""
        for file_path in BLM_DOMAIN_FILES:
            for module in _extract_imports(file_path):
                if module == "__future__":
                    continue
                if module.startswith("src."):
                    assert _top_layer(module) == "domain" or module.count(".") >= 2 and module.split(".")[1] == "domain", (
                        f"{file_path.name} 反向依赖: {module}（domain 只能依赖 domain）"
                    )
                else:
                    assert module.split(".")[0] in _DOMAIN_ALLOWED_TOP_LEVELS - {"src"}, (
                        f"{file_path.name} 非标准库 import: {module}"
                    )


# ===================================================================
# 验证器 B：依赖方向矩阵（六边形四层）
# ===================================================================


class TestDependencyDirection:
    """依赖方向矩阵（application 编排语义/infrastructure 实现端口/入口层）。"""

    def test_blm_planning_service_in_application_layer(self) -> None:
        """BlmPlanningService 在 application/services/（编排语义——R2）。"""
        service = SRC_ROOT / "application" / "services" / "blm_planning_service.py"
        assert service.is_file()

    def test_service_depends_on_domain_and_ports_only(self) -> None:
        """服务 import 面：domain + application 同层 + 标准库（不直连 infrastructure 实现类）。"""
        service = SRC_ROOT / "application" / "services" / "blm_planning_service.py"
        for module in _extract_imports(service):
            if module.startswith("src."):
                top_two = ".".join(module.split(".")[:2])
                assert top_two in {"src.domain", "src.application"}, (
                    f"blm_planning_service 直连 infrastructure: {module}（须经端口注入）"
                )

    def test_sp_blm_graph_in_infrastructure(self) -> None:
        """sp_blm_graph.py 在 infrastructure/agent_orch/graphs/（R3 落位钦定 OD-4）。"""
        graph = SRC_ROOT / "infrastructure" / "agent_orch" / "graphs" / "sp_blm_graph.py"
        assert graph.is_file(), "sp_blm_graph.py 不在钦定落位（architecture L3244）"

    def test_graph_depends_on_application_port(self) -> None:
        """图工厂依赖 application 端口（BlmPlanningServicePort——R3 实现应用层端口）。"""
        graph = SRC_ROOT / "infrastructure" / "agent_orch" / "graphs" / "sp_blm_graph.py"
        modules = _extract_imports(graph)
        assert "src.application.ports.blm_planning" in modules, (
            "sp_blm_graph 未依赖 BlmPlanningServicePort（R3：基础设施实现应用层端口）"
        )

    def test_use_cases_in_application_layer(self) -> None:
        """两用例在 application/use_cases/（编排层）。"""
        for name in ("run_blm_planning.py", "get_blm_planning_status.py"):
            path = SRC_ROOT / "application" / "use_cases" / name
            assert path.is_file(), f"用例不在 application/use_cases/: {name}"

    def test_cli_in_entrypoints_layer(self) -> None:
        """CLI blm-plan 在 entrypoints（D1 方案 A——interfaces 层零组合根引用）。"""
        cli = SRC_ROOT / "entrypoints" / "agent_cli.py"
        assert cli.is_file()
        content = cli.read_text(encoding="utf-8")
        assert "blm-plan" in content, "agent_cli 未含 blm-plan 子命令"
        assert "blm_planning_use_case" in content, "CLI 未接线 blm_planning_use_case"


# ===================================================================
# 验证器 C：组合根唯一装配 + 零抑制注释
# ===================================================================


class TestCompositionRootAssembly:
    """组合根装配面（唯一实例化点 + 注册族 + 零抑制注释）。"""

    def test_service_instantiated_only_in_composition_root(self) -> None:
        """BlmPlanningService 实例化收窄（src/ 下仅组合根与定义文件）。"""
        instantiation_sites: list[str] = []
        for py_file in SRC_ROOT.rglob("*.py"):
            if py_file.name == "blm_planning_service.py":
                continue
            content = py_file.read_text(encoding="utf-8")
            if "BlmPlanningService(" in content:
                relative = py_file.relative_to(REPO_ROOT)
                instantiation_sites.append(str(relative))
        assert instantiation_sites == ["src/composition_root.py"], (
            f"BlmPlanningService 实例化点越界: {instantiation_sites}（仅组合根）"
        )

    def test_graph_factory_only_in_engine_dispatch(self) -> None:
        """build_sp_blm_graph 消费面收窄（src/ 下仅引擎分派）。"""
        sites: list[str] = []
        for py_file in SRC_ROOT.rglob("*.py"):
            if py_file.name == "sp_blm_graph.py":
                continue
            content = py_file.read_text(encoding="utf-8")
            if "build_sp_blm_graph" in content:
                sites.append(str(py_file.relative_to(REPO_ROOT)))
        assert sites == ["src/infrastructure/agent_orch/langgraph_engine.py"], (
            f"build_sp_blm_graph 消费面越界: {sites}（仅引擎 _build_graph 分派）"
        )

    def test_no_suppression_comments(self) -> None:
        """交付件零抑制注释（noqa/type: ignore/pylint disable——红线）。"""
        delivery_files = [
            *BLM_DOMAIN_FILES,
            SRC_ROOT / "application" / "ports" / "blm_planning.py",
            SRC_ROOT / "application" / "services" / "blm_planning_service.py",
            SRC_ROOT / "application" / "services" / "blm_planning_prompts.py",
            SRC_ROOT / "application" / "use_cases" / "run_blm_planning.py",
            SRC_ROOT / "application" / "use_cases" / "get_blm_planning_status.py",
            SRC_ROOT / "infrastructure" / "agent_orch" / "graphs" / "sp_blm_graph.py",
        ]
        for file_path in delivery_files:
            content = file_path.read_text(encoding="utf-8")
            for marker in ("# noqa", "# type: ignore", "# pylint: disable"):
                assert marker not in content, f"{file_path.name} 含抑制注释 {marker}（红线）"

    def test_openapi_unchanged(self) -> None:
        """零 REST API 面（OD-5）：docs/api/openapi.yaml 无 BLM 路径新增。"""
        openapi = REPO_ROOT / "docs" / "api" / "openapi.yaml"
        if not openapi.is_file():
            return  # 无 openapi 文件形态（零 API 面自然成立）
        content = openapi.read_text(encoding="utf-8")
        assert "blm" not in content.lower(), "OD-5 红线：BLM 不进 REST API（7-2 才是入口 Story）"
