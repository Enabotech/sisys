"""Story 5.1: 架构约束测试 — CEO Agent 实例化 MVP

验证（六边形架构四层约束 + YAML 边界 + 组合根唯一装配）：
1. 验证器 A——domain 零依赖：agent 域四文件（value_objects/ports/events/
   exceptions）无第三方 import（AST 扫描，参照 test_hexagonal_architecture_
   constraints.py 与 test_arch_data_source.py 模式）
2. 验证器 B——YAML 解析边界：① src/domain/ 全目录零 import yaml /
   yaml.safe_load；② Agent 配置解析链的 yaml 用法仅新增于
   yaml_agent_config_loader.py 一处（⚠️ 禁止断言「全仓仅命中一处」——
   frontmatter.py / event_bus_config_loader.py 为既有合法存量）
3. 验证器 C——依赖方向：RedisAgentRepository 不 import application/
   interfaces；agent_cli 不 import infrastructure；用例仅依赖 domain +
   application 端口
4. 验证器 D——组合根唯一装配：三个实现类在 src/ 下仅 composition_root.py
   实例化（rglob 全仓扫描类名实例化，技术参照 test_arch_data_source.py）
5. 验证器 E——循环依赖检测用 ruff（--select I，不引入 pylint）

Run with:
    poetry run pytest tests/unit/architecture/test_arch_agent_instantiation.py -v
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "src"
REPO_ROOT = SRC_ROOT.parent

# Story 5.1 新增/修改的 domain 层文件
DOMAIN_FILES = [
    SRC_ROOT / "domain" / "value_objects" / "agent_config.py",
    SRC_ROOT / "domain" / "ports" / "agent_repository.py",
    SRC_ROOT / "domain" / "events" / "agent_events.py",
    SRC_ROOT / "domain" / "exceptions" / "agent_exceptions.py",
]

# domain 层禁止导入的外部包（对齐 test_arch_data_source.py 黑名单口径）
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
    "httpx",
    "yaml",  # YAML 解析严格限定 infrastructure——本 Story 核心边界
    "dotenv",
}

# 实现类 → (定义模块, 类名)；组合根唯一装配断言用
IMPL_CLASSES = {
    "RedisAgentRepository": SRC_ROOT / "infrastructure" / "storage" / "redis" / "redis_agent_repository.py",
    "YamlAgentConfigLoader": SRC_ROOT / "infrastructure" / "agent_orch" / "yaml_agent_config_loader.py",
    "InstantiateAgentUseCase": SRC_ROOT / "application" / "use_cases" / "agent_instantiation.py",
}


def _extract_imports(file_path: Path) -> list[str]:
    """从 Python 文件提取全部 import 的点分模块路径（ast.walk 覆盖函数内延迟 import）。"""
    if not file_path.exists():
        return []
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.append(node.module)
    return imports


def _top_layer(module_path: str) -> str:
    """剥离可选 src. 前缀后的顶层包名。"""
    return module_path.removeprefix("src.").split(".")[0]


# ============================================================
# 验证器 A: domain 层零依赖
# ============================================================


class TestDomainZeroDependencies:
    """agent 域 domain 文件零第三方依赖 + 零跨层导入。"""

    def test_all_domain_files_exist(self) -> None:
        for file_path in DOMAIN_FILES:
            assert file_path.exists(), f"domain 文件不存在: {file_path}"

    def test_no_forbidden_imports(self) -> None:
        for file_path in DOMAIN_FILES:
            violations = set(_extract_imports(file_path)) & FORBIDDEN_IMPORTS
            assert not violations, f"{file_path.name} 导入禁止的外部包: {violations}"

    def test_no_cross_layer_imports(self) -> None:
        """domain 禁止导入 application/interfaces/infrastructure 层。"""
        for file_path in DOMAIN_FILES:
            for imp in _extract_imports(file_path):
                assert _top_layer(imp) not in ("application", "interfaces", "infrastructure"), (
                    f"{file_path.name} 跨层导入: {imp}"
                )

    def test_domain_imports_only_stdlib_and_domain(self) -> None:
        """白名单口径：仅标准库 + src.domain.*（允许 __future__）。"""
        stdlib = sys.stdlib_module_names
        for file_path in DOMAIN_FILES:
            for imp in _extract_imports(file_path):
                top = imp.split(".")[0]
                assert top in stdlib or top == "__future__" or _top_layer(imp) == "domain", (
                    f"{file_path.name} 非法 import: {imp}"
                )


# ============================================================
# 验证器 B: YAML 解析边界
# ============================================================


class TestYamlBoundary:
    """YAML 解析严格限定 infrastructure（domain 全目录零 yaml + 新增仅一处）。"""

    def test_domain_directory_zero_yaml_usage(self) -> None:
        """① src/domain/ 全目录（rglob）零 import yaml / yaml.safe_load。"""
        offenders: list[str] = []
        for py_file in (SRC_ROOT / "domain").rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            if "import yaml" in source or "yaml.safe_load" in source:
                offenders.append(str(py_file.relative_to(SRC_ROOT)))
        assert not offenders, f"domain 层 YAML 泄漏: {offenders}"

    def test_agent_chain_yaml_usage_only_in_loader(self) -> None:
        """② Agent 配置解析链 yaml 用法仅 yaml_agent_config_loader.py（限定断言面）。

        ⚠️ 禁止断言「全仓仅命中一处」——src/application/skills/frontmatter.py
        与 event_bus_config_loader.py 为既有合法存量，不在断言面。
        """
        loader = SRC_ROOT / "infrastructure" / "agent_orch" / "yaml_agent_config_loader.py"
        assert "import yaml" in loader.read_text(encoding="utf-8"), "加载器必须使用 yaml（本断言面的唯一新增）"

        # Agent 解析链其余新文件不得 import yaml（import 级检查——docstring
        # 提及 yaml 字样不构成违规）
        for py_file in [
            SRC_ROOT / "infrastructure" / "storage" / "redis" / "redis_agent_repository.py",
            SRC_ROOT / "entrypoints" / "agent_cli.py",
            SRC_ROOT / "application" / "use_cases" / "agent_instantiation.py",
            SRC_ROOT / "application" / "ports" / "agent_config_loader.py",
        ]:
            for imp in _extract_imports(py_file):
                assert imp.split(".")[0] != "yaml", f"{py_file.name} 不得 import yaml: {imp}"


# ============================================================
# 验证器 C: 依赖方向
# ============================================================


class TestDependencyDirection:
    """infrastructure 不 import application/interfaces；CLI 不 import infrastructure。"""

    def test_redis_repo_no_application_or_interfaces(self) -> None:
        imports = _extract_imports(IMPL_CLASSES["RedisAgentRepository"])
        for imp in imports:
            assert _top_layer(imp) not in ("application", "interfaces"), f"RedisAgentRepository 违规跨层导入: {imp}"

    def test_yaml_loader_imports_ok(self) -> None:
        """YamlAgentConfigLoader 实现 application 端口属合法（端口实现方向），
        但不得 import interfaces。"""
        imports = _extract_imports(IMPL_CLASSES["YamlAgentConfigLoader"])
        for imp in imports:
            assert _top_layer(imp) != "interfaces", f"YamlAgentConfigLoader 违规导入 interfaces: {imp}"

    def test_agent_cli_no_infrastructure(self) -> None:
        imports = _extract_imports(SRC_ROOT / "entrypoints" / "agent_cli.py")
        for imp in imports:
            assert _top_layer(imp) != "infrastructure", f"agent_cli 违规导入 infrastructure: {imp}"

    def test_use_case_only_domain_and_application(self) -> None:
        """用例仅依赖 domain + application（+标准库），不触 infrastructure/interfaces。"""
        imports = _extract_imports(IMPL_CLASSES["InstantiateAgentUseCase"])
        for imp in imports:
            top = _top_layer(imp)
            assert top not in ("infrastructure", "interfaces"), f"用例违规导入: {imp}"


# ============================================================
# 验证器 D: 组合根唯一装配
# ============================================================


class TestCompositionRootOnlyAssembly:
    """三个实现类在 src/ 下仅自身定义文件与 composition_root.py 出现实例化。"""

    def test_impl_classes_instantiated_only_in_composition_root(self) -> None:
        composition = SRC_ROOT / "composition_root.py"
        assert composition.exists()
        for cls_name, definition in IMPL_CLASSES.items():
            assert definition.exists(), f"实现文件不存在: {definition}"
            # 全 src 扫描类名实例化（AST Call 扫描——func 名或属性名命中类名；
            # 覆盖直接调用 Cls(...) 与 __import__(...).Cls(...) 形态，且不受
            # docstring/注释文本与前缀同类名（FakeXxx(Cls)）的子串误报影响）
            offenders: list[str] = []
            for py_file in SRC_ROOT.rglob("*.py"):
                if py_file == definition or py_file == composition:
                    continue
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        func = node.func
                        if isinstance(func, ast.Name):
                            target = func.id
                        elif isinstance(func, ast.Attribute):
                            target = func.attr
                        else:
                            target = None
                        if target == cls_name:
                            offenders.append(str(py_file.relative_to(SRC_ROOT)))
                            break
            assert not offenders, f"{cls_name} 在组合根外被实例化: {offenders}"

    def test_composition_root_registers_all_three(self) -> None:
        source = (SRC_ROOT / "composition_root.py").read_text(encoding="utf-8")
        for cls_name in IMPL_CLASSES:
            assert cls_name in source, f"组合根未装配 {cls_name}"
        for port_name in ('"agent_repository"', '"agent_config_loader"', '"agent_instantiation_use_case"'):
            assert port_name in source, f"组合根未注册端口 {port_name}"


# ============================================================
# 验证器 E: 循环依赖检测（ruff --select I，不引入 pylint）
# ============================================================


class TestNoCircularImports:
    """ruff isort 规则（I）对 Story 5.1 全部新文件的 import 排序/可解析性检查。"""

    def test_ruff_isort_on_new_files(self) -> None:
        targets = [str(path) for path in [*IMPL_CLASSES.values(), SRC_ROOT / "entrypoints" / "agent_cli.py"]]
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--select", "I", *targets],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"ruff isort 检查失败:\n{result.stdout}\n{result.stderr}"
